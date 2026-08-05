import { useEffect, useState } from 'react'
import Taro from '@tarojs/taro'
import { Button, Input, Text, View } from '@tarojs/components'
import { employeePasswordLogin, fetchEmployeeMe } from '../../api/employee'
import { getToken, setToken } from '../../services/http'
import { getSafeStyle } from '../../utils/safeArea'
import './index.scss'

export default function EntryPage() {
  const [loading, setLoading] = useState(Boolean(getToken()))
  const [error, setError] = useState('')
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  useEffect(() => { if (getToken()) fetchEmployeeMe().then((user) => { if (!['employee', 'admin'].includes(user.role)) throw new Error(); Taro.reLaunch({ url: '/pages/workbench/index' }) }).catch(() => { setToken(''); setError('登录状态已失效，请重新验证') }).finally(() => setLoading(false)) }, [])
  const login = async () => {
    if (!identifier.trim() || !password) { setError('请输入内部账号和密码'); return }
    setLoading(true); setError('')
    try { const session = await employeePasswordLogin(identifier, password); if (!['employee', 'admin'].includes(session.role || '')) throw new Error('该账号没有店员权限'); setToken(session.access_token); Taro.reLaunch({ url: '/pages/workbench/index' }) }
    catch { setError('验证失败') }
    finally { setLoading(false) }
  }
  return <View className="page entry-page" style={getSafeStyle()}><View className="entry-card"><Text className="entry-title">工作台</Text>{error && <Text className="entry-error">{error}</Text>}<View className="entry-fields"><Input className="entry-input" value={identifier} placeholder="账号" onInput={(event) => setIdentifier(event.detail.value)} /><Input className="entry-input" value={password} password placeholder="密码" onInput={(event) => setPassword(event.detail.value)} /></View><Button className="entry-login" loading={loading} onClick={login}>进入</Button></View></View>
}
