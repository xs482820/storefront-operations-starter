import { useEffect, useState } from 'react'
import Taro from '@tarojs/taro'
import { Text, View } from '@tarojs/components'
import { Popup } from '@antmjs/vantui/lib/popup'
import { Icon } from '@antmjs/vantui/lib/icon'
import { fetchStorefrontConfig } from '../../api/catalog'
import { CUSTOMER_NOTIFICATIONS_CHANGED, fetchUnreadNotificationCount } from '../../services/notificationState'
import './index.scss'

type TopUtilityActionsProps = {
  onOpenNotifications?: () => void
  className?: string
}

export function TopUtilityActions({ onOpenNotifications, className = '' }: TopUtilityActionsProps) {
  const [serviceOpen, setServiceOpen] = useState(false)
  const [wechatId, setWechatId] = useState('')
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    const refreshUnreadCount = (nextCount?: unknown) => {
      if (typeof nextCount === 'number') {
        setUnreadCount(nextCount)
        return
      }
      fetchUnreadNotificationCount().then(setUnreadCount).catch(() => setUnreadCount(0))
    }
    refreshUnreadCount()
    Taro.eventCenter.on(CUSTOMER_NOTIFICATIONS_CHANGED, refreshUnreadCount)
    return () => Taro.eventCenter.off(CUSTOMER_NOTIFICATIONS_CHANGED, refreshUnreadCount)
  }, [])

  useEffect(() => {
    if (!serviceOpen || wechatId) return
    fetchStorefrontConfig()
      .then((config) => setWechatId(config.customer_service?.wechat_id?.trim() || ''))
      .catch(() => undefined)
  }, [serviceOpen, wechatId])

  const openNotifications = () => {
    if (onOpenNotifications) {
      onOpenNotifications()
      return
    }
    const current = Taro.getCurrentPages().slice(-1)[0]
    const returnTo = current?.route ? `&returnTo=${encodeURIComponent(`/${current.route}`)}` : ''
    Taro.navigateTo({ url: `/pages/profile/index?view=notifications${returnTo}` })
  }

  const copyWechatId = () => {
    if (!wechatId) {
      Taro.showToast({ title: '微信客服暂未配置', icon: 'none' })
      return
    }
    Taro.setClipboardData({ data: wechatId })
  }

  return (
    <>
      <View className={`top-utility-actions ${className}`}>
        <View className="top-utility-button" onClick={() => setServiceOpen(true)}>
          <Icon className="top-utility-glyph" name="service-o" size="32rpx" />
        </View>
        <View className="top-utility-button" onClick={openNotifications}>
          <Icon className="top-utility-glyph" name="bell" size="32rpx" />
          {unreadCount > 0 && <Text className="top-utility-dot">{unreadCount > 9 ? '9+' : unreadCount}</Text>}
        </View>
      </View>

      <Popup show={serviceOpen} position="bottom" round safeAreaInsetBottom={false} onClose={() => setServiceOpen(false)}>
        <View className="top-service-sheet">
          <View className="top-service-handle" />
          <View className="top-service-head">
            <View>
              <Text className="top-service-title">联系客服</Text>
              <Text className="top-service-copy">复制微信号后，在微信中搜索并联系店内客服。</Text>
            </View>
            <View className="top-service-close" onClick={() => setServiceOpen(false)}>×</View>
          </View>
          <View className="top-service-wechat-row">
            <Text className="top-service-wechat-label">微信客服</Text>
            <Text className="top-service-wechat-value">{wechatId || '暂未配置'}</Text>
            <View className="top-service-copy-button" onClick={copyWechatId}>复制</View>
          </View>
        </View>
      </Popup>
    </>
  )
}
