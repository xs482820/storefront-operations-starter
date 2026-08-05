import Taro from '@tarojs/taro'
import { type CSSProperties } from 'react'

export function getSafeVars(): CSSProperties {
  try {
    const info = Taro.getWindowInfo()
    const menu = Taro.getMenuButtonBoundingClientRect()
    const safeBottom = Math.max(0, (info.screenHeight || info.windowHeight) - (info.safeArea?.bottom || info.windowHeight))

    return {
      '--safe-top': `${info.statusBarHeight || 24}px`,
      '--capsule-bottom': `${menu?.bottom || (info.statusBarHeight || 24) + 44}px`,
      '--safe-bottom': `${safeBottom}px`,
    } as CSSProperties
  } catch {
    return {
      '--safe-top': '24px',
      '--capsule-bottom': '72px',
      '--safe-bottom': '0px',
    } as CSSProperties
  }
}
