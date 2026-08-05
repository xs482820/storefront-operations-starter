import { http } from '../services/http'
import { type CustomerProduct } from './catalog'

export type CustomerFavorite = {
  id: number
  product_id: number
  created_at: string
  product: CustomerProduct
}

export function fetchFavorites() {
  return http.get<CustomerFavorite[]>('/customer/favorites')
}

export function addFavorite(productId: number | string) {
  return http.post<CustomerFavorite>(`/customer/favorites/${productId}`)
}

export function removeFavorite(productId: number | string) {
  return http.delete<{ removed: number }>(`/customer/favorites/${productId}`)
}
