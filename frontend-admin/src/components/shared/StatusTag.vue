<template>
  <el-tag :type="tagType" effect="light" size="small">{{ label }}</el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type OrderStatus = 'pending_payment' | 'awaiting_shipment' | 'shipped' | 'completed' | 'canceled'
type FulfillmentChannel = 'courier' | 'linehaul' | 'local_delivery' | 'pickup' | '' | null | undefined
type AftersaleStatus = 'pending' | 'resolved'
type ReviewStatus = 'pending' | 'approved' | 'rejected'

const props = defineProps<{
  kind: 'order' | 'aftersale' | 'review' | 'operation'
  status: string
  fulfillmentChannel?: FulfillmentChannel
}>()

// ponytail: 配送方式属于详情信息，不再扩展订单主状态。
const orderLabel = (status: OrderStatus, _ch?: FulfillmentChannel) => {
  if (status === 'pending_payment') return '待支付'
  if (status === 'awaiting_shipment') return '待发货'
  if (status === 'shipped') return '已发货'
  if (status === 'completed') return '已完成'
  if (status === 'canceled')  return '已取消'
  return status
}

const orderType = (status: OrderStatus, _ch?: FulfillmentChannel): '' | 'warning' | 'success' | 'info' | 'danger' => {
  if (status === 'pending_payment')    return 'warning'
  if (status === 'awaiting_shipment')  return 'warning'
  if (status === 'shipped') return 'success'
  if (status === 'completed') return 'success'
  if (status === 'canceled')  return 'danger'
  return 'info'
}

const label = computed(() => {
  if (props.kind === 'order') {
    return orderLabel(props.status as OrderStatus, props.fulfillmentChannel)
  }
  if (props.kind === 'aftersale') {
    const map: Record<AftersaleStatus, string> = { pending: '待处理', resolved: '已处理' }
    return map[props.status as AftersaleStatus] ?? props.status
  }
  if (props.kind === 'review') {
    const map: Record<ReviewStatus, string> = { pending: '待审核', approved: '已通过', rejected: '已拒绝' }
    return map[props.status as ReviewStatus] ?? props.status
  }
  if (props.kind === 'operation') return props.status.includes('.deleted') ? '已删除' : props.status
  return props.status
})

const tagType = computed((): '' | 'warning' | 'success' | 'info' | 'danger' => {
  if (props.kind === 'order') {
    return orderType(props.status as OrderStatus, props.fulfillmentChannel)
  }
  if (props.kind === 'aftersale') {
    return props.status === 'resolved' ? 'success' : 'warning'
  }
  if (props.kind === 'review') {
    if (props.status === 'approved') return 'success'
    if (props.status === 'rejected') return 'danger'
    return 'warning'
  }
  if (props.kind === 'operation') return 'danger'
  return 'info'
})
</script>
