import { useEffect, useMemo, useState } from 'react'
import Taro, { useRouter } from '@tarojs/taro'
import { Button, Image, ScrollView, Text, Textarea, View } from '@tarojs/components'
import { BackButton } from '../../components/BackButton'
import { CopyIcon } from '../../components/CopyIcon'
import { ShippingSheet } from '../../components/ShippingSheet'
import { cancelEmployeeOrder, createEmployeePickListPrintJob, fetchEmployeeOrders, markEmployeeOrderDelivered, saveEmployeeOrderNote, type EmployeeOrder } from '../../api/employee'
import { resolveMediaUrl } from '../../services/http'
import { copyText } from '../../utils/clipboard'
import { getSafeStyle } from '../../utils/safeArea'
import { EmployeeWatermark } from '../../components/EmployeeWatermark'
import './index.scss'

const statusText: Record<string, string> = {
  pending_payment: '待支付',
  awaiting_shipment: '待发货',
  shipped: '已发货',
  completed: '已完成',
  canceled: '已取消',
}

const channelText: Record<string, string> = {
  courier: '快递',
  linehaul: '物流部',
  local_delivery: '同城配送',
  pickup: '到店自提',
}
const ORDER_CHANGED_EVENT = 'employee:orders-changed'

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString() : ''
}

function collectEvidence(order: EmployeeOrder) {
  const evidence = order.shipping_evidence || {}
  return ['photos', 'handoff', 'scene', 'freight']
    .flatMap((key) => evidence[key] || [])
    .filter(Boolean)
}

function cancellationText(order: EmployeeOrder) {
  const label = order.cancellation_source === 'auto_timeout'
    ? '超时自动取消'
    : order.cancellation_source === 'customer'
      ? '客户手动取消'
      : order.cancellation_source === 'staff'
        ? '店内手动取消'
        : '订单已取消'
  const reason = order.cancellation_reason === 'payment timeout' ? '超过支付时限，订单已自动取消' : order.cancellation_reason
  return reason ? label + ' · ' + reason : label
}

export default function OrderDetailPage() {
  const router = useRouter()
  const orderId = Number(router.params.id)
  const [order, setOrder] = useState<EmployeeOrder | null>(null)
  const [note, setNote] = useState('')
  const [loading, setLoading] = useState(true)
  const [showShipping, setShowShipping] = useState(false)
  const [creatingPrintJob, setCreatingPrintJob] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const item = (await fetchEmployeeOrders()).find((value) => value.id === orderId) || null
      setOrder(item)
      setNote(item?.internal_note || '')
    } catch (error) {
      Taro.showToast({ title: error instanceof Error ? error.message : '订单加载失败', icon: 'none' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [orderId])

  const evidencePhotos = useMemo(() => order ? collectEvidence(order) : [], [order])
  const resolvedEvidencePhotos = evidencePhotos.map(resolveMediaUrl).filter(Boolean)
  const productImageUrls = useMemo(() => order ? order.lines.map((line) => resolveMediaUrl(line.image_url)).filter(Boolean) : [], [order])

  const saveNote = async () => {
    if (!order) return
    try {
      await saveEmployeeOrderNote(order.id, note)
      Taro.showToast({ title: '备注已保存', icon: 'success' })
    } catch (error) {
      Taro.showToast({ title: error instanceof Error ? error.message : '保存失败', icon: 'none' })
    }
  }

  const complete = async () => {
    if (!order) return
    const result = await Taro.showModal({ title: '确认交付', content: '确认货物已实际交给客户后，再完成订单。' })
    if (!result.confirm) return
    try {
      await markEmployeeOrderDelivered(order.id)
      Taro.showToast({ title: '订单已完成', icon: 'success' })
      Taro.eventCenter.trigger(ORDER_CHANGED_EVENT)
      void load()
    } catch (error) {
      Taro.showToast({ title: error instanceof Error ? error.message : '操作失败', icon: 'none' })
    }
  }

  const cancel = async () => {
    if (!order) return
    const result = await Taro.showModal({ title: '终止订单', content: '该订单尚未付款，终止后会保留操作记录。', confirmColor: '#b54747' })
    if (!result.confirm) return
    try {
      await cancelEmployeeOrder(order.id)
      Taro.showToast({ title: '订单已终止', icon: 'success' })
      Taro.eventCenter.trigger(ORDER_CHANGED_EVENT)
      void load()
    } catch (error) {
      Taro.showToast({ title: error instanceof Error ? error.message : '操作失败', icon: 'none' })
    }
  }

  const requestPickListPrint = async () => {
    if (!order || creatingPrintJob) return
    const result = await Taro.showModal({ title: '打印配货单', content: '将创建一张配货单打印任务，在线网关会自动处理。' })
    if (!result.confirm) return
    setCreatingPrintJob(true)
    try {
      await createEmployeePickListPrintJob(order.id)
      Taro.showToast({ title: '已进入打印队列', icon: 'success' })
    } catch (error) {
      Taro.showToast({ title: error instanceof Error ? error.message : '登记失败', icon: 'none' })
    } finally { setCreatingPrintJob(false) }
  }

  const previewEvidence = (url: string) => {
    if (!resolvedEvidencePhotos.length) return
    Taro.previewImage({ current: url, urls: resolvedEvidencePhotos })
  }

  const previewProductImage = (url: string) => {
    if (!productImageUrls.length) return
    Taro.previewImage({ current: url, urls: productImageUrls })
  }

  const finishShipping = () => {
    setShowShipping(false)
    Taro.eventCenter.trigger(ORDER_CHANGED_EVENT)
    void load()
  }

  if (loading) {
    return <View className="detail-shell" style={getSafeStyle()}><EmployeeWatermark /><BackButton /><Text className="detail-empty">正在读取订单...</Text></View>
  }
  if (!order) {
    return <View className="detail-shell" style={getSafeStyle()}><EmployeeWatermark /><BackButton /><Text className="detail-empty">订单不存在或没有访问权限</Text></View>
  }

  return (
    <View className="detail-shell" style={getSafeStyle()}>
      <EmployeeWatermark />
      <View className="detail-content">
        <BackButton />

          <View className="page-title">
            <View>
              <Text className="page-title-main">订单详情</Text>
              <View className="order-no-row">
                <Text className="page-title-sub">{order.order_no}</Text>
                <View className="copy-icon" onClick={() => copyText(order.order_no, '订单号')}>
                  <View className="copy-icon-back" />
                  <View className="copy-icon-front" />
                </View>
              </View>
            </View>
            <Text className={'pill pill--' + (order.status === 'completed' ? 'success' : order.status === 'canceled' ? 'info' : 'warning')}>{statusText[order.status] || order.status}</Text>
          </View>

          <View className="card detail-card">
            <View className="detail-top">
              <View>
                <Text className="detail-customer">{order.customer_name}</Text>
                <View className="detail-copy-line"><Text className="detail-line">{order.customer_phone || '未留联系电话'}</Text>{order.customer_phone && <CopyIcon value={order.customer_phone} label="客户电话" />}</View>
              </View>
              <Text className="detail-amount">¥{order.payable_amount}</Text>
            </View>
            <View className="detail-divider" />
            <Text className="detail-line">{channelText[order.fulfillment_channel || ''] || '交接方式待确认'} · {order.shipping_recipient || '收货人待确认'}</Text>
            <Text className="detail-line">{order.shipping_address || '暂无地址或提货说明'}</Text>
            {order.logistics_company && <View className="detail-copy-line"><Text className="detail-line">{order.logistics_company}{order.tracking_no ? ' · ' + order.tracking_no : ''}</Text><CopyIcon value={order.tracking_no || order.logistics_company} label={order.tracking_no ? '物流单号' : '物流公司'} /></View>}
          </View>

          <Text className="section-title">商品清单</Text>
          <View className="card lines-card">
            {order.lines.map((line, index) => {
              const imageUrl = resolveMediaUrl(line.image_url)
              return (
              <View className="order-line" key={line.product_name + '-' + index}>
                {imageUrl && <Image className="line-image" src={imageUrl} mode="aspectFill" onClick={() => previewProductImage(imageUrl)} />}
                <View className="line-content">
                  <Text className="line-name">{line.product_name}</Text>
                  <View className="detail-copy-line"><Text className="line-spec">{[line.spec_value_1, line.spec_value_2].filter(Boolean).join(' / ') || '默认规格'} · {line.sku_code || '未留货号'} · ¥{line.unit_price}</Text>{line.sku_code && <CopyIcon value={line.sku_code} label="SKU 货号" />}</View>
                </View>
                <Text className="line-count">×{line.quantity}</Text>
              </View>
              )
            })}
          </View>

          {resolvedEvidencePhotos.length > 0 && (
            <>
              <Text className="section-title">照片凭证</Text>
              <ScrollView className="evidence-scroll" scrollX enhanced showScrollbar={false}>
                <View className="card evidence-card">
                  {resolvedEvidencePhotos.map((url, index) => (
                    <Image key={url + '-' + index} className="evidence-image" src={url} mode="aspectFill" onClick={() => previewEvidence(url)} />
                  ))}
                </View>
              </ScrollView>
            </>
          )}

          <Text className="section-title">处理记录</Text>
          <View className="card timeline-card">
            <Text className="timeline-line">下单 · {formatTime(order.created_at)}</Text>
            {order.paid_at && <Text className="timeline-line">付款 · {formatTime(order.paid_at)}</Text>}
            {order.shipped_at && <Text className="timeline-line">发货 · {formatTime(order.shipped_at)}</Text>}
            {order.completed_at && <Text className="timeline-line">完成 · {formatTime(order.completed_at)}</Text>}
            {order.canceled_at && !order.terminated_at && <Text className="timeline-line">{cancellationText(order)} · {formatTime(order.canceled_at)}</Text>}
            {order.terminated_at && <Text className="timeline-line">订单终止 · {order.termination_reason || '已按沟通结果终止'} · {formatTime(order.terminated_at)}</Text>}
          </View>

          <Text className="section-title">内部备注</Text>
          <View className="card note-card">
            <Textarea value={note} autoHeight maxlength={255} placeholder="交接人、客户沟通或异常说明" onInput={(event) => setNote(event.detail.value)} />
            <Text className="note-save" onClick={saveNote}>保存</Text>
          </View>

        <View className="detail-action-spacer" />
      </View>

      <View className="detail-action-bar">
        {order.can_cancel && <Button className="detail-action-button detail-action-button--plain" onClick={cancel}>终止订单</Button>}
        {order.can_ship && <Button className="detail-action-button detail-action-button--secondary" loading={creatingPrintJob} onClick={requestPickListPrint}>打印配货单</Button>}
        {order.can_ship && <Button className="detail-action-button detail-action-button--primary" onClick={() => setShowShipping(true)}>登记发货</Button>}
        {order.can_mark_delivered && <Button className="detail-action-button detail-action-button--primary" onClick={complete}>确认交付</Button>}
        {!order.can_cancel && !order.can_ship && !order.can_mark_delivered && <Button className="detail-action-button detail-action-button--primary" onClick={() => Taro.navigateBack()}>返回</Button>}
      </View>

      {showShipping && <ShippingSheet orderId={order.id} onClose={() => setShowShipping(false)} onDone={finishShipping} />}
    </View>
  )
}
