import { useEffect, useMemo, useState } from 'react'
import Taro, { useDidShow } from '@tarojs/taro'
import { Image, Input, ScrollView, Text, View } from '@tarojs/components'
import { fetchEmployeeProducts, type EmployeeProduct } from '../../api/employee'
import { BackButton } from '../../components/BackButton'
import { CopyIcon } from '../../components/CopyIcon'
import { resolveMediaUrl } from '../../services/http'
import { getSafeStyle } from '../../utils/safeArea'
import { EmployeeWatermark } from '../../components/EmployeeWatermark'
import './index.scss'

export default function ProductPage() {
  const [items, setItems] = useState<EmployeeProduct[]>([])
  const [keyword, setKeyword] = useState('')
  const [error, setError] = useState('')
  const [activeFilter, setActiveFilter] = useState('all')
  const [filterIntoView, setFilterIntoView] = useState('product-filter-0')
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const load = () => fetchEmployeeProducts()
    .then((data) => { setItems(data); setError('') })
    .catch((reason) => setError(reason instanceof Error ? reason.message : '商品加载失败'))

  useEffect(() => { void load() }, [])
  useDidShow(() => { void load() })

  const categories = useMemo(() => Array.from(new Set(items.map((item) => item.category).filter(Boolean))) as string[], [items])
  const visible = useMemo(() => {
    const value = keyword.trim().toLowerCase()
    return items.filter((item) => (
      (!value || [item.name, item.model_name, item.product_code, item.brand, item.category].some((field) => String(field || '').toLowerCase().includes(value)))
      && (activeFilter === 'all'
        || (activeFilter === 'active' && item.is_active)
        || (activeFilter === 'wholesale' && item.supports_wholesale)
        || activeFilter === `category:${item.category}`)
    ))
  }, [items, keyword, activeFilter])

  const selectFilter = (value: string, index: number) => {
    setActiveFilter(value)
    setFilterIntoView(`product-filter-${index}`)
  }

  return (
    <View className="page products-page" style={getSafeStyle()}>
      <EmployeeWatermark />
      <BackButton />
      <View className="page-title">
        <View><Text className="page-title-main">商品库</Text><Text className="page-title-sub">仅查看商品、规格与价格</Text></View>
        <View className="product-header-actions"><Text className="product-quick-add" onClick={() => Taro.navigateTo({ url: '/pages/productQuick/index' })}>快速上架</Text><Text className="workbench-refresh" onClick={load}>刷新</Text></View>
      </View>
      <Input className="product-search card" value={keyword} placeholder="搜索商品名、货号或品牌" onInput={(event) => setKeyword(event.detail.value)} />
      <ScrollView className="product-filters" scrollX enhanced showScrollbar={false} scrollIntoView={filterIntoView}><View className="product-filter-row"><Text id="product-filter-0" className={'product-filter ' + (activeFilter === 'all' ? 'active' : '')} onClick={() => selectFilter('all', 0)}>全部</Text><Text id="product-filter-1" className={'product-filter ' + (activeFilter === 'active' ? 'active' : '')} onClick={() => selectFilter('active', 1)}>在售</Text><Text id="product-filter-2" className={'product-filter ' + (activeFilter === 'wholesale' ? 'active' : '')} onClick={() => selectFilter('wholesale', 2)}>支持批发</Text>{categories.map((category, index) => <Text id={`product-filter-${index + 3}`} key={category} className={'product-filter ' + (activeFilter === `category:${category}` ? 'active' : '')} onClick={() => selectFilter(`category:${category}`, index + 3)}>{category}</Text>)}</View></ScrollView>
      {error && <Text className="product-error">{error}</Text>}
      {visible.map((item) => {
        const imageUrl = resolveMediaUrl(item.image_urls[0])
        const isExpanded = expandedId === item.id
        return (
          <View key={item.id} className={'product-card card ' + (isExpanded ? 'expanded' : '')} onClick={() => setExpandedId(isExpanded ? null : item.id)}>
            <View className="product-card-summary">
              <View className="product-thumb">{imageUrl ? <Image src={imageUrl} mode="aspectFill" onClick={(event) => { event.stopPropagation(); Taro.previewImage({ current: imageUrl, urls: item.image_urls.map(resolveMediaUrl) }) }} /> : <Text>商品</Text>}</View>
              <View className="product-main">
                <View className="product-name-row"><Text className="product-name">{item.name}</Text><View className="product-spec-toggle"><Text>{item.skus.length} 规格</Text><View className="product-spec-arrow" /></View></View>
                <View className="product-code-row"><Text>{item.product_code}</Text><CopyIcon value={item.product_code} label="货号" stopPropagation /></View>
                <Text className="product-category">{[item.brand, item.category].filter(Boolean).join(' · ') || '未分类'}</Text>
                <View className="product-state-line"><Text className={item.is_active ? 'product-state available' : 'product-state'}>{item.is_active ? '在售' : '已停用'}</Text>{item.supports_wholesale && <Text className="product-state wholesale">批发</Text>}</View>
              </View>
            </View>
            {isExpanded && <View className="product-sku-list">{item.description && <Text className="product-description">{item.description}</Text>}{item.skus.map((sku, index) => <View className="product-sku-row" key={sku.id}><View className="product-sku-main"><Text className="product-sku-name">{sku.sku_label || [sku.spec_value_1, sku.spec_value_2].filter(Boolean).join(' / ') || `规格 ${index + 1}`}</Text><Text className="product-sku-code">{sku.sku_code || '未填写货号'}</Text><Text className="product-sku-meta">库存 {sku.online_stock} · 零售起订 {sku.min_sale_qty} · 批发起订 {sku.min_wholesale_qty}</Text></View><View className="product-sku-price"><Text>零售 ¥{sku.retail_price}</Text>{item.supports_wholesale && <Text>批发 ¥{sku.wholesale_price}</Text>}</View></View>)}{item.skus.length <= 2 && <Text className="product-quick-edit" onClick={(event) => { event.stopPropagation(); Taro.navigateTo({ url: `/pages/productQuick/index?id=${item.id}` }) }}>快速编辑</Text>}</View>}
          </View>
        )
      })}
      {!error && visible.length === 0 && <View className="product-empty card"><Text>暂无匹配商品</Text></View>}
    </View>
  )
}
