import { http } from '../services/http'

export type CartItem = {
  product_id: number
  sku_id: number
  sku_type: string
  product_name: string
  sku_code: string
  spec_value_1?: string | null
  spec_value_2?: string | null
  quantity: number
  online_stock: number
  retail_price: string | number
  wholesale_price?: string | number | null
  min_sale_qty: number
  min_wholesale_qty: number
  selected: boolean
  delisted: boolean
  product_image_url?: string | null
}

export type BatchSyncCartItem = {
  sku_id: number
  quantity: number
  selected: boolean
}

export type BatchSyncCartIssue = {
  sku_id?: number | null
  product_name?: string | null
  reason: string
}

export type BatchSyncCartResult = {
  synced_count: number
  removed_count: number
  cart_items: CartItem[]
  issues: BatchSyncCartIssue[]
}

export function fetchCart() {
  return http.get<CartItem[]>('/customer/cart')
}

export function upsertCartItem(skuId: number | string, payload: { quantity: number; selected: boolean }) {
  return http.put<CartItem>(`/customer/cart/items/${skuId}`, payload)
}

export function batchSyncCart(payload: { items: BatchSyncCartItem[]; replace_existing?: boolean }) {
  return http.post<BatchSyncCartResult>('/customer/cart/batch-sync', payload)
}

export function removeCartItem(skuId: number | string) {
  return http.delete<{ removed: number }>(`/customer/cart/items/${skuId}`)
}

export function clearCart() {
  return http.delete<{ cleared: number }>('/customer/cart/clear')
}
