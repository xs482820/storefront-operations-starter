import { http } from '../services/http'

export type CustomerAddress = {
  id: number
  contact_name: string
  phone: string
  region: string
  detail: string
  tag: string
  is_default: boolean
  created_at: string
}

export type CustomerAddressInput = {
  contact_name: string
  phone: string
  region: string
  detail: string
  tag?: string
  is_default?: boolean
}

export function fetchAddresses() {
  return http.get<CustomerAddress[]>('/customer/addresses')
}

export function createAddress(payload: CustomerAddressInput) {
  return http.post<CustomerAddress>('/customer/addresses', payload)
}

export function updateAddress(addressId: number | string, payload: CustomerAddressInput) {
  return http.patch<CustomerAddress>(`/customer/addresses/${addressId}`, payload)
}

export function deleteAddress(addressId: number | string) {
  return http.delete<{ removed: number }>(`/customer/addresses/${addressId}`)
}
