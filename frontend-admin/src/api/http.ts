import axios from 'axios'
import { ElMessage } from '@/utils/message'

import { getAccessToken, useAuthStore } from '../stores/auth'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 20000,
})

api.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      '请求失败'

    if (error.response?.status === 401) {
      try {
        useAuthStore().logout()
      } catch {
        localStorage.removeItem('yyy-admin-access-token')
        localStorage.removeItem('yyy-admin-auth-profile')
      }
      if (location.pathname !== '/login') {
        location.href = `/login?redirect=${encodeURIComponent(location.pathname + location.search)}`
      }
    } else {
      ElMessage.error(String(message))
    }

    return Promise.reject(error)
  },
)
