import Taro from '@tarojs/taro'
import { type CSSProperties } from 'react'

export function getSafeStyle(): CSSProperties {
  try {
    const info = Taro.getWindowInfo()
    const capsule = Taro.getMenuButtonBoundingClientRect?.()
    const safeTop = info.statusBarHeight || 24
    const headerBottom = capsule?.bottom || safeTop + 48
    return {
      '--safe-top': `${safeTop}px`,
      '--header-bottom': `${headerBottom}px`,
      '--safe-bottom': `${Math.max(0, (info.screenHeight || 0) - (info.safeArea?.bottom || info.screenHeight || 0))}px`,
    } as CSSProperties
  } catch {
    return {
      '--safe-top': '24px',
      '--header-bottom': '68px',
      '--safe-bottom': '0px',
    } as CSSProperties
  }
}
