import { http } from '../services/http'

export type PaymentStatus = 'pending' | 'paid' | 'failed' | 'refunded'

export type WechatPayCreateOut = {
  payment_no: string
  order_no: string
  status: PaymentStatus | string
  amount: string
  prepay_id?: string | null
  jsapi_params?: Record<string, unknown> | null
  message: string
}

export type PaymentRecord = {
  payment_no: string
  order_no: string
  channel: string
  status: PaymentStatus
  amount: string
  openid?: string | null
  prepay_id?: string | null
  provider_txn_no?: string | null
  note?: string | null
  created_at: string
}

export function createCustomerWechatPay(orderId: number | string) {
  return http.post<WechatPayCreateOut>(`/customer/orders/${orderId}/wechat-pay`)
}

export function syncWechatPayment(orderId: number | string) {
  return http.post<PaymentRecord>('/payments/wechat/sync', { order_id: Number(orderId) })
}
