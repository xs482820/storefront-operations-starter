import { useEffect, useMemo, useState } from 'react'
import Taro from '@tarojs/taro'
import { Image, Input, Text, Textarea, View } from '@tarojs/components'
import { fetchEmployeeAfterSales, resolveEmployeeAfterSale, type EmployeeAfterSale } from '../../api/employee'
import { BackButton } from '../../components/BackButton'
import { CopyIcon } from '../../components/CopyIcon'
import { resolveMediaUrl } from '../../services/http'
import { getSafeStyle } from '../../utils/safeArea'
import { EmployeeWatermark } from '../../components/EmployeeWatermark'
import './index.scss'

const statusText: Record<string, string> = { pending: '待处理', resolved: '已处理', rejected: '已驳回' }
const reasonText: Record<string, string> = {
  quality_issue: '质量问题',
  wrong_item: '发错商品',
  damaged: '运输破损',
  size_problem: '规格不符',
  other: '其他原因',
}

export default function AftersalePage() {
  const [items, setItems] = useState<EmployeeAfterSale[]>([])
  const [error, setError] = useState('')
  const [activeId, setActiveId] = useState<number | null>(null)
  const [processType, setProcessType] = useState('refund_only')
  const [refundAmount, setRefundAmount] = useState('')
  const [customerNote, setCustomerNote] = useState('')
  const [internalNote, setInternalNote] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const proofUrls = useMemo(() => items.map((item) => resolveMediaUrl(item.chat_proof_url)).filter(Boolean), [items])

  const load = () => fetchEmployeeAfterSales()
    .then((data) => { setItems(data); setError('') })
    .catch((reason) => setError(reason instanceof Error ? reason.message : '售后加载失败'))

  useEffect(() => { load() }, [])

  const previewProof = (url: string) => {
    Taro.previewImage({ current: url, urls: proofUrls.length ? proofUrls : [url] })
  }

  const openResolve = (item: EmployeeAfterSale) => {
    setActiveId(item.id)
    setProcessType('refund_only')
    setRefundAmount(item.refund_amount || '')
    setCustomerNote(item.customer_note || item.note || '')
    setInternalNote(item.internal_note || '')
  }

  const submitResolve = async (item: EmployeeAfterSale) => {
    const needsRefund = processType === 'refund_only' || processType === 'refund_and_return'
    if (needsRefund && (!refundAmount || Number(refundAmount) < 0)) {
      Taro.showToast({ title: '请填写退款金额', icon: 'none' })
      return
    }
    if (!customerNote.trim()) {
      Taro.showToast({ title: '请填写给客户的处理说明', icon: 'none' })
      return
    }
    setSubmitting(true)
    try {
      await resolveEmployeeAfterSale(item.id, {
        process_type: processType,
        refund_amount: needsRefund ? Number(refundAmount) : undefined,
        customer_note: customerNote.trim(),
        internal_note: internalNote.trim() || undefined,
      })
      Taro.showToast({ title: '售后已处理', icon: 'success' })
      setActiveId(null)
      load()
    } catch (reason) {
      Taro.showToast({ title: reason instanceof Error ? reason.message : '处理失败', icon: 'none' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <View className="page aftersale-page" style={getSafeStyle()}>
      <EmployeeWatermark />
      <BackButton />
      <View className="page-title">
        <View>
          <Text className="page-title-main">售后</Text>
          <Text className="page-title-sub">优先处理待处理申请，处理记录会同步给客户</Text>
        </View>
        <Text className="workbench-refresh" onClick={load}>刷新列表</Text>
      </View>

      {error && <Text className="aftersale-error">{error}</Text>}
      {items.map((item) => {
        const proofUrl = resolveMediaUrl(item.chat_proof_url)
        return (
          <View key={item.id} className="aftersale-card card">
            <View className="aftersale-head">
              <View className="aftersale-copy-line"><Text className="aftersale-id">售后单 AS{item.id} · {item.order_no || '订单待同步'}</Text><CopyIcon value={`AS${item.id}`} label="售后单号" /></View>
              <Text className={'pill ' + (item.status === 'pending' ? 'pill--warning' : 'pill--success')}>{statusText[item.status] || item.status}</Text>
            </View>
            <View className="aftersale-body">
              <View className="aftersale-info">
                <View className="aftersale-copy-line"><Text className="aftersale-main">{item.customer_name} · {item.customer_phone || '未留电话'}</Text>{item.customer_phone && <CopyIcon value={item.customer_phone} label="客户电话" />}</View>
                <Text className="aftersale-reason">{reasonText[item.reason] || item.reason}</Text>
                {item.refund_amount && <Text className="aftersale-amount">退款金额 ¥{item.refund_amount}</Text>}
              </View>
              {proofUrl && <Image className="aftersale-proof" src={proofUrl} mode="aspectFill" onClick={() => previewProof(proofUrl)} />}
            </View>
            {item.status === 'pending' && activeId !== item.id && <View className="aftersale-action" onClick={() => openResolve(item)}>处理售后</View>}
            {activeId === item.id && (
              <View className="aftersale-form">
                <Text className="aftersale-form-title">处理方式</Text>
                <View className="aftersale-type-row">
                  {[['refund_only', '仅退款'], ['refund_and_return', '退货退款'], ['exchange', '换货'], ['rejected', '不受理']].map(([value, label]) => <Text key={value} className={'aftersale-type ' + (processType === value ? 'active' : '')} onClick={() => setProcessType(value)}>{label}</Text>)}
                </View>
                {(processType === 'refund_only' || processType === 'refund_and_return') && <Input className="aftersale-input" type="digit" value={refundAmount} placeholder="退款金额" onInput={(event) => setRefundAmount(event.detail.value)} />}
                <Textarea className="aftersale-textarea" value={customerNote} maxlength={255} placeholder="给客户的处理说明（必填）" onInput={(event) => setCustomerNote(event.detail.value)} />
                <Textarea className="aftersale-textarea" value={internalNote} maxlength={1000} placeholder="内部备注（仅店内可见，可留空）" onInput={(event) => setInternalNote(event.detail.value)} />
                <View className="aftersale-form-actions"><View className="aftersale-cancel" onClick={() => setActiveId(null)}>取消</View><View className={'aftersale-submit ' + (submitting ? 'disabled' : '')} onClick={() => !submitting && submitResolve(item)}>{submitting ? '提交中' : '确认处理'}</View></View>
              </View>
            )}
          </View>
        )
      })}
      {!error && items.length === 0 && <View className="aftersale-empty card"><Text>暂无需要处理的售后</Text></View>}
    </View>
  )
}
