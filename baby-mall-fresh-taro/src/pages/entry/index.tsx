import { useEffect, useState } from 'react'
import Taro from '@tarojs/taro'
import { View, Text } from '@tarojs/components'
import { Button } from '@antmjs/vantui/lib/button'
import { fetchAuthMe, wechatMiniLogin } from '../../api/auth'
import { getAuthToken, setAuthToken } from '../../services/http'
import { getSafeVars } from '../../utils/safeArea'
import './index.scss'

export default function EntryPage() {
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!getAuthToken()) return
    fetchAuthMe()
      .then(() => Taro.redirectTo({ url: '/pages/home/index' }))
      .catch(() => setAuthToken(''))
  }, [])

  const enterHome = () => Taro.redirectTo({ url: '/pages/home/index' })

  const loginWithWechat = async () => {
    setLoading(true)
    try {
      const login = await Taro.login()
      if (!login.code) throw new Error('微信登录凭证获取失败')
      const token = await wechatMiniLogin({ code: login.code, display_name: '微信用户' })
      setAuthToken(token.access_token)
      Taro.showToast({ title: '登录成功', icon: 'success' })
      enterHome()
    } catch (error) {
      Taro.showToast({ title: error instanceof Error ? error.message : '登录失败，先进入浏览', icon: 'none' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <View className="entry-page safe-page" style={getSafeVars()}>
      <View className="entry-shell">
        <View className="entry-hero">
          <View className="entry-orbit">
            <View className="entry-orbit-large" />
            <View className="entry-orbit-small" />
            <View className="entry-logo-mark">赵</View>
          </View>
          <View className="entry-brand">
            <Text className="entry-eyebrow">示例门店</Text>
            <Text className="entry-title">安心选货，轻松下单</Text>
            <Text className="entry-copy">登录后可同步清单、订单、售后和收货地址。</Text>
          </View>
        </View>

        <View className="entry-action-card">
          <Button
            block
            round
            type="primary"
            size="large"
            loading={loading}
            onClick={loginWithWechat}
          >
            微信一键登录
          </Button>
          <Text className="entry-safe-copy">仅用于确认身份和同步采购记录</Text>
          <View className="entry-skip" onClick={enterHome}>暂不登录，先进入浏览</View>
        </View>
      </View>
    </View>
  )
}
