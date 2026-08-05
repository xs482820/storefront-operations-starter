import { useEffect, useMemo, useState } from 'react'
import Taro, { useDidShow } from '@tarojs/taro'
import { Input, Text, View } from '@tarojs/components'
import { fetchEmployeeOrders, fetchWorkbench, type EmployeeOrder, type WorkbenchSummary } from '../../api/employee'
import { EmployeeOrderCard } from '../../components/EmployeeOrderCard'
import { EmployeeWatermark } from '../../components/EmployeeWatermark'
import { getSafeStyle } from '../../utils/safeArea'
import './index.scss'

const emptySummary: WorkbenchSummary = {
  pending_payment_orders: 0,
  awaiting_shipment_orders: 0,
  shipped_orders: 0,
  pending_aftersales: 0,
  today_new_orders: 0,
  today_new_aftersales: 0,
}

const tabs = [
  { key: '', label: '全部' },
  { key: 'pending_payment', label: '待支付' },
  { key: 'awaiting_shipment', label: '待发货' },
  { key: 'shipped', label: '已发货' },
  { key: 'completed', label: '已完成' },
  { key: 'canceled', label: '已取消' },
]
const ORDER_CHANGED_EVENT = 'employee:orders-changed'

export default function WorkbenchPage() {
  const [summary, setSummary] = useState(emptySummary)
  const [orders, setOrders] = useState<EmployeeOrder[]>([])
  const [active, setActive] = useState('')
  const [keyword, setKeyword] = useState('')
  const [error, setError] = useState('')
  const [lastUpdated, setLastUpdated] = useState('')

  const load = () => Promise.all([fetchWorkbench(), fetchEmployeeOrders()])
    .then(([nextSummary, nextOrders]) => {
      setSummary(nextSummary)
      setOrders(nextOrders)
      setError('')
      setLastUpdated(new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }))
    })
    .catch((reason) => setError(reason instanceof Error ? reason.message : '工作台数据加载失败'))

  useEffect(() => {
    const reload = () => { void load() }
    Taro.eventCenter.on(ORDER_CHANGED_EVENT, reload)
    let refreshing = false
    const timer = setInterval(async () => {
      if (refreshing) return
      refreshing = true
      await load()
      refreshing = false
    }, 15000)
    return () => {
      Taro.eventCenter.off(ORDER_CHANGED_EVENT, reload)
      clearInterval(timer)
    }
  }, [])

  useDidShow(() => { void load() })

  const stats = [
    { label: '今日订单', value: summary.today_new_orders, tone: 'info' },
    { label: '待发货', value: summary.awaiting_shipment_orders, status: 'awaiting_shipment', tone: 'warning' },
    { label: '待售后', value: summary.pending_aftersales, url: '/pages/aftersale/index', tone: 'danger' },
  ]

  const visible = useMemo(() => orders.filter((order) => (
    (!active || order.status === active) &&
    (order.order_no + order.customer_name + (order.customer_phone || '')).toLowerCase().includes(keyword.toLowerCase())
  )), [active, keyword, orders])

  const activeLabel = active ? tabs.find((tab) => tab.key === active)?.label : '全部订单'

  return (
    <View className="page workbench-page" style={getSafeStyle()}>
      <EmployeeWatermark />
      <View className="page-title">
        <View><Text className="page-title-main">工作台</Text><Text className="workbench-refresh-time">{lastUpdated ? `自动更新 ${lastUpdated}` : '正在同步'}</Text></View>
        <Text className="workbench-refresh" onClick={load}>刷新</Text>
      </View>

      {error && <View className="workbench-error"><Text>{error}</Text><Text onClick={load}>重试</Text></View>}

      <View className="workbench-summary">
        {stats.map((item) => (
          <View key={item.label} className={'summary-item summary-item--' + item.tone} onClick={() => item.url ? Taro.navigateTo({ url: item.url }) : setActive(item.status || '')}>
            <Text className="summary-value">{item.value}</Text>
            <Text className="summary-label">{item.label}</Text>
          </View>
        ))}
      </View>

      <View className="workbench-tools card">
        <Text onClick={() => Taro.navigateTo({ url: '/pages/aftersale/index' })}>售后记录</Text>
        <Text onClick={() => Taro.navigateTo({ url: '/pages/customer/index' })}>客户</Text>
        <Text onClick={() => Taro.navigateTo({ url: '/pages/products/index' })}>商品</Text>
        <Text onClick={() => Taro.navigateTo({ url: '/pages/media/index' })}>图片准备</Text>
      </View>

      <Input className="order-search" value={keyword} placeholder="搜索订单号、客户或手机号" onInput={(event) => setKeyword(event.detail.value)} />

      <View className="tab-row">
        {tabs.map((tab) => <Text key={tab.key} className={'tab ' + (active === tab.key ? 'tab--active' : '')} onClick={() => setActive(tab.key)}>{tab.label}</Text>)}
      </View>

      <View className="section-head"><Text className="section-title">{activeLabel} · {visible.length}</Text></View>
      {visible.map((order) => <EmployeeOrderCard key={order.id} order={order} onClick={() => Taro.navigateTo({ url: '/pages/orderDetail/index?id=' + order.id })} />)}
    </View>
  )
}
