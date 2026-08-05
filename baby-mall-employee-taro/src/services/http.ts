import Taro from '@tarojs/taro'

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:19000/api/v1'
const API_BASE_URL_KEY = 'storefront_employee_api_base_url'
const TOKEN_KEY = 'baby_mall_employee_auth_token'

function trimSlash(value: string) {
  return value.trim().replace(/\/+$/, '')
}

export function getApiBaseUrl() {
  const raw = Taro.getStorageSync(API_BASE_URL_KEY)
  return typeof raw === 'string' && trimSlash(raw) ? trimSlash(raw) : DEFAULT_API_BASE_URL
}

export function setApiBaseUrl(value: string) {
  const normalized = trimSlash(value)
  if (normalized) Taro.setStorageSync(API_BASE_URL_KEY, normalized)
  else Taro.removeStorageSync(API_BASE_URL_KEY)
}

export function resolveMediaUrl(value?: string | null) {
  if (!value) return ''
  if (/^(https?:|wxfile:|data:|blob:|file:)/i.test(value)) return value
  if (/^(__tmp__|tmp\/|tmp_|\/tmp\/|\/private\/)/i.test(value)) return value
  const origin = getApiBaseUrl().replace(/\/api\/v\d+.*$/i, '')
  return `${origin}${value.startsWith('/') ? value : `/${value}`}`
}

export function getToken() {
  const value = Taro.getStorageSync(TOKEN_KEY)
  return typeof value === 'string' ? value : ''
}

export function setToken(value: string) {
  if (value) Taro.setStorageSync(TOKEN_KEY, value)
  else Taro.removeStorageSync(TOKEN_KEY)
}

export async function request<T>(url: string, method: 'GET' | 'POST' = 'GET', data?: unknown, auth = true) {
  const token = auth ? getToken() : ''
  const response = await Taro.request<T>({
    url: `${getApiBaseUrl()}${url}`,
    method,
    data,
    header: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (response.statusCode >= 200 && response.statusCode < 300) return response.data
  if (response.statusCode === 401) setToken('')
  const body = response.data as { detail?: string; message?: string }
  throw new Error(body?.detail || body?.message || `请求失败 (${response.statusCode})`)
}
