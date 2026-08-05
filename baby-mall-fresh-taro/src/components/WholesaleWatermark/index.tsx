import { useEffect, useState } from 'react'
import { Text, View } from '@tarojs/components'
import { fetchCustomerMe } from '../../api/customer'
import { fetchStorefrontConfig } from '../../api/catalog'
import { getAuthToken } from '../../services/http'
import './index.scss'

function today() {
  const date = new Date()
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

type WholesaleWatermarkProps = {
  contained?: boolean
}

export function WholesaleWatermark({ contained = false }: WholesaleWatermarkProps) {
  const [label, setLabel] = useState<string | null>(null)
  const [opacity, setOpacity] = useState(0.045)
  const [count, setCount] = useState(9)
  const [token, setToken] = useState(() => getAuthToken())

  useEffect(() => {
    // ponytail: storage has no subscription; refresh after the login page stores a token.
    const timer = setInterval(() => setToken((current) => {
      const next = getAuthToken()
      return current === next ? current : next
    }), 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!token) { setLabel(null); return }
    let alive = true
    Promise.all([fetchCustomerMe(), fetchStorefrontConfig()])
      .then(([user, config]) => {
        if (!alive) return
        const watermark = config.watermark
        const enabled = watermark?.enabled !== false && watermark?.customer_enabled !== false
        setOpacity(Math.max(0.04, Math.min(0.1, Number(watermark?.opacity ?? 0.05))))
        setCount(Math.max(6, Math.min(12, Math.round(Number(watermark?.density ?? 5) + 4))))
        setLabel(enabled
          ? `${user.user_id} · ${(user.phone || user.username).slice(-4)} · ${today()}`
          : null)
      })
      .catch(() => {
        if (alive) setLabel(null)
      })
    return () => {
      alive = false
    }
  }, [token])

  if (!label) return null

  return (
    <View className={`wholesale-watermark ${contained ? 'wholesale-watermark-contained' : ''}`} style={{ opacity }} aria-hidden>
      {Array.from({ length: count }, (_, index) => <Text key={index} style={{ transform: 'rotate(-45deg)' }}>{label}</Text>)}
    </View>
  )
}
