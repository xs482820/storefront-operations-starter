export type Category = {
  id: string
  name: string
  tone: string
}

export type Product = {
  id: string
  backendId?: number
  categoryId: string
  name: string
  subtitle: string
  price: number
  marketPrice?: number
  imageUrl?: string
  badge: string
  tone: 'mint' | 'cream' | 'peach' | 'blue' | 'lilac'
  stock: string
  colors: string[]
  sizes: string[]
  skus?: ProductSkuOption[]
  isFavorited?: boolean
}

export type ProductSkuOption = {
  skuId?: number
  code?: string
  color: string
  size: string
  price: number
  stock: number
  minQty: number
}

export type Benefit = {
  id: string
  label: string
  value: string
}

export const categories: Category[] = []
export const products: Product[] = []
export const benefits: Benefit[] = []
