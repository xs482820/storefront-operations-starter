import { useSyncExternalStore } from 'react'
import { removeCartItem, upsertCartItem } from '../api/cart'
import { findProductSku } from '../domain/adapters'
import { products, type Product } from '../mock/catalog'

export type CartKey = string
export type CartItem = {
  key: CartKey
  product: Product
  productId: string
  skuId?: number
  color: string
  size: string
  quantity: number
  unitPrice: number
}
export type CartMap = Record<CartKey, CartItem>

const listeners = new Set<() => void>()
let cart: CartMap = {}

function emit() {
  listeners.forEach((listener) => listener())
}

function getSnapshot() {
  return cart
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function makeCartKey(productId: string, color = '默认', size = '默认', skuId?: number) {
  return skuId ? `sku__${skuId}` : `${productId}__${color}__${size}`
}

export function parseCartKey(key: string) {
  if (key.startsWith('sku__')) return { productId: '', color: '默认', size: '默认', skuId: Number(key.replace('sku__', '')) }
  const [productId, color = '默认', size = '默认'] = key.split('__')
  return { productId, color, size }
}

function resolveProduct(input: Product | string) {
  return typeof input === 'string' ? products.find((item) => item.id === input) : input
}

function setQuantity(productInput: Product | string, quantity: number, color = '默认', size = '默认') {
  const product = resolveProduct(productInput)
  if (!product) return
  const sku = findProductSku(product, color, size)
  const key = makeCartKey(product.id, color, size, sku?.skuId)
  const next = { ...cart }
  const nextQuantity = sku && quantity > 0 && quantity < sku.minQty ? sku.minQty : quantity
  if (nextQuantity <= 0) {
    delete next[key]
  } else {
    next[key] = {
      key,
      product,
      productId: product.id,
      skuId: sku?.skuId,
      color,
      size,
      quantity: nextQuantity,
      unitPrice: sku ? sku.price : product.price,
    }
  }
  cart = next
  emit()
}

export function replaceCartItems(items: CartItem[]) {
  cart = items.reduce<CartMap>((next, item) => ({ ...next, [item.key]: item }), {})
  emit()
}

export function getCartItemsSnapshot() {
  return Object.values(cart)
}

export function syncProductQuantity(product: Product, color = '默认', size = '默认', quantity: number) {
  const sku = findProductSku(product, color, size)
  if (!sku?.skuId) return Promise.resolve()
  const nextQuantity = quantity > 0 && quantity < sku.minQty ? sku.minQty : quantity
  if (nextQuantity <= 0) return removeCartItem(sku.skuId).then(() => undefined)
  return upsertCartItem(sku.skuId, { quantity: nextQuantity, selected: nextQuantity > 0 }).then(() => undefined)
}

export function useCart() {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, getSnapshot)

  const items = Object.values(snapshot)

  const count = items.reduce((sum, item) => sum + item.quantity, 0)
  const total = items.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0)

  const getQuantity = (productInput: Product | string, color = '默认', size = '默认') => {
    const product = resolveProduct(productInput)
    if (!product) return 0
    const sku = findProductSku(product, color, size)
    return snapshot[makeCartKey(product.id, color, size, sku?.skuId)]?.quantity || 0
  }

  const add = (productInput: Product | string, color = '默认', size = '默认', delta = 1) => {
    setQuantity(productInput, getQuantity(productInput, color, size) + delta, color, size)
  }

  const remove = (productInput: Product | string, color = '默认', size = '默认') => {
    setQuantity(productInput, getQuantity(productInput, color, size) - 1, color, size)
  }

  const clear = () => {
    cart = {}
    emit()
  }

  const replace = (nextItems: CartItem[]) => replaceCartItems(nextItems)

  return { cart: snapshot, items, count, total, getQuantity, setQuantity, add, remove, clear, replace, syncProductQuantity }
}
