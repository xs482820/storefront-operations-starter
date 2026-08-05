import { http } from '../services/http'

export type UserRole = 'admin' | 'employee' | 'retail' | 'wholesale'

export type TokenResponse = {
  access_token: string
  token_type: string
  user_id?: number | null
  username?: string | null
  role?: UserRole | null
  phone?: string | null
  wechat_openid?: string | null
  wechat_bound: boolean
  is_new_user: boolean
  generated_password?: string | null
}

export type CurrentUser = {
  id: number
  username: string
  role: UserRole
  display_name?: string | null
  avatar_url?: string | null
  phone?: string | null
  wechat_openid?: string | null
  wechat_bound: boolean
}

export type WechatMiniCodeOut = {
  openid: string
  unionid?: string | null
  session_key_present: boolean
}

export function wechatCode2Session(code: string) {
  return http.post<WechatMiniCodeOut>('/auth/wechat/mini/code2session', { code }, false)
}

export function wechatMiniLogin(payload: { code: string; display_name?: string }) {
  return http.post<TokenResponse>('/auth/wechat/mini/login', payload, false)
}

export function wechatMiniLoginWithPhone(payload: { login_code: string; phone_code: string; display_name?: string }) {
  return http.post<TokenResponse>('/auth/wechat/mini/login-with-phone', payload, false)
}

export function wechatMiniBindPhone(code: string) {
  return http.post<{ bound: boolean; phone: string }>('/auth/wechat/mini/bind-phone', { code })
}

export function fetchAuthMe() {
  return http.get<CurrentUser>('/auth/me')
}
