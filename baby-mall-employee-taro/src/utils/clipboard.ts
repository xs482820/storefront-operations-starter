import Taro from '@tarojs/taro'

export function copyText(value?: string | null, label = '内容') {
  if (!value) {
    Taro.showToast({ title: `暂无${label}`, icon: 'none' })
    return
  }
  Taro.setClipboardData({ data: value })
}
