import { http } from '../services/http'

export type CustomerNotification = {
  id: number
  title: string
  summary: string
  kind: string
  route?: string | null
  unread: boolean
  created_at: string
}

export function fetchNotifications() {
  return http.get<CustomerNotification[]>('/customer/notifications')
}

export function markNotificationRead(notificationId: number | string) {
  return http.post<{ updated: number }>(`/customer/notifications/${notificationId}/read`)
}

export function markAllNotificationsRead() {
  return http.post<{ updated: number }>('/customer/notifications/read-all')
}
