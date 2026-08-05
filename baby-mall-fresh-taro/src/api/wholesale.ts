import { http } from '../services/http'

export type WholesaleApplicationInput = {
  company_name?: string | null
  store_name?: string | null
  contact_name?: string | null
  contact_phone?: string | null
  business_license_url?: string | null
  remark?: string | null
}

export type WholesaleApplication = WholesaleApplicationInput & {
  id: number
  status: 'pending' | 'approved' | 'rejected' | string
  effective_status: 'pending' | 'approved' | 'rejected' | 'revoked' | string
  review_note?: string | null
  created_at: string
}

export function createWholesaleApplication(payload: WholesaleApplicationInput) {
  return http.post<WholesaleApplication>('/customer/wholesale-applications', payload)
}

export function fetchWholesaleApplications() {
  return http.get<WholesaleApplication[]>('/customer/wholesale-applications')
}
