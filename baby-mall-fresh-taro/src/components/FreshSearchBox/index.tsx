import { View, Text } from '@tarojs/components'
import './index.scss'

type FreshSearchBoxProps = {
  value?: string
  placeholder?: string
  compact?: boolean
  onClick?: () => void
}

export function FreshSearchBox({
  value,
  placeholder = '搜索奶瓶、纸尿裤、洗护...',
  compact = false,
  onClick,
}: FreshSearchBoxProps) {
  return (
    <View className={`fresh-search-box ${compact ? 'compact' : ''}`} onClick={onClick}>
      <View className="fresh-search-icon" />
      {!compact && (
        <Text className={`fresh-search-text ${value ? 'has-value' : ''}`}>
          {value || placeholder}
        </Text>
      )}
    </View>
  )
}
