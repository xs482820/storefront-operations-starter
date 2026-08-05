import { http } from '../services/http'

export type StorefrontConfig = {
  home_banners?: Array<{
    title?: string
    name?: string
    image_url: string
    description?: string
    link_type: string
    link_value: string
    sort_order: number
    is_active: boolean
  }>
  store_info?: {
    name?: string
    phone?: string
    address?: string
    pickup_note?: string
  }
  customer_service?: {
    wechat_id?: string
    wechat_qr_url?: string
  }
  shipping_thresholds?: {
    retail?: string
    wholesale?: string
  }
  shipping_rules?: {
    retail?: Record<string, string>
    wholesale?: Record<string, string>
  }
  watermark?: {
    enabled?: boolean
    customer_enabled?: boolean
    employee_enabled?: boolean
    opacity?: number
    density?: number
    angle?: number
  }
  search_suggestions?: string[]
  marquee_notices?: Array<{
    id: number
    title: string
    body: string
    action_label: string
    action_type: string
    action_value?: string | null
  }>
  updated_at?: string | null
}

export type CustomerCategory = {
  id?: number
  code: string
  name: string
  product_count?: number
}

export type ProductSku = {
  sku_id: number
  sku_code: string
  sku_type: 'retail' | 'wholesale' | string
  spec_value_1?: string | null
  spec_value_2?: string | null
  sku_label?: string | null
  online_stock: number
  retail_price: string | number
  wholesale_price?: string | number | null
  min_sale_qty: number
  min_wholesale_qty: number
  is_mixed_pack: boolean
  mixed_pack_note?: string | null
}

export type CustomerProduct = {
  product_id: number
  product_code: string
  name: string
  model_name?: string | null
  brand?: string | null
  category?: string | null
  description?: string | null
  image_urls: string[]
  spec_dim_1_name: string
  spec_dim_2_name: string
  skus: ProductSku[]
  is_favorited: boolean
}

export type ProductListParams = {
  keyword?: string
}

function toQuery(params: Record<string, string | number | undefined>) {
  const search = Object.entries(params)
    .filter(([, value]) => value !== undefined && String(value).trim() !== '')
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join('&')
  return search ? `?${search}` : ''
}

export function fetchStorefrontConfig() {
  return http.get<StorefrontConfig>('/customer/storefront-config', false)
}

export function fetchCategories() {
  return http.get<CustomerCategory[]>('/products/categories', false)
}

export function fetchSearchSuggestions() {
  return http.get<{ suggestions: string[] }>('/customer/storefront-search-suggestions', false)
}

export function fetchProducts(params: ProductListParams = {}) {
  return http.get<CustomerProduct[]>(`/customer/products${toQuery({ keyword: params.keyword })}`)
}

export function fetchProductDetail(productId: number | string) {
  return http.get<CustomerProduct>(`/customer/products/${productId}`)
}
