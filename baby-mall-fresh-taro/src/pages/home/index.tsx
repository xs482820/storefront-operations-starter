import { useEffect, useMemo, useRef, useState } from 'react'
import Taro, { useDidShow } from '@tarojs/taro'
import { Image, ScrollView, Swiper, SwiperItem, Text, View } from '@tarojs/components'
import { Empty } from '@antmjs/vantui/lib/empty'
import { Icon } from '@antmjs/vantui/lib/icon'
import { Popup } from '@antmjs/vantui/lib/popup'
import { fetchCart } from '../../api/cart'
import { fetchCategories, fetchProducts, fetchStorefrontConfig } from '../../api/catalog'
import { FreshSearchBox } from '../../components/FreshSearchBox'
import { HomeAnnouncementPill } from '../../components/HomeAnnouncementPill'
import { TopUtilityActions } from '../../components/TopUtilityActions'
import { ProductCard } from '../../components/ProductCard'
import { ProductDetailSheet } from '../../components/ProductDetailSheet'
import { adaptCartItem, adaptCustomerProduct } from '../../domain/adapters'
import { benefits, type Category, type Product } from '../../mock/catalog'
import { useCart } from '../../store/useCart'
import { fetchUnreadNotificationCount } from '../../services/notificationState'
import { getSafeVars } from '../../utils/safeArea'
import { previewImages } from '../../utils/imagePreview'
import { resolveMediaUrl } from '../../services/http'
import { WholesaleWatermark } from '../../components/WholesaleWatermark'
import './index.scss'

type HomeAnnouncement = { id: string; title: string; body: string; action: string; type: string; value?: string | null }
type HomeBanner = { id: string; title: string; imageUrl: string; linkType: string; linkValue: string }
type SortMode = 'default' | 'priceAsc' | 'priceDesc' | 'newest'
type FilterState = {
  priceRange: 'all' | '0-50' | '50-100' | '100-300' | '300+'
}

function ProductGridSkeleton() {
  return (
    <View className="product-skeleton-grid">
      {[0, 1, 2, 3].map((item) => (
        <View key={item} className="product-skeleton-card">
          <View className="product-skeleton-visual" />
          <View className="product-skeleton-line wide" />
          <View className="product-skeleton-line" />
          <View className="product-skeleton-row">
            <View className="product-skeleton-line price" />
            <View className="product-skeleton-dot" />
          </View>
        </View>
      ))}
    </View>
  )
}

export default function HomePage() {
  const [activeCategory, setActiveCategory] = useState('all')
  const [sortMode, setSortMode] = useState<SortMode>('default')
  const [filterState, setFilterState] = useState<FilterState>({
    priceRange: 'all',
  })
  const [query, setQuery] = useState('')
  const [headerCompact, setHeaderCompact] = useState(false)
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [announcementPanelOpen, setAnnouncementPanelOpen] = useState(false)
  const [filterPanelOpen, setFilterPanelOpen] = useState(false)
  const [scrollTop, setScrollTop] = useState(0)
  const [categoryScrollLeft, setCategoryScrollLeft] = useState(0)
  const [catalogLoading, setCatalogLoading] = useState(true)
  const [categoryList, setCategoryList] = useState<Category[]>([])
  const [productList, setProductList] = useState<Product[]>([])
  const [homeAnnouncements, setHomeAnnouncements] = useState<HomeAnnouncement[]>([])
  const [homeBanners, setHomeBanners] = useState<HomeBanner[]>([])
  const [storeName, setStoreName] = useState('')
  const [catalogError, setCatalogError] = useState('')
  const [profileUnread, setProfileUnread] = useState(0)
  const currentScrollTop = useRef(0)
  const scrollMeasureTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const categoryIntentUntil = useRef(0)
  const cart = useCart()

  useDidShow(() => {
    fetchUnreadNotificationCount()
      .then(setProfileUnread)
      .catch(() => setProfileUnread(0))
  })

  useEffect(() => {
    let alive = true
    fetchCart()
      .then((items) => {
        if (alive) cart.replace(items.map(adaptCartItem))
      })
      .catch(() => {
        if (alive) cart.replace([])
      })
    Promise.all([fetchCategories(), fetchProducts()])
      .then(([nextCategories, nextProducts]) => {
        if (!alive) return
        const activeCategoryNames = new Set(nextProducts.map((product) => product.category).filter(Boolean))
        setCategoryList([
          { id: 'all', name: '全部', tone: '0' },
          ...nextCategories.filter((category) => activeCategoryNames.has(category.code || category.name) || activeCategoryNames.has(category.name)).map((category, index) => ({
            id: category.code || category.name || String(category.id || index),
            name: category.name,
            tone: String(index % 5),
          })),
        ])
        setProductList(nextProducts.map(adaptCustomerProduct))
        setCatalogError('')
      })
      .catch(() => {
        if (!alive) return
        setCategoryList([])
        setProductList([])
        setCatalogError('商品暂时没有加载成功，请稍后重试')
      })
      .finally(() => {
        if (alive) setCatalogLoading(false)
      })
    fetchStorefrontConfig()
      .then((config) => {
        if (!alive) return
        setStoreName(config.store_info?.name?.trim() || '')
        setHomeBanners((config.home_banners || [])
          .filter((banner) => banner.is_active && banner.image_url)
          .sort((first, second) => Number(second.sort_order || 0) - Number(first.sort_order || 0))
          .map((banner, index) => ({
            id: `${banner.title || banner.name || 'banner'}-${index}`,
            title: banner.title || banner.name || '首页活动',
            imageUrl: resolveMediaUrl(banner.image_url),
            linkType: banner.link_type || 'none',
            linkValue: banner.link_value || '',
          })))
        setHomeAnnouncements((config.marquee_notices || []).map((notice) => ({
          id: String(notice.id),
          title: notice.title,
          body: notice.body,
          action: notice.action_label,
          type: notice.action_type,
          value: notice.action_value,
        })))
      })
      .catch(() => {
        if (!alive) return
        setStoreName('')
        setHomeBanners([])
        setHomeAnnouncements([])
      })
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    const handleSearchConfirm = (nextQuery: string) => setQuery(nextQuery)
    Taro.eventCenter.on('home-search-confirm', handleSearchConfirm)
    return () => {
      Taro.eventCenter.off('home-search-confirm', handleSearchConfirm)
    }
  }, [])

  const activeFilterCount = useMemo(() => (
    Number(filterState.priceRange !== 'all')
  ), [filterState])

  const inPriceRange = (product: Product) => {
    if (filterState.priceRange === 'all') return true
    if (filterState.priceRange === '0-50') return product.price < 50
    if (filterState.priceRange === '50-100') return product.price >= 50 && product.price < 100
    if (filterState.priceRange === '100-300') return product.price >= 100 && product.price < 300
    return product.price >= 300
  }

  const visibleProducts = useMemo(() => {
    const keyword = query.trim().toLowerCase()
    const filtered = productList.filter((product) => {
      const searchMatch = !keyword || `${product.name}${product.subtitle}`.toLowerCase().includes(keyword)
      const priceMatch = inPriceRange(product)
      return searchMatch && priceMatch
    })
    if (sortMode === 'priceAsc') return [...filtered].sort((first, second) => first.price - second.price)
    if (sortMode === 'priceDesc') return [...filtered].sort((first, second) => second.price - first.price)
    if (sortMode === 'newest') return filtered
    return filtered
  }, [filterState, productList, query, sortMode])

  const categoryGroups = useMemo(() => {
    const names = new Map(categoryList.map((category) => [category.id, category.name]))
    const groups = categoryList
      .filter((category) => category.id !== 'all')
      .map((category) => ({
        category,
        products: visibleProducts.filter((product) => product.categoryId === category.id || product.categoryId === category.name),
      }))
      .filter((group) => group.products.length > 0)
    const knownIds = new Set(categoryList.map((category) => category.id))
    const otherProducts = visibleProducts.filter((product) => !knownIds.has(product.categoryId) && !names.has(product.categoryId))
    return otherProducts.length
      ? [...groups, { category: { id: 'other', name: '其他', tone: '0' }, products: otherProducts }]
      : groups
  }, [categoryList, filterState.priceRange, query, visibleProducts])

  const sortLabel = sortMode === 'priceAsc' ? '低价' : sortMode === 'priceDesc' ? '高价' : sortMode === 'newest' ? '最新' : '综合'

  const addProduct = (product: Product) => {
    const hasMultipleSku = (product.skus?.length || 0) > 1 || product.colors.length * product.sizes.length > 1
    if (hasMultipleSku) {
      openProductDetail(product)
      return
    }
    cart.add(product, product.colors[0], product.sizes[0])
    const quantity = cart.getQuantity(product, product.colors[0], product.sizes[0]) + 1
    cart.syncProductQuantity(product, product.colors[0], product.sizes[0], quantity).catch(() => undefined)
    Taro.showToast({ title: '已加入清单', icon: 'success', duration: 900 })
  }

  const openSearchPage = () => {
    Taro.navigateTo({ url: `/pages/search/index?keyword=${encodeURIComponent(query)}` })
  }

  const openCartPage = () => {
    Taro.redirectTo({ url: '/pages/cart/index' })
  }

  const handleAnnouncementAction = (announcement: HomeAnnouncement) => {
    setAnnouncementPanelOpen(false)
    if (announcement.type === 'category') {
      if (announcement.value) {
        jumpToCategory(announcement.value)
      }
      return
    }
    if (announcement.type === 'cart') {
      openCartPage()
      return
    }
    if (announcement.type === 'profile') {
      const returnTo = encodeURIComponent('/pages/home/index')
      Taro.navigateTo({ url: announcement.value ? `/pages/profile/index?view=${announcement.value}&returnTo=${returnTo}` : `/pages/profile/index?returnTo=${returnTo}` })
      return
    }
    if (announcement.type === 'url' && announcement.value) {
      Taro.navigateTo({ url: announcement.value })
    }
  }

  const handleBannerClick = (banner: HomeBanner) => {
    if (banner.linkType === 'product_code' && banner.linkValue) {
      const product = productList.find((item) => (
        item.id === banner.linkValue ||
        String(item.backendId || '') === banner.linkValue ||
        item.skus?.some((sku) => sku.code === banner.linkValue)
      ))
      if (product) setSelectedProduct(product)
      return
    }
    if (banner.linkType === 'url' && banner.linkValue) {
      Taro.navigateTo({ url: banner.linkValue })
    }
  }

  const openProductDetail = (product: Product) => {
    setScrollTop(currentScrollTop.current)
    setSelectedProduct(product)
  }

  const closeProductDetail = () => {
    const restoreTop = currentScrollTop.current
    setSelectedProduct(null)
    Taro.nextTick(() => setScrollTop(restoreTop))
    setTimeout(() => setScrollTop(restoreTop), 80)
  }

  const updateProductFavorite = (product: Product, favorited: boolean) => {
    setProductList((current) => current.map((item) => (
      item.id === product.id ? { ...item, isFavorited: favorited } : item
    )))
    setSelectedProduct((current) => (current?.id === product.id ? { ...current, isFavorited: favorited } : current))
  }

  const syncCategoryBar = (categoryId: string) => {
    const index = Math.max(0, categoryList.findIndex((category) => category.id === categoryId))
    // ponytail: estimate pill width instead of measuring every chip; enough to keep the active chip visible.
    setCategoryScrollLeft(Math.max(0, index * 92 - 150))
  }

  const jumpToCategory = (categoryId: string) => {
    categoryIntentUntil.current = Date.now() + 420
    setActiveCategory(categoryId)
    syncCategoryBar(categoryId)
    if (categoryId === 'all') {
      setHeaderCompact(false)
      setScrollTop(0)
      return
    }
    const groupIndex = categoryGroups.findIndex((group) => group.category.id === categoryId)
    if (groupIndex < 0) return
    Taro.nextTick(() => {
      const querySelector = Taro.createSelectorQuery()
      querySelector.select(`#category-section-${groupIndex}`).boundingClientRect()
      querySelector.select('.shelf-sticky-tools').boundingClientRect()
      querySelector.exec((res) => {
        const section = res?.[0] as { top?: number } | null
        const tools = res?.[1] as { bottom?: number } | null
        if (typeof section?.top !== 'number') return
        const targetTop = Math.max(0, Math.round(currentScrollTop.current + section.top - (tools?.bottom || 0) - 10))
        // ponytail: nudge equal values so ScrollView still receives a fresh scroll command.
        setScrollTop((current) => (current === targetTop ? targetTop + 1 : targetTop))
      })
    })
  }

  const measureActiveCategory = () => {
    if (scrollMeasureTimer.current) return
    scrollMeasureTimer.current = setTimeout(() => {
      scrollMeasureTimer.current = null
      if (Date.now() < categoryIntentUntil.current) return
      const querySelector = Taro.createSelectorQuery()
      querySelector.selectAll('.product-category-section').boundingClientRect()
      querySelector.select('.shelf-sticky-tools').boundingClientRect()
      querySelector.exec((res) => {
        const sections = (res?.[0] || []) as Array<{ id?: string; top: number }>
        const tools = res?.[1] as { bottom?: number } | null
        const activationLine = (tools?.bottom || 260) + 18
        const candidate = sections
          .filter((section) => section.top <= activationLine)
          .sort((first, second) => second.top - first.top)[0]
        const candidateIndex = candidate ? sections.indexOf(candidate) : -1
        const nextId = candidateIndex >= 0 ? categoryGroups[candidateIndex]?.category.id : 'all'
        if (nextId && nextId !== activeCategory) {
          setActiveCategory(nextId)
          syncCategoryBar(nextId)
        }
      })
    }, 90)
  }

  const updateFilter = <K extends keyof FilterState>(key: K, value: FilterState[K]) => {
    setFilterState((current) => ({ ...current, [key]: value }))
  }

  return (
    <View className={`fresh-page safe-page ${headerCompact ? 'is-compact' : ''}`} style={getSafeVars()}>
      <WholesaleWatermark />
      <View className="fresh-header-shell">
        <View className="fresh-header">
          <View className="fresh-title-row">
            <View className="brand-title-wrap">
              <View className="brand-avatar" aria-label="示例门店">
                <Text>店</Text>
              </View>
              <Text className="fresh-title">{storeName || 'Storefront'}</Text>
            </View>
          </View>

          <View className="home-search-entry">
            <FreshSearchBox value={query} onClick={openSearchPage} />
          </View>

          {homeAnnouncements.length > 0 && (
            <View className="home-header-announcement">
              <HomeAnnouncementPill announcements={homeAnnouncements} onClick={() => setAnnouncementPanelOpen(true)} />
            </View>
          )}

          <View className="compact-filter-row">
            <FreshSearchBox compact onClick={openSearchPage} />
            <HomeAnnouncementPill compact announcements={homeAnnouncements} onClick={() => setAnnouncementPanelOpen(true)} />
          </View>
        </View>
      </View>
      <TopUtilityActions className="home-top-utility" />

      <ScrollView
        scrollY
        className="fresh-scroll"
        enhanced
        scrollTop={scrollTop}
        onScroll={(event) => {
          const nextTop = Number(event.detail?.scrollTop || 0)
          currentScrollTop.current = nextTop
          // ponytail: fixed trigger matches the current hero/benefits layout; use SelectorQuery if modules become dynamic.
          const nextCompact = nextTop > 288
          if (nextCompact !== headerCompact) setHeaderCompact(nextCompact)
          measureActiveCategory()
        }}
      >
        <View className="fresh-scroll-content">
          <View className="hero-card">
            {homeBanners.length > 0 ? (
              <Swiper
                className="hero-swiper"
                indicatorDots={homeBanners.length > 1}
                autoplay={homeBanners.length > 1}
                circular={homeBanners.length > 1}
                interval={4200}
              >
                {homeBanners.map((banner) => (
                  <SwiperItem key={banner.id}>
                    <View className="hero-banner" onClick={() => previewImages(homeBanners.map((item) => item.imageUrl), banner.imageUrl)}>
                      <Image className="hero-banner-image" src={banner.imageUrl} mode="aspectFill" />
                      {banner.title && <Text className="hero-banner-title">{banner.title}</Text>}
                      {banner.linkType !== 'none' && banner.linkValue && (
                        <View
                          className="hero-banner-link"
                          onClick={(event) => {
                            event.stopPropagation()
                            handleBannerClick(banner)
                          }}
                        >
                          查看
                        </View>
                      )}
                    </View>
                  </SwiperItem>
                ))}
              </Swiper>
            ) : (
              <View className="hero-image-placeholder">
                <View className="hero-image-dot" />
                <View className="hero-image-line wide" />
                <View className="hero-image-line" />
              </View>
            )}
          </View>

          {benefits.length > 0 && (
            <View className="benefit-grid">
              {benefits.map((item) => (
                <View key={item.id} className="benefit-card">
                  <Text className="benefit-value">{item.value}</Text>
                  <Text className="benefit-label">{item.label}</Text>
                </View>
              ))}
            </View>
          )}

          <View className="shelf-sticky-tools">
            {categoryList.length > 0 && (
              <View className="shelf-category-block">
                <ScrollView
                  scrollX
                  className="category-scroll shelf-category-scroll"
                  showScrollbar={false}
                  scrollLeft={categoryScrollLeft}
                  scrollWithAnimation
                >
                  <View className="category-scroll-inner">
                    {categoryList.map((category) => (
                      <View
                        key={category.id}
                        className={`category-pill ${activeCategory === category.id ? 'active' : ''}`}
                        onClick={() => jumpToCategory(category.id)}
                      >
                        <Text>{category.name}</Text>
                      </View>
                    ))}
                  </View>
                </ScrollView>
              </View>
            )}
            <View className="shelf-divider" />
            <View className="shelf-filter-control" onClick={() => setFilterPanelOpen(true)}>
              <View className="sort-chip">
                <Text>{sortLabel}</Text>
                <Text className="sort-arrow">⌄</Text>
              </View>
              <View className={`filter-entry ${activeFilterCount > 0 ? 'active' : ''}`}>
                <Icon name="filter-o" size="28rpx" />
                {activeFilterCount > 0 && <Text className="filter-count">{activeFilterCount}</Text>}
              </View>
            </View>
          </View>

          {catalogLoading ? (
            <ProductGridSkeleton />
          ) : visibleProducts.length === 0 ? (
            <View className="home-empty-card">
              <Empty description={catalogError || '货架正在整理中，请稍后再来看看'} />
            </View>
          ) : (
            <View className="product-section-list">
              {categoryGroups.map((group, groupIndex) => (
                <View key={group.category.id} id={`category-section-${groupIndex}`} className="product-category-section">
                  <View className="category-section-head">
                    <Text className="category-section-title">{group.category.name}</Text>
                    <Text className="category-section-count">{group.products.length} 件</Text>
                  </View>
                  {group.products.length > 0 ? (
                    <View className="product-grid">
                      {group.products.map((product) => (
                        <ProductCard key={product.id} product={product} onClick={openProductDetail} onAdd={addProduct} />
                      ))}
                    </View>
                  ) : (
                    <View className="category-empty"><Icon name="goods-collect-o" size="30rpx" /><Text>该分类暂未上架商品</Text></View>
                  )}
                </View>
              ))}
            </View>
          )}

          <View className="bottom-spacer" />
        </View>
      </ScrollView>

      <View className="tabbar-backdrop" />
      <View className="fresh-tabbar">
        <View className="tabbar-item active">
          <Icon className="tabbar-icon" name="shop-o" size="36rpx" />
          <Text className="tabbar-label">选购</Text>
        </View>
        <View className="tabbar-item" onClick={openCartPage}>
          <Icon className="tabbar-icon" name="shopping-cart-o" size="36rpx" />
          <Text className="tabbar-label">清单</Text>
          {cart.count > 0 && <Text className="tabbar-badge">{cart.count}</Text>}
        </View>
        <View className="tabbar-item" onClick={() => Taro.redirectTo({ url: '/pages/profile/index' })}>
          <Icon className="tabbar-icon" name="user-o" size="36rpx" />
          <Text className="tabbar-label">个人</Text>
          {profileUnread > 0 && <Text className="tabbar-dot" />}
        </View>
      </View>

      <ProductDetailSheet
        showWholesaleWatermark
        show={Boolean(selectedProduct)}
        product={selectedProduct}
        onClose={closeProductDetail}
        onFavoriteChange={updateProductFavorite}
      />

      <Popup show={announcementPanelOpen} position="bottom" round safeAreaInsetBottom={false} onClose={() => setAnnouncementPanelOpen(false)}>
        <View className="notice-sheet">
          <View className="notice-sheet-handle" />
          <View className="notice-sheet-head">
            <Text className="notice-sheet-title">公告记录</Text>
            <Text className="notice-sheet-close" onClick={() => setAnnouncementPanelOpen(false)}>关闭</Text>
          </View>
          {homeAnnouncements.map((announcement) => (
            <View key={announcement.id} className="notice-record">
              <Text className="notice-record-title">{announcement.title}</Text>
              <Text className="notice-record-body">{announcement.body}</Text>
              {announcement.type !== 'none' && <View className="notice-record-action" onClick={() => handleAnnouncementAction(announcement)}>{announcement.action}</View>}
            </View>
          ))}
        </View>
      </Popup>

      <Popup show={filterPanelOpen} position="bottom" round safeAreaInsetBottom={false} onClose={() => setFilterPanelOpen(false)}>
        <View className="filter-sheet">
          <View className="notice-sheet-handle" />
          <View className="notice-sheet-head">
            <Text className="notice-sheet-title">筛选商品</Text>
            <Text className="notice-sheet-close" onClick={() => setFilterPanelOpen(false)}>关闭</Text>
          </View>

          <Text className="filter-sheet-title">排序</Text>
          <View className="filter-option-grid">
            {[
              ['default', '综合排序'],
              ['priceAsc', '低价优先'],
              ['priceDesc', '高价优先'],
              ['newest', '最新上架'],
            ].map(([value, label]) => (
              <View key={value} className={`filter-option ${sortMode === value ? 'active' : ''}`} onClick={() => setSortMode(value as SortMode)}>
                {label}
              </View>
            ))}
          </View>

          <Text className="filter-sheet-title">价格区间</Text>
          <View className="filter-option-grid">
            {[
              ['all', '不限'],
              ['0-50', '50 元内'],
              ['50-100', '50-100'],
              ['100-300', '100-300'],
              ['300+', '300 以上'],
            ].map(([value, label]) => (
              <View key={value} className={`filter-option ${filterState.priceRange === value ? 'active' : ''}`} onClick={() => updateFilter('priceRange', value as FilterState['priceRange'])}>
                {label}
              </View>
            ))}
          </View>

          <View className="filter-sheet-actions">
            <View className="filter-reset" onClick={() => {
              setSortMode('default')
              setFilterState({ priceRange: 'all' })
            }}>重置</View>
            <View className="filter-confirm" onClick={() => setFilterPanelOpen(false)}>确认筛选</View>
          </View>
        </View>
      </Popup>
    </View>
  )
}
