import { useState } from 'react'
import Taro from '@tarojs/taro'
import { Button, Image, Input, PageContainer, ScrollView, Text, Textarea, View } from '@tarojs/components'
import { shipEmployeeOrder, uploadEmployeeEvidence } from '../../api/employee'
import { resolveMediaUrl } from '../../services/http'
import './index.scss'

type Channel = 'courier' | 'linehaul' | 'local_delivery' | 'pickup'
type PhotoItem = { id: string; preview: string; url?: string; status: 'uploading' | 'ready' | 'failed' }

const channels: Array<{ value: Channel; label: string; companyPlaceholder?: string; trackingPlaceholder?: string }> = [
  { value: 'courier', label: '快递', companyPlaceholder: '快递公司', trackingPlaceholder: '快递单号' },
  { value: 'linehaul', label: '物流部', companyPlaceholder: '物流部 / 承运方', trackingPlaceholder: '交接编号（可选）' },
  { value: 'local_delivery', label: '同城配送' },
  { value: 'pickup', label: '到店自提' },
]

const minimumPhotos: Record<Channel, number> = { courier: 1, linehaul: 2, local_delivery: 1, pickup: 0 }

export function ShippingSheet({ orderId, onClose, onDone }: { orderId: number; onClose: () => void; onDone: () => void }) {
  const [channel, setChannel] = useState<Channel>('courier')
  const [company, setCompany] = useState('')
  const [trackingNo, setTrackingNo] = useState('')
  const [note, setNote] = useState('')
  const [showNote, setShowNote] = useState(false)
  const [photos, setPhotos] = useState<PhotoItem[]>([])
  const [saving, setSaving] = useState(false)
  const minPhotoCount = minimumPhotos[channel]
  const currentChannel = channels.find((item) => item.value === channel)!

  const addPhotos = async () => {
    const remaining = 5 - photos.length
    if (!remaining) return
    try {
      const image = await Taro.chooseImage({ count: remaining, sizeType: ['compressed'], sourceType: ['camera', 'album'] })
      const selected = image.tempFilePaths.map((path, index) => ({
        id: `${Date.now()}-${index}-${Math.random().toString(16).slice(2)}`,
        preview: path,
        status: 'uploading' as const,
      }))
      setPhotos((current) => [...current, ...selected].slice(0, 5))

      await Promise.all(selected.map(async (photo) => {
        try {
          const upload = await uploadEmployeeEvidence(photo.preview)
          setPhotos((current) => current.map((item) => item.id === photo.id ? { ...item, url: upload.url, status: 'ready' } : item))
        } catch {
          setPhotos((current) => current.map((item) => item.id === photo.id ? { ...item, status: 'failed' } : item))
        }
      }))
    } catch {
      Taro.showToast({ title: '未选择照片', icon: 'none' })
    }
  }

  const removePhoto = (id: string) => setPhotos((current) => current.filter((item) => item.id !== id))

  const submit = async () => {
    if (channel === 'courier' && (!company.trim() || !trackingNo.trim())) {
      return Taro.showToast({ title: '请填写快递公司和单号', icon: 'none' })
    }
    if (channel === 'linehaul' && !company.trim()) {
      return Taro.showToast({ title: '请填写物流部或承运方', icon: 'none' })
    }
    if (photos.length < minPhotoCount) {
      return Taro.showToast({ title: `请至少上传 ${minPhotoCount} 张照片`, icon: 'none' })
    }
    if (photos.some((photo) => photo.status === 'uploading')) {
      return Taro.showToast({ title: '照片还在上传，请稍等', icon: 'none' })
    }
    if (photos.some((photo) => photo.status === 'failed' || !photo.url)) {
      return Taro.showToast({ title: '有照片上传失败，请删除后重传', icon: 'none' })
    }

    setSaving(true)
    try {
      await shipEmployeeOrder(orderId, {
        shipping_mode: channel === 'courier' ? 'express' : 'offline',
        fulfillment_channel: channel,
        logistics_company: company.trim() || undefined,
        tracking_no: trackingNo.trim() || undefined,
        shipping_evidence: photos.length ? { photos: photos.map((photo) => photo.url!) } : {},
        note: note.trim() || undefined,
      })
      Taro.showToast({ title: channel === 'pickup' ? '已登记待提货' : '已发货', icon: 'success' })
      onDone()
      onClose()
    } catch (error) {
      Taro.showToast({ title: error instanceof Error ? error.message : '提交失败', icon: 'none' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <PageContainer show position="bottom" overlay round closeOnSlideDown onClickOverlay={onClose} onAfterLeave={onClose}>
      <View className="shipping-sheet">
        <View className="shipping-sheet-handle" />
        <View className="shipping-sheet-head">
          <Text className="shipping-sheet-title">登记发货</Text>
          <Text className="shipping-sheet-close" onClick={onClose}>关闭</Text>
        </View>

        <ScrollView scrollY className="shipping-sheet-scroll">
          <View className="shipping-mode-row">
            {channels.map((item) => (
              <Text key={item.value} className={`shipping-mode-tab ${channel === item.value ? 'shipping-mode-tab--active' : ''}`} onClick={() => setChannel(item.value)}>
                {item.label}
              </Text>
            ))}
          </View>

          <View className="shipping-fields">
            {(channel === 'courier' || channel === 'linehaul') && (
              <Input className="shipping-field-input" value={company} placeholder={currentChannel.companyPlaceholder} onInput={(event) => setCompany(event.detail.value)} />
            )}
            {(channel === 'courier' || channel === 'linehaul') && (
              <Input className="shipping-field-input" value={trackingNo} placeholder={currentChannel.trackingPlaceholder} onInput={(event) => setTrackingNo(event.detail.value)} />
            )}
            {showNote ? (
              <Textarea className="shipping-field-note" value={note} autoHeight placeholder="交接人、运费或补充说明（可选）" onInput={(event) => setNote(event.detail.value)} />
            ) : (
              <Text className="shipping-add-note" onClick={() => setShowNote(true)}>+ 添加补充说明</Text>
            )}
          </View>

          <View className="shipping-photo-head">
            <Text className="shipping-evidence-title">照片凭证</Text>
            <Text className="shipping-photo-count">{minPhotoCount ? `至少 ${minPhotoCount} 张，最多 5 张` : '最多 5 张（可选）'}</Text>
          </View>

          <ScrollView className="shipping-photo-strip" scrollX>
            <View className="shipping-photo-list">
              {photos.map((photo) => (
                <View key={photo.id} className="shipping-photo-item">
                  <Image src={resolveMediaUrl(photo.preview || photo.url)} mode="aspectFill" />
                  {photo.status !== 'ready' && <Text className={`shipping-photo-state shipping-photo-state--${photo.status}`}>{photo.status === 'uploading' ? '上传中' : '失败'}</Text>}
                  <Text className="shipping-photo-remove" onClick={() => removePhoto(photo.id)}>×</Text>
                </View>
              ))}
              {photos.length < 5 && (
                <View className="shipping-photo-add" onClick={addPhotos}>
                  <Text className="shipping-photo-plus">+</Text>
                  <Text>添加照片</Text>
                </View>
              )}
            </View>
          </ScrollView>
        </ScrollView>

        <View className="shipping-sheet-actions">
          <Button className="shipping-sheet-button shipping-sheet-button--plain" onClick={onClose}>取消</Button>
          <Button className="shipping-sheet-button shipping-sheet-button--primary" loading={saving} onClick={submit}>确认登记</Button>
        </View>
      </View>
    </PageContainer>
  )
}
