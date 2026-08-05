import Taro from '@tarojs/taro'
import { Text, View } from '@tarojs/components'

export function BackButton({ fallbackUrl = '/pages/workbench/index' }: { fallbackUrl?: string }) {
  return <View className="subpage-back" onClick={() => {
    const pages = Taro.getCurrentPages()
    if (pages.length > 1) Taro.navigateBack()
    else Taro.reLaunch({ url: fallbackUrl })
  }}><Text className="subpage-back-arrow">‹</Text></View>
}
