import { fetchNotifications } from '../api/notification'
import Taro from '@tarojs/taro'

export const CUSTOMER_NOTIFICATIONS_CHANGED = 'customer:notifications-changed'

export function notifyCustomerNotificationsChanged(unreadCount?: number) {
  Taro.eventCenter.trigger(CUSTOMER_NOTIFICATIONS_CHANGED, unreadCount)
}

export async function fetchUnreadNotificationCount() {
  const items = await fetchNotifications()
  return items.filter((item) => item.unread).length
}
