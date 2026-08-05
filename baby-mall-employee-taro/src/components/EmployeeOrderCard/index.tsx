import { Image, Text, View } from '@tarojs/components'
import { type EmployeeOrder } from '../../api/employee'
import { resolveMediaUrl } from '../../services/http'
import './index.scss'

const statusText: Record<string, string> = {
  pending_payment: '待支付',
  paid: '已付款',
  awaiting_shipment: '待发货',
  shipped: '已发货',
  completed: '已完成',
  canceled: '已取消',
}

function productSummary(order: EmployeeOrder) {
  const names = order.lines.slice(0, 2).map((line) => `${line.product_name} ×${line.quantity}`).join('、')
  return order.item_count > 2 ? `${names} 等${order.item_count}件` : names || '商品明细待同步'
}

export function EmployeeOrderCard({ order, onClick }: { order: EmployeeOrder; onClick: () => void }) {
  return (
    <View className="employee-order-card" onClick={onClick}>
      <View className="employee-order-head">
        <Text className="employee-order-no">{order.order_no}</Text>
        <Text className={`employee-order-status ${order.status}`}>{statusText[order.status] || order.status}</Text>
      </View>
      <Text className="employee-order-customer">{order.customer_name} · {order.customer_phone || '未留电话'}</Text>
      <View className="employee-order-products">
        <View className="employee-order-thumbs">
          {order.lines.slice(0, 3).map((line, index) => (
            <View key={`${line.product_name}-${index}`} className="employee-order-thumb">
              {line.image_url && <Image src={resolveMediaUrl(line.image_url)} mode="aspectFill" />}
            </View>
          ))}
        </View>
        <Text className="employee-order-summary">{productSummary(order)}</Text>
      </View>
      <View className="employee-order-foot">
        <Text className="employee-order-amount">¥{order.payable_amount}</Text>
        <Text className="employee-order-time">{new Date(order.created_at).toLocaleString()}</Text>
      </View>
    </View>
  )
}
