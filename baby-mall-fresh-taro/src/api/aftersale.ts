import { http } from '../services/http'

export type AfterSaleReason = 'quality_issue' | 'wrong_item' | 'damaged' | 'size_problem' | 'other'

export type AfterSaleInput = {
  order_id: number
  reason: AfterSaleReason
  requested_amount?: string | number | null
  custom_reason_text?: string | null
  chat_proof_url?: string | null
  note?: string | null
}

export type AfterSale = {
  id: number
  order_id: number
  order_no?: string | null
  reason: string
  custom_reason_text?: string | null
  process_type?: string | null
  refund_amount?: string | number | null
  chat_proof_url?: string | null
  status: 'pending' | 'resolved' | string
  note?: string | null
  created_at: string
}

export function createAfterSale(payload: AfterSaleInput) {
  return http.post<AfterSale>('/customer/aftersales', payload)
}

export function fetchAfterSales() {
  return http.get<AfterSale[]>('/customer/aftersales')
}
