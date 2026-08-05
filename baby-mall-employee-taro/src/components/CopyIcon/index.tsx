import { View } from '@tarojs/components'
import { copyText } from '../../utils/clipboard'
import './index.scss'

type CopyIconProps = { value?: string | null; label?: string; stopPropagation?: boolean; className?: string }

export function CopyIcon({ value, label = '内容', stopPropagation = false, className = '' }: CopyIconProps) {
  return <View className={`copy-action ${className}`} onClick={(event) => {
    if (stopPropagation) event.stopPropagation()
    copyText(value, label)
  }}><View className="copy-action-back" /><View className="copy-action-front" /></View>
}
