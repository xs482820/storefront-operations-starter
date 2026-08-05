import { useEffect, useMemo, useState } from 'react'
import Taro, { useDidShow, useRouter } from '@tarojs/taro'
import { Image, Input, Text, View } from '@tarojs/components'
import { Icon } from '@antmjs/vantui/lib/icon'
import { Popup } from '@antmjs/vantui/lib/popup'
import { createAddress, deleteAddress, fetchAddresses, updateAddress } from '../../api/address'
import { createAfterSale, fetchAfterSales, type AfterSale, type AfterSaleReason } from '../../api/aftersale'
import { fetchCart } from '../../api/cart'
import { fetchProductDetail, fetchStorefrontConfig } from '../../api/catalog'
import { fetchCustomerMe, updateCustomerMe, uploadCustomerImage } from '../../api/customer'
import { fetchFavorites, removeFavorite, type CustomerFavorite } from '../../api/favorite'
import { cancelOrder as cancelApiOrder, confirmReceipt, fetchOrder, fetchOrders } from '../../api/order'
import { fetchNotifications, markAllNotificationsRead, markNotificationRead } from '../../api/notification'
import { createWholesaleApplication, fetchWholesaleApplications, type WholesaleApplication } from '../../api/wholesale'
import { ProductDetailSheet } from '../../components/ProductDetailSheet'
import { WholesaleWatermark } from '../../components/WholesaleWatermark'
import { TopUtilityActions } from '../../components/TopUtilityActions'
import { adaptAddress, adaptCartItem, adaptCustomerOrder, adaptCustomerProduct } from '../../domain/adapters'
import { type Product } from '../../mock/catalog'
import { runWechatPaymentFlow } from '../../services/paymentFlow'
import {
  fetchMiniappSubscribeEvents,
  isSubscribeEnabled,
  requestOrderSubscribeMessages,
  setSubscribeEnabled,
  type MiniappSubscribeEvent,
} from '../../services/subscribeMessage'
import { useCart } from '../../store/useCart'
import { type Address, type Order, type OrderStatus, orderStatusMeta, useCommerce } from '../../store/useCommerce'
import { getSafeVars } from '../../utils/safeArea'
import { previewImages } from '../../utils/imagePreview'
import { resolveMediaUrl } from '../../services/http'
import { notifyCustomerNotificationsChanged } from '../../services/notificationState'
import './index.scss'

type ProfileView = 'home' | 'notifications' | 'notificationSettings' | 'orders' | 'orderDetail' | 'addresses' | 'addressEdit' | 'wholesale' | 'aftersale' | 'aftersaleApply' | 'favorites' | 'service' | 'settings'
type IdentityMode = 'retail' | 'wholesale'
type OrderFilter = '全部' | OrderStatus
type NotificationKindFilter = '全部' | '订单' | '售后' | '批发' | '系统'
type NotificationItem = { id: string; title: string; body: string; read: boolean; kind: string; route?: string | null; createdAt: string }
type AfterSaleRecord = {
  id: string
  orderId: string
  orderNo?: string
  status: string
  reason: string
  note: string
  amount?: string
  proofUrl?: string
  processType?: string
  createdAt: string
}
type AfterSaleType = 'refund_only' | 'return_refund' | 'exchange' | 'resend'

const statusOrder: OrderStatus[] = ['待支付', '待发货', '已发货', '已完成', '已取消']
const homeOrderStatuses: OrderStatus[] = ['待支付', '待发货', '已发货', '已完成', '已取消']
const statusIcons: Record<OrderStatus, string> = {
  待支付: 'pending-payment',
  待发货: 'tosend',
  已发货: 'logistics',
  已完成: 'completed',
  已取消: 'close',
}

const statusClassMap: Record<OrderStatus, string> = {
  待支付: 'pending-pay',
  待发货: 'ready-ship',
  已发货: 'shipped',
  已完成: 'done',
  已取消: 'closed',
}

const afterSaleReasons: { value: AfterSaleReason; label: string }[] = [
  { value: 'quality_issue', label: '质量问题' },
  { value: 'wrong_item', label: '发错商品' },
  { value: 'damaged', label: '运输破损' },
  { value: 'size_problem', label: '规格不符' },
  { value: 'other', label: '其他原因' },
]

const afterSaleTypes: { value: AfterSaleType; label: string; desc: string }[] = [
  { value: 'refund_only', label: '仅退款', desc: '未收到货、少发漏发或协商退款' },
  { value: 'return_refund', label: '退货退款', desc: '需要退回商品后处理' },
  { value: 'exchange', label: '换货', desc: '规格不符或商品问题需换新' },
  { value: 'resend', label: '补发', desc: '漏发、破损件补寄' },
]

const afterSaleReasonLabels: Record<string, string> = {
  quality_issue: '质量问题',
  wrong_item: '发错商品',
  damaged: '运输破损',
  size_problem: '规格不符',
  other: '其他原因',
}

const afterSaleStatusLabels: Record<string, string> = {
  pending: '待处理',
  processing: '处理中',
  resolved: '已处理',
  rejected: '已驳回',
}

const afterSaleProcessLabels: Record<string, string> = {
  refund_only: '仅退款',
  refund_and_return: '退货退款',
  exchange: '换货',
  resend: '补发',
  rejected: '拒绝',
}

const wholesaleStatusLabels: Record<string, string> = {
  pending: '待审核',
  approved: '已通过',
  rejected: '已驳回',
  revoked: '已失效',
}

const blankAddress: Address = {
  id: '',
  name: '',
  phone: '',
  region: '',
  detail: '',
  isDefault: false,
}

const READ_ORDER_IDS_KEY = 'baby_mall_fresh_read_order_ids'
const NICKNAME_PATTERN = /^[A-Za-z\u4E00-\u9FFF]+$/

function avatarInitial(name: string) {
  const initial = name.trim().slice(0, 1)
  return /^[A-Za-z]$/.test(initial) ? initial.toUpperCase() : initial || '?'
}

export default function ProfilePage() {
  const router = useRouter()
  const cart = useCart()
  const commerce = useCommerce()
  const initialView = ['notifications', 'notificationSettings', 'orders', 'addresses', 'wholesale', 'aftersale', 'favorites', 'service', 'settings'].includes(String(router.params.view))
    ? String(router.params.view) as ProfileView
    : 'home'
  const initialFilter = statusOrder.includes(String(router.params.status) as OrderStatus)
    ? String(router.params.status) as OrderStatus
    : '全部'
  const returnTo = typeof router.params.returnTo === 'string' ? decodeURIComponent(router.params.returnTo) : ''
  const [view, setView] = useState<ProfileView>(initialView)
  const [orderFilter, setOrderFilter] = useState<OrderFilter>(initialFilter)
  const [identityMode, setIdentityMode] = useState<IdentityMode>('retail')
  const [nickname, setNickname] = useState('')
  const [avatarUrl, setAvatarUrl] = useState('')
  const [phone, setPhone] = useState('')
  const [storeName, setStoreName] = useState('')
  const [realName, setRealName] = useState('')
  const [storeAddress, setStoreAddress] = useState('')
  const [businessLicenseUrl, setBusinessLicenseUrl] = useState('')
  const [storePhotoUrl, setStorePhotoUrl] = useState('')
  const [contactPhone, setContactPhone] = useState('')
  const [serviceWechat, setServiceWechat] = useState('')
  const [selectedOrderId, setSelectedOrderId] = useState('')
  const [viewHistory, setViewHistory] = useState<ProfileView[]>([])
  const [notifications, setNotifications] = useState<NotificationItem[]>([])
  const [notificationFilter, setNotificationFilter] = useState<NotificationKindFilter>('全部')
  const [notificationUnreadOnly, setNotificationUnreadOnly] = useState(false)
  const [notificationSearch, setNotificationSearch] = useState('')
  const [selectedNotification, setSelectedNotification] = useState<NotificationItem | null>(null)
  const [orderSearch, setOrderSearch] = useState('')
  const [favoriteSearch, setFavoriteSearch] = useState('')
  const [afterSaleSearch, setAfterSaleSearch] = useState('')
  const [afterSaleStatusFilter, setAfterSaleStatusFilter] = useState('全部')
  const [subscribeEnabled, setSubscribeEnabledState] = useState(() => isSubscribeEnabled())
  const [subscribeEvents, setSubscribeEvents] = useState<MiniappSubscribeEvent[]>([])
  const [subscribeEventKeys, setSubscribeEventKeys] = useState<string[]>([])
  const [afterSales, setAfterSales] = useState<AfterSaleRecord[]>([])
  const [wholesaleApplications, setWholesaleApplications] = useState<WholesaleApplication[]>([])
  const [favorites, setFavorites] = useState<CustomerFavorite[]>([])
  const [selectedFavoriteProduct, setSelectedFavoriteProduct] = useState<Product | null>(null)
  const [readOrderIds, setReadOrderIds] = useState<string[]>([])
  const [afterSaleType, setAfterSaleType] = useState<AfterSaleType>('return_refund')
  const [afterSaleReason, setAfterSaleReason] = useState<AfterSaleReason>('quality_issue')
  const [afterSaleNote, setAfterSaleNote] = useState('')
  const [afterSaleProofUrl, setAfterSaleProofUrl] = useState('')
  const [editingAddress, setEditingAddress] = useState<Address>(blankAddress)

  const adaptAfterSaleRecord = (item: AfterSale): AfterSaleRecord => ({
    id: String(item.id),
    orderId: String(item.order_id),
    orderNo: item.order_no || undefined,
    status: afterSaleStatusLabels[item.status] || item.status || '处理中',
    reason: item.custom_reason_text || afterSaleReasonLabels[item.reason] || item.reason,
    note: item.note || '',
    amount: item.refund_amount == null ? undefined : String(item.refund_amount),
    proofUrl: resolveMediaUrl(item.chat_proof_url) || undefined,
    processType: item.process_type ? afterSaleProcessLabels[item.process_type] || item.process_type : undefined,
    createdAt: item.created_at,
  })

  const refreshAddresses = async (silent = true) => {
    try {
      const items = await fetchAddresses()
      commerce.replaceAddresses(items.map(adaptAddress))
      if (!silent) Taro.showToast({ title: '地址已刷新', icon: 'success' })
    } catch {
      if (!silent) Taro.showToast({ title: '地址加载失败，请稍后重试', icon: 'none' })
    }
  }

  const refreshFavorites = async () => {
    try {
      setFavorites(await fetchFavorites())
    } catch {
      // ponytail: favorites are non-critical; keep the current list if refresh fails.
    }
  }

  const refreshCartItems = async () => {
    try {
      const items = await fetchCart()
      cart.replace(items.map(adaptCartItem))
    } catch {
      // ponytail: product detail can still open with local cart state.
    }
  }

  useDidShow(() => {
    if (view !== 'addressEdit') refreshAddresses()
  })

  useEffect(() => {
    const storedReadOrderIds = Taro.getStorageSync(READ_ORDER_IDS_KEY)
    if (Array.isArray(storedReadOrderIds)) {
      setReadOrderIds(storedReadOrderIds.filter((item) => typeof item === 'string'))
    }
    fetchCustomerMe()
      .then((me) => {
        setNickname(me.display_name || me.username || '')
        setAvatarUrl(resolveMediaUrl(me.avatar_url))
        setPhone(me.phone || '')
        setStoreName(me.store_name || me.company_name || '')
        setRealName(me.contact_name || '')
        setStoreAddress(me.address || '')
        setBusinessLicenseUrl(resolveMediaUrl(me.business_license_url))
        setContactPhone(me.phone || '')
        setIdentityMode(me.role === 'wholesale' || me.is_verified_wholesale ? 'wholesale' : 'retail')
        setSubscribeEnabled(me.miniapp_notification_enabled)
        setSubscribeEnabledState(me.miniapp_notification_enabled)
        setSubscribeEventKeys(me.miniapp_notification_event_keys || [])
      })
      .catch(() => undefined)
    refreshAddresses()
    fetchOrders()
      .then((items) => commerce.replaceOrders(items.map(adaptCustomerOrder)))
      .catch(() => undefined)
    fetchNotifications()
      .then((items) => setNotifications(items.map((item) => ({
        id: String(item.id),
        title: item.title,
        body: item.summary,
        read: !item.unread,
        kind: item.kind,
        route: item.route,
        createdAt: item.created_at,
      }))))
      .catch(() => undefined)
    fetchAfterSales()
      .then((records) => setAfterSales(records.map(adaptAfterSaleRecord)))
      .catch(() => undefined)
    fetchWholesaleApplications()
      .then(setWholesaleApplications)
      .catch(() => undefined)
    refreshFavorites()
    refreshCartItems()
    fetchStorefrontConfig()
      .then((config) => {
        setContactPhone((current) => current || config.store_info?.phone || '')
        setServiceWechat(config.customer_service?.wechat_id || '')
      })
      .catch(() => undefined)
    fetchMiniappSubscribeEvents()
      .then((events) => {
        setSubscribeEvents(events)
        setSubscribeEventKeys((current) => (current.length ? current : events.map((event) => event.key)))
      })
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    if (view === 'addresses' || view === 'addressEdit') refreshAddresses()
    if (view === 'favorites') {
      refreshFavorites()
      refreshCartItems()
    }
  }, [view])

  const unreadCount = notifications.filter((item) => !item.read).length
  const selectedOrder = commerce.orders.find((item) => item.id === selectedOrderId)
  const normalizeSearch = (value: string) => value.trim().toLowerCase()
  const includesQuery = (query: string, ...values: Array<string | number | undefined | null>) => {
    const normalized = normalizeSearch(query)
    if (!normalized) return true
    return values.some((value) => String(value || '').toLowerCase().includes(normalized))
  }
  const notificationKindLabel = (kind: string): NotificationKindFilter => {
    if (kind.includes('order')) return '订单'
    if (kind.includes('aftersale')) return '售后'
    if (kind.includes('wholesale')) return '批发'
    return '系统'
  }
  const notificationKindClass = (kind: string) => ({ 订单: 'order', 售后: 'aftersale', 批发: 'wholesale', 系统: 'system' }[notificationKindLabel(kind)])
  const filteredNotifications = notifications.filter((item) => (
    (notificationFilter === '全部' || notificationKindLabel(item.kind) === notificationFilter)
    && (!notificationUnreadOnly || !item.read)
    && includesQuery(notificationSearch, item.title, item.body, item.kind)
  ))
  const filteredOrders = (orderFilter === '全部' ? commerce.orders : commerce.orders.filter((order) => order.status === orderFilter))
    .filter((order) => includesQuery(orderSearch, order.id, order.note, order.status, order.lines.map((item) => item.product.name).join(' ')))
  const filteredAfterSales = afterSales.filter((record) => (
    (afterSaleStatusFilter === '全部' || record.status === afterSaleStatusFilter)
    && includesQuery(afterSaleSearch, record.id, record.orderNo, record.orderId, record.status, record.reason, record.note)
  ))
  const filteredFavorites = favorites.filter((item) => includesQuery(
    favoriteSearch,
    item.product_id,
    item.product?.name,
    item.product?.description,
    item.product?.model_name,
  ))
  const afterSaleStatusOptions = ['全部', ...Array.from(new Set(afterSales.map((item) => item.status).filter(Boolean)))]
  const orderCount = commerce.orders.length
  const afterSaleCount = afterSales.length
  const favoriteCount = favorites.length
  const latestWholesaleApplication = wholesaleApplications[0]
  const unreadOrderCounts = commerce.orders.reduce<Record<OrderStatus, number>>((counts, order) => {
    if (!readOrderIds.includes(order.id)) counts[order.status] += 1
    return counts
  }, { ...commerce.statusCounts, ...Object.fromEntries(statusOrder.map((status) => [status, 0])) } as Record<OrderStatus, number>)

  const viewTitle = useMemo(() => {
    const titles: Record<ProfileView, string> = {
      home: '我的',
      notifications: '通知中心',
      notificationSettings: '通知设置',
      orders: '我的订单',
      orderDetail: '订单详情',
      addresses: '收货地址',
      addressEdit: editingAddress.id ? '编辑地址' : '新增地址',
      wholesale: '批发认证',
      aftersale: '售后服务',
      aftersaleApply: '申请售后',
      favorites: '我的收藏',
      service: '联系客服',
      settings: '资料设置',
    }
    return titles[view]
  }, [editingAddress.id, view])

  const displayName = nickname.trim() || '未登录用户'
  const defaultAvatarText = avatarInitial(displayName)
  const maskedPhone = phone && phone.length >= 7 ? `${phone.slice(0, 3)}****${phone.slice(-4)}` : phone || '未绑定'
  const shippingModeLabel = (mode?: string) => {
    if (mode === 'pickup') return '自提'
    if (mode === 'linehaul') return '物流'
    if (mode === 'offline') return '发货'
    if (mode === 'express') return '快递'
    return '发货'
  }
  const paymentMethodLabel = (method?: string) => {
    if (method === 'wechat_pay') return '微信支付'
    if (method === 'offline_transfer') return '线下转账'
    return method || '未确认'
  }
  const orderAfterSales = selectedOrder
    ? afterSales.filter((record) => (
      record.orderNo === selectedOrder.id || record.orderId === selectedOrder.id || (selectedOrder.backendId && record.orderId === String(selectedOrder.backendId))
    ))
    : []
  const afterSaleOrderNo = (record: AfterSaleRecord) => (
    record.orderNo || commerce.orders.find((order) => String(order.backendId) === record.orderId)?.id || record.orderId
  )

  const chooseAndUploadImage = async (onUploaded: (url: string) => void) => {
    try {
      const chosen = await Taro.chooseImage({ count: 1, sizeType: ['compressed'], sourceType: ['album', 'camera'] })
      const filePath = chosen.tempFilePaths?.[0]
      if (!filePath) return
      Taro.showLoading({ title: '上传中' })
      const result = await uploadCustomerImage(filePath)
      onUploaded(result.url)
      Taro.showToast({ title: '上传成功', icon: 'success' })
    } catch (error) {
      Taro.showToast({ title: error instanceof Error ? error.message : '上传失败', icon: 'none' })
    } finally {
      Taro.hideLoading()
    }
  }

  const navigateView = (nextView: ProfileView) => {
    setViewHistory((current) => [...current, view])
    setView(nextView)
  }

  const openOrdersWithFilter = (filter: OrderFilter) => {
    setOrderFilter(filter)
    navigateView('orders')
  }

  const openOrderDetail = (order: Order) => {
    setSelectedOrderId(order.id)
    setReadOrderIds((current) => {
      if (current.includes(order.id)) return current
      const next = [...current, order.id]
      Taro.setStorageSync(READ_ORDER_IDS_KEY, next)
      return next
    })
    navigateView('orderDetail')
  }

  const openAfterSaleApply = (order: Order) => {
    setSelectedOrderId(order.id)
    setAfterSaleType(order.status === '已发货' || order.status === '已完成' ? 'return_refund' : 'refund_only')
    setAfterSaleReason('quality_issue')
    setAfterSaleNote('')
    setAfterSaleProofUrl('')
    navigateView('aftersaleApply')
  }

  const openAddressEditor = (address?: Address) => {
    setEditingAddress(address || { ...blankAddress, id: `a${Date.now()}` })
    navigateView('addressEdit')
  }

  const saveSubscribePreference = async (enabled: boolean, eventKeys = subscribeEventKeys) => {
    setSubscribeEnabled(enabled)
    setSubscribeEnabledState(enabled)
    setSubscribeEventKeys(eventKeys)
    try {
      await updateCustomerMe({
        miniapp_notification_enabled: enabled,
        miniapp_notification_event_keys: enabled ? eventKeys : [],
      })
    } catch {
      Taro.showToast({ title: '通知设置保存失败，请稍后重试', icon: 'none' })
    }
  }

  const updateSubscribeSetting = async (enabled: boolean, requestPermission = false, eventKeys = subscribeEventKeys) => {
    if (!enabled) {
      await saveSubscribePreference(false, [])
      Taro.showToast({ title: '已关闭微信提醒', icon: 'none' })
      return
    }
    if (requestPermission) {
      const result = await requestOrderSubscribeMessages(eventKeys)
      await saveSubscribePreference(true, result.acceptedEventKeys)
      Taro.showToast({
        title: result.acceptedEventKeys.length > 0
          ? `已授权 ${result.acceptedEventKeys.length} 项通知`
          : '微信未授权通知，请在弹窗中允许',
        icon: result.acceptedEventKeys.length > 0 ? 'success' : 'none',
      })
      return
    }
    await saveSubscribePreference(true, eventKeys)
    Taro.showToast({ title: '通知设置已保存', icon: 'success' })
  }

  const toggleSubscribeEvent = async (eventKey: string) => {
    const willEnable = !subscribeEventKeys.includes(eventKey)
    const nextKeys = subscribeEventKeys.includes(eventKey)
      ? subscribeEventKeys.filter((key) => key !== eventKey)
      : [...subscribeEventKeys, eventKey]
    if (subscribeEnabled && willEnable) {
      const result = await requestOrderSubscribeMessages([eventKey])
      if (result.acceptedEventKeys.length === 0) {
        Taro.showToast({ title: '微信未授权此通知', icon: 'none' })
        return
      }
    }
    await saveSubscribePreference(subscribeEnabled, nextKeys)
  }

  const handleBack = () => {
    if (viewHistory.length > 0) {
      const previous = viewHistory[viewHistory.length - 1]
      setViewHistory((current) => current.slice(0, -1))
      setView(previous)
      return
    }
    if (view === 'orderDetail') {
      setView('orders')
      return
    }
    if (view === 'addressEdit') {
      setView('addresses')
      return
    }
    if (view === 'aftersaleApply') {
      setView('orderDetail')
      return
    }
    if (view === 'wholesale') {
      setView('settings')
      return
    }
    if (returnTo) {
      if (Taro.getCurrentPages().length > 1) Taro.navigateBack()
      else Taro.redirectTo({ url: returnTo })
      return
    }
    setView('home')
  }

  const saveAddress = async () => {
    if (!editingAddress.name || !editingAddress.phone || !editingAddress.detail) {
      Taro.showToast({ title: '请补全收货信息', icon: 'none' })
      return
    }
    const payload = {
      contact_name: editingAddress.name,
      phone: editingAddress.phone,
      region: editingAddress.region,
      detail: editingAddress.detail,
      is_default: editingAddress.isDefault,
    }
    try {
      const address = editingAddress.backendId ? await updateAddress(editingAddress.backendId, payload) : await createAddress(payload)
      commerce.saveAddress(adaptAddress(address))
      await refreshAddresses()
      setView('addresses')
      Taro.showToast({ title: '地址已保存', icon: 'success' })
    } catch {
      Taro.showToast({ title: '地址保存失败，请稍后重试', icon: 'none' })
    }
  }

  const payOrder = async (order: Order) => {
    try {
      if (!order.backendId) {
        const nextOrder = commerce.payOrder(order.id)
        if (nextOrder) setSelectedOrderId(nextOrder.id)
        Taro.showToast({ title: '支付已完成', icon: 'success' })
        return
      }
      const result = await runWechatPaymentFlow(order.backendId)
      if (result.status === 'paid') {
        commerce.upsertOrder(result.order)
        setSelectedOrderId(result.order.id)
        Taro.showToast({ title: result.message, icon: 'success' })
        return
      }
      Taro.showToast({ title: result.message, icon: 'none' })
    } catch (error) {
      Taro.showToast({ title: error instanceof Error ? error.message : '支付未完成，订单已保留', icon: 'none' })
    }
  }

  const cancelOrder = async (order: Order) => {
    try {
      if (order.backendId) {
        await cancelApiOrder(order.backendId)
      }
      commerce.cancelOrder(order.id)
      Taro.showToast({ title: '订单已取消', icon: 'success' })
    } catch (error) {
      Taro.showToast({ title: error instanceof Error ? error.message : '取消失败', icon: 'none' })
    }
  }

  const completeOrder = async (order: Order) => {
    try {
      if (order.backendId) {
        const nextOrder = await confirmReceipt(order.backendId)
        commerce.upsertOrder(adaptCustomerOrder(nextOrder))
      } else {
        commerce.completeOrder(order.id)
      }
      Taro.showToast({ title: '已确认收货', icon: 'success' })
    } catch (error) {
      Taro.showToast({ title: error instanceof Error ? error.message : '确认失败', icon: 'none' })
    }
  }

  const reorder = (order: Order) => {
    order.lines.forEach((line) => cart.add(line.product, line.color, line.size, line.quantity))
    Taro.showToast({ title: '已加入清单', icon: 'success' })
    Taro.redirectTo({ url: '/pages/cart/index' })
  }

  const loadAfterSales = async () => {
    try {
      const records = await fetchAfterSales()
      setAfterSales(records.map(adaptAfterSaleRecord))
    } catch {
      Taro.showToast({ title: '售后记录加载失败，请稍后重试', icon: 'none' })
    }
  }

  const loadAddresses = async () => {
    await refreshAddresses(false)
  }

  const submitAfterSale = async () => {
    const order = selectedOrder
    if (!order) {
      Taro.showToast({ title: '请先选择订单', icon: 'none' })
      return
    }
    if (order.count <= 0) {
      Taro.showToast({ title: '订单商品异常，暂不能申请', icon: 'none' })
      return
    }
    if (!afterSaleNote.trim()) {
      Taro.showToast({ title: '请填写问题说明', icon: 'none' })
      return
    }
    const typeLabel = afterSaleTypes.find((item) => item.value === afterSaleType)?.label || '售后'
    const reasonLabel = afterSaleReasons.find((item) => item.value === afterSaleReason)?.label || '其他原因'
    const readonlyAmount = Number(order.amount || 0).toFixed(2)
    const note = `售后类型：${typeLabel}；问题说明：${afterSaleNote.trim()}`
    try {
      if (order.backendId) {
        const record = await createAfterSale({
          order_id: order.backendId,
          reason: afterSaleReason,
          custom_reason_text: afterSaleReason === 'other' ? afterSaleNote.trim() : null,
          requested_amount: readonlyAmount,
          chat_proof_url: afterSaleProofUrl || null,
          note,
        })
        setAfterSales((current) => [{ ...adaptAfterSaleRecord(record), reason: reasonLabel }, ...current])
      } else {
        setAfterSales((current) => [{
          id: `local-${Date.now()}`,
          orderId: order.id,
          status: '处理中',
          reason: reasonLabel,
          note,
          amount: readonlyAmount,
          createdAt: new Date().toLocaleString(),
        }, ...current])
      }
      Taro.showToast({ title: '售后已提交', icon: 'success' })
      setViewHistory([])
      setView('home')
    } catch (error) {
      Taro.showToast({ title: error instanceof Error ? error.message : '售后提交失败', icon: 'none' })
    }
  }

  const submitWholesaleApplication = async () => {
    if (!realName.trim() || !storeName.trim() || !storeAddress.trim()) {
      Taro.showToast({ title: '请补全姓名、门店和地址', icon: 'none' })
      return
    }
    if (!businessLicenseUrl) {
      Taro.showToast({ title: '请上传营业执照', icon: 'none' })
      return
    }
    try {
      const applications = await fetchWholesaleApplications().catch(() => [])
      if (applications.some((item) => item.effective_status === 'pending' || item.status === 'pending')) {
        Taro.showToast({ title: '已有批发申请待审核', icon: 'none' })
        setView('settings')
        return
      }
      const application = await createWholesaleApplication({
        store_name: storeName.trim(),
        contact_name: realName.trim(),
        contact_phone: phone || contactPhone || null,
        business_license_url: businessLicenseUrl,
        remark: storePhotoUrl ? `门店照片：${storePhotoUrl}` : '未上传门店照片',
      })
      await updateCustomerMe({
        store_name: storeName.trim(),
        contact_name: realName.trim(),
        address: storeAddress.trim(),
        business_license_url: businessLicenseUrl,
      }).catch(() => undefined)
      setWholesaleApplications((current) => [application, ...current])
      Taro.showToast({ title: '批发申请已提交', icon: 'success' })
      setView('settings')
    } catch (error) {
      const message = error instanceof Error ? error.message : '提交失败'
      if (message.includes('pending wholesale application')) {
        Taro.showToast({ title: '已有批发申请待审核', icon: 'none' })
        setView('settings')
        return
      }
      if (message.includes('already wholesale')) {
        Taro.showToast({ title: '已是批发客户', icon: 'none' })
        setView('settings')
        return
      }
      Taro.showToast({ title: message, icon: 'none' })
    }
  }

  const deleteFavorite = async (item: CustomerFavorite) => {
    setFavorites((current) => current.filter((favorite) => favorite.id !== item.id))
    setSelectedFavoriteProduct((current) => (
      current && (current.backendId === item.product_id || current.id === String(item.product_id))
        ? { ...current, isFavorited: false }
        : current
    ))
    try {
      await removeFavorite(item.product_id)
      Taro.showToast({ title: '已取消收藏', icon: 'success' })
    } catch {
      Taro.showToast({ title: '已取消收藏', icon: 'success' })
    }
  }

  const copyText = (value: string, label = '内容') => {
    Taro.setClipboardData({
      data: value,
      success: () => Taro.showToast({ title: `${label}已复制`, icon: 'success' }),
    })
  }

  const openProductDetail = async (product: Product) => {
    await refreshCartItems()
    setSelectedFavoriteProduct(product)
    if (!product.backendId) return
    try {
      const detail = await fetchProductDetail(product.backendId)
      setSelectedFavoriteProduct(adaptCustomerProduct(detail))
    } catch {
      // ponytail: keep the order snapshot visible if the live product detail cannot be loaded.
    }
  }

  const renderCopyableNo = (value: string, label: string, title = value) => (
    <View className="profile-copyable-no">
      <Text className="profile-record-title">{title}</Text>
      <View
        className="profile-copy-icon"
        onClick={(event) => {
          event.stopPropagation()
          copyText(value, label)
        }}
      >
        <Icon name="description" size="26rpx" />
      </View>
    </View>
  )

  const renderTopBar = () => (
    <View className="profile-header">
      {view !== 'home' && (
        <View className="profile-back-button" onClick={handleBack}>
          <Text>‹</Text>
        </View>
      )}
      <Text className="profile-title">{viewTitle}</Text>
      {view === 'home' && (
        <View className="profile-header-actions"><TopUtilityActions onOpenNotifications={() => navigateView('notifications')} /></View>
      )}
    </View>
  )

  const renderOrderStatusGrid = () => (
    <View className="profile-order-status-card">
      <View className="profile-order-card-head">
        <View>
          <Text className="profile-card-title">我的订单</Text>
          <Text className="profile-menu-desc">
            {orderCount > 0 ? `${orderCount} 笔订单` : '暂无订单'}
          </Text>
        </View>
        <View className="profile-order-count-box" onClick={() => openOrdersWithFilter('全部')}>
          <Text className="profile-order-count-value">{orderCount}</Text>
          <Text className="profile-order-count-label">全部订单</Text>
        </View>
      </View>
      <View className="profile-order-status-grid">
        {homeOrderStatuses.map((status) => {
          const count = commerce.statusCounts[status]
          return (
            <View key={status} className="profile-order-status-item" onClick={() => openOrdersWithFilter(status)}>
              <View className={`profile-order-status-icon ${count > 0 ? 'has-count' : ''}`}>
                <Icon name={statusIcons[status]} size="32rpx" />
              </View>
              <Text className="profile-order-status-label">{status}</Text>
            </View>
          )
        })}
        <View className="profile-order-status-item" onClick={() => navigateView('aftersale')}>
          <View className={`profile-order-status-icon ${afterSaleCount > 0 ? 'has-count' : ''}`}>
            <Icon name="after-sale" size="32rpx" />
          </View>
          <Text className="profile-order-status-label">售后</Text>
        </View>
      </View>
    </View>
  )

  const renderOrderEmpty = () => (
    <View className="profile-order-empty">
      <Icon name="description" size="84rpx" />
      <Text className="profile-order-empty-title">{orderFilter === '全部' ? '暂无订单' : `暂无${orderFilter}订单`}</Text>
      <Text className="profile-order-empty-copy">{orderFilter === '全部' ? '提交订单后，可在这里查看处理进度。' : '暂时没有符合当前筛选条件的订单。'}</Text>
      <View
        className="profile-order-empty-action"
        onClick={() => {
          if (orderFilter === '全部') {
            Taro.switchTab({ url: '/pages/home/index' })
            return
          }
          setOrderFilter('全部')
        }}
      >
        {orderFilter === '全部' ? '去选购' : '查看全部订单'}
      </View>
    </View>
  )

  const renderAfterSaleEmpty = () => (
    <View className="profile-order-empty profile-aftersale-empty">
      <Icon name="after-sale" size="84rpx" />
      <Text className="profile-order-empty-title">暂无售后记录</Text>
      <Text className="profile-order-empty-copy">售后申请和处理进度会集中显示在这里。</Text>
      <View className="profile-order-empty-action" onClick={() => openOrdersWithFilter('全部')}>查看订单</View>
    </View>
  )

  const renderEmptyCard = (title: string, body: string, action?: string, onAction?: () => void) => (
    <View className="profile-empty-card">
      <Icon className="profile-empty-icon" name="description" size="56rpx" />
      <Text className="profile-record-title">{title}</Text>
      <Text className="profile-record-copy">{body}</Text>
      {action && onAction && <View className="profile-primary-button" onClick={onAction}>{action}</View>}
    </View>
  )

  const renderListSearch = (value: string, onChange: (value: string) => void, placeholder: string) => (
    <View className="profile-list-search">
      <Icon name="search" size="26rpx" />
      <Input value={value} placeholder={placeholder} onInput={(event) => onChange(String(event.detail.value || ''))} />
      {value.trim() && <Text className="profile-search-clear" onClick={() => onChange('')}>清除</Text>}
    </View>
  )

  const renderChipRow = <T extends string,>(items: T[], active: T, onChange: (value: T) => void) => (
    <View className="profile-order-filter-row compact">
      {items.map((item) => (
        <View key={item} className={`profile-order-filter-chip ${active === item ? 'active' : ''}`} onClick={() => onChange(item)}>
          <Text>{item}</Text>
        </View>
      ))}
    </View>
  )

  const renderHome = () => (
    <>
      <View className="profile-card">
        <View className="profile-avatar">
          {avatarUrl ? <Image className="profile-avatar-image" src={avatarUrl} mode="aspectFill" /> : defaultAvatarText}
        </View>
        <View className="profile-card-copy">
          <Text className="profile-name">{displayName}</Text>
          <View className="profile-role-row">
            <Text className={`profile-role-pill ${identityMode}`}>{identityMode === 'wholesale' ? '批发客户' : '零售会员'}</Text>
            <Text className="profile-role">资料用于订单、售后和收货联系</Text>
          </View>
        </View>
        <View className="profile-edit-link" onClick={() => navigateView('settings')}>编辑</View>
      </View>

      {renderOrderStatusGrid()}

      <Text className="profile-section-title">常用功能</Text>
      <View className="profile-menu">
        {[
          ['addresses', '收货地址', commerce.addresses.length ? `${commerce.addresses.length} 个地址` : '暂无地址'],
          ['favorites', '我的收藏', favoriteCount ? `${favoriteCount} 件已收藏商品` : '收藏后会集中显示'],
        ].map(([nextView, label, desc]) => (
          <View key={nextView} className="profile-menu-row" onClick={() => navigateView(nextView as ProfileView)}>
            <View>
              <Text className="profile-menu-title">{label}</Text>
              <Text className="profile-menu-desc">{desc}</Text>
            </View>
            <Text className="profile-menu-arrow">›</Text>
          </View>
        ))}
      </View>
      <Text className="profile-section-title">设置</Text>
      <View className="profile-menu">
        <View className="profile-menu-row" onClick={() => navigateView('notificationSettings')}>
          <View>
            <Text className="profile-menu-title">通知设置</Text>
            <Text className="profile-menu-desc">{subscribeEnabled ? '微信服务通知已开启' : '微信服务通知已关闭'}</Text>
          </View>
          <Text className="profile-menu-arrow">›</Text>
        </View>
      </View>
    </>
  )

  const renderNotifications = () => (
    <View className="profile-panel-list">
      {renderListSearch(notificationSearch, setNotificationSearch, '搜索订单、售后、认证消息')}
      {renderChipRow(['全部', '订单', '售后', '批发', '系统'] as NotificationKindFilter[], notificationFilter, setNotificationFilter)}
      <View className="profile-filter-toggle" onClick={() => setNotificationUnreadOnly((current) => !current)}>
        <Text>{notificationUnreadOnly ? '只看未读' : '查看全部'}</Text>
        <Text className="profile-filter-toggle-copy">{unreadCount} 条未读</Text>
      </View>
      {notifications.length > 0 && (
        <View
          className="profile-panel-action"
          onClick={() => {
            markAllNotificationsRead().catch(() => undefined)
            setNotifications((current) => current.map((item) => ({ ...item, read: true })))
            notifyCustomerNotificationsChanged(0)
          }}
        >
          全部标为已读
        </View>
      )}
      {filteredNotifications.length === 0
        ? renderEmptyCard('暂无通知', '有新的订单进度、售后处理或认证结果时，会第一时间放在这里。')
        : filteredNotifications.map((item) => (
          <View
            key={item.id}
            className={`profile-record-card profile-notification-row ${item.read ? 'is-read' : 'unread'}`}
            onClick={() => {
              if (!item.read) {
                markNotificationRead(item.id).catch(() => undefined)
                setNotifications((current) => current.map((next) => (next.id === item.id ? { ...next, read: true } : next)))
                notifyCustomerNotificationsChanged(notifications.filter((next) => !next.read && next.id !== item.id).length)
              }
              setSelectedNotification({ ...item, read: true })
            }}
          >
            <View className="profile-record-head">
              <View className="profile-notification-title-wrap">
                {!item.read && <View className="profile-notification-unread-dot" />}
                <Text className="profile-record-title">{item.title}</Text>
              </View>
              <Text className={`profile-notification-kind kind-${notificationKindClass(item.kind)}`}>{notificationKindLabel(item.kind)}</Text>
            </View>
            <Text className="profile-record-copy">{item.body}</Text>
            <View className="profile-notification-foot"><Text>{String(item.createdAt || '').slice(0, 16).replace('T', ' ')}</Text><Text>{item.read ? '已读' : '未读'}</Text></View>
          </View>
        ))}
      <Popup show={Boolean(selectedNotification)} position="center" round onClose={() => setSelectedNotification(null)}>
        {selectedNotification && <View className="profile-notification-detail">
          <View className="profile-notification-detail-head"><Text className={`profile-notification-kind kind-${notificationKindClass(selectedNotification.kind)}`}>{notificationKindLabel(selectedNotification.kind)}</Text><Text className="profile-notification-detail-close" onClick={() => setSelectedNotification(null)}>关闭</Text></View>
          <Text className="profile-notification-detail-title">{selectedNotification.title}</Text>
          <Text className="profile-notification-detail-body">{selectedNotification.body}</Text>
          <Text className="profile-notification-detail-time">{String(selectedNotification.createdAt || '').replace('T', ' ').slice(0, 16)} · 已读</Text>
        </View>}
      </Popup>
    </View>
  )

  const renderOrderFilters = () => (
    <View className="profile-order-filter-row">
      {(['全部', ...statusOrder] as OrderFilter[]).map((status) => (
        <View key={status} className={`profile-order-filter-chip ${orderFilter === status ? 'active' : ''}`} onClick={() => setOrderFilter(status)}>
          <Text>{status}</Text>
          {status !== '全部' && unreadOrderCounts[status] > 0 && <Text className="profile-filter-badge">{unreadOrderCounts[status]}</Text>}
        </View>
      ))}
    </View>
  )

  const renderOrders = () => (
    <View className="profile-panel-list">
      {renderOrderFilters()}
      {renderListSearch(orderSearch, setOrderSearch, '搜索订单号、商品、备注')}
      {filteredOrders.length === 0 ? (
        renderOrderEmpty()
      ) : (
        filteredOrders.map((order) => (
          <View key={order.id} className={`profile-record-card ${readOrderIds.includes(order.id) ? '' : 'unread-order'}`} onClick={() => openOrderDetail(order)}>
            <View className="profile-record-head">
              {renderCopyableNo(order.id, '订单号')}
              <View className="profile-record-tags">
                {!readOrderIds.includes(order.id) && <Text className="profile-unread-pill">未读</Text>}
                <Text className={`profile-status-pill status-${statusClassMap[order.status]}`}>{order.status}</Text>
              </View>
            </View>
            <Text className="profile-record-copy">{orderStatusMeta[order.status].actionHint}</Text>
            <Text className="profile-record-copy">{order.note}</Text>
            <Text className="profile-record-price">¥{order.amount} / {order.count} 件</Text>
          </View>
        ))
      )}
    </View>
  )

  const renderOrderActions = (order: Order) => {
    if (order.status === '待支付') {
      return (
        <View className="profile-detail-actions">
          <View className="profile-secondary-button" onClick={() => cancelOrder(order)}>取消订单</View>
          <View className="profile-primary-button" onClick={() => payOrder(order)}>继续支付</View>
        </View>
      )
    }
    if (order.status === '待发货') {
      return (
        <View className="profile-detail-actions">
          <View className="profile-secondary-button" onClick={() => navigateView('service')}>联系客服</View>
          <View className="profile-primary-button" onClick={() => Taro.showToast({ title: '商家正在备货', icon: 'none' })}>等待发货</View>
        </View>
      )
    }
    if (order.status === '已发货') {
      return (
        <View className="profile-detail-actions">
          <View className="profile-secondary-button" onClick={() => navigateView('service')}>联系店里</View>
          <View className="profile-primary-button" onClick={() => completeOrder(order)}>确认收货</View>
        </View>
      )
    }
    if (order.status === '已完成') {
      return (
        <View className="profile-detail-actions">
          <View className="profile-secondary-button" onClick={() => openAfterSaleApply(order)}>申请售后</View>
          <View className="profile-primary-button" onClick={() => reorder(order)}>再次购买</View>
        </View>
      )
    }
    if (order.canAfterSale) {
      return <View className="profile-primary-button" onClick={() => openAfterSaleApply(order)}>申请售后</View>
    }
    return <View className="profile-secondary-button" onClick={() => reorder(order)}>重新加入清单</View>
  }

  const renderOrderDetail = () => (
    <View className="profile-panel-list">
      {!selectedOrder ? (
        renderEmptyCard('暂无订单详情', '请选择一笔订单后查看详情。')
      ) : (
        <>
          <View className="profile-record-card detail order-detail-hero">
            <View className="profile-record-head">
              {renderCopyableNo(selectedOrder.id, '订单号')}
              <Text className={`profile-status-pill status-${statusClassMap[selectedOrder.status]}`}>{selectedOrder.status}</Text>
            </View>
            <Text className="profile-record-copy">{orderStatusMeta[selectedOrder.status].actionHint}</Text>
            <View className="order-detail-meta-grid">
              <View>
                <Text className="profile-menu-desc">商品件数</Text>
                <Text className="order-detail-meta-value">{selectedOrder.count} 件</Text>
              </View>
              <View>
                <Text className="profile-menu-desc">支付方式</Text>
                <Text className="order-detail-meta-value">{paymentMethodLabel(selectedOrder.paymentMethod)}</Text>
              </View>
              <View>
                <Text className="profile-menu-desc">配送方式</Text>
                <Text className="order-detail-meta-value">{shippingModeLabel(selectedOrder.shippingMode)}</Text>
              </View>
              <View>
                <Text className="profile-menu-desc">订单金额</Text>
                <Text className="order-detail-meta-value">¥{selectedOrder.amount}</Text>
              </View>
            </View>
            {renderOrderActions(selectedOrder)}
          </View>

          <View className="profile-record-card">
            <Text className="profile-record-title">商品清单</Text>
            {selectedOrder.lines.map((line) => (
              <View key={line.key} className="order-line-row" onClick={() => openProductDetail(line.product)}>
                <View className={`order-line-thumb ${line.product.tone}`}>
                  {line.product.imageUrl && (
                    <Image
                      className="order-line-image"
                      src={line.product.imageUrl}
                      mode="aspectFill"
                      onClick={(event) => {
                        event.stopPropagation()
                        previewImages([line.product.imageUrl], line.product.imageUrl)
                      }}
                    />
                  )}
                </View>
                <View className="order-line-info">
                  <Text className="order-line-name">{line.product.name}</Text>
                  <Text className="profile-record-copy">{line.color} / {line.size} · x{line.quantity}</Text>
                </View>
                <Text className="order-line-price">¥{(line.product.price * line.quantity).toFixed(2)}</Text>
              </View>
            ))}
          </View>

          <View className="profile-record-card">
            <Text className="profile-record-title">{selectedOrder.shippingMode === 'pickup' ? '自提信息' : '配送信息'}</Text>
            {selectedOrder.shippingMode === 'pickup' ? (
              <Text className="profile-record-copy">到店时间和取货安排请以店内确认内容为准。</Text>
            ) : (
              <>
                <Text className="profile-record-copy">收货人：{selectedOrder.address.name || '待确认'} {selectedOrder.address.phone || ''}</Text>
                <Text className="profile-record-copy">地址：{selectedOrder.address.detail || '下单后由店里确认'}</Text>
                <Text className="profile-record-copy">配送和交接信息请以店内确认内容为准。</Text>
              </>
            )}
            {selectedOrder.remark && <Text className="profile-record-copy">备注：{selectedOrder.remark}</Text>}
          </View>

          {orderAfterSales.length > 0 && (
            <View className="profile-record-card">
              <View className="profile-record-head">
                <Text className="profile-record-title">关联售后</Text>
              </View>
              {orderAfterSales.map((record) => (
                <View key={record.id} className="order-aftersale-row" onClick={() => navigateView('aftersale')}>
                  <View>
                    <Text className="profile-record-copy">售后单 AS{record.id} · {record.status}</Text>
                    <Text className="profile-menu-desc">{record.reason}</Text>
                  </View>
                  <Text className="profile-menu-arrow">›</Text>
                </View>
              ))}
            </View>
          )}

          <View className="profile-record-card">
            <Text className="profile-record-title">状态记录</Text>
            {selectedOrder.events.map((event) => (
              <View key={`${event.time}-${event.title}`} className="profile-timeline-row">
                <View className="profile-timeline-dot" />
                <View>
                  <Text className="profile-record-copy">{event.time} · {event.title}</Text>
                  <Text className="profile-menu-desc">{event.body}</Text>
                </View>
              </View>
            ))}
          </View>
        </>
      )}
    </View>
  )

  const renderAddresses = () => (
    <View className="profile-panel-list">
      <View className="profile-action-grid">
        <View className="profile-panel-action" onClick={() => openAddressEditor()}>新增地址</View>
        <View className="profile-panel-action secondary" onClick={loadAddresses}>刷新地址</View>
      </View>
      {commerce.addresses.length === 0 ? (
        renderEmptyCard('暂无收货地址', '添加地址后，结算页会自动使用默认地址。')
      ) : (
        commerce.addresses.map((address) => (
          <View key={address.id} className="profile-record-card">
            <View className="profile-record-head">
              <Text className="profile-record-title">{address.name} {address.phone}</Text>
              {address.isDefault && <Text className="profile-status-pill">默认</Text>}
            </View>
            <Text className="profile-record-copy">{address.region}</Text>
            <Text className="profile-record-copy">{address.detail}</Text>
            <View className="profile-action-row">
              <Text onClick={() => openAddressEditor(address)}>编辑</Text>
              <Text
                onClick={async () => {
                  try {
                    if (address.backendId) {
                      await updateAddress(address.backendId, {
                        contact_name: address.name,
                        phone: address.phone,
                        region: address.region,
                        detail: address.detail,
                        is_default: true,
                      })
                      await refreshAddresses()
                    } else {
                      commerce.setDefaultAddress(address.id)
                    }
                    Taro.showToast({ title: '默认地址已更新', icon: 'success' })
                  } catch {
                    Taro.showToast({ title: '设置失败，请稍后重试', icon: 'none' })
                  }
                }}
              >设为默认</Text>
              <Text
                onClick={async () => {
                  try {
                    if (address.backendId) await deleteAddress(address.backendId)
                    commerce.removeAddress(address.id)
                    await refreshAddresses()
                    Taro.showToast({ title: '地址已删除', icon: 'success' })
                  } catch {
                    Taro.showToast({ title: '删除失败，请稍后重试', icon: 'none' })
                  }
                }}
              >
                删除
              </Text>
            </View>
          </View>
        ))
      )}
    </View>
  )

  const renderAddressEdit = () => (
    <View className="profile-form-card">
      {[
        ['name', '收货人'],
        ['phone', '联系电话'],
        ['region', '省市区'],
        ['detail', '详细地址'],
      ].map(([field, label]) => (
        <View key={field} className="profile-input-row">
          <Text>{label}</Text>
          <Input value={String(editingAddress[field as keyof Address])} onInput={(event) => setEditingAddress((current) => ({ ...current, [field]: String(event.detail.value || '') }))} />
        </View>
      ))}
      <View className="profile-switch-row" onClick={() => setEditingAddress((current) => ({ ...current, isDefault: !current.isDefault }))}>
        <Text>设为默认地址</Text>
        <Text className={`profile-switch ${editingAddress.isDefault ? 'active' : ''}`}>{editingAddress.isDefault ? '开' : '关'}</Text>
      </View>
      <View className="profile-primary-button" onClick={saveAddress}>保存地址</View>
    </View>
  )

  const renderWholesale = () => (
    <View className="profile-form-card">
      <Text className="profile-form-tip">批发认证需要人工审核。营业执照是核心资料，门店照片可选，但上传后更方便我们判断合作场景。</Text>
      <View className="profile-input-row">
        <Text>真实姓名</Text>
        <Input value={realName} placeholder="请输入真实姓名" onInput={(event) => setRealName(String(event.detail.value || ''))} />
      </View>
      <View className="profile-input-row">
        <Text>门店名称</Text>
        <Input value={storeName} placeholder="请输入门店或公司名称" onInput={(event) => setStoreName(String(event.detail.value || ''))} />
      </View>
      <View className="profile-input-row">
        <Text>绑定手机号</Text>
        <Text className="profile-readonly-value">{maskedPhone}</Text>
      </View>
      <View className="profile-input-row">
        <Text>门店地址</Text>
        <Input value={storeAddress} placeholder="请输入实际经营地址" onInput={(event) => setStoreAddress(String(event.detail.value || ''))} />
      </View>
      <View className="profile-upload-row">
        <View>
          <Text className="profile-record-title">营业执照</Text>
          <Text className="profile-record-copy">{businessLicenseUrl ? '已上传，可重新选择' : '必填，用于审核批发身份'}</Text>
          {businessLicenseUrl && (
            <Image
              className="profile-upload-preview"
              src={businessLicenseUrl}
              mode="aspectFill"
              onClick={() => previewImages([businessLicenseUrl], businessLicenseUrl)}
            />
          )}
        </View>
        <View className="profile-upload-button" onClick={() => chooseAndUploadImage(setBusinessLicenseUrl)}>上传</View>
      </View>
      <View className="profile-upload-row">
        <View>
          <Text className="profile-record-title">门店照片</Text>
          <Text className="profile-record-copy">{storePhotoUrl ? '已上传，可重新选择' : '选填，上传后更容易通过审核'}</Text>
          {storePhotoUrl && (
            <Image
              className="profile-upload-preview"
              src={storePhotoUrl}
              mode="aspectFill"
              onClick={() => previewImages([storePhotoUrl], storePhotoUrl)}
            />
          )}
        </View>
        <View className="profile-upload-button secondary" onClick={() => chooseAndUploadImage(setStorePhotoUrl)}>选填</View>
      </View>
      <View
        className="profile-primary-button"
        onClick={submitWholesaleApplication}
      >
        提交批发申请
      </View>
    </View>
  )

  const renderService = () => (
    <View className="profile-panel-list">
      <View className="profile-record-card">
        <Text className="profile-record-title">联系客服</Text>
        <Text className="profile-record-copy">{serviceWechat ? `微信：${serviceWechat}` : '微信客服暂未配置。'}</Text>
        <Text className="profile-record-copy">复制微信号后，在微信中搜索并联系店内客服。</Text>
      </View>
      <View
        className="profile-secondary-button"
        onClick={() => {
          if (!serviceWechat) {
            Taro.showToast({ title: '微信客服暂未配置', icon: 'none' })
            return
          }
          Taro.setClipboardData({ data: serviceWechat })
        }}
      >
        复制微信客服号
      </View>
    </View>
  )

  const renderAfterSale = () => (
    <View className="profile-panel-list">
      <View className="profile-after-sale-search-row">
        {renderListSearch(afterSaleSearch, setAfterSaleSearch, '搜索售后单、订单号、原因')}
        <View className="profile-after-sale-refresh" onClick={loadAfterSales} aria-label="刷新售后记录">
          <Icon name="replay" size="30rpx" />
        </View>
      </View>
      {afterSaleStatusOptions.length > 1 && renderChipRow(afterSaleStatusOptions, afterSaleStatusFilter, setAfterSaleStatusFilter)}
      {filteredAfterSales.length === 0 ? (
        renderAfterSaleEmpty()
      ) : (
        filteredAfterSales.map((record) => (
          <View key={record.id} className="profile-record-card">
            <View className="profile-record-head">
              {renderCopyableNo(`AS${record.id}`, '售后单号', `售后单 AS${record.id}`)}
              <Text className="profile-status-pill">{record.status}</Text>
            </View>
            <View className="profile-copyable-line">
              <Text className="profile-record-copy">关联订单：{afterSaleOrderNo(record)}</Text>
              <View className="profile-copy-icon small" onClick={() => copyText(afterSaleOrderNo(record), '订单号')}>
                <Icon name="description" size="22rpx" />
              </View>
            </View>
            <Text className="profile-record-copy">原因：{record.reason}</Text>
            <Text className="profile-record-copy">说明：{record.note}</Text>
            {record.processType && <Text className="profile-record-copy">处理方式：{record.processType}</Text>}
            {record.proofUrl && (
              <Image
                className="aftersale-proof-image"
                src={record.proofUrl}
                mode="aspectFill"
                onClick={() => previewImages([record.proofUrl], record.proofUrl)}
              />
            )}
            {record.amount && <Text className="profile-record-price">处理金额 ¥{record.amount}</Text>}
          </View>
        ))
      )}
    </View>
  )

  const renderFavorites = () => (
    <View className="profile-panel-list">
      {renderListSearch(favoriteSearch, setFavoriteSearch, '搜索商品名称、型号、说明')}
      {filteredFavorites.length === 0 ? (
        renderEmptyCard('暂无收藏商品', '在商品详情里点“收藏”后，常看的商品会集中显示在这里。')
      ) : (
        filteredFavorites.map((item) => {
          const product = item.product ? adaptCustomerProduct(item.product) : null
          const lowestSku = product?.skus?.slice().sort((first, second) => first.price - second.price)[0]
          return (
            <View
              key={item.id}
              className="profile-record-card favorite-card"
              onLongPress={() => deleteFavorite(item)}
              onClick={() => {
                if (!product) {
                  Taro.showToast({ title: '商品详情暂时不可用', icon: 'none' })
                  return
                }
                openProductDetail({ ...product, isFavorited: true })
              }}
            >
              <View className={`favorite-thumb ${product?.tone || 'cream'}`}>
                {product?.imageUrl && (
                  <Image
                    className="favorite-image"
                    src={product.imageUrl}
                    mode="aspectFill"
                    onClick={(event) => {
                      event.stopPropagation()
                      previewImages([product.imageUrl], product.imageUrl)
                    }}
                  />
                )}
              </View>
              <View className="favorite-info">
                <View className="profile-record-head">
                  <Text className="profile-record-title">{item.product?.name || `商品 ${item.product_id}`}</Text>
                  <View className="profile-record-tags">
                    <Text className="profile-status-pill">已收藏</Text>
                    <Text
                      className="profile-remove-pill"
                      onClick={(event) => {
                        event.stopPropagation()
                        deleteFavorite(item)
                      }}
                    >
                      取消
                    </Text>
                  </View>
                </View>
                <Text className="profile-record-copy">{item.product?.description || item.product?.model_name || '商品信息会持续更新。'}</Text>
                {lowestSku && <Text className="profile-record-copy">默认最低价规格：{lowestSku.color} / {lowestSku.size} · ¥{lowestSku.price}</Text>}
                <Text className="profile-record-copy">收藏时间：{String(item.created_at || '').slice(0, 10)}</Text>
                <Text className="profile-record-copy">点击卡片可查看详情并调整规格数量</Text>
              </View>
            </View>
          )
        })
      )}
    </View>
  )

  const renderAfterSaleApply = () => (
    <View className="profile-form-card aftersale-apply-card">
      {!selectedOrder ? (
        renderEmptyCard('未选择订单', '请先从订单详情中进入售后申请。', '查看订单', () => openOrdersWithFilter('全部'))
      ) : (
        <>
          <View className="aftersale-order-summary">
            <View>
              <Text className="profile-record-title">关联订单</Text>
              <View className="profile-copyable-line">
                <Text className="profile-record-copy">{selectedOrder.id}</Text>
                <View className="profile-copy-icon small" onClick={() => copyText(selectedOrder.id, '订单号')}>
                  <Icon name="description" size="22rpx" />
                </View>
              </View>
            </View>
            <View className="aftersale-amount-box">
              <Text className="aftersale-amount-label">系统预估</Text>
              <Text className="aftersale-amount-value">¥{Number(selectedOrder.amount || 0).toFixed(2)}</Text>
            </View>
          </View>

          <View className="aftersale-section">
            <Text className="aftersale-section-title">选择售后方式</Text>
            <View className="aftersale-type-grid">
              {afterSaleTypes.map((type) => (
                <View
                  key={type.value}
                  className={`aftersale-type-card ${afterSaleType === type.value ? 'active' : ''}`}
                  onClick={() => setAfterSaleType(type.value)}
                >
                  <Text className="aftersale-type-title">{type.label}</Text>
                  <Text className="aftersale-type-desc">{type.desc}</Text>
                </View>
              ))}
            </View>
          </View>

          <View className="aftersale-section">
            <Text className="aftersale-section-title">本次申请商品</Text>
            {selectedOrder.lines.map((line) => (
              <View key={line.key} className="aftersale-line-row" onClick={() => openProductDetail(line.product)}>
                <View className={`aftersale-line-thumb ${line.product.tone}`}>
                  {line.product.imageUrl && (
                    <Image
                      className="aftersale-line-image"
                      src={line.product.imageUrl}
                      mode="aspectFill"
                      onClick={(event) => {
                        event.stopPropagation()
                        previewImages([line.product.imageUrl], line.product.imageUrl)
                      }}
                    />
                  )}
                </View>
                <View className="aftersale-line-info">
                  <Text className="aftersale-line-name">{line.product.name}</Text>
                  <Text className="profile-record-copy">{line.color} / {line.size} · x{line.quantity}</Text>
                </View>
                <Text className="aftersale-line-price">¥{(line.product.price * line.quantity).toFixed(2)}</Text>
              </View>
            ))}
          </View>

          <View className="aftersale-section">
            <Text className="aftersale-section-title">问题原因</Text>
            <View className="profile-reason-grid">
              {afterSaleReasons.map((reason) => (
                <View
                  key={reason.value}
                  className={`profile-reason-chip ${afterSaleReason === reason.value ? 'active' : ''}`}
                  onClick={() => setAfterSaleReason(reason.value)}
                >
                  {reason.label}
                </View>
              ))}
            </View>
          </View>

          <View className="profile-upload-row aftersale-proof-row">
            <View>
              <Text className="profile-record-title">问题凭证</Text>
              <Text className="profile-record-copy">{afterSaleProofUrl ? '已上传，可重新选择' : '建议上传破损、错发或聊天凭证'}</Text>
              {afterSaleProofUrl && (
                <Image
                  className="profile-upload-preview"
                  src={afterSaleProofUrl}
                  mode="aspectFill"
                  onClick={() => previewImages([afterSaleProofUrl], afterSaleProofUrl)}
                />
              )}
            </View>
            <View className="profile-upload-button secondary" onClick={() => chooseAndUploadImage(setAfterSaleProofUrl)}>上传</View>
          </View>

          <View className="profile-input-row aftersale-note-row">
            <Text>问题说明</Text>
            <Input value={afterSaleNote} placeholder="请说明问题和诉求" onInput={(event) => setAfterSaleNote(String(event.detail.value || ''))} />
          </View>

          <View className="aftersale-rule-card">
            <Text className="aftersale-rule-title">处理规则</Text>
            <Text className="profile-record-copy">金额由订单商品自动计算，最终以店员审核结果为准；如需退货，请保持商品和包装完整。</Text>
          </View>

          <View className="profile-primary-button" onClick={submitAfterSale}>提交售后申请</View>
        </>
      )}
    </View>
  )

  const renderWholesaleStatusCard = () => {
    const effectiveStatus = latestWholesaleApplication?.effective_status || latestWholesaleApplication?.status || ''
    if (identityMode === 'wholesale') {
      return (
        <View className="profile-wholesale-summary approved">
          <View className="profile-record-head">
            <Text className="profile-record-title">批发资料</Text>
            <Text className="profile-status-pill">已通过</Text>
          </View>
          <Text className="profile-record-copy">门店：{storeName || latestWholesaleApplication?.store_name || '待补充'}</Text>
          <Text className="profile-record-copy">联系人：{realName || latestWholesaleApplication?.contact_name || '待补充'}</Text>
          <Text className="profile-record-copy">地址：{storeAddress || '待补充'}</Text>
        </View>
      )
    }
    if (latestWholesaleApplication) {
      const statusLabel = wholesaleStatusLabels[effectiveStatus] || '审核中'
      const isRejected = effectiveStatus === 'rejected'
      const isPending = effectiveStatus === 'pending'
      return (
        <View className={`profile-wholesale-summary ${effectiveStatus || 'pending'}`}>
          <View className="profile-record-head">
            <Text className="profile-record-title">批发申请</Text>
            <Text className={`profile-status-pill status-${isRejected ? 'closed' : isPending ? 'pending-pay' : 'done'}`}>{statusLabel}</Text>
          </View>
          <Text className="profile-record-copy">门店：{latestWholesaleApplication.store_name || storeName || '未填写'}</Text>
          <Text className="profile-record-copy">联系人：{latestWholesaleApplication.contact_name || realName || '未填写'}</Text>
          <Text className="profile-record-copy">提交时间：{String(latestWholesaleApplication.created_at || '').slice(0, 10) || '已提交'}</Text>
          {latestWholesaleApplication.review_note && <Text className="profile-record-copy">审核说明：{latestWholesaleApplication.review_note}</Text>}
          {isPending && <Text className="profile-record-copy">店里会尽快审核，通过后即可使用批发权益。</Text>}
          {isRejected && <View className="profile-panel-action secondary" onClick={() => navigateView('wholesale')}>修改资料后重新申请</View>}
        </View>
      )
    }
    return (
      <View className="profile-wholesale-summary">
        <View className="profile-record-head">
          <Text className="profile-record-title">批发身份</Text>
          <Text className="profile-status-pill status-pending-pay">未申请</Text>
        </View>
        <Text className="profile-record-copy">补充门店资料和营业执照后，店里审核通过即可查看批发权益。</Text>
        <View className="profile-panel-action secondary" onClick={() => navigateView('wholesale')}>申请批发身份</View>
      </View>
    )
  }

  const renderSettings = () => (
    <View className="profile-form-card">
      <View className="profile-avatar-setting">
        <View className="profile-avatar large" onClick={() => chooseAndUploadImage(setAvatarUrl)}>
          {avatarUrl ? <Image className="profile-avatar-image" src={avatarUrl} mode="aspectFill" /> : defaultAvatarText}
        </View>
        <View>
          <Text className="profile-record-title">头像</Text>
          <Text className="profile-record-copy">点击头像可重新上传</Text>
        </View>
      </View>
      <View className="profile-input-row">
        <Text>昵称</Text>
        <Input value={nickname} maxLength={20} placeholder="请输入昵称" onInput={(event) => setNickname(String(event.detail.value || ''))} />
      </View>
      <View className="profile-switch-row">
        <Text>手机号</Text>
        <Text className="profile-readonly-value">{maskedPhone}</Text>
      </View>
      {renderWholesaleStatusCard()}
      <View
        className="profile-primary-button"
        onClick={async () => {
          const nextNickname = nickname.trim()
          if (!nextNickname || nextNickname.length > 20 || !NICKNAME_PATTERN.test(nextNickname)) {
            Taro.showToast({ title: '昵称限20字，仅支持中英文', icon: 'none' })
            return
          }
          try {
            const saved = await updateCustomerMe({ display_name: nextNickname, avatar_url: avatarUrl || null })
            setNickname(saved.display_name || nextNickname)
            setAvatarUrl(resolveMediaUrl(saved.avatar_url))
            Taro.showToast({ title: '资料已保存', icon: 'success' })
          } catch (error) {
            Taro.showToast({ title: error instanceof Error ? error.message : '资料保存失败', icon: 'none' })
          }
        }}
      >
        保存资料
      </View>
    </View>
  )

  const renderNotificationSettings = () => (
    <View className="profile-form-card">
      <View className="profile-subscribe-card standalone">
        <View>
          <Text className="profile-record-title">微信服务通知</Text>
          <Text className="profile-record-copy">开启后，下单、发货、订单完成和售后进度会尝试通过微信服务通知提醒你。</Text>
          <Text className="profile-record-copy">微信小程序必须由用户主动授权，单次最多申请 3 个模板；如果换了模板，需要重新点一次申请授权。</Text>
        </View>
        <View className="profile-subscribe-actions">
          <View
            className={`profile-subscribe-toggle ${subscribeEnabled ? 'active' : ''}`}
            onClick={() => updateSubscribeSetting(!subscribeEnabled)}
          >
            {subscribeEnabled ? '已开启' : '已关闭'}
          </View>
          <View className="profile-panel-action secondary inline" onClick={() => updateSubscribeSetting(true, true)}>
            申请授权
          </View>
        </View>
      </View>
    </View>
  )

  const renderNotificationSettingsV2 = () => {
    const selectedEvents = subscribeEvents.filter((event) => subscribeEventKeys.includes(event.key))
    return (
      <View className="profile-form-card">
        <View className="profile-subscribe-card standalone">
          <View className="profile-record-head">
            <View>
              <Text className="profile-record-title">微信服务通知</Text>
              <Text className="profile-record-copy">
                后端当前配置 {subscribeEvents.length} 种通知，已选择 {selectedEvents.length} 种。微信订阅消息需要用户主动授权，单次最多申请 3 个模板。
              </Text>
            </View>
            <View
              className="profile-subscribe-switch-wrap"
              onClick={() => {
                const nextEnabled = !subscribeEnabled
                const nextKeys = nextEnabled && subscribeEventKeys.length === 0
                  ? subscribeEvents.map((event) => event.key)
                  : subscribeEventKeys
                updateSubscribeSetting(nextEnabled, nextEnabled, nextKeys)
              }}
            >
              <Text className="profile-subscribe-switch-label">{subscribeEnabled ? '已开启' : '已关闭'}</Text>
              <View className={`profile-ios-switch ${subscribeEnabled ? 'active' : ''}`}>
                <View className="profile-ios-switch-thumb" />
              </View>
            </View>
          </View>

          <View className="profile-subscribe-list">
            {subscribeEvents.map((event) => {
              const checked = subscribeEventKeys.includes(event.key)
              const active = subscribeEnabled && checked
              return (
                <View
                  key={event.key}
                  className={`profile-subscribe-row ${subscribeEnabled ? '' : 'disabled'}`}
                  onClick={() => {
                    if (!subscribeEnabled) {
                      Taro.showToast({ title: '请先开启总开关', icon: 'none' })
                      return
                    }
                    toggleSubscribeEvent(event.key)
                  }}
                >
                  <View>
                    <Text className="profile-record-title">{event.label}</Text>
                    <Text className="profile-record-copy">{event.desc || event.key}</Text>
                  </View>
                  <View className={`profile-ios-switch small ${active ? 'active' : ''}`}>
                    <View className="profile-ios-switch-thumb" />
                  </View>
                </View>
              )
            })}
          </View>

        </View>
      </View>
    )
  }

  const renderContent = () => {
    if (view === 'notifications') return renderNotifications()
    if (view === 'notificationSettings') return renderNotificationSettingsV2()
    if (view === 'orders') return renderOrders()
    if (view === 'orderDetail') return renderOrderDetail()
    if (view === 'addresses') return renderAddresses()
    if (view === 'addressEdit') return renderAddressEdit()
    if (view === 'wholesale') return renderWholesale()
    if (view === 'aftersale') return renderAfterSale()
    if (view === 'aftersaleApply') return renderAfterSaleApply()
    if (view === 'favorites') return renderFavorites()
    if (view === 'service') return renderService()
    if (view === 'settings') return renderSettings()
    return renderHome()
  }


  return (
    <View className={`profile-page safe-page ${view !== 'home' ? 'is-subview' : ''}`} style={getSafeVars()}>
      <WholesaleWatermark />
      {renderTopBar()}
      {renderContent()}
      {view === 'home' && <View className="tabbar-backdrop" />}

      {view === 'home' && (
        <View className="profile-tabbar">
          <View className="profile-tab-item" onClick={() => Taro.redirectTo({ url: '/pages/home/index' })}>
            <Icon className="profile-tab-icon" name="shop-o" size="36rpx" />
            <Text className="profile-tab-label">选购</Text>
          </View>
          <View className="profile-tab-item" onClick={() => Taro.redirectTo({ url: '/pages/cart/index' })}>
            <Icon className="profile-tab-icon" name="shopping-cart-o" size="36rpx" />
            <Text className="profile-tab-label">清单</Text>
            {cart.count > 0 && <Text className="profile-tab-badge">{cart.count}</Text>}
          </View>
          <View className="profile-tab-item active">
            <Icon className="profile-tab-icon" name="user-o" size="36rpx" />
            <Text className="profile-tab-label">个人</Text>
            {unreadCount > 0 && <Text className="profile-tab-dot" />}
          </View>
        </View>
      )}

      <ProductDetailSheet
        show={Boolean(selectedFavoriteProduct)}
        product={selectedFavoriteProduct}
        showWholesaleWatermark
        onClose={() => setSelectedFavoriteProduct(null)}
        onFavoriteChange={(product, favorited) => {
          setSelectedFavoriteProduct((current) => (current?.id === product.id ? { ...current, isFavorited: favorited } : current))
          if (!favorited) {
            setFavorites((current) => current.filter((item) => (
              item.product_id !== product.backendId && String(item.product_id) !== product.id
            )))
          }
        }}
      />
    </View>
  )
}
