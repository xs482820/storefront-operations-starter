import Taro from '@tarojs/taro'

type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

type RequestOptions = {
  url: string
  method: HttpMethod
  data?: unknown
  auth?: boolean
  header?: Record<string, string>
}

export type ApiErrorPayload = {
  detail?: string
  message?: string
}

// Replace this in a private deployment, or set it in the app's connection settings.
const DEFAULT_API_BASE_URL = 'http://127.0.0.1:19000/api/v1'
const API_BASE_URL_KEY = 'baby_mall_fresh_api_base_url'
const AUTH_TOKEN_KEY = 'baby_mall_fresh_auth_token'

function trimSlash(value: string) {
  return value.trim().replace(/\/+$/, '')
}

export function getApiBaseUrl() {
  const raw = Taro.getStorageSync(API_BASE_URL_KEY)
  if (typeof raw === 'string') {
    const value = trimSlash(raw)
    if (value) return value
  }
  return DEFAULT_API_BASE_URL
}

export function resolveMediaUrl(url?: string | null) {
  if (!url) return ''
  const value = url.trim()
  if (!value) return ''
  if (/^https?:\/\/127\.0\.0\.1:\d+\/__tmp__\//i.test(value)) return ''
  if (/^http:\/\/tmp\//i.test(value)) return ''
  if (/^(https?:|wxfile:|cloud:|data:|blob:)/i.test(value)) return value

  const apiBase = getApiBaseUrl()
  const origin = apiBase.replace(/\/api\/v\d+.*$/i, '')
  if (value.startsWith('/api/')) return `${origin}${value}`
  return `${origin}${value.startsWith('/') ? value : `/${value}`}`
}

export function setApiBaseUrl(url: string) {
  const value = trimSlash(url)
  if (value) {
    Taro.setStorageSync(API_BASE_URL_KEY, value)
    return
  }
  Taro.removeStorageSync(API_BASE_URL_KEY)
}

export function getAuthToken() {
  const token = Taro.getStorageSync(AUTH_TOKEN_KEY)
  return typeof token === 'string' ? token : ''
}

export function setAuthToken(token: string) {
  if (token) {
    Taro.setStorageSync(AUTH_TOKEN_KEY, token)
    return
  }
  Taro.removeStorageSync(AUTH_TOKEN_KEY)
}

function resolveErrorMessage(data: unknown) {
  if (data && typeof data === 'object') {
    const payload = data as ApiErrorPayload
    return payload.detail || payload.message
  }
  return undefined
}

export async function request<T>(options: RequestOptions): Promise<T> {
  const token = options.auth === false ? '' : getAuthToken()
  const header = {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.header || {}),
  }

  const response = await Taro.request<T>({
    url: `${getApiBaseUrl()}${options.url}`,
    method: options.method,
    data: options.data,
    header,
  })

  if (response.statusCode >= 200 && response.statusCode < 300) {
    return response.data
  }
  if (response.statusCode === 401) {
    setAuthToken('')
  }
  throw new Error(resolveErrorMessage(response.data) || `请求失败 (${response.statusCode})`)
}

export const http = {
  get<T>(url: string, auth = true) {
    return request<T>({ url, method: 'GET', auth })
  },
  post<T>(url: string, data?: unknown, auth = true) {
    return request<T>({ url, method: 'POST', data, auth })
  },
  patch<T>(url: string, data?: unknown, auth = true) {
    return request<T>({ url, method: 'PATCH', data, auth })
  },
  put<T>(url: string, data?: unknown, auth = true) {
    return request<T>({ url, method: 'PUT', data, auth })
  },
  delete<T>(url: string, auth = true) {
    return request<T>({ url, method: 'DELETE', auth })
  },
}
