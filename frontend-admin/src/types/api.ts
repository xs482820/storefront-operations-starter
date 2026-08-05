export interface AuthProfile {
  id: number
  username: string
  role: 'admin' | 'employee' | 'retail' | 'wholesale'
  display_name?: string | null
  avatar_url?: string | null
  phone?: string | null
  wechat_openid?: string | null
  wechat_bound: boolean
}

export interface LoginPayload {
  identifier: string
  username?: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user_id: number
  username: string
  role: AuthProfile['role']
}

export interface ProductListItem {
  id: number
  name: string
  model_name?: string | null
  product_code: string
  category?: string | null
  image_urls?: string[]
  supports_retail: boolean
  supports_wholesale: boolean
  has_dual_price?: boolean
  is_active: boolean
  sku_count: number
  total_online_stock?: number
  low_stock_sku_count?: number
  price_mode?: string
}

export interface ProductCategoryItem {
  id: number
  name: string
  sort_order: number
  is_active: boolean
  product_count: number
}

export interface ProductSkuItem {
  id: number
  sku_code: string
  sku_type: 'retail' | 'wholesale'
  spec_value_1?: string | null
  spec_value_2?: string | null
  sku_label?: string | null
  is_mixed_pack: boolean
  mixed_pack_note?: string | null
  online_stock: number
  retail_price: string
  wholesale_price: string
  min_sale_qty: number
  min_wholesale_qty: number
  is_active: boolean
}

export interface ProductDetail extends ProductListItem {
  brand?: string | null
  category?: string | null
  image_urls?: string[]
  description?: string | null
  spec_dim_1_name: string
  spec_dim_2_name: string
  has_dual_price: boolean
  total_online_stock?: number
  skus: ProductSkuItem[]
}

export interface CreateProductPayload {
  name: string
  product_code: string
  model_name?: string
  brand?: string
  category?: string
  description?: string
  image_urls?: string[]
  spec_dim_1_name: string
  spec_dim_2_name: string
  supports_retail: boolean
  supports_wholesale: boolean
  has_dual_price: boolean
}

export type UpdateProductPayload = Partial<CreateProductPayload> & { is_active?: boolean }

export interface BulkSkuPayload {
  product_id: number
  sku_type: 'retail' | 'wholesale'
  spec_values_1: string[]
  spec_values_2: string[]
  online_stock: number
  retail_price: number
  wholesale_price: number
  min_sale_qty: number
  min_wholesale_qty: number
  is_mixed_pack: boolean
  mixed_pack_note?: string
}

export interface UpdateSkuPayload {
  online_stock?: number
  retail_price?: number
  wholesale_price?: number
  min_sale_qty?: number
  min_wholesale_qty?: number
  is_active?: boolean
}

export interface StockLogItem {
  id: number
  delta_qty: number
  before_qty: number
  after_qty: number
  reason: string
  ref_order_no?: string | null
  operator_user_id?: number | null
  note?: string | null
  created_at: string
}

export interface WorkbenchOrderItem {
  id: number
  order_no: string
  status: 'pending_payment' | 'awaiting_shipment' | 'shipped' | 'completed' | 'canceled'
  buyer_role: 'retail' | 'wholesale'
  payment_method: 'wechat_pay' | 'offline_transfer'
  shipping_mode?: 'express' | 'offline' | null
  shipping_recipient?: string | null
  shipping_phone?: string | null
  shipping_address?: string | null
  shipping_proof_url?: string | null
  logistics_company?: string | null
  fulfillment_channel?: 'courier' | 'linehaul' | 'local_delivery' | 'pickup' | null
  carrier_contact?: string | null
  tracking_no?: string | null
  wechat_shipping_status?: 'pending' | 'succeeded' | 'failed' | 'skipped' | 'manual_required' | null
  wechat_shipping_error?: string | null
  wechat_shipping_attempts?: number
  wechat_shipping_attempted_at?: string | null
  wechat_shipping_uploaded_at?: string | null
  note?: string | null
  customer_note?: string | null
  internal_note?: string | null
  cancellation_reason?: string | null
  cancellation_source?: string | null
  termination_reason?: string | null
  termination_disposition?: string | null
  customer_name?: string | null
  customer_phone?: string | null
  original_amount?: string
  shipping_fee?: string
  payable_amount?: string
  paid_at?: string | null
  shipped_at?: string | null
  delivery_signed_at?: string | null
  completed_at?: string | null
  canceled_at?: string | null
  terminated_at?: string | null
  item_count?: number
  item_summary?: string | null
  lines?: Array<{
    sku_id: number
    product_name: string
    sku_code: string
    image_url?: string | null
    spec_value_1?: string | null
    spec_value_2?: string | null
    quantity: number
    unit_price: string
    line_amount: string
  }>
  created_at: string
}

export interface AftersaleItem {
  id: number
  order_id: number
  order_no?: string | null
  buyer_role?: 'retail' | 'wholesale' | null
  customer_name?: string | null
  customer_phone?: string | null
  reason: 'quality_issue' | 'wrong_item' | 'damaged' | 'size_problem' | 'other'
  custom_reason_text?: string | null
  process_type?: 'refund_and_return' | 'refund_only' | 'exchange' | 'rejected' | null
  refund_amount?: string | null
  chat_proof_url?: string | null
  note?: string | null
  customer_note?: string | null
  internal_note?: string | null
  handler_employee_id?: number | null
  handler_name?: string | null
  status: 'pending' | 'resolved'
  created_at: string
}

export interface WholesaleApplicationItem {
  id: number
  username: string
  status: 'pending' | 'approved' | 'rejected'
  company_name?: string | null
  store_name?: string | null
  contact_name?: string | null
  contact_phone?: string | null
  business_license_url?: string | null
  remark?: string | null
  review_note?: string | null
  created_at?: string
  reviewed_at?: string | null
}

export interface UserListItem {
  id: number
  username: string
  role: string
  is_active: boolean
  is_blacklisted?: boolean
  is_flagged?: boolean
  display_name?: string | null
  phone?: string | null
  company_name?: string | null
  store_name?: string | null
  is_verified_wholesale: boolean
  order_count?: number
  latest_application_id?: number | null
  application_status?: 'pending' | 'approved' | 'rejected' | null
  application_remark?: string | null
  application_review_note?: string | null
  created_at: string
}

export interface Customer360OrderItem {
  order_no: string
  created_at: string
  amount: string
  status: string
}

export interface Customer360AftersaleItem {
  id: number
  order_no?: string | null
  type: string
  refund_amount: string
  status: string
  created_at: string
}

export interface Customer360CartItem {
  id: number
  sku_id: number
  sku_code: string
  product_name: string
  spec_text: string
  quantity: number
  selected: boolean
  unit_price: string
  created_at?: string | null
}

export interface Customer360AddressItem {
  id: number
  contact_name: string
  phone: string
  region: string
  detail: string
  tag: string
  is_default: boolean
  created_at?: string | null
}

export interface Customer360NotificationItem {
  id: number
  title: string
  summary: string
  kind: string
  route?: string | null
  unread: boolean
  created_at?: string | null
}

export interface Customer360Payload {
  id: number
  name: string
  type: 'retail' | 'wholesale'
  current_role: 'admin' | 'employee' | 'retail' | 'wholesale'
  phone?: string | null
  company_name?: string | null
  store_name?: string | null
  contact_name?: string | null
  address?: string | null
  business_license_url?: string | null
  location?: string | null
  created_at?: string | null
  default_receiver?: string | null
  total_spent: string
  total_orders: number
  last_order_time?: string | null
  business_type?: string | null
  apply_note?: string | null
  note?: string | null
  miniapp_notification_enabled?: boolean
  miniapp_notification_event_keys?: string[]
  miniapp_notification_event_labels?: string[]
  miniapp_notification_updated_at?: string | null
  orders: Customer360OrderItem[]
  aftersales: Customer360AftersaleItem[]
  cart_items: Customer360CartItem[]
  addresses: Customer360AddressItem[]
  notifications: Customer360NotificationItem[]
}

export interface StorefrontConfigItem {
  title?: string
  name?: string
  image_url: string
  description?: string
  link_type: string
  link_value: string
  sort_order: number
  is_active: boolean
}

export interface StorefrontNotificationFieldKeys {
  [key: string]: string | undefined
  title?: string
  time?: string
  status?: string
  amount?: string
  note?: string
  order_no?: string
  product_name?: string
  aftersale_type?: string
  result?: string
  merchant_name?: string
  phone?: string
  apply_time?: string
  review_time?: string
}

export interface StorefrontNotificationEventConfig {
  key: string
  label: string
  desc?: string
  enabled: boolean
  template_id: string
  page: string
  field_keys: StorefrontNotificationFieldKeys
  field_mode?: 'editable' | 'fixed'
  field_note?: string
}

export interface StorefrontNotificationSettings {
  enabled: boolean
  miniapp_subscribe?: {
    enabled: boolean
    events: StorefrontNotificationEventConfig[]
  }
}

export interface ImageAiSettings {
  enabled: boolean
  provider: 'openai_compatible'
  base_url: string
  model: string
  api_key?: string
  api_key_set?: boolean
  timeout_seconds: number
  max_input_images: number
}

export interface ImageAiHistoryItem {
  id: number
  username?: string | null
  model_name: string
  prompt: string
  reference_urls: string[]
  result_url?: string | null
  status: string
  error_message?: string | null
  created_at?: string | null
}

export interface ImagePromptTemplateItem {
  id: number
  name: string
  prompt: string
  is_shared: boolean
  username?: string | null
}

export interface StorefrontConfigPayload {
  home_banners: StorefrontConfigItem[]
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
  shipping_policy?: {
    role_specific?: boolean
    delivery_fee?: string
    free_shipping_threshold?: string
    retail?: { delivery_fee?: string; free_shipping_threshold?: string }
    wholesale?: { delivery_fee?: string; free_shipping_threshold?: string }
  }
  notification_settings?: StorefrontNotificationSettings
  image_ai_settings?: ImageAiSettings
  print_layout?: string
  watermark?: {
    enabled: boolean
    customer_enabled?: boolean
    employee_enabled?: boolean
    opacity: number
    density: number
    angle: number
  }
  updated_at?: string | null
}

export interface StorefrontMarqueeNoticeItem {
  id?: number
  title: string
  body: string
  action_label: string
  action_type: 'none' | 'category' | 'cart' | 'profile' | 'url' | string
  action_value?: string | null
  is_active: boolean
  sort_order: number
  starts_at?: string | null
  ends_at?: string | null
  created_at?: string
  updated_at?: string
}

export interface StorefrontMarqueeNoticeListPayload {
  notices: StorefrontMarqueeNoticeItem[]
}

export interface SelfProfileUpdatePayload {
  display_name?: string | null
  avatar_url?: string | null
}

export interface SelfPasswordUpdatePayload {
  current_password: string
  new_password: string
}

export interface AdminAiPageContext {
  route: string
  entity_type?: 'dashboard' | 'product' | 'order' | 'aftersale' | 'customer' | 'wholesale' | 'storefront' | null
  entity_id?: number | string | null
  filters?: Record<string, string | number | boolean | null>
}

export interface AdminAiChatRequest {
  message: string
  session_id?: string | null
  page_context?: AdminAiPageContext | null
}

export interface AdminAiToolResult {
  name: string
  title: string
  summary: string
  data: Record<string, unknown>
}

export interface AdminAiChatResponse {
  answer: string
  session_id: string
  model?: string | null
  disabled: boolean
  tool_results: AdminAiToolResult[]
}

export interface CustomerRoleChangePayload {
  role: 'employee' | 'retail' | 'wholesale'
  company_name?: string
  store_name?: string
  business_type?: string
  contact_name?: string
  contact_phone?: string
  address?: string
  business_license_url?: string
  admin_confirm_password?: string
}

export interface DashboardSnapshot {
  today_revenue: string
  pending_order_count: number
  active_product_count: number
  pending_wholesale_count: number
}

export interface DashboardTrendPoint {
  date: string
  revenue: string
  orders: number
}

export interface DashboardMixItem {
  name: string
  value: string | number
}

export interface DashboardRankingItem {
  name: string
  sales: number
  percent: number
}

export interface DashboardTaskItem {
  id: string
  title: string
  desc: string
  time: string
  path: string
  count?: number
}

export interface DashboardRecentOrder {
  order_id: number
  order_no: string
  customer_name: string
  identity: string
  status: string
  payment_method: string
  amount: string
  item_summary?: string | null
}

export interface DashboardStockAlert {
  sku_id: number
  product_name: string
  spec?: string | null
  stock: number
}

export interface DashboardPayload {
  snapshot: DashboardSnapshot
  trend: {
    days: number
    points: DashboardTrendPoint[]
  }
  customer_mix: {
    revenue: DashboardMixItem[]
    orders: DashboardMixItem[]
  }
  rankings: {
    week: DashboardRankingItem[]
    month: DashboardRankingItem[]
  }
  tasks: {
    urgent: DashboardTaskItem[]
    follow: DashboardTaskItem[]
  }
  recent_orders: DashboardRecentOrder[]
  stock_alerts: DashboardStockAlert[]
}

export interface BusinessEventItem {
  id: number
  event_no: string
  entity_type: string
  entity_id?: number | null
  entity_no?: string | null
  action_code: string
  action_label: string
  source: string
  actor_user_id?: number | null
  actor_role?: string | null
  actor_name_snapshot?: string | null
  visibility: string
  correlation_id?: string | null
  request_id?: string | null
  before_data: Record<string, unknown>
  after_data: Record<string, unknown>
  evidence: Record<string, unknown>
  note?: string | null
  created_at: string
}
