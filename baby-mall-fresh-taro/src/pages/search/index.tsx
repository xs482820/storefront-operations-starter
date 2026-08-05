import { useEffect, useMemo, useState } from 'react'
import Taro, { useRouter } from '@tarojs/taro'
import { Input, Text, View } from '@tarojs/components'
import { Empty } from '@antmjs/vantui/lib/empty'
import { Icon } from '@antmjs/vantui/lib/icon'
import { fetchProducts, fetchSearchSuggestions } from '../../api/catalog'
import { TopUtilityActions } from '../../components/TopUtilityActions'
import { ProductCard } from '../../components/ProductCard'
import { ProductDetailSheet } from '../../components/ProductDetailSheet'
import { adaptCustomerProduct } from '../../domain/adapters'
import { type Product } from '../../mock/catalog'
import { useCart } from '../../store/useCart'
import { getSafeVars } from '../../utils/safeArea'
import { WholesaleWatermark } from '../../components/WholesaleWatermark'
import './index.scss'

type FilterMode = 'default' | 'price'

function SearchSkeleton() {
  return (
    <View className="search-skeleton-card">
      <View className="search-skeleton-line wide" />
      <View className="search-skeleton-pill-row">
        <View className="search-skeleton-pill" />
        <View className="search-skeleton-pill short" />
      </View>
      <View className="search-skeleton-mini" />
      <View className="search-skeleton-mini" />
    </View>
  )
}

export default function SearchPage() {
  const router = useRouter()
  const initialKeyword = decodeURIComponent(String(router.params.keyword || ''))
  const [keyword, setKeyword] = useState(initialKeyword)
  const [confirmedKeyword, setConfirmedKeyword] = useState('')
  const [filterMode, setFilterMode] = useState<FilterMode>('default')
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [searchLoading, setSearchLoading] = useState(true)
  const [hotKeywords, setHotKeywords] = useState<string[]>([])
  const [productList, setProductList] = useState<Product[]>([])
  const [searchError, setSearchError] = useState('')
  const cart = useCart()

  useEffect(() => {
    let alive = true
    Promise.all([fetchSearchSuggestions(), fetchProducts()])
      .then(([suggestions, nextProducts]) => {
        if (!alive) return
        setHotKeywords(suggestions.suggestions || [])
        setProductList(nextProducts.map(adaptCustomerProduct))
        setSearchError('')
      })
      .catch(() => {
        if (!alive) return
        setHotKeywords([])
        setProductList([])
        setSearchError('搜索数据暂时没有加载成功，请稍后重试')
      })
      .finally(() => {
        if (alive) setSearchLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

  const results = useMemo(() => {
    const nextKeyword = confirmedKeyword.trim().toLowerCase()
    const filtered = !nextKeyword
      ? productList
      : productList.filter((product) => `${product.name}${product.subtitle}`.toLowerCase().includes(nextKeyword))
    if (filterMode === 'price') return [...filtered].sort((first, second) => first.price - second.price)
    return filtered
  }, [confirmedKeyword, filterMode, productList])

  const isResultMode = confirmedKeyword.length > 0

  const confirmSearch = (nextKeyword = keyword) => {
    const trimmed = nextKeyword.trim()
    setKeyword(trimmed)
    setConfirmedKeyword(trimmed)
  }

  const addProduct = (product: Product) => {
    cart.add(product, product.colors[0], product.sizes[0])
    const quantity = cart.getQuantity(product, product.colors[0], product.sizes[0]) + 1
    cart.syncProductQuantity(product, product.colors[0], product.sizes[0], quantity).catch(() => undefined)
    Taro.showToast({ title: '已加入清单', icon: 'success', duration: 900 })
  }

  const goBack = () => {
    if (isResultMode) {
      setConfirmedKeyword('')
      setFilterMode('default')
      return
    }
    Taro.navigateBack()
  }

  const updateProductFavorite = (product: Product, favorited: boolean) => {
    setProductList((current) => current.map((item) => (
      item.id === product.id ? { ...item, isFavorited: favorited } : item
    )))
    setSelectedProduct((current) => (current?.id === product.id ? { ...current, isFavorited: favorited } : current))
  }

  return (
    <View className="search-page safe-page" style={getSafeVars()}>
      <WholesaleWatermark />
      <View className="search-header">
        <View className="search-header-top">
        <View className="search-back-button" onClick={goBack}>
          <Icon name={isResultMode ? 'arrow-left' : 'shop-o'} size="36rpx" />
        </View>
        <TopUtilityActions />
        </View>
        <View className="search-input-row">
        <View className="search-input-wrap">
          <View className="search-input-icon" />
          <Input
            className="search-input"
            value={keyword}
            confirmType="search"
            focus
            placeholder="搜索奶瓶、纸尿裤、洗护..."
            onInput={(event) => setKeyword(String(event.detail.value || ''))}
            onConfirm={() => confirmSearch()}
          />
        </View>
        <View className="search-submit" onClick={() => confirmSearch()}>
          搜索
        </View>
        </View>
      </View>

      <View className={`search-body ${isResultMode ? 'is-result' : ''}`}>
        {!isResultMode ? searchLoading ? (
          <SearchSkeleton />
        ) : (
          <>
            <View className="search-suggest-card">
              <View className="search-suggest-head">
                <Text className="search-suggest-title">推荐搜索</Text>
              </View>
              {hotKeywords.length > 0 ? (
                <View className="search-keyword-grid">
                  {hotKeywords.map((item) => (
                    <View key={item} className="search-keyword-pill" onClick={() => confirmSearch(item)}>
                      <Text>{item}</Text>
                    </View>
                  ))}
                </View>
              ) : (
                <Text className="search-empty-copy">{searchError || '暂无推荐词'}</Text>
              )}
            </View>

            <View className="search-suggest-card search-product-suggest">
              <View className="search-suggest-head">
                <Text className="search-suggest-title">大家常找</Text>
              </View>
              {productList.length > 0 ? (
                <View className="search-mini-list">
                  {productList.slice(0, 3).map((product) => (
                    <View key={product.id} className="search-mini-item" onClick={() => setSelectedProduct(product)}>
                      <View className={`search-mini-thumb ${product.tone}`} />
                      <View className="search-mini-copy">
                        <Text className="search-mini-name">{product.name}</Text>
                        <Text className="search-mini-subtitle">{product.subtitle}</Text>
                      </View>
                      <Text className="search-mini-price">¥{product.price}</Text>
                    </View>
                  ))}
                </View>
              ) : (
                <Text className="search-empty-copy">{searchError || '暂无推荐商品'}</Text>
              )}
            </View>
          </>
        ) : (
          <>
            <View className="search-result-summary">
              <Text className="search-result-count">{results.length} 个结果</Text>
              <Text className="search-result-keyword">“{confirmedKeyword}”</Text>
            </View>
            <View className="search-filter-row">
              {[
                ['default', '综合'],
                ['price', '低价优先'],
              ].map(([value, label]) => (
                <View
                  key={value}
                  className={`search-filter-chip ${filterMode === value ? 'active' : ''}`}
                  onClick={() => setFilterMode(value as FilterMode)}
                >
                  <Text>{label}</Text>
                </View>
              ))}
            </View>
            {results.length === 0 ? (
              <View className="search-empty-card">
                <Empty description="没有找到相关商品，换个关键词试试" />
              </View>
            ) : (
              <View className="search-result-grid">
                {results.map((product) => (
                  <ProductCard key={product.id} product={product} onClick={setSelectedProduct} onAdd={addProduct} />
                ))}
              </View>
            )}
          </>
        )}
      </View>

      <ProductDetailSheet show={Boolean(selectedProduct)} product={selectedProduct} showWholesaleWatermark onClose={() => setSelectedProduct(null)} onFavoriteChange={updateProductFavorite} />
    </View>
  )
}
