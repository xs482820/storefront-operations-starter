import Taro from '@tarojs/taro'
import { getApiBaseUrl, getAuthToken, http, resolveMediaUrl } from '../services/http'
import { type UserRole } from './auth'

export type CustomerMe = {
  user_id: number
  username: string
  role: UserRole | string
  display_name?: string | null
  phone?: string | null
  avatar_url?: string | null
  company_name?: string | null
  store_name?: string | null
  contact_name?: string | null
  address?: string | null
  business_license_url?: string | null
  is_verified_wholesale: boolean
  wechat_bound: boolean
  employee_mode: string
  miniapp_notification_enabled: boolean
  miniapp_notification_event_keys: string[]
  miniapp_notification_updated_at?: string | null
}

export type CustomerMeUpdate = Partial<{
  display_name: string | null
  avatar_url: string | null
  company_name: string | null
  store_name: string | null
  contact_name: string | null
  address: string | null
  business_license_url: string | null
  note: string | null
  employee_mode: 'shopping' | 'workbench'
  miniapp_notification_enabled: boolean
  miniapp_notification_event_keys: string[]
}>

export function fetchCustomerMe() {
  return http.get<CustomerMe>('/customer/me')
}

export function updateCustomerMe(payload: CustomerMeUpdate) {
  return http.patch<CustomerMe>('/customer/me', payload)
}

export function uploadCustomerImage(filePath: string) {
  const token = getAuthToken()
  return Taro.uploadFile({
    url: `${getApiBaseUrl()}/customer/upload-image`,
    filePath,
    name: 'file',
    header: token ? { Authorization: `Bearer ${token}` } : {},
  }).then((response) => {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw new Error(`上传失败 (${response.statusCode})`)
    }
    const data = typeof response.data === 'string' ? JSON.parse(response.data) : response.data
    return {
      ...(data as { url: string; name: string; size: number }),
      url: resolveMediaUrl((data as { url: string }).url),
    }
  })
}
