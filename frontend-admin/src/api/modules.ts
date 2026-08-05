import { api } from './http'
import type {
  AftersaleItem,
  AuthProfile,
  BulkSkuPayload,
  BusinessEventItem,
  CustomerRoleChangePayload,
  AdminAiChatRequest,
  AdminAiChatResponse,
  CreateProductPayload,
  DashboardPayload,
  Customer360Payload,
  ProductDetail,
  ProductCategoryItem,
  ProductListItem,
  StorefrontConfigPayload,
  ImageAiHistoryItem,
  ImagePromptTemplateItem,
  StorefrontMarqueeNoticeItem,
  StorefrontMarqueeNoticeListPayload,
  SelfPasswordUpdatePayload,
  SelfProfileUpdatePayload,
  StockLogItem,
  UpdateProductPayload,
  UpdateSkuPayload,
  UserListItem,
  WholesaleApplicationItem,
  WorkbenchOrderItem,
} from '../types/api'

export async function fetchDashboardSummary() {
  const response = await api.get<DashboardPayload>('/admin/dashboard')
  return response.data
}

export function fetchPrintJobs() {
  return api.get<Array<{ id: number; order_id: number; order_no: string; status: string; document_type: string; requested_by: string; created_at: string; payload: Record<string, unknown> }>>('/admin/print-jobs')
}

export function fetchProducts(keyword?: string) {
  return api.get<ProductListItem[]>('/admin/products', { params: { keyword: keyword || undefined } })
}

export function fetchProductCategories() {
  return api.get<ProductCategoryItem[]>('/admin/product-categories')
}

export function createProductCategory(payload: { name: string; sort_order?: number; is_active?: boolean }) {
  return api.post<ProductCategoryItem>('/admin/product-categories', payload)
}

export function updateProductCategory(categoryId: number, payload: { name?: string; sort_order?: number; is_active?: boolean }) {
  return api.patch<ProductCategoryItem>(`/admin/product-categories/${categoryId}`, payload)
}

export function deleteProductCategory(categoryId: number) {
  return api.delete(`/admin/product-categories/${categoryId}`)
}

export function uploadProductImage(file: File) {
  const form = new FormData()
  form.append('file', file)
  return api.post<{ url: string; name: string; size: number }>('/admin/upload-image', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function fetchProductDetail(productId: number) {
  return api.get<ProductDetail>(`/admin/products/${productId}`)
}

export function createProduct(payload: CreateProductPayload) {
  return api.post('/admin/products', payload)
}

export function updateProduct(productId: number, payload: UpdateProductPayload) {
  return api.patch(`/admin/products/${productId}`, payload)
}

export function deleteProduct(productId: number) {
  return api.delete(`/admin/products/${productId}`)
}

export function bulkCreateSku(payload: BulkSkuPayload) {
  return api.post('/admin/products/bulk-sku', payload)
}

export function updateSku(skuId: number, payload: UpdateSkuPayload) {
  return api.patch(`/admin/skus/${skuId}`, payload)
}

export function fetchStockLogs(skuId: number) {
  return api.get<StockLogItem[]>(`/admin/skus/${skuId}/stock-logs`)
}

export function fetchStorefrontConfig() {
  return api.get<StorefrontConfigPayload>('/admin/storefront-config')
}

export function updateStorefrontConfig(payload: Partial<StorefrontConfigPayload>) {
  return api.put('/admin/storefront-config', payload)
}

export function fetchImageAiHistory() {
  return api.get<ImageAiHistoryItem[]>('/admin/image-ai/history')
}

export function testImageAiConnection() {
  return api.post<{ ok: boolean; status_code: number; message: string }>('/admin/image-ai/connection-test')
}

export function fetchImageAiTemplates() {
  return api.get<ImagePromptTemplateItem[]>('/admin/image-ai/templates')
}

export function createImageAiTemplate(payload: { name: string; prompt: string }) {
  return api.post<ImagePromptTemplateItem>('/admin/image-ai/templates', payload)
}

export function updateImageAiTemplate(templateId: number, payload: { name: string; prompt: string }) {
  return api.patch<ImagePromptTemplateItem>(`/admin/image-ai/templates/${templateId}`, payload)
}

export function deleteImageAiTemplate(templateId: number) {
  return api.delete(`/admin/image-ai/templates/${templateId}`)
}

export function fetchStorefrontMarqueeNotices() {
  return api.get<StorefrontMarqueeNoticeItem[]>('/admin/storefront-marquee-notices')
}

export function updateStorefrontMarqueeNotices(payload: StorefrontMarqueeNoticeListPayload) {
  return api.put<StorefrontMarqueeNoticeItem[]>('/admin/storefront-marquee-notices', payload)
}

export function fetchWorkbenchOrders(status?: WorkbenchOrderItem['status'] | 'all') {
  return api.get<WorkbenchOrderItem[]>('/employee/orders', {
    params: { status: status && status !== 'all' ? status : undefined },
  })
}

export function confirmWechatPayment(orderId: number) {
  return api.post(`/admin/orders/${orderId}/confirm-wechat-payment`)
}

export function confirmOfflinePayment(orderId: number, note?: string) {
  return api.post(`/employee/orders/${orderId}/confirm-offline-payment`, { note })
}

export function shipOrder(orderId: number, payload: Record<string, unknown>) {
  return api.post(`/employee/orders/${orderId}/ship`, payload)
}

export function retryWechatShipping(orderId: number) {
  return api.post(`/employee/orders/${orderId}/wechat-shipping/retry`)
}

export function markDelivered(orderId: number, signedAt: string) {
  return api.post(`/employee/orders/${orderId}/mark-delivered`, { signed_at: signedAt })
}

export function cancelOrder(orderId: number, note?: string) {
  return api.post(`/employee/orders/${orderId}/cancel`, { note })
}

export function deleteAdminOrder(orderId: number, confirmation_text: string) {
  return api.delete(`/admin/orders/${orderId}`, { data: { confirmation_text } })
}

export function adjustAdminOrder(orderId: number, payload: Record<string, unknown>) {
  return api.patch(`/admin/orders/${orderId}`, payload)
}

export function terminateAdminOrder(orderId: number, payload: { reason: string; disposition?: string; internal_note?: string }) {
  return api.post(`/admin/orders/${orderId}/terminate`, payload)
}

export function fetchAftersales(status?: AftersaleItem['status'] | 'all') {
  return api.get<AftersaleItem[]>('/employee/aftersales', {
    params: { status: status && status !== 'all' ? status : undefined },
  })
}

export function createPickListPrintJob(orderId: number) {
  return api.post<{ id: number; status: string; order_no: string }>(`/employee/orders/${orderId}/print-pick-list`)
}

export function resolveAftersale(aftersaleId: number, payload: Record<string, unknown>) {
  return api.post(`/employee/aftersales/${aftersaleId}/resolve`, payload)
}

export function deleteAdminAftersale(aftersaleId: number, confirmation_text: string) {
  return api.delete(`/admin/aftersales/${aftersaleId}`, { data: { confirmation_text } })
}

export function updateAftersaleNotes(aftersaleId: number, payload: { customer_note?: string | null; internal_note?: string | null }) {
  return api.patch(`/admin/aftersales/${aftersaleId}/notes`, payload)
}

export function fetchWholesaleApplications() {
  return api.get<WholesaleApplicationItem[]>('/admin/wholesale-applications')
}

export function reviewWholesaleApplication(applicationId: number, payload: { status: string; review_note?: string }) {
  return api.post(`/admin/wholesale-applications/${applicationId}/review`, payload)
}

export function fetchUsers(params?: { role?: string; applicationStatus?: 'pending' | 'approved' | 'rejected'; keyword?: string }) {
  return api.get<UserListItem[]>('/admin/users', {
    params: {
      role: params?.role || undefined,
      application_status: params?.applicationStatus || undefined,
      keyword: params?.keyword?.trim() || undefined,
    },
  })
}

export function updateUserRuntimeState(userId: number, payload: { is_blacklisted?: boolean; is_flagged?: boolean }) {
  return api.patch(`/admin/users/${userId}/runtime-state`, payload)
}

export function fetchCustomer360(userId: number | string) {
  return api.get<Customer360Payload>(`/admin/users/${userId}/customer-360`)
}

export function updateCustomerNote(userId: number | string, note: string) {
  return api.patch<{ id: number; note?: string | null }>(`/admin/users/${userId}/note`, { note })
}

export function updateCustomerRole(userId: number | string, payload: CustomerRoleChangePayload) {
  return api.post<{ id: number; role: string; is_verified_wholesale: boolean }>(`/admin/users/${userId}/role-change`, payload)
}

export function createEmployeeAccount(payload: { username: string; password: string; display_name?: string; admin_confirm_password: string }) {
  return api.post('/admin/employee-accounts', payload)
}

export function deleteEmployeeAccount(userId: number, confirmation_text: string) {
  return api.delete(`/admin/users/${userId}/employee-account`, { data: { confirmation_text } })
}

export function fetchDeletionEvents() {
  return api.get<BusinessEventItem[]>('/events', { params: { action_contains: '.deleted' } })
}

export function fetchEntityEvents(entityType: string, entityId: number) {
  return api.get<BusinessEventItem[]>('/events', { params: { entity_type: entityType, entity_id: entityId } })
}

export function updateEmployeeAccount(userId: number | string, payload: { username?: string; password?: string; is_active?: boolean; admin_confirm_password: string }) {
  return api.patch(`/admin/users/${userId}/employee-account`, payload)
}

export function fetchMe() {
  return api.get<AuthProfile>('/auth/me')
}

export function updateSelfProfile(payload: SelfProfileUpdatePayload) {
  return api.patch<AuthProfile>('/admin/me/profile', payload)
}

export function updateSelfPassword(payload: SelfPasswordUpdatePayload) {
  return api.patch('/admin/me/password', payload)
}

export function chatAdminAssistant(payload: AdminAiChatRequest) {
  return api.post<AdminAiChatResponse>('/admin/ai/chat', payload)
}
