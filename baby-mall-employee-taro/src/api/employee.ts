import Taro from '@tarojs/taro'
import { getApiBaseUrl, getToken, request } from '../services/http'

export type EmployeeMe = { id: number; username: string; role: string; display_name?: string | null; phone?: string | null }
export type WorkbenchSummary = { pending_payment_orders: number; awaiting_shipment_orders: number; shipped_orders: number; pending_aftersales: number; today_new_orders: number; today_new_aftersales: number }
export type EmployeeOrderLine = { product_name: string; sku_code?: string | null; quantity: number; image_url?: string | null; spec_value_1?: string | null; spec_value_2?: string | null; unit_price: string; line_amount: string }
export type EmployeeOrder = {
  id: number
  order_no: string
  status: string
  buyer_role: string
  customer_name: string
  customer_phone?: string | null
  item_count: number
  item_summary?: string | null
  payable_amount: string
  original_amount?: string
  shipping_fee?: string
  created_at: string
  lines: EmployeeOrderLine[]
  can_ship: boolean
  can_mark_delivered: boolean
  can_cancel: boolean
  shipping_recipient?: string | null
  shipping_address?: string | null
  shipping_mode?: string | null
  fulfillment_channel?: string | null
  logistics_company?: string | null
  tracking_no?: string | null
  carrier_contact?: string | null
  shipping_proof_url?: string | null
  shipping_evidence?: Record<string, string[]>
  note?: string | null
  customer_note?: string | null
  internal_note?: string | null
  cancellation_reason?: string | null
  cancellation_source?: string | null
  termination_reason?: string | null
  terminated_at?: string | null
  paid_at?: string | null
  shipped_at?: string | null
  delivery_signed_at?: string | null
  completed_at?: string | null
  canceled_at?: string | null
}
export type EmployeeAfterSale = { id: number; order_no?: string | null; customer_name: string; customer_phone?: string | null; reason: string; status: string; refund_amount?: string | null; created_at: string; custom_reason_text?: string | null; note?: string | null; customer_note?: string | null; internal_note?: string | null; chat_proof_url?: string | null; process_type?: string | null; handler_name?: string | null }
export type EmployeeCustomer = { id: number; username: string; role: string; is_active: boolean; is_blacklisted: boolean; is_flagged: boolean; display_name?: string | null; phone?: string | null; avatar_url?: string | null; company_name?: string | null; store_name?: string | null; contact_name?: string | null; address?: string | null; note?: string | null; business_license_url?: string | null; is_verified_wholesale: boolean; order_count: number; order_amount: string }
export type EmployeeProductSku = { id: number; sku_code: string; sku_type: string; spec_value_1?: string | null; spec_value_2?: string | null; sku_label?: string | null; online_stock: number; retail_price: string; wholesale_price: string; min_sale_qty: number; min_wholesale_qty: number; is_active: boolean }
export type EmployeeProduct = { id: number; name: string; model_name?: string | null; product_code: string; brand?: string | null; category?: string | null; description?: string | null; image_urls: string[]; supports_retail: boolean; supports_wholesale: boolean; has_dual_price: boolean; is_active: boolean; skus: EmployeeProductSku[] }
export type EmployeeQuickProductInput = { name: string; product_code: string; category?: string | null; description?: string | null; image_urls: string[]; retail_price?: number | null; wholesale_price?: number | null; min_wholesale_qty: number; is_active: boolean }
export type EmployeeCustomerDetail = EmployeeCustomer & { favorite_count: number; cart_count: number; unread_notification_count: number; addresses: Array<{ id: number; contact_name: string; phone: string; region: string; detail: string; tag: string; is_default: boolean }>; orders: Array<{ id: number; order_no: string; status: string; amount: string; created_at: string }>; aftersales: Array<{ id: number; order_no?: string | null; status: string; reason: string; created_at: string }> }

export const fetchEmployeeMe = () => request<EmployeeMe>('/auth/me')
export const fetchEmployeeWatermarkSettings = () => request<{ watermark?: { enabled?: boolean; employee_enabled?: boolean; opacity?: number; density?: number; angle?: number } }>('/customer/storefront-config', 'GET', undefined, false)
export const fetchWorkbench = () => request<WorkbenchSummary>('/employee/workbench-summary')
export const fetchEmployeeOrders = () => request<EmployeeOrder[]>('/employee/orders')
export const fetchEmployeeAfterSales = () => request<EmployeeAfterSale[]>('/employee/aftersales')
export const fetchEmployeeCustomers = (keyword?: string) => request<EmployeeCustomer[]>(`/employee/customers${keyword?.trim() ? `?keyword=${encodeURIComponent(keyword.trim())}` : ''}`)
export const fetchEmployeeCustomerDetail = (customerId: number) => request<EmployeeCustomerDetail>(`/employee/customers/${customerId}`)
export const fetchEmployeeProducts = (keyword?: string) => request<EmployeeProduct[]>(`/employee/products${keyword?.trim() ? `?keyword=${encodeURIComponent(keyword.trim())}` : ''}`)
export const createEmployeeQuickProduct = (data: EmployeeQuickProductInput) => request<{ id: number; product_code: string }>('/employee/products', 'POST', data)
export const updateEmployeeQuickProduct = (productId: number, data: EmployeeQuickProductInput) => request<{ id: number; product_code: string }>(`/employee/products/${productId}`, 'PATCH', data)
export const fetchEmployeeImageAiStatus = () => request<{ enabled: boolean; configured: boolean; max_input_images: number }>('/employee/image-ai/status')
export type EmployeeImageHistory = { id: number; username?: string | null; model_name: string; prompt: string; reference_urls: string[]; result_url?: string | null; status: string; error_message?: string | null; created_at?: string | null }
export type EmployeeImagePromptTemplate = { id: number; name: string; prompt: string; is_shared: boolean; username?: string | null }
export const fetchEmployeeImageAiHistory = () => request<EmployeeImageHistory[]>('/employee/image-ai/history')
export const fetchEmployeeImageAiTemplates = () => request<EmployeeImagePromptTemplate[]>('/employee/image-ai/templates')
export const createEmployeeImageAiTemplate = (data: { name: string; prompt: string }) => request<EmployeeImagePromptTemplate>('/employee/image-ai/templates', 'POST', data)
export const deleteEmployeeImageAiTemplate = (templateId: number) => request<{ ok: boolean }>(`/employee/image-ai/templates/${templateId}`, 'DELETE')
export const generateEmployeeImage = (data: { prompt: string; reference_urls: string[] }) => request<{ id: number; status: string }>('/employee/image-ai/generate', 'POST', data)

export function employeePasswordLogin(identifier: string, password: string) {
  return request<{ access_token: string; role?: string }>('/auth/login', 'POST', {
    identifier: identifier.trim(),
    password,
  }, false)
}

export function employeeWechatPhoneLogin(loginCode: string, phoneCode: string) {
  return request<{ access_token: string; role?: string }>('/auth/wechat/mini/login-with-phone', 'POST', {
    login_code: loginCode,
    phone_code: phoneCode,
    app_scope: 'employee',
  }, false)
}

export const shipEmployeeOrder = (orderId: number, data: Record<string, unknown>) => request(`/employee/orders/${orderId}/ship`, 'POST', data)
export const markEmployeeOrderDelivered = (orderId: number) => request(`/employee/orders/${orderId}/mark-delivered`, 'POST', { signed_at: new Date().toISOString() })
export const saveEmployeeOrderNote = (orderId: number, note: string) => request(`/employee/orders/${orderId}/note`, 'POST', { note })
export const cancelEmployeeOrder = (orderId: number) => request(`/employee/orders/${orderId}/cancel`, 'POST', { note: '店员终止未付款订单' })
export const createEmployeePickListPrintJob = (orderId: number) => request<{ id: number; status: string; order_no: string }>(`/employee/orders/${orderId}/print-pick-list`, 'POST')
export const resolveEmployeeAfterSale = (id: number, data: Record<string, unknown>) => request(`/employee/aftersales/${id}/resolve`, 'POST', data)

export async function uploadEmployeeEvidence(filePath: string) {
  const result = await Taro.uploadFile({ url: `${getApiBaseUrl()}/employee/upload-evidence`, filePath, name: 'file', header: { Authorization: `Bearer ${getToken()}` } })
  if (result.statusCode < 200 || result.statusCode >= 300) throw new Error('凭证上传失败')
  return JSON.parse(result.data) as { url: string }
}
