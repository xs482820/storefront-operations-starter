import { useEffect, useMemo, useState } from 'react'
import Taro from '@tarojs/taro'
import { Image, Input, ScrollView, Text, View } from '@tarojs/components'
import { Empty } from '@antmjs/vantui/lib/empty'
import { Icon } from '@antmjs/vantui/lib/icon'
import { fetchAddresses } from '../../api/address'
import { fetchStorefrontConfig } from '../../api/catalog'
import { clearCart as clearRemoteCart, removeCartItem } from '../../api/cart'
import {
  createOrder as createApiOrder,
  previewCheckout,
  type CheckoutPayload,
  type CheckoutPreview,
  type ShippingChannel,
} from '../../api/order'
import { ProductDetailSheet } from '../../components/ProductDetailSheet'
import { WholesaleWatermark } from '../../components/WholesaleWatermark'
import { adaptAddress, adaptCustomerOrder } from '../../domain/adapters'
import { type Product } from '../../mock/catalog'
import { runWechatPaymentFlow } from '../../services/paymentFlow'
import { requestOrderSubscribeMessages } from '../../services/subscribeMessage'
import { useCart } from '../../store/useCart'
import { type Order, useCommerce } from '../../store/useCommerce'
import { previewImages } from '../../utils/imagePreview'
import { getSafeVars } from '../../utils/safeArea'
import './index.scss'

const CHECKOUT_KEYS_KEY = 'baby_mall_fresh_checkout_keys'

const shippingOptions: Array<{ value: ShippingChannel; label: string; desc: string }> = [
  { value: 'delivery', label: '配送', desc: '配送费已按订单规则计入，具体承运方式由店内安排' },
  { value: 'pickup', label: '到店自提', desc: '到店取货，具体时间请以店内确认内容为准' },
]

function money(value: string | number | undefined, fallback = 0) {
  const next = Number(value ?? fallback)
  return Number.isFinite(next) ? next.toFixed(2) : fallback.toFixed(2)
}

export default function CheckoutPage() {
  const cart = useCart()
  const commerce = useCommerce()
  const [checkoutKeys, setCheckoutKeys] = useState<string[]>([])
  const [selectedAddressId, setSelectedAddressId] = useState('')
  const [shippingChannel, setShippingChannel] = useState<ShippingChannel>('delivery')
  const [remark, setRemark] = useState('')
  const [preview, setPreview] = useState<CheckoutPreview | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [addressLoading, setAddressLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [paying, setPaying] = useState(false)
  const [submittedOrder, setSubmittedOrder] = useState<Order | null>(null)
  const [paidOrder, setPaidOrder] = useState<Order | null>(null)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [pickupSite, setPickupSite] = useState('')

  useEffect(() => {
    let alive = true
    fetchAddresses()
      .then((items) => {
        if (alive) commerce.replaceAddresses(items.map(adaptAddress))
      })
      .catch(() => undefined)
      .finally(() => {
        if (alive) setAddressLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    const storedKeys = Taro.getStorageSync(CHECKOUT_KEYS_KEY)
    setCheckoutKeys(Array.isArray(storedKeys) ? storedKeys.filter((item) => typeof item === 'string') : [])
  }, [])

  useEffect(() => {
    let alive = true
    fetchStorefrontConfig()
      .then((config) => {
        if (!alive) return
        const storeAddress = config.store_info?.address?.trim()
        const pickupNote = config.store_info?.pickup_note?.trim()
        setPickupSite([storeAddress, pickupNote].filter(Boolean).join('，'))
      })
      .catch(() => undefined)
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    if (!selectedAddressId && commerce.defaultAddress) setSelectedAddressId(commerce.defaultAddress.id)
  }, [commerce.defaultAddress?.id, selectedAddressId])

  const selectedAddress = useMemo(() => {
    return commerce.addresses.find((item) => item.id === selectedAddressId) || commerce.defaultAddress
  }, [commerce.addresses, commerce.defaultAddress, selectedAddressId])

  const checkoutItems = useMemo(() => {
    return checkoutKeys.length > 0 ? cart.items.filter((item) => checkoutKeys.includes(item.key)) : cart.items
  }, [cart.items, checkoutKeys])

  const isPickup = shippingChannel === 'pickup'
  const checkoutCount = checkoutItems.reduce((sum, item) => sum + item.quantity, 0)
  const localAmount = checkoutItems.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0)
  const payableAmount = preview ? Number(preview.payable_amount) : localAmount
  const canSubmit = Boolean(preview?.can_submit) && checkoutItems.length > 0 && (isPickup || Boolean(selectedAddress))
  const checkoutSignature = checkoutItems.map((item) => `${item.skuId || item.key}:${item.quantity}`).join('|')

  const buildPayload = (): CheckoutPayload | null => {
    const items = checkoutItems
      .filter((item) => item.skuId)
      .map((item) => ({ sku_id: Number(item.skuId), quantity: item.quantity }))
    if (items.length !== checkoutItems.length || items.length === 0) return null
    if (isPickup) {
      return {
        items,
        shipping_channel: 'pickup',
        payment_method: 'wechat_pay',
        shipping_recipient: selectedAddress?.name || '到店自提',
        shipping_phone: selectedAddress?.phone || null,
        shipping_address: pickupSite ? `到店自提：${pickupSite}` : '到店自提',
        note: remark.trim() || null,
      }
    }
    if (!selectedAddress) return null
    return {
      items,
      shipping_channel: 'delivery',
      payment_method: 'wechat_pay',
      shipping_recipient: selectedAddress.name,
      shipping_phone: selectedAddress.phone,
      shipping_address: `${selectedAddress.region} ${selectedAddress.detail}`.trim(),
      note: remark.trim() || null,
    }
  }

  useEffect(() => {
    let alive = true
    const payload = buildPayload()
    if (!payload) {
      setPreview(null)
      return undefined
    }
    setPreviewing(true)
    previewCheckout(payload)
      .then((nextPreview) => {
        if (alive) setPreview(nextPreview)
      })
      .catch((error) => {
        if (!alive) return
        setPreview(null)
        Taro.showToast({ title: error instanceof Error ? error.message : '结算预览失败', icon: 'none' })
      })
      .finally(() => {
        if (alive) setPreviewing(false)
      })
    return () => {
      alive = false
    }
  }, [checkoutSignature, selectedAddress?.id, shippingChannel, remark, pickupSite])

  const removeCheckedOutItems = () => {
    if (checkoutKeys.length === 0 || checkoutKeys.length === cart.items.length) {
      cart.clear()
      clearRemoteCart().catch(() => undefined)
      Taro.removeStorageSync(CHECKOUT_KEYS_KEY)
      return
    }
    checkoutItems.forEach((item) => {
      cart.setQuantity(item.product, 0, item.color, item.size)
      if (item.skuId) removeCartItem(item.skuId).catch(() => undefined)
    })
    Taro.removeStorageSync(CHECKOUT_KEYS_KEY)
  }

  const submitOrder = async () => {
    if (checkoutCount <= 0) {
      Taro.showToast({ title: '没有可提交的商品', icon: 'none' })
      return
    }
    if (!isPickup && !selectedAddress) {
      Taro.showToast({ title: '请先添加收货地址', icon: 'none' })
      return
    }
    const payload = buildPayload()
    if (!payload) {
      Taro.showToast({ title: '商品规格信息不完整，请回清单检查', icon: 'none' })
      return
    }
    if (!preview?.can_submit) {
      Taro.showToast({ title: preview?.issues?.[0] || '当前清单暂不可提交', icon: 'none' })
      return
    }
    setSubmitting(true)
    try {
      const apiOrder = await createApiOrder(payload)
      const order = adaptCustomerOrder(apiOrder)
      commerce.upsertOrder(order)
      removeCheckedOutItems()
      setSubmittedOrder(order)
      requestOrderSubscribeMessages().catch(() => undefined)
      Taro.showToast({ title: '订单已创建', icon: 'success' })
    } catch (error) {
      Taro.showToast({ title: error instanceof Error ? error.message : '订单提交失败', icon: 'none' })
    } finally {
      setSubmitting(false)
    }
  }

  const payOrder = async (order: Order) => {
    setPaying(true)
    try {
      if (!order.backendId) {
        const localOrder = commerce.payOrder(order.id)
        if (localOrder) setPaidOrder(localOrder)
        return
      }
      const result = await runWechatPaymentFlow(order.backendId)
      if (result.status === 'paid') {
        commerce.upsertOrder(result.order)
        setSubmittedOrder(result.order)
        setPaidOrder(result.order)
        Taro.showToast({ title: result.message, icon: 'success' })
        return
      }
      Taro.showToast({ title: result.message, icon: 'none' })
    } catch (error) {
      Taro.showToast({ title: error instanceof Error ? error.message : '支付未完成，订单已保留', icon: 'none' })
    } finally {
      setPaying(false)
    }
  }

  const renderHeader = (title: string) => (
    <View className="checkout-header">
      <View
        className="checkout-back-button"
        onClick={() => (submittedOrder ? Taro.redirectTo({ url: '/pages/profile/index?view=orders&status=待支付' }) : Taro.navigateBack())}
      >
        <Text>‹</Text>
      </View>
      <Text className="checkout-title">{title}</Text>
    </View>
  )

  const copyOrderNo = (orderNo: string) => {
    Taro.setClipboardData({
      data: orderNo,
      success: () => Taro.showToast({ title: '订单号已复制', icon: 'success' }),
    })
  }

  const renderOrderNoValue = (orderNo: string) => (
    <View className="checkout-copyable-no">
      <Text>{orderNo}</Text>
      <View className="checkout-copy-icon" onClick={() => copyOrderNo(orderNo)}>
        <Icon name="description" size="24rpx" />
      </View>
    </View>
  )

  if (paidOrder) {
    return (
      <View className="checkout-page safe-page" style={getSafeVars()}>
        <WholesaleWatermark />
        {renderHeader('支付结果')}
        <View className="checkout-success-card">
          <View className="checkout-success-icon">✓</View>
          <Text className="checkout-success-title">订单已进入处理流程</Text>
          <Text className="checkout-success-copy">如果微信支付已完成，订单会继续进入处理流程；你也可以在订单详情里查看最新进度。</Text>
          <View className="checkout-success-meta"><Text>订单号</Text>{renderOrderNoValue(paidOrder.id)}</View>
          <View className="checkout-success-meta"><Text>应付金额</Text><Text>¥{money(paidOrder.amount)}</Text></View>
        </View>
        <View className="checkout-success-actions">
          <View className="checkout-secondary-button" onClick={() => Taro.redirectTo({ url: '/pages/home/index' })}>继续选购</View>
          <View className="checkout-primary-button" onClick={() => Taro.redirectTo({ url: '/pages/profile/index?view=orders' })}>查看订单</View>
        </View>
      </View>
    )
  }

  if (submittedOrder) {
    return (
      <View className="checkout-page safe-page" style={getSafeVars()}>
        <WholesaleWatermark />
        {renderHeader('等待支付')}
        <View className="checkout-success-card">
          <View className="checkout-pay-icon">¥</View>
          <Text className="checkout-success-title">订单已创建</Text>
          <Text className="checkout-success-copy">现在退出也没关系，稍后可以在“我的订单 - 待支付”继续支付或取消订单。</Text>
          <View className="checkout-success-meta"><Text>订单号</Text>{renderOrderNoValue(submittedOrder.id)}</View>
          <View className="checkout-success-meta"><Text>待支付</Text><Text>¥{money(submittedOrder.amount)}</Text></View>
        </View>
        <View className="checkout-success-actions">
          <View className="checkout-secondary-button" onClick={() => Taro.redirectTo({ url: '/pages/profile/index?view=orders&status=待支付' })}>稍后支付</View>
          <View className="checkout-primary-button" onClick={paying ? undefined : () => payOrder(submittedOrder)}>
            {paying ? '支付中...' : '立即支付'}
          </View>
        </View>
      </View>
    )
  }

  return (
    <View className="checkout-page safe-page" style={getSafeVars()}>
      <WholesaleWatermark />
      {renderHeader('确认订单')}

      <ScrollView scrollY className="checkout-scroll">
        <View className="checkout-content">
          {checkoutItems.length === 0 ? (
            <View className="checkout-empty-card">
              <Empty description="还没有可结算商品" />
              <View className="checkout-primary-button" onClick={() => Taro.redirectTo({ url: '/pages/home/index' })}>去选购</View>
            </View>
          ) : (
            <>
              {!isPickup && <View className="checkout-address-card">
                <View className="checkout-section-head">
                  <Text className="checkout-card-title">配送信息</Text>
                  <Text
                    className="checkout-section-action"
                    onClick={() => Taro.navigateTo({ url: `/pages/profile/index?view=addresses&returnTo=${encodeURIComponent('/pages/checkout/index')}` })}
                  >
                    管理
                  </Text>
                </View>
                {addressLoading ? (
                  <Text className="checkout-address-sub">正在加载收货地址...</Text>
                ) : selectedAddress ? (
                  <>
                    <Text className="checkout-address">{selectedAddress.region} {selectedAddress.detail}</Text>
                    <Text className="checkout-address-sub">{selectedAddress.name} {selectedAddress.phone}</Text>
                  </>
                ) : (
                  <Text className="checkout-address-sub">送货需要填写地址，店内会再与您确认配送安排。</Text>
                )}
                {commerce.addresses.length > 1 && (
                  <View className="checkout-address-list">
                    {commerce.addresses.map((address) => (
                      <View
                        key={address.id}
                        className={`checkout-address-chip ${selectedAddress?.id === address.id ? 'active' : ''}`}
                        onClick={() => setSelectedAddressId(address.id)}
                      >
                        {address.name}
                      </View>
                    ))}
                  </View>
                )}
              </View>}

              <View className="checkout-shipping-card">
                <Text className="checkout-card-title">配送方式</Text>
                <View className="checkout-shipping-grid">
                  {shippingOptions.map((option) => (
                    <View
                      key={option.value}
                      className={`checkout-shipping-option ${shippingChannel === option.value ? 'active' : ''}`}
                      onClick={() => setShippingChannel(option.value)}
                    >
                      <Text className="checkout-shipping-title">{option.label}</Text>
                      <Text className="checkout-shipping-desc">{option.desc}</Text>
                    </View>
                  ))}
                </View>
              </View>

              {isPickup && (
                <View className="checkout-address-card">
                  <View className="checkout-section-head">
                    <Text className="checkout-card-title">自提信息</Text>
                  </View>
                  <Text className="checkout-address">{pickupSite || '到店自提，具体地址请以门店通知为准'}</Text>
                  <Text className="checkout-address-sub">自提订单不需要选择收货地址。</Text>
                </View>
              )}

              <View className="checkout-list">
                <Text className="checkout-card-title">商品明细</Text>
                {checkoutItems.map((item) => (
                  <View key={item.key} className="checkout-row" onClick={() => setSelectedProduct(item.product)}>
                    <View className={`checkout-thumb ${item.product.tone}`}>
                      {item.product.imageUrl && (
                        <Image
                          className="checkout-thumb-image"
                          src={item.product.imageUrl}
                          mode="aspectFill"
                          onClick={(event) => {
                            event.stopPropagation()
                            previewImages([item.product.imageUrl], item.product.imageUrl)
                          }}
                        />
                      )}
                    </View>
                    <View className="checkout-info">
                      <Text className="checkout-name">{item.product.name}</Text>
                      <Text className="checkout-spec">{item.color} / {item.size} × {item.quantity}</Text>
                    </View>
                    <Text className="checkout-price">¥{money(item.unitPrice * item.quantity)}</Text>
                  </View>
                ))}
              </View>

              {preview?.issues?.length ? (
                <View className="checkout-issue-card">
                  <Text className="checkout-card-title">需要处理</Text>
                  {preview.issues.map((issue) => <Text key={issue} className="checkout-issue-text">{issue}</Text>)}
                </View>
              ) : null}

              <View className="checkout-remark-card">
                <Text className="checkout-card-title">采购备注</Text>
                <Input
                  className="checkout-remark-input"
                  value={remark}
                  placeholder="例如：尽量上午送达，缺货请先联系"
                  onInput={(event) => setRemark(String(event.detail.value || ''))}
                />
              </View>

              <View className="checkout-price-card">
                <View className="checkout-price-line"><Text>商品金额</Text><Text>¥{money(preview?.merchandise_amount, localAmount)}</Text></View>
                <View className="checkout-price-line"><Text>配送费用</Text><Text>{Number(preview?.shipping_fee || 0) === 0 ? '包邮/自提' : `¥${money(preview?.shipping_fee)}`}</Text></View>
                {Number(preview?.shortfall_to_free_shipping || 0) > 0 && (
                  <View className="checkout-price-line subtle"><Text>距免邮还差</Text><Text>¥{money(preview?.shortfall_to_free_shipping)}</Text></View>
                )}
                <View className="checkout-price-line total"><Text>应付金额</Text><Text>¥{money(payableAmount)}</Text></View>
              </View>

              <View className="checkout-bottom-spacer" />
            </>
          )}
        </View>
      </ScrollView>

      {checkoutItems.length > 0 && (
        <View className="checkout-footer">
          <View>
            <Text className="checkout-total-label">{previewing ? '正在核价' : '应付'}</Text>
            <Text className="checkout-total">¥{money(payableAmount)}</Text>
          </View>
          <View className={`checkout-submit ${!canSubmit || submitting ? 'disabled' : ''}`} onClick={canSubmit && !submitting ? submitOrder : undefined}>
            {submitting ? '提交中...' : '提交订单'}
          </View>
        </View>
      )}
      <ProductDetailSheet show={Boolean(selectedProduct)} product={selectedProduct} showWholesaleWatermark onClose={() => setSelectedProduct(null)} />
    </View>
  )
}
