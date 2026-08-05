import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { api } from '../api/http'
import type { AuthProfile, LoginPayload, LoginResponse } from '../types/api'

const ACCESS_TOKEN_KEY = 'yyy-admin-access-token'
const AUTH_PROFILE_KEY = 'yyy-admin-auth-profile'

function readStoredProfile(): AuthProfile | null {
  const raw = localStorage.getItem(AUTH_PROFILE_KEY)
  if (!raw) {
    return null
  }
  try {
    return JSON.parse(raw) as AuthProfile
  } catch {
    localStorage.removeItem(AUTH_PROFILE_KEY)
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem(ACCESS_TOKEN_KEY) || '')
  const profile = ref<AuthProfile | null>(readStoredProfile())
  const loading = ref(false)

  const isAuthenticated = computed(() => Boolean(token.value))
  const hasProfile = computed(() => Boolean(profile.value))

  function persistState() {
    if (token.value) {
      localStorage.setItem(ACCESS_TOKEN_KEY, token.value)
    } else {
      localStorage.removeItem(ACCESS_TOKEN_KEY)
    }
    if (profile.value) {
      localStorage.setItem(AUTH_PROFILE_KEY, JSON.stringify(profile.value))
    } else {
      localStorage.removeItem(AUTH_PROFILE_KEY)
    }
  }

  async function login(payload: LoginPayload, bootstrap = false) {
    loading.value = true
    try {
      const response = await api.post<LoginResponse>(bootstrap ? '/auth/bootstrap-admin' : '/auth/login', payload)
      token.value = response.data.access_token
      persistState()
      await fetchProfile()
    } finally {
      loading.value = false
    }
  }

  async function fetchProfile() {
    const response = await api.get<AuthProfile>('/auth/me')
    profile.value = response.data
    persistState()
    return response.data
  }

  function logout() {
    token.value = ''
    profile.value = null
    persistState()
  }

  return {
    token,
    profile,
    loading,
    isAuthenticated,
    hasProfile,
    login,
    fetchProfile,
    logout,
  }
})

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY) || ''
}
