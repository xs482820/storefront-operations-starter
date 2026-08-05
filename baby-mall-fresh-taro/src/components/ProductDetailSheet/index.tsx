import Taro from '@tarojs/taro'
import { Image, Input, ScrollView, Text, View } from '@tarojs/components'
import { Popup } from '@antmjs/vantui/lib/popup'
import { Tag } from '@antmjs/vantui/lib/tag'
import { useEffect, useMemo, useState } from 'react'
import { addFavorite, removeFavorite } from '../../api/favorite'
import { batchSyncCart, fetchCart, removeCartItem } from '../../api/cart'
import { type Product } from '../../mock/catalog'
import { adaptCartItem, findProductSku } from '../../domain/adapters'
import { makeCartKey, useCart } from '../../store/useCart'
import { WholesaleWatermark } from '../WholesaleWatermark'
import './index.scss'

type ProductDetailSheetProps = {
  product: Product | null
  show: boolean
  onClose: () => void
  onFavoriteChange?: (product: Product, favorited: boolean) => void
  showWholesaleWatermark?: boolean
}

function money(value = 0) {
  return Number(value || 0).toFixed(2)
}

function skuStockHint(stock = 0, quantity = 0) {
  if (quantity <= 0) return ''
  if (stock <= 0) return '该规格暂不可售'
  const remaining = stock - quantity
  if (remaining < 0) return '超过可售库存，请减少数量'
  const threshold = Math.max(1, Math.floor(stock * 0.1))
  return remaining <= threshold ? `该规格仅剩 ${remaining} 件` : ''
}

export function ProductDetailSheet({ product, show, onClose, onFavoriteChange, showWholesaleWatermark = false }: ProductDetailSheetProps) {
  const cart = useCart()
  const [activeSkuKey, setActiveSkuKey] = useState('')
  const [draft, setDraft] = useState<Record<string, number>>({})
  const [favorited, setFavorited] = useState(false)
  const cartSignature = useMemo(
    () => cart.items.map((item) => `${item.key}:${item.quantity}`).sort().join('|'),
    [cart.items],
  )

  useEffect(() => {
    if (!product || !show) return
    const nextDraft: Record<string, number> = {}
    product.colors.forEach((color) => {
      product.sizes.forEach((size) => {
        const sku = findProductSku(product, color, size)
        nextDraft[makeCartKey(product.id, color, size, sku?.skuId)] = cart.getQuantity(product, color, size)
      })
    })
    setDraft(nextDraft)
    setFavorited(Boolean(product.isFavorited))
  }, [product?.id, show, cartSignature])

  const selectedTotal = useMemo(() => Object.values(draft).reduce((sum, value) => sum + value, 0), [draft])
  const selectedAmount = useMemo(() => {
    if (!product) return 0
    return product.colors.reduce((sum, color) => (
      sum + product.sizes.reduce((rowSum, size) => {
        const sku = findProductSku(product, color, size)
        const quantity = draft[makeCartKey(product.id, color, size, sku?.skuId)] || 0
        return rowSum + quantity * (sku ? sku.price : product.price)
      }, 0)
    ), 0)
  }, [draft, product])

  if (!product) return null
  const matrixStyle = { gridTemplateColumns: `96rpx repeat(${product.sizes.length}, minmax(0, 1fr))` }
  const stockWarnings = product.colors.flatMap((color) => (
    product.sizes.map((size) => {
      const sku = findProductSku(product, color, size)
      const skuKey = makeCartKey(product.id, color, size, sku?.skuId)
      const warning = skuStockHint(sku?.stock || 0, draft[skuKey] || 0)
      return warning ? `${color} / ${size}：${warning}` : ''
    })
  )).filter(Boolean)

  const commitDraft = () => {
    if (selectedTotal <= 0) {
      Taro.showToast({ title: '请先输入数量', icon: 'none', duration: 900 })
      return false
    }
    const invalidSku = product.skus?.find((sku) => {
      const quantity = draft[makeCartKey(product.id, sku.color, sku.size, sku.skuId)] || 0
      return quantity > 0 && quantity < sku.minQty
    })
    if (invalidSku) {
      Taro.showToast({ title: `${invalidSku.color}/${invalidSku.size} 至少 ${invalidSku.minQty} 件起`, icon: 'none', duration: 1200 })
      return false
    }
    product.colors.forEach((color) => {
      product.sizes.forEach((size) => {
        const sku = findProductSku(product, color, size)
        const quantity = draft[makeCartKey(product.id, color, size, sku?.skuId)] || 0
        cart.setQuantity(product, quantity, color, size)
      })
    })
    return true
  }

  const syncDraftToRemote = async () => {
    let existingSkuIds = cart.items
      .filter((item) => item.productId === product.id)
      .map((item) => item.skuId)
      .filter((skuId): skuId is number => Boolean(skuId))
    try {
      const remoteItems = await fetchCart()
      existingSkuIds = remoteItems
        .filter((item) => String(item.product_id) === product.id)
        .map((item) => item.sku_id)
    } catch {
      // ponytail: local cart is good enough to remove stale SKUs when the refresh is unavailable.
    }
    const items = product.colors.flatMap((color) => product.sizes.map((size) => {
      const sku = findProductSku(product, color, size)
      if (!sku?.skuId) return null
      const quantity = draft[makeCartKey(product.id, color, size, sku.skuId)] || 0
      if (quantity <= 0) return null
      return { sku_id: sku.skuId, quantity, selected: quantity > 0 }
    })).filter(Boolean) as { sku_id: number; quantity: number; selected: boolean }[]
    const nextSkuIds = items.map((item) => item.sku_id)
    const removedSkuIds = existingSkuIds.filter((skuId) => !nextSkuIds.includes(skuId))
    await Promise.all(removedSkuIds.map((skuId) => removeCartItem(skuId)))
    const result = items.length > 0 ? await batchSyncCart({ items, replace_existing: false }) : null
    const remoteCartItems = result ? result.cart_items : (removedSkuIds.length > 0 ? await fetchCart() : null)
    if (remoteCartItems) cart.replace(remoteCartItems.map(adaptCartItem))
    if (result?.issues?.length) {
      throw new Error(result.issues[0].reason || '清单同步失败')
    }
  }

  const buyNow = async () => {
    if (!commitDraft()) return
    try {
      await syncDraftToRemote()
    } catch (error) {
      Taro.showToast({ title: error instanceof Error ? error.message : '清单同步失败', icon: 'none' })
      return
    }
    onClose()
    Taro.navigateTo({ url: '/pages/checkout/index' })
  }

  const toggleFavorite = async () => {
    const nextFavorited = !favorited
    setFavorited(nextFavorited)
    try {
      if (nextFavorited) {
        await addFavorite(product.backendId || product.id)
      } else {
        await removeFavorite(product.backendId || product.id)
      }
      onFavoriteChange?.(product, nextFavorited)
      Taro.showToast({ title: nextFavorited ? '已收藏' : '已取消收藏', icon: 'success', duration: 800 })
    } catch (error) {
      setFavorited(!nextFavorited)
      Taro.showToast({ title: error instanceof Error ? error.message : '收藏暂时没有成功', icon: 'none', duration: 1200 })
    }
  }

  return (
    <Popup show={show} position="bottom" round safeAreaInsetBottom={false} onClose={onClose}>
      <View className="product-detail-sheet">
        {showWholesaleWatermark && <WholesaleWatermark contained />}
        <View className="detail-close-button" onClick={onClose}>
          ×
        </View>

        <ScrollView scrollY className="detail-scroll">
          <View className="detail-scroll-content">
            <View className={`detail-hero ${product.tone}`}>
              {product.imageUrl && <Image className="detail-hero-image" src={product.imageUrl} mode="aspectFill" />}
              <Tag type={product.categoryId === 'bulk' ? 'primary' : 'success'} round>
                {product.badge}
              </Tag>
            </View>
            <View className="detail-body">
              <View className="detail-title-row">
                <View className="detail-title-copy">
                  <Text className="detail-name">{product.name}</Text>
                  <Text className="detail-subtitle">{product.subtitle}</Text>
                </View>
              </View>

              <View className="detail-price-row">
                <Text className="detail-price">¥{product.price}<Text className="detail-price-suffix"> 起</Text></Text>
                {product.marketPrice && <Text className="detail-market-price">¥{product.marketPrice}</Text>}
              </View>

              <View className="sku-matrix">
                <View className="sku-title-row">
                  <Text className="sku-title">选择规格和数量</Text>
                  <Text className="sku-help">点格子输入数量，确认后自动进入清单</Text>
                </View>
                <View className="sku-header-row" style={matrixStyle}>
                  <Text className="sku-axis-label">款式</Text>
                  {product.sizes.map((size) => (
                    <Text key={size} className="sku-size-label">
                      {size}
                    </Text>
                  ))}
                </View>
                {product.colors.map((color) => (
                  <View key={color} className="sku-row" style={matrixStyle}>
                    <Text className="sku-color-label">{color}</Text>
                    {product.sizes.map((size) => {
                      const sku = findProductSku(product, color, size)
                      const skuKey = makeCartKey(product.id, color, size, sku?.skuId)
                      const quantity = draft[skuKey] || 0
                      const valueText = String(quantity)
                      const stockHint = skuStockHint(sku?.stock || 0, quantity)
                      return (
                        <View key={`${color}-${size}`} className={`sku-cell ${quantity ? 'active' : ''} ${stockHint ? 'warning' : ''}`}>
                          <Input
                            className="sku-input"
                            type="number"
                            value={valueText}
                            selectionStart={activeSkuKey === skuKey ? 0 : -1}
                            selectionEnd={activeSkuKey === skuKey ? valueText.length : -1}
                            onFocus={() => setActiveSkuKey(skuKey)}
                            onInput={(event) => {
                              const nextValue = String(event.detail.value || '').replace(/\D/g, '')
                              setDraft((current) => ({ ...current, [skuKey]: Number(nextValue || 0) }))
                            }}
                          />
                          {sku && <Text className="sku-price">¥{money(sku.price)}</Text>}
                          {quantity > 0 && <Text className="sku-subtotal">小计 ¥{money(quantity * (sku ? sku.price : product.price))}</Text>}
                        </View>
                      )
                    })}
                  </View>
                ))}
                {stockWarnings.length > 0 && (
                  <View className="sku-warning-panel">
                    {stockWarnings.slice(0, 3).map((warning) => (
                      <Text key={warning}>{warning}</Text>
                    ))}
                    {stockWarnings.length > 3 && <Text>还有 {stockWarnings.length - 3} 个规格需要调整</Text>}
                  </View>
                )}
                <View className="sku-summary">
                  <Text>已选 {selectedTotal} 件</Text>
                  <Text>小计 ¥{money(selectedAmount)}</Text>
                </View>
              </View>

              <View className="detail-note-card">
                <Text className="detail-note-title">采购提示</Text>
                <Text className="detail-note-text">可直接点某个 SKU 单元格输入数量，系统会在接近售罄或超量时提前提醒。</Text>
              </View>
            </View>
          </View>
        </ScrollView>

        <View className="detail-action-bar">
          <View className={`detail-action-favorite ${favorited ? 'active' : ''}`} onClick={toggleFavorite}>
            {favorited ? '已收藏' : '收藏'}
          </View>
          <View
            className="detail-action-add"
            onClick={async () => {
              if (!commitDraft()) return
              try {
                await syncDraftToRemote()
              } catch (error) {
                Taro.showToast({ title: error instanceof Error ? error.message : '清单同步失败', icon: 'none' })
                return
              }
              Taro.showToast({ title: `已加入 ${selectedTotal} 件`, icon: 'success', duration: 900 })
              onClose()
            }}
          >
            加入清单 · ¥{money(selectedAmount)}
          </View>
          <View className="detail-action-buy" onClick={buyNow}>
            立即购买
          </View>
        </View>
      </View>
    </Popup>
  )
}
