import { useEffect, useMemo, useState } from 'react'
import Taro, { useDidShow } from '@tarojs/taro'
import { Image, Input, ScrollView, Text, View } from '@tarojs/components'
import { Empty } from '@antmjs/vantui/lib/empty'
import { Icon } from '@antmjs/vantui/lib/icon'
import { Popup } from '@antmjs/vantui/lib/popup'
import { batchSyncCart, clearCart as clearRemoteCart, fetchCart, removeCartItem } from '../../api/cart'
import { fetchProducts } from '../../api/catalog'
import { TopUtilityActions } from '../../components/TopUtilityActions'
import { ProductDetailSheet } from '../../components/ProductDetailSheet'
import { adaptCartItem, adaptCustomerProduct, findProductSku } from '../../domain/adapters'
import { type Product } from '../../mock/catalog'
import { makeCartKey, type CartItem, useCart } from '../../store/useCart'
import { fetchUnreadNotificationCount } from '../../services/notificationState'
import { previewImages } from '../../utils/imagePreview'
import { getSafeVars } from '../../utils/safeArea'
import { WholesaleWatermark } from '../../components/WholesaleWatermark'
import './index.scss'

const CHECKOUT_KEYS_KEY = 'baby_mall_fresh_checkout_keys'

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

type CartProductGroup = {
  product: Product
  items: CartItem[]
  keys: string[]
  quantity: number
  total: number
}

export default function CartPage() {
  const cart = useCart()
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [editingGroup, setEditingGroup] = useState<CartProductGroup | null>(null)
  const [skuDraft, setSkuDraft] = useState<Record<string, number>>({})
  const [activeSkuKey, setActiveSkuKey] = useState('')
  const [cartLoading, setCartLoading] = useState(true)
  const [cartError, setCartError] = useState('')
  const [selectedKeys, setSelectedKeys] = useState<string[]>([])
  const [profileUnread, setProfileUnread] = useState(0)

  useDidShow(() => {
    fetchUnreadNotificationCount()
      .then(setProfileUnread)
      .catch(() => setProfileUnread(0))
  })

  const cartGroups = useMemo(() => {
    const groupMap = new Map<string, CartProductGroup>()
    cart.items.forEach((item) => {
      const group = groupMap.get(item.productId)
      if (group) {
        group.items.push(item)
        group.keys.push(item.key)
        group.quantity += item.quantity
        group.total += item.unitPrice * item.quantity
      } else {
        groupMap.set(item.productId, {
          product: item.product,
          items: [item],
          keys: [item.key],
          quantity: item.quantity,
          total: item.unitPrice * item.quantity,
        })
      }
    })
    return Array.from(groupMap.values())
  }, [cart.items])

  const selectedItems = cart.items.filter((item) => selectedKeys.includes(item.key))
  const selectedCount = selectedItems.reduce((sum, item) => sum + item.quantity, 0)
  const selectedTotal = selectedItems.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0)
  const allSelected = cart.items.length > 0 && selectedKeys.length === cart.items.length

  const loadCart = () => {
    let alive = true
    cart.replace([])
    setCartError('')
    setCartLoading(true)
    fetchCart()
      .then(async (items) => {
        if (!alive) return
        const productMap = new Map<string, Product>()
        try {
          const products = await fetchProducts()
          products.map(adaptCustomerProduct).forEach((product) => productMap.set(product.id, product))
        } catch {
          // ponytail: cart remains usable; catalog only enriches thumbnails and full SKU options.
        }
        const nextItems = items.map((item) => {
          const cartItem = adaptCartItem(item)
          const catalogProduct = productMap.get(cartItem.productId)
          if (!catalogProduct) return cartItem
          return {
            ...cartItem,
            product: {
              ...catalogProduct,
              price: cartItem.unitPrice,
            },
          }
        })
        cart.replace(nextItems)
        setSelectedKeys(nextItems.map((item) => item.key))
      })
      .catch(() => {
        if (!alive) return
        cart.replace([])
        setSelectedKeys([])
        setCartError('清单加载失败，请稍后重试')
        Taro.showToast({ title: '清单加载失败', icon: 'none' })
      })
      .finally(() => {
        if (alive) setCartLoading(false)
      })
    return () => {
      alive = false
    }
  }

  useEffect(() => loadCart(), [])

  const goHome = () => Taro.redirectTo({ url: '/pages/home/index' })

  const goCheckout = () => {
    if (selectedCount <= 0) {
      Taro.showToast({ title: '请先选择商品', icon: 'none' })
      return
    }
    Taro.setStorageSync(CHECKOUT_KEYS_KEY, selectedKeys)
    Taro.navigateTo({ url: '/pages/checkout/index' })
  }

  const clearCart = () => {
    if (cart.count <= 0) return
    Taro.showModal({
      title: '清空清单',
      content: '确定要清空当前采购清单吗？',
      success: (result) => {
        if (!result.confirm) return
        cart.clear()
        setSelectedKeys([])
        clearRemoteCart()
          .then(() => Taro.showToast({ title: '清单已清空', icon: 'success' }))
          .catch(() => Taro.showToast({ title: '清单已清空', icon: 'success' }))
      },
    })
  }

  const toggleAll = () => {
    setSelectedKeys(allSelected ? [] : cart.items.map((item) => item.key))
  }

  const toggleGroup = (group: CartProductGroup) => {
    const groupSelected = group.keys.every((key) => selectedKeys.includes(key))
    setSelectedKeys((current) => {
      if (groupSelected) return current.filter((key) => !group.keys.includes(key))
      return Array.from(new Set([...current, ...group.keys]))
    })
  }

  const removeSelected = async () => {
    if (selectedKeys.length === 0) {
      Taro.showToast({ title: '请先勾选商品', icon: 'none' })
      return
    }
    const deletingItems = cart.items.filter((item) => selectedKeys.includes(item.key))
    deletingItems.forEach((item) => cart.setQuantity(item.product, 0, item.color, item.size))
    setSelectedKeys([])
    try {
      await Promise.all(deletingItems.filter((item) => item.skuId).map((item) => removeCartItem(Number(item.skuId))))
      Taro.showToast({ title: '已移出选中商品', icon: 'success' })
    } catch {
      Taro.showToast({ title: '已移出清单', icon: 'success' })
    }
  }

  const removeGroup = async (group: CartProductGroup) => {
    group.items.forEach((item) => cart.setQuantity(item.product, 0, item.color, item.size))
    setSelectedKeys((current) => current.filter((key) => !group.keys.includes(key)))
    try {
      await Promise.all(group.items.filter((item) => item.skuId).map((item) => removeCartItem(Number(item.skuId))))
      Taro.showToast({ title: '已移出清单', icon: 'success' })
    } catch {
      Taro.showToast({ title: '已移出清单', icon: 'success' })
    }
  }

  const confirmRemoveGroup = (group: CartProductGroup) => {
    Taro.showModal({
      title: '移出商品',
      content: `确定把「${group.product.name}」移出清单吗？`,
      success: (result) => {
        if (result.confirm) removeGroup(group)
      },
    })
  }

  const openSkuEditor = (group: CartProductGroup) => {
    const nextDraft: Record<string, number> = {}
    group.product.colors.forEach((color) => {
      group.product.sizes.forEach((size) => {
        const sku = findProductSku(group.product, color, size)
        if (!sku) return
        nextDraft[makeCartKey(group.product.id, color, size, sku.skuId)] = cart.getQuantity(group.product, color, size)
      })
    })
    setSkuDraft(nextDraft)
    setActiveSkuKey('')
    setEditingGroup(group)
  }

  const saveSkuEditor = async () => {
    if (!editingGroup) return
    const product = editingGroup.product
    const existingProductItems = cart.items.filter((item) => item.productId === product.id)
    const existingProductKeys = existingProductItems.map((item) => item.key)
    const existingSkuIds = existingProductItems
      .map((item) => item.skuId)
      .filter((skuId): skuId is number => Boolean(skuId))
    const positiveItems: { sku_id: number; quantity: number; selected: boolean }[] = []
    const positiveKeys: string[] = []
    const positiveSkuIds: number[] = []
    const invalidSku = product.skus?.find((sku) => {
      const quantity = skuDraft[makeCartKey(product.id, sku.color, sku.size, sku.skuId)] || 0
      return quantity > 0 && quantity < sku.minQty
    })
    if (invalidSku) {
      Taro.showToast({ title: `${invalidSku.color}/${invalidSku.size} 至少 ${invalidSku.minQty} 件起`, icon: 'none', duration: 1200 })
      return
    }

    existingProductItems.forEach((item) => {
      cart.setQuantity(item.product, 0, item.color, item.size)
    })
    product.colors.forEach((color) => {
      product.sizes.forEach((size) => {
        const sku = findProductSku(product, color, size)
        if (!sku?.skuId) return
        const key = makeCartKey(product.id, color, size, sku.skuId)
        const quantity = skuDraft[key] || 0
        cart.setQuantity(product, quantity, color, size)
        if (quantity > 0) {
          positiveItems.push({ sku_id: sku.skuId, quantity, selected: true })
          positiveKeys.push(key)
          positiveSkuIds.push(sku.skuId)
        }
      })
    })
    const zeroSkuIds = existingSkuIds.filter((skuId) => !positiveSkuIds.includes(skuId))
    setSelectedKeys((current) => {
      const withoutOldGroup = current.filter((key) => !existingProductKeys.includes(key))
      return Array.from(new Set([...withoutOldGroup, ...positiveKeys]))
    })
    setEditingGroup(null)
    try {
      await Promise.all(zeroSkuIds.map((skuId) => removeCartItem(skuId)))
      const result = positiveItems.length > 0 ? await batchSyncCart({ items: positiveItems, replace_existing: false }) : null
      loadCart()
      if (result?.issues?.length) {
        Taro.showToast({ title: result.issues[0].reason || '规格同步失败', icon: 'none' })
        return
      }
      Taro.showToast({ title: '规格已更新', icon: 'success' })
    } catch {
      loadCart()
      Taro.showToast({ title: '规格已更新', icon: 'success' })
    }
  }

  const renderSkuEditor = () => {
    if (!editingGroup) return null
    const product = editingGroup.product
    const hasMatrix = product.colors.length > 1 || product.sizes.length > 1
    const matrixStyle = { gridTemplateColumns: `104rpx repeat(${product.sizes.length}, minmax(146rpx, 1fr))` }
    const draftTotal = product.colors.reduce((sum, color) => (
      sum + product.sizes.reduce((rowSum, size) => {
        const sku = findProductSku(product, color, size)
        const key = makeCartKey(product.id, color, size, sku?.skuId)
        return rowSum + (skuDraft[key] || 0)
      }, 0)
    ), 0)
    const draftAmount = product.colors.reduce((sum, color) => (
      sum + product.sizes.reduce((rowSum, size) => {
        const sku = findProductSku(product, color, size)
        const key = makeCartKey(product.id, color, size, sku?.skuId)
        return rowSum + (skuDraft[key] || 0) * (sku ? sku.price : product.price)
      }, 0)
    ), 0)
    const stockWarnings = product.colors.flatMap((color) => (
      product.sizes.map((size) => {
        const sku = findProductSku(product, color, size)
        const key = makeCartKey(product.id, color, size, sku?.skuId)
        const warning = skuStockHint(sku?.stock || 0, skuDraft[key] || 0)
        return warning ? `${color} / ${size}：${warning}` : ''
      })
    )).filter(Boolean)
    return (
      <Popup show={Boolean(editingGroup)} position="bottom" round safeAreaInsetBottom={false} onClose={() => setEditingGroup(null)}>
        <View className="cart-sku-editor">
          <View className="cart-editor-head">
            <View>
              <Text className="cart-editor-title">{hasMatrix ? '选择规格与数量' : '选择数量'}</Text>
              <Text className="cart-editor-subtitle">{product.name}</Text>
            </View>
            <View className="cart-editor-close" onClick={() => setEditingGroup(null)}>×</View>
          </View>

          <View className="cart-editor-product">
            <View className={`cart-editor-thumb ${product.tone}`}>
              {product.imageUrl && (
                <Image
                  className="cart-editor-image"
                  src={product.imageUrl}
                  mode="aspectFill"
                  onClick={() => previewImages([product.imageUrl], product.imageUrl)}
                />
              )}
            </View>
            <Text className="cart-editor-tip">每个格子就是一个具体 SKU。点击格子输入数量，输入 0 即移出该规格。</Text>
          </View>

          <ScrollView scrollY className="cart-editor-scroll">
            <View className="cart-editor-content">
              <View className="cart-editor-matrix">
                <View className="cart-editor-row header" style={matrixStyle}>
                  <Text className="cart-editor-axis">款式 / 规格</Text>
                  {product.sizes.map((size) => <Text key={size} className="cart-editor-size">{size}</Text>)}
                </View>
                {product.colors.map((color) => (
                  <View key={color} className="cart-editor-row" style={matrixStyle}>
                    <Text className="cart-editor-color">{color}</Text>
                    {product.sizes.map((size) => {
                      const sku = findProductSku(product, color, size)
                      const key = makeCartKey(product.id, color, size, sku?.skuId)
                      const value = skuDraft[key] || 0
                      const valueText = String(value)
                      const stockHint = skuStockHint(sku?.stock || 0, value)
                      return (
                        <View key={`${color}-${size}`} className={`cart-editor-cell ${value > 0 ? 'active' : ''} ${sku ? '' : 'disabled'} ${stockHint ? 'warning' : ''}`}>
                          {sku ? (
                            <>
                              <Input
                                className="cart-editor-input"
                                type="number"
                                value={valueText}
                                selectionStart={activeSkuKey === key ? 0 : -1}
                                selectionEnd={activeSkuKey === key ? valueText.length : -1}
                                onFocus={() => setActiveSkuKey(key)}
                                onInput={(event) => {
                                  const nextValue = String(event.detail.value || '').replace(/\D/g, '')
                                  setSkuDraft((current) => ({ ...current, [key]: Number(nextValue || 0) }))
                                }}
                              />
                              <Text className="cart-editor-price">¥{money(sku.price)}</Text>
                              {value > 0 && <Text className="cart-editor-subtotal">小计 ¥{money(value * sku.price)}</Text>}
                            </>
                          ) : (
                            <Text className="cart-editor-disabled">-</Text>
                          )}
                        </View>
                      )
                    })}
                  </View>
                ))}
                {stockWarnings.length > 0 && (
                  <View className="cart-editor-warning-panel">
                    {stockWarnings.slice(0, 3).map((warning) => (
                      <Text key={warning}>{warning}</Text>
                    ))}
                    {stockWarnings.length > 3 && <Text>还有 {stockWarnings.length - 3} 个规格需要调整</Text>}
                  </View>
                )}
              </View>
            </View>
          </ScrollView>

          <View className="cart-editor-actions">
            <View className="cart-editor-summary">
              <Text>已选 {draftTotal} 件</Text>
              <Text>小计 ¥{money(draftAmount)}</Text>
            </View>
            <View className="cart-editor-secondary" onClick={() => setSkuDraft((current) => Object.fromEntries(Object.keys(current).map((key) => [key, 0])))}>
              清空本商品
            </View>
            <View className="cart-editor-primary" onClick={saveSkuEditor}>保存清单</View>
          </View>
        </View>
      </Popup>
    )
  }

  return (
    <View className="cart-page safe-page" style={getSafeVars()}>
      <WholesaleWatermark />
      <View className="cart-page-header">
        <View className="cart-page-heading">
          <Text className="cart-page-title">采购清单</Text>
          <Text className="cart-page-count">{selectedCount || cart.count} 件</Text>
        </View>
        <TopUtilityActions />
      </View>

      <ScrollView scrollY className="cart-page-scroll">
        <View className="cart-page-content">
          {cartLoading ? (
            <View className="cart-empty-card">
              <Empty description="正在加载清单..." />
            </View>
          ) : cart.items.length === 0 ? (
            <View className="cart-empty-card">
              <Empty description={cartError || '清单还是空的，先去选几件吧'} />
              <View className="cart-empty-actions">
                <Text onClick={goHome}>去选购</Text>
                <Text onClick={loadCart}>重新加载</Text>
              </View>
            </View>
          ) : (
            <>
              <View className="cart-bulk-bar">
                <Text onClick={toggleAll}>{allSelected ? '取消全选' : '全选'}</Text>
                <Text onClick={removeSelected}>移出已选</Text>
                <Text onClick={clearCart}>清空</Text>
              </View>
              <View className="cart-sku-list">
                {cartGroups.map((group) => {
                  const groupSelected = group.keys.every((key) => selectedKeys.includes(key))
                  const firstItem = group.items[0]
                  return (
                    <View
                      key={group.product.id}
                      className="cart-sku-row"
                      onClick={() => setSelectedProduct(group.product)}
                      onLongPress={() => confirmRemoveGroup(group)}
                    >
                      <View
                        className={`cart-sku-check ${groupSelected ? 'checked' : ''}`}
                        onClick={(event) => {
                          event.stopPropagation()
                          toggleGroup(group)
                        }}
                      >
                        {groupSelected ? '✓' : ''}
                      </View>
                      <View className={`cart-sku-thumb ${group.product.tone}`}>
                        {group.product.imageUrl && (
                          <Image
                            className="cart-sku-image"
                            src={group.product.imageUrl}
                            mode="aspectFill"
                            onClick={(event) => {
                              event.stopPropagation()
                              previewImages([group.product.imageUrl], group.product.imageUrl)
                            }}
                          />
                        )}
                      </View>
                      <View className="cart-sku-info">
                        <View className="cart-sku-title-row">
                          <Text className="cart-sku-name">{group.product.name}</Text>
                          <View className="cart-sku-actions">
                            <Text className="cart-sku-total">¥{group.total}</Text>
                            <Text
                              className="cart-sku-remove"
                              onClick={(event) => {
                                event.stopPropagation()
                                confirmRemoveGroup(group)
                              }}
                            >
                              移出
                            </Text>
                          </View>
                        </View>
                        <Text className="cart-sku-price">已选 {group.quantity} 件</Text>
                        <View
                          className="cart-spec-pill"
                          onClick={(event) => {
                            event.stopPropagation()
                            openSkuEditor(group)
                          }}
                        >
                          <Text className="cart-spec-copy">
                            {group.items.length === 1
                              ? `${firstItem.color} / ${firstItem.size} × ${firstItem.quantity}`
                              : `${group.items.length} 个规格，共 ${group.quantity} 件`}
                          </Text>
                          <Text className="cart-spec-edit">改</Text>
                        </View>
                      </View>
                    </View>
                  )
                })}
              </View>
            </>
          )}

          <View className="cart-bottom-spacer" />
        </View>
      </ScrollView>

      {cart.items.length > 0 && (
        <View className="cart-summary-card">
          <View>
            <Text className="cart-summary-label">已选 {selectedCount} 件</Text>
            <Text className="cart-summary-total">¥{selectedTotal}</Text>
          </View>
          <View className="cart-submit" onClick={goCheckout}>结算</View>
        </View>
      )}

      <View className="tabbar-backdrop" />
      <View className="cart-tabbar">
        <View className="cart-tab-item" onClick={goHome}>
          <Icon className="cart-tab-icon" name="shop-o" size="36rpx" />
          <Text className="cart-tab-label">选购</Text>
        </View>
        <View className="cart-tab-item active">
          <Icon className="cart-tab-icon" name="shopping-cart-o" size="36rpx" />
          <Text className="cart-tab-label">清单</Text>
          {cart.count > 0 && <Text className="cart-tab-badge">{cart.count}</Text>}
        </View>
        <View className="cart-tab-item" onClick={() => Taro.redirectTo({ url: '/pages/profile/index' })}>
          <Icon className="cart-tab-icon" name="user-o" size="36rpx" />
          <Text className="cart-tab-label">个人</Text>
          {profileUnread > 0 && <Text className="cart-tab-dot" />}
        </View>
      </View>

      <ProductDetailSheet show={Boolean(selectedProduct)} product={selectedProduct} showWholesaleWatermark onClose={() => setSelectedProduct(null)} />
      {renderSkuEditor()}
    </View>
  )
}
