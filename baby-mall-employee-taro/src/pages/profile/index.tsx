import Taro from '@tarojs/taro'
import { Button, View, Text } from '@tarojs/components'
import { BackButton } from '../../components/BackButton'
import { getSafeStyle } from '../../utils/safeArea'
import { EmployeeWatermark } from '../../components/EmployeeWatermark'
import './index.scss'

export default function ProfilePage() {
  return (
    <View className="page profile-page" style={getSafeStyle()}>
      <EmployeeWatermark />
      <BackButton />
      <View className="profile-card card">
        <View className="avatar">赵</View>
        <View>
          <Text className="profile-name">店员小赵</Text>
          <Text className="profile-role">订单处理员 · 今日在线</Text>
        </View>
      </View>
      <View className="menu-card card" onClick={() => Taro.navigateTo({ url: '/pages/workbench/index' })}>工作台</View>
      <View className="menu-card card" onClick={() => Taro.navigateTo({ url: '/pages/orders/index' })}>订单处理</View>
      <View className="menu-card card" onClick={() => Taro.navigateTo({ url: '/pages/aftersale/index' })}>售后处理</View>
      <View className="menu-card card" onClick={() => Taro.navigateTo({ url: '/pages/customer/index' })}>客户查询</View>
      <View className="menu-card card" onClick={() => Taro.navigateTo({ url: '/pages/products/index' })}>商品库</View>
      <View className="menu-card card" onClick={() => Taro.navigateTo({ url: '/pages/media/index' })}>图片准备</View>
      <Button className="profile-logout" onClick={() => Taro.reLaunch({ url: '/pages/entry/index' })}>退出到登录页</Button>
    </View>
  )
}
