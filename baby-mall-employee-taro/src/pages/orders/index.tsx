import { useEffect, useMemo, useState } from 'react'
import Taro, { useDidShow, useRouter } from '@tarojs/taro'
import { Input, Text, View } from '@tarojs/components'
import { BackButton } from '../../components/BackButton'
import { fetchEmployeeOrders, type EmployeeOrder } from '../../api/employee'
import { EmployeeOrderCard } from '../../components/EmployeeOrderCard'
import { EmployeeWatermark } from '../../components/EmployeeWatermark'
import { getSafeStyle } from '../../utils/safeArea'
import './index.scss'

const tabs = [
  { key: '', label: '全部' },
  { key: 'pending_payment', label: '待支付' },
  { key: 'awaiting_shipment', label: '待发货' },
  { key: 'shipped', label: '已发货' },
  { key: 'completed', label: '已完成' },
  { key: 'canceled', label: '已取消' },
]
const ORDER_CHANGED_EVENT = 'employee:orders-changed'

export default function OrdersPage() {
  const router = useRouter()
  const [active, setActive] = useState(String(router.params.status || ''))
  const [keyword, setKeyword] = useState('')
  const [orders, setOrders] = useState<EmployeeOrder[]>([])
  const [error, setError] = useState('')

  const load = () => fetchEmployeeOrders()
    .then((data) => { setOrders(data); setError('') })
    .catch((reason) => setError(reason instanceof Error ? reason.message : '订单加载失败'))

  useEffect(() => {
    const reload = () => { void load() }
    Taro.eventCenter.on(ORDER_CHANGED_EVENT, reload)
    return () => Taro.eventCenter.off(ORDER_CHANGED_EVENT, reload)
  }, [])

  useDidShow(() => { void load() })

  const visible = useMemo(() => orders.filter((order) => (
    (!active || order.status === active) &&
    (order.order_no + order.customer_name + (order.customer_phone || '')).toLowerCase().includes(keyword.toLowerCase())
  )), [active, keyword, orders])

  return (
    <View className="page orders-page" style={getSafeStyle()}>
      <EmployeeWatermark />
      <View className="page-title">
        <View className="page-title-leading">
          <BackButton />
          <View>
            <Text className="page-title-main">订单</Text>
            <Text className="page-title-sub">发货、签收与订单备注</Text>
          </View>
        </View>
        <Text className="workbench-refresh" onClick={load}>刷新列表</Text>
      </View>
      <Input className="order-search" value={keyword} placeholder="订单号、客户名或手机号" onInput={(event) => setKeyword(event.detail.value)} />
      <View className="tab-row">{tabs.map((tab) => <Text key={tab.key} className={'tab ' + (active === tab.key ? 'tab--active' : '')} onClick={() => setActive(tab.key)}>{tab.label}</Text>)}</View>
      {error && <Text className="orders-error">{error}</Text>}
      {visible.map((order) => <EmployeeOrderCard key={order.id} order={order} onClick={() => Taro.navigateTo({ url: '/pages/orderDetail/index?id=' + order.id })} />)}
    </View>
  )
}
