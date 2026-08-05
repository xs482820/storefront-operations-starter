import { useEffect, useMemo, useState } from 'react'
import Taro, { useDidShow } from '@tarojs/taro'
import { Image, Input, ScrollView, Text, View } from '@tarojs/components'
import { fetchEmployeeCustomers, type EmployeeCustomer } from '../../api/employee'
import { BackButton } from '../../components/BackButton'
import { resolveMediaUrl } from '../../services/http'
import { getSafeStyle } from '../../utils/safeArea'
import { EmployeeWatermark } from '../../components/EmployeeWatermark'
import './index.scss'

function customerName(item: EmployeeCustomer) {
  return item.display_name || item.contact_name || item.store_name || item.username
}

export default function CustomerPage() {
  const [items, setItems] = useState<EmployeeCustomer[]>([])
  const [keyword, setKeyword] = useState('')
  const [error, setError] = useState('')
  const [customerFilter, setCustomerFilter] = useState<'all' | 'retail' | 'wholesale' | 'flagged' | 'inactive'>('all')

  const load = () => fetchEmployeeCustomers()
    .then((data) => { setItems(data); setError('') })
    .catch((reason) => setError(reason instanceof Error ? reason.message : '客户加载失败'))

  useEffect(() => { void load() }, [])
  useDidShow(() => { void load() })

  const visible = useMemo(() => {
    const value = keyword.trim().toLowerCase()
    return items.filter((item) => (
      (!value || [customerName(item), item.phone, item.username, item.store_name, item.company_name].some((field) => String(field || '').toLowerCase().includes(value)))
      && (customerFilter === 'all'
        || (customerFilter === 'retail' && !item.is_verified_wholesale)
        || (customerFilter === 'wholesale' && item.is_verified_wholesale)
        || (customerFilter === 'flagged' && (item.is_flagged || item.is_blacklisted))
        || (customerFilter === 'inactive' && !item.is_active))
    ))
  }, [items, keyword, customerFilter])

  return (
    <View className="page customer-page" style={getSafeStyle()}>
      <EmployeeWatermark />
      <BackButton />
      <View className="page-title">
        <View>
          <Text className="page-title-main">客户</Text>
          <Text className="page-title-sub">仅查看资料与交易概况</Text>
        </View>
        <Text className="workbench-refresh" onClick={load}>刷新</Text>
      </View>
      <Input className="customer-search card" value={keyword} placeholder="搜索姓名、门店、手机号或账号" onInput={(event) => setKeyword(event.detail.value)} />
      <ScrollView className="customer-filters" scrollX enhanced showScrollbar={false}><View className="customer-filter-row"><Text className={'customer-filter ' + (customerFilter === 'all' ? 'active' : '')} onClick={() => setCustomerFilter('all')}>全部</Text><Text className={'customer-filter ' + (customerFilter === 'retail' ? 'active' : '')} onClick={() => setCustomerFilter('retail')}>零售</Text><Text className={'customer-filter ' + (customerFilter === 'wholesale' ? 'active' : '')} onClick={() => setCustomerFilter('wholesale')}>批发</Text><Text className={'customer-filter ' + (customerFilter === 'flagged' ? 'active' : '')} onClick={() => setCustomerFilter('flagged')}>已标记</Text><Text className={'customer-filter ' + (customerFilter === 'inactive' ? 'active' : '')} onClick={() => setCustomerFilter('inactive')}>已停用</Text></View></ScrollView>
      {error && <Text className="customer-error">{error}</Text>}
      {visible.map((item) => (
        <View key={item.id} className="customer-card card" onClick={() => Taro.navigateTo({ url: `/pages/customerDetail/index?id=${item.id}` })}>
          <View className="customer-avatar">
            {item.avatar_url ? <Image src={resolveMediaUrl(item.avatar_url)} mode="aspectFill" /> : <Text>{customerName(item).slice(0, 1)}</Text>}
          </View>
          <View className="customer-main">
            <View className="customer-name-row"><Text className="customer-name">{customerName(item)}</Text><Text className={`customer-role ${item.role}`}>{item.is_verified_wholesale ? '批发' : '零售'}</Text></View>
            <Text className="customer-meta">{item.phone || '未留手机号'} · {item.order_count} 笔订单 · ¥{item.order_amount}</Text>
            {(item.store_name || item.company_name) && <Text className="customer-meta">{item.store_name || item.company_name}</Text>}
          </View>
        </View>
      ))}
      {!error && visible.length === 0 && <View className="customer-empty card"><Text>暂无匹配客户</Text></View>}
    </View>
  )
}
