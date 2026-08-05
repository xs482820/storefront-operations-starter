import { http } from '../services/http'

export type CustomerSearchHistory = {
  id: number
  keyword: string
  created_at: string
}

export function fetchSearchHistories() {
  return http.get<CustomerSearchHistory[]>('/customer/search-histories')
}

export function addSearchHistory(keyword: string) {
  return http.post<CustomerSearchHistory>('/customer/search-histories', { keyword })
}

export function clearSearchHistories() {
  return http.delete<{ cleared: number }>('/customer/search-histories')
}
