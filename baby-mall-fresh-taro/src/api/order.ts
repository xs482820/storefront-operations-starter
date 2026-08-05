import { http } from '../services/http'

export type OrderStatus = 'pending_payment' | 'paid' | 'picking' | 'awaiting_shipment' | 'shipped' | 'completed' | 'canceled' | 'deleted'
export type PaymentMethod = 'wechat_pay' | 'offline_transfer'
export type PricingMode = 'retail' | 'wholesale'
export type ShippingChannel = 'delivery' | 'pickup'

export type OrderItemInput = {
  sku_id: number
  quantity: number
}

export type CheckoutPayload = {
  items: OrderItemInput[]
  shipping_channel?: ShippingChannel | string
  pricing_mode?: PricingMode
  payment_method?: PaymentMethod
  shipping_recipient?: string | null
  shipping_phone?: string | null
  shipping_province?: string | null
  shipping_city?: string | null
  shipping_district?: string | null
  shipping_address?: string | null
  note?: string | null
  cancellation_reason?: string | null
  cancellation_source?: string | null
  termination_reason?: string | null
  termination_reason?: string | null
  termination_disposition?: string | null
}

export type CheckoutPreviewItem = {
  product_id: number
  sku_id: number
  product_name: string
  sku_code: string
  sku_type: string
  spec_value_1?: string | null
  spec_value_2?: string | null
  quantity: number
  unit_price: string | number
  line_amount: string | number
  online_stock: number
  min_required_qty: number
  product_image_url?: string | null
}

export type CheckoutPreview = {
  buyer_role: string
  pricing_mode: string
  shipping_channel: string
  payment_method: string
  merchandise_amount: string | number
  shipping_fee: string | number
  payable_amount: string | number
  free_shipping_threshold: string | number
  shortfall_to_free_shipping: string | number
  can_submit: boolean
  issues: string[]
  items: CheckoutPreviewItem[]
}

export type CustomerOrderItem = {
  product_id?: number | null
  sku_id: number
  product_name: string
  sku_code: string
  sku_type: string
  spec_value_1?: string | null
  spec_value_2?: string | null
  product_image_url?: string | null
  quantity: number
  unit_price: string | number
  line_amount: string | number
}

export type CustomerOrder = {
  order_id: number
  order_no: string
  status: OrderStatus
  buyer_role: string
  original_amount: string | number
  shipping_fee: string | number
  payable_amount: string | number
  payment_method: PaymentMethod | string
  shipping_mode?: string | null
  shipping_proof_url?: string | null
  shipping_recipient?: string | null
  shipping_phone?: string | null
  shipping_address?: string | null
  note?: string | null
  created_at: string
  paid_at?: string | null
  shipped_at?: string | null
  delivery_signed_at?: string | null
  completed_at?: string | null
  canceled_at?: string | null
  terminated_at?: string | null
  items: CustomerOrderItem[]
  can_cancel: boolean
  can_confirm_receipt: boolean
  can_aftersale: boolean
  can_delete: boolean
}

export function previewCheckout(payload: CheckoutPayload) {
  return http.post<CheckoutPreview>('/customer/checkout/preview', payload)
}

export function createOrder(payload: CheckoutPayload) {
  return http.post<CustomerOrder>('/customer/orders', payload)
}

export function fetchOrders() {
  return http.get<CustomerOrder[]>('/customer/orders')
}

export function fetchOrder(orderId: number | string) {
  return http.get<CustomerOrder>(`/customer/orders/${orderId}`)
}

export function cancelOrder(orderId: number | string) {
  return http.post<{ order_id: number; order_no: string; status: OrderStatus }>(`/customer/orders/${orderId}/cancel`)
}

export function deleteOrder(orderId: number | string) {
  return http.delete<{ order_id: number; order_no: string; status: OrderStatus; deleted_at?: string | null }>(`/customer/orders/${orderId}`)
}

export function confirmReceipt(orderId: number | string) {
  return http.post<CustomerOrder>(`/customer/orders/${orderId}/confirm-receipt`)
}
