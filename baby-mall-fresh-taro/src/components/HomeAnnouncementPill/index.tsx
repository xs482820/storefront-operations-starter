import { useEffect, useState } from 'react'
import { Text, View } from '@tarojs/components'
import './index.scss'

export type HomeAnnouncementItem = {
  id: string
  title: string
}

type HomeAnnouncementPillProps = {
  announcements: HomeAnnouncementItem[]
  compact?: boolean
  onClick?: () => void
}

export function HomeAnnouncementPill({ announcements, compact = false, onClick }: HomeAnnouncementPillProps) {
  const [activeIndex, setActiveIndex] = useState(0)

  useEffect(() => {
    setActiveIndex(0)
    if (announcements.length < 2) return undefined
    const timer = setInterval(() => setActiveIndex((current) => (current + 1) % announcements.length), 3600)
    return () => clearInterval(timer)
  }, [announcements])

  if (announcements.length === 0) return null

  return (
    <View className={`home-announcement-pill ${compact ? 'compact' : ''}`} onClick={onClick}>
      <Text className="home-announcement-label">{'\u516c\u544a'}</Text>
      <View className="home-announcement-window">
        <View className="home-announcement-track" style={{ transform: `translateY(-${activeIndex * 58}rpx)` }}>
          {announcements.map((announcement) => (
            <View key={announcement.id} className="home-announcement-row">
              <Text className="home-announcement-text">{announcement.title}</Text>
            </View>
          ))}
        </View>
        <View className="home-announcement-fade" />
      </View>
    </View>
  )
}
