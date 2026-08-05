import { useSyncExternalStore } from 'react'
import { type Product } from '../mock/catalog'

export type Address = {
  id: string
  backendId?: number
  name: string
  phone: string
  region: string
  detail: string
  isDefault: boolean
}

export type OrderStatus = '待支付' | '待发货' | '已发货' | '已完成' | '已取消'

export type OrderLine = {
  key: string
  product: Product
  productId: string
  skuId?: number
  color: string
  size: string
  quantity: number
}

export type OrderEvent = {
  time: string
  title: string
  body: string
}

export type Order = {
  id: string
  backendId?: number
  status: OrderStatus
  amount: number
  merchandiseAmount?: number
  shippingFee?: number
  paymentMethod?: string
  shippingMode?: string
  shippingProofUrl?: string
  count: number
  date: string
  note: string
  remark: string
  address: Address
  lines: OrderLine[]
  paidAt?: string
  shippedAt?: string
  signedAt?: string
  completedAt?: string
  canceledAt?: string
  canCancel?: boolean
  canConfirmReceipt?: boolean
  canAfterSale?: boolean
  canDelete?: boolean
  events: OrderEvent[]
}

type CommerceState = {
  addresses: Address[]
  orders: Order[]
}

export const emptyStatusCounts: Record<OrderStatus, number> = {
  待支付: 0,
  待发货: 0,
  已发货: 0,
  已完成: 0,
  已取消: 0,
}

export const orderStatusMeta: Record<OrderStatus, { label: OrderStatus; actionHint: string }> = {
  待支付: { label: '待支付', actionHint: '请继续完成支付' },
  待发货: { label: '待发货', actionHint: '商家正在备货' },
  已发货: { label: '已发货', actionHint: '商品已交接，请以店内确认信息为准' },
  已完成: { label: '已完成', actionHint: '可再次购买' },
  已取消: { label: '已取消', actionHint: '订单已关闭' },
}

const listeners = new Set<() => void>()

let state: CommerceState = {
  addresses: [],
  orders: [],
}

function emit() {
  listeners.forEach((listener) => listener())
}

function getSnapshot() {
  return state
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function nowText() {
  const now = new Date()
  return `${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
}

function todayText() {
  return nowText().slice(0, 5)
}

function nextOrderId() {
  const now = new Date()
  const stamp = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`
  return `O${stamp}${String(state.orders.length + 1).padStart(2, '0')}`
}

function setState(next: CommerceState) {
  state = next
  emit()
}

function appendEvent(order: Order, title: string, body: string): Order {
  return { ...order, events: [{ time: nowText(), title, body }, ...order.events] }
}

export function useCommerce() {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
  const defaultAddress = snapshot.addresses.find((item) => item.isDefault) || snapshot.addresses[0]

  const saveAddress = (address: Address) => {
    const nextAddress = address.isDefault || snapshot.addresses.length === 0 ? { ...address, isDefault: true } : address
    const exists = snapshot.addresses.some((item) => item.id === nextAddress.id)
    const addresses = exists
      ? snapshot.addresses.map((item) => (item.id === nextAddress.id ? nextAddress : item))
      : [...snapshot.addresses, nextAddress]
    setState({
      ...snapshot,
      addresses: nextAddress.isDefault ? addresses.map((item) => ({ ...item, isDefault: item.id === nextAddress.id })) : addresses,
    })
  }

  const removeAddress = (id: string) => {
    const addresses = snapshot.addresses.filter((item) => item.id !== id)
    setState({
      ...snapshot,
      addresses: addresses.some((item) => item.isDefault) || addresses.length === 0
        ? addresses
        : addresses.map((item, index) => ({ ...item, isDefault: index === 0 })),
    })
  }

  const setDefaultAddress = (id: string) => {
    setState({
      ...snapshot,
      addresses: snapshot.addresses.map((item) => ({ ...item, isDefault: item.id === id })),
    })
  }

  const replaceAddresses = (addresses: Address[]) => {
    setState({ ...snapshot, addresses })
  }

  const replaceOrders = (orders: Order[]) => {
    setState({ ...snapshot, orders })
  }

  const createOrder = (lines: OrderLine[], amount: number, address: Address, remark: string) => {
    const order: Order = {
      id: nextOrderId(),
      status: '待支付',
      amount,
      count: lines.reduce((sum, item) => sum + item.quantity, 0),
      date: todayText(),
      note: lines.slice(0, 2).map((item) => item.product.name).join('、') || '采购清单',
      remark,
      address,
      lines: lines.map((item) => ({ ...item })),
      events: [{ time: nowText(), title: '订单已创建', body: '等待继续支付。' }],
    }
    setState({ ...snapshot, orders: [order, ...snapshot.orders] })
    return order
  }

  const updateOrder = (id: string, updater: (order: Order) => Order) => {
    let nextOrder: Order | undefined
    const orders = snapshot.orders.map((order) => {
      if (order.id !== id) return order
      nextOrder = updater(order)
      return nextOrder
    })
    setState({ ...snapshot, orders })
    return nextOrder
  }

  const upsertOrder = (order: Order) => {
    const exists = snapshot.orders.some((item) => item.id === order.id || (item.backendId && item.backendId === order.backendId))
    setState({
      ...snapshot,
      orders: exists
        ? snapshot.orders.map((item) => (item.id === order.id || (item.backendId && item.backendId === order.backendId) ? order : item))
        : [order, ...snapshot.orders],
    })
  }

  const payOrder = (id: string) => updateOrder(id, (order) => appendEvent({ ...order, status: '待发货', paidAt: nowText() }, '支付成功', '订单已支付，等待店内发货。'))
  const confirmOrder = (id: string) => updateOrder(id, (order) => appendEvent({ ...order, status: '待发货' }, '商家已确认', '库存和价格已确认，等待发货。'))
  const shipOrder = (id: string) => updateOrder(id, (order) => appendEvent({ ...order, status: '已发货', shippedAt: nowText() }, '订单已发货', '商品已出库，请留意收货。'))
  const completeOrder = (id: string) => updateOrder(id, (order) => appendEvent({ ...order, status: '已完成', completedAt: nowText() }, '订单已完成', '本次采购已完成。'))
  const cancelOrder = (id: string) => updateOrder(id, (order) => appendEvent({ ...order, status: '已取消' }, '订单已取消', '订单已关闭。'))

  const statusCounts = snapshot.orders.reduce<Record<OrderStatus, number>>((counts, order) => {
    counts[order.status] += 1
    return counts
  }, { ...emptyStatusCounts })

  return {
    addresses: snapshot.addresses,
    defaultAddress,
    orders: snapshot.orders,
    statusCounts,
    saveAddress,
    removeAddress,
    setDefaultAddress,
    replaceAddresses,
    replaceOrders,
    createOrder,
    upsertOrder,
    payOrder,
    confirmOrder,
    shipOrder,
    completeOrder,
    cancelOrder,
  }
}
