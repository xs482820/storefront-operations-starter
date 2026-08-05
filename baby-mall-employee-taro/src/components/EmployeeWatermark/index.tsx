import { useEffect, useState } from 'react'
import { Text, View } from '@tarojs/components'
import { fetchEmployeeMe, fetchEmployeeWatermarkSettings } from '../../api/employee'
import { getToken } from '../../services/http'
import './index.scss'

export function EmployeeWatermark() {
  const [label, setLabel] = useState('')
  const [opacity, setOpacity] = useState(0.045)
  const [count, setCount] = useState(9)
  const [token, setToken] = useState(() => getToken())

  useEffect(() => {
    // ponytail: storage has no subscription; this keeps the app-level overlay in sync after login.
    const timer = setInterval(() => setToken((current) => {
      const next = getToken()
      return next === current ? current : next
    }), 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!token) { setLabel(''); return }
    let alive = true
    Promise.all([fetchEmployeeMe(), fetchEmployeeWatermarkSettings()])
      .then(([user, config]) => {
        const watermark = config.watermark
        if (!alive || watermark?.enabled === false || watermark?.employee_enabled !== true) { setLabel(''); return }
        setOpacity(Math.max(0.04, Math.min(0.1, Number(watermark?.opacity ?? 0.05))))
        setCount(Math.max(6, Math.min(12, Math.round(Number(watermark?.density ?? 5) + 4))))
        setLabel(`${user.id} · ${(user.phone || user.username).slice(-4)}`)
      })
      .catch(() => { if (alive) setLabel('') })
    return () => { alive = false }
  }, [token])

  if (!label) return null
  return <View className="employee-watermark" style={{ opacity }} aria-hidden>{Array.from({ length: count }, (_, index) => <Text key={index} style={{ transform: 'rotate(-45deg)' }}>{label}</Text>)}</View>
}
