import { type CustomerProduct, type ProductSku } from '../api/catalog'
import { type CartItem as ApiCartItem } from '../api/cart'
import { type CustomerAddress } from '../api/address'
import { type CustomerOrder, type OrderStatus as ApiOrderStatus } from '../api/order'
import { type Product, type ProductSkuOption } from '../mock/catalog'
import { type Order, type OrderEvent, type OrderStatus } from '../store/useCommerce'
import { type CartItem } from '../store/useCart'
import { resolveMediaUrl } from '../services/http'

const toneCycle: Product['tone'][] = ['mint', 'cream', 'peach', 'blue', 'lilac']

export const apiOrderStatusText: Record<ApiOrderStatus, OrderStatus> = {
  pending_payment: '待支付',
  paid: '待发货',
  picking: '待发货',
  awaiting_shipment: '待发货',
  shipped: '已发货',
  completed: '已完成',
  canceled: '已取消',
  deleted: '已取消',
}

export const orderStatusToApi: Record<OrderStatus, ApiOrderStatus> = {
  待支付: 'pending_payment',
  待发货: 'awaiting_shipment',
  已发货: 'shipped',
  已完成: 'completed',
  已取消: 'canceled',
}

function toNumber(value: string | number | null | undefined, fallback = 0) {
  const next = Number(value)
  return Number.isFinite(next) ? next : fallback
}

function effectivePrice(retail: string | number | null | undefined, wholesale?: string | number | null) {
  if (wholesale !== null && wholesale !== undefined && String(wholesale).trim() !== '') {
    return toNumber(wholesale)
  }
  return toNumber(retail)
}

function skuPrice(sku: ProductSku) {
  return effectivePrice(sku.retail_price, sku.wholesale_price)
}

function skuMinQty(sku: Pick<ProductSku, 'sku_type' | 'min_sale_qty' | 'min_wholesale_qty'>) {
  const minQty = sku.sku_type === 'wholesale' ? sku.min_wholesale_qty : sku.min_sale_qty
  return Math.max(1, minQty || 1)
}

function textOrFallback(value: string | null | undefined, fallback: string) {
  const next = String(value || '').trim()
  return next || fallback
}

function productDisplayPrice(skus: ProductSkuOption[]) {
  if (skus.length === 0) return 0
  return Math.min(...skus.map((sku) => sku.price))
}

function skuTypeLabel(value?: string | null) {
  if (value === 'retail') return '零售'
  if (value === 'wholesale') return '批发'
  return value || '现货'
}

export function adaptCustomerProduct(product: CustomerProduct, index = 0): Product {
  const skus: ProductSkuOption[] = product.skus.map((sku) => ({
    skuId: sku.sku_id,
    code: sku.sku_code,
    color: textOrFallback(sku.spec_value_1, textOrFallback(sku.sku_label, '默认')),
    size: textOrFallback(sku.spec_value_2, '默认'),
    price: skuPrice(sku),
    stock: sku.online_stock,
    minQty: skuMinQty(sku),
  }))
  const colors = Array.from(new Set(skus.map((sku) => sku.color)))
  const sizes = Array.from(new Set(skus.map((sku) => sku.size)))
  const firstSku = skus[0]
  const firstApiSku = product.skus[0]
  const displayPrice = productDisplayPrice(skus)

  return {
    id: String(product.product_id),
    backendId: product.product_id,
    categoryId: product.category || 'all',
    name: product.name,
    subtitle: product.description || product.model_name || product.brand || '商品详情待补充',
    price: displayPrice,
    imageUrl: resolveMediaUrl(product.image_urls?.[0]) || undefined,
    badge: skuTypeLabel(firstApiSku?.sku_type),
    tone: toneCycle[index % toneCycle.length],
    stock: firstSku ? `库存 ${skus.reduce((sum, sku) => sum + sku.stock, 0)} 件` : '库存待同步',
    colors: colors.length ? colors : ['默认'],
    sizes: sizes.length ? sizes : ['默认'],
    skus,
    isFavorited: product.is_favorited,
  }
}

export function findProductSku(product: Product, color = '默认', size = '默认') {
  return product.skus?.find((sku) => sku.color === color && sku.size === size)
}

export function adaptCartItem(item: ApiCartItem): CartItem {
  const price = effectivePrice(item.retail_price, item.wholesale_price)
  const color = textOrFallback(item.spec_value_1, '默认')
  const size = textOrFallback(item.spec_value_2, '默认')
  const product: Product = {
    id: String(item.product_id),
    backendId: item.product_id,
    categoryId: 'cart',
    name: item.product_name,
    subtitle: item.sku_code,
    price,
    imageUrl: resolveMediaUrl(item.product_image_url) || undefined,
    badge: skuTypeLabel(item.sku_type),
    tone: 'mint',
    stock: item.delisted ? '已下架' : `库存 ${item.online_stock} 件`,
    colors: [color],
    sizes: [size],
    skus: [{
      skuId: item.sku_id,
      code: item.sku_code,
      color,
      size,
      price,
      stock: item.online_stock,
      minQty: skuMinQty(item),
    }],
  }
  return {
    key: `sku__${item.sku_id}`,
    product,
    productId: String(item.product_id),
    skuId: item.sku_id,
    color,
    size,
    quantity: item.quantity,
    unitPrice: price,
  }
}

export function adaptAddress(address: CustomerAddress) {
  return {
    id: String(address.id),
    backendId: address.id,
    name: address.contact_name,
    phone: address.phone,
    region: address.region,
    detail: address.detail,
    isDefault: address.is_default,
  }
}

function orderEventsFromApi(order: CustomerOrder): OrderEvent[] {
  const events: OrderEvent[] = []
  if (order.completed_at) events.push({ time: order.completed_at, title: '订单已完成', body: '本次采购已完成。' })
  if (order.terminated_at) events.push({ time: order.terminated_at, title: '订单已终止', body: order.termination_reason || '订单已按沟通结果终止。' })
  if (order.canceled_at && !order.terminated_at) {
    const source = order.cancellation_source
    const title = source === 'auto_timeout' ? '超时自动取消' : source === 'customer' ? '客户手动取消' : source === 'staff' ? '店内手动取消' : '订单已取消'
    const fallback = source === 'auto_timeout' ? '订单未在支付时限内完成付款。' : '订单已取消。'
    const reason = order.cancellation_reason === 'payment timeout' ? fallback : order.cancellation_reason
    events.push({ time: order.canceled_at, title, body: reason || fallback })
  }
  if (order.delivery_signed_at) events.push({ time: order.delivery_signed_at, title: '已确认收货', body: '收货信息已确认。' })
  if (order.shipped_at) events.push({ time: order.shipped_at, title: '订单已发货', body: '商品已出库，请留意收货。' })
  if (order.paid_at) events.push({ time: order.paid_at, title: '支付成功', body: '订单已支付，等待商家处理。' })
  events.push({ time: order.created_at, title: '订单已创建', body: order.status === 'pending_payment' ? '等待继续支付。' : '订单已提交。' })
  return events
}

export function adaptCustomerOrder(order: CustomerOrder): Order {
  const status = apiOrderStatusText[order.status] || '待支付'
  return {
    id: order.order_no || String(order.order_id),
    backendId: order.order_id,
    status,
    amount: toNumber(order.payable_amount),
    merchandiseAmount: toNumber(order.original_amount),
    shippingFee: toNumber(order.shipping_fee),
    paymentMethod: order.payment_method,
    shippingMode: order.shipping_mode || undefined,
    shippingProofUrl: resolveMediaUrl(order.shipping_proof_url) || undefined,
    count: order.items.reduce((sum, item) => sum + item.quantity, 0),
    date: String(order.created_at || '').slice(5, 10) || '',
    note: order.items.slice(0, 2).map((item) => item.product_name).join('、') || '采购清单',
    remark: order.note || '',
    address: {
      id: 'order-address',
      name: order.shipping_recipient || '',
      phone: order.shipping_phone || '',
      region: '',
      detail: order.shipping_address || '',
      isDefault: false,
    },
    lines: order.items.map((item) => ({
      key: String(item.sku_id),
      productId: String(item.product_id || item.sku_id),
      skuId: item.sku_id,
      color: textOrFallback(item.spec_value_1, '默认'),
      size: textOrFallback(item.spec_value_2, '默认'),
      quantity: item.quantity,
      product: {
        id: String(item.product_id || item.sku_id),
        backendId: item.product_id || undefined,
        categoryId: 'order',
        name: item.product_name,
        subtitle: item.sku_code,
        price: toNumber(item.unit_price),
        imageUrl: resolveMediaUrl(item.product_image_url) || undefined,
        badge: skuTypeLabel(item.sku_type),
        tone: 'mint',
        stock: '',
        colors: [textOrFallback(item.spec_value_1, '默认')],
        sizes: [textOrFallback(item.spec_value_2, '默认')],
      },
    })),
    paidAt: order.paid_at || undefined,
    shippedAt: order.shipped_at || undefined,
    signedAt: order.delivery_signed_at || undefined,
    completedAt: order.completed_at || undefined,
    canceledAt: order.canceled_at || undefined,
    canCancel: order.can_cancel,
    canConfirmReceipt: order.can_confirm_receipt,
    canAfterSale: order.can_aftersale,
    canDelete: order.can_delete,
    events: orderEventsFromApi(order),
  }
}
