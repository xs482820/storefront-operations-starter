import { useEffect, useState } from 'react'
import Taro, { useRouter } from '@tarojs/taro'
import { Image, Text, View } from '@tarojs/components'
import { fetchEmployeeCustomerDetail, type EmployeeCustomerDetail } from '../../api/employee'
import { BackButton } from '../../components/BackButton'
import { CopyIcon } from '../../components/CopyIcon'
import { resolveMediaUrl } from '../../services/http'
import { getSafeStyle } from '../../utils/safeArea'
import { EmployeeWatermark } from '../../components/EmployeeWatermark'
import './index.scss'

export default function CustomerDetailPage() {
  const router = useRouter()
  const customerId = Number(router.params.id || 0)
  const [item, setItem] = useState<EmployeeCustomerDetail | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!customerId) return
    fetchEmployeeCustomerDetail(customerId).then(setItem).catch((reason) => setError(reason instanceof Error ? reason.message : '客户资料加载失败'))
  }, [customerId])

  if (error) return <View className="page customer-detail-page" style={getSafeStyle()}><EmployeeWatermark /><BackButton fallbackUrl="/pages/customer/index" /><Text className="customer-detail-error">{error}</Text></View>
  if (!item) return <View className="page customer-detail-page" style={getSafeStyle()}><EmployeeWatermark /><BackButton fallbackUrl="/pages/customer/index" /><Text className="customer-detail-loading">正在加载客户资料</Text></View>
  const name = item.display_name || item.contact_name || item.store_name || item.username

  return <View className="page customer-detail-page" style={getSafeStyle()}>
    <EmployeeWatermark />
    <BackButton fallbackUrl="/pages/customer/index" />
    <View className="page-title"><View><Text className="page-title-main">客户资料</Text><Text className="page-title-sub">只读资料与交易概况</Text></View></View>
    <View className="customer-profile-card card">
      <View className="customer-detail-avatar">{item.avatar_url ? <Image src={resolveMediaUrl(item.avatar_url)} mode="aspectFill" /> : <Text>{name.slice(0, 1)}</Text>}</View>
      <View><Text className="customer-detail-name">{name}</Text><View className="customer-detail-meta-row"><Text className="customer-detail-meta">{item.is_verified_wholesale ? '批发客户' : '零售客户'} · {item.phone || '未留手机号'}</Text>{item.phone && <CopyIcon value={item.phone} label="手机号" />}</View></View>
    </View>
    <View className="customer-runtime-grid"><View><Text>{item.orders.length}</Text><Text>订单</Text></View><View><Text>{item.aftersales.length}</Text><Text>售后</Text></View><View><Text>{item.favorite_count}</Text><Text>收藏</Text></View><View><Text>{item.cart_count}</Text><Text>清单</Text></View></View>
    <Text className="section-title">基础资料</Text>
    <View className="customer-detail-card card"><View className="customer-detail-copy-line"><Text>账号：{item.username}</Text><CopyIcon value={item.username} label="账号" /></View><View className="customer-detail-copy-line"><Text>门店：{item.store_name || item.company_name || '未填写'}</Text><CopyIcon value={item.store_name || item.company_name} label="门店" /></View><View className="customer-detail-copy-line"><Text>联系人：{item.contact_name || '未填写'}</Text><CopyIcon value={item.contact_name} label="联系人" /></View><View className="customer-detail-copy-line"><Text>资料地址：{item.address || '未填写'}</Text><CopyIcon value={item.address} label="资料地址" /></View><Text>状态：{item.is_active ? '正常' : '已停用'}{item.is_flagged ? ' · 已标记' : ''}{item.is_blacklisted ? ' · 黑名单' : ''}</Text>{item.note && <Text>备注：{item.note}</Text>}{item.business_license_url && <Image className="customer-detail-license" src={resolveMediaUrl(item.business_license_url)} mode="aspectFill" onClick={() => { const url = resolveMediaUrl(item.business_license_url); Taro.previewImage({ current: url, urls: [url] }) }} />}</View>
    <Text className="section-title">收货地址</Text>
    <View className="customer-detail-card card">{item.addresses.length ? item.addresses.map((address) => <View className="customer-detail-copy-line" key={address.id}><Text>{address.is_default ? '默认 · ' : ''}{address.tag} · {address.contact_name} {address.phone} · {address.region}{address.detail}</Text><CopyIcon value={`${address.contact_name} ${address.phone} ${address.region}${address.detail}`} label="地址" /></View>) : <Text>暂无地址</Text>}</View>
    <Text className="section-title">最近订单</Text>
    <View className="customer-detail-card card">{item.orders.length ? item.orders.slice(0, 5).map((order) => <View className="customer-detail-copy-line" key={order.id}><Text>{order.order_no} · {order.status} · ¥{order.amount}</Text><CopyIcon value={order.order_no} label="订单号" /></View>) : <Text>暂无订单</Text>}</View>
    <Text className="section-title">售后记录</Text>
    <View className="customer-detail-card card">{item.aftersales.length ? item.aftersales.slice(0, 5).map((record) => <View className="customer-detail-copy-line" key={record.id}><Text>AS{record.id} · {record.order_no || '订单待同步'} · {record.reason} · {record.status}</Text><CopyIcon value={`AS${record.id}`} label="售后单号" /></View>) : <Text>暂无售后</Text>}</View>
  </View>
}
