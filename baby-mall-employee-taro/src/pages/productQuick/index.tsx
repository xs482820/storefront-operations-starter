import { useEffect, useState } from 'react'
import Taro, { useRouter } from '@tarojs/taro'
import { Image, Input, Picker, ScrollView, Switch, Text, Textarea, View } from '@tarojs/components'
import { EmployeeProduct, createEmployeeQuickProduct, fetchEmployeeProducts, updateEmployeeQuickProduct, uploadEmployeeEvidence } from '../../api/employee'
import { BackButton } from '../../components/BackButton'
import { resolveMediaUrl } from '../../services/http'
import { getSafeStyle } from '../../utils/safeArea'
import { EmployeeWatermark } from '../../components/EmployeeWatermark'
import './index.scss'

type Form = { name: string; productCode: string; category: string; description: string; imageUrls: string[]; retailPrice: string; wholesalePrice: string; minWholesaleQty: string; isActive: boolean }
const emptyForm: Form = { name: '', productCode: '', category: '', description: '', imageUrls: [], retailPrice: '', wholesalePrice: '', minWholesaleQty: '1', isActive: true }

function asForm(item: EmployeeProduct): Form {
  const retail = item.skus.find((sku) => sku.sku_type === 'retail') || item.skus[0]
  const wholesale = item.skus.find((sku) => sku.sku_type === 'wholesale')
  return { name: item.name, productCode: item.product_code || '', category: item.category || '', description: item.description || '', imageUrls: item.image_urls || [], retailPrice: retail?.retail_price || '', wholesalePrice: wholesale?.wholesale_price || '', minWholesaleQty: String(wholesale?.min_wholesale_qty || 1), isActive: item.is_active }
}

export default function ProductQuickPage() {
  const router = useRouter()
  const productId = Number(router.params.id || 0)
  const [form, setForm] = useState<Form>(emptyForm)
  const [loading, setLoading] = useState(Boolean(productId))
  const [saving, setSaving] = useState(false)
  const [categories, setCategories] = useState<string[]>([])
  const [categoryChoice, setCategoryChoice] = useState(-1)

  useEffect(() => {
    fetchEmployeeProducts().then((items) => {
      const existingCategories = Array.from(new Set(items.map((item) => item.category?.trim()).filter(Boolean))) as string[]
      setCategories(existingCategories)
      if (!productId) return
      const item = items.find((row) => row.id === productId)
      if (!item) throw new Error('商品不存在')
      const next = asForm(item)
      setForm(next)
      setCategoryChoice(existingCategories.indexOf(next.category))
    }).catch((error) => Taro.showToast({ title: error instanceof Error ? error.message : '商品加载失败', icon: 'none' })).finally(() => setLoading(false))
  }, [productId])

  const update = (patch: Partial<Form>) => setForm((current) => ({ ...current, ...patch }))
  const chooseImages = async () => {
    try {
      const result = await Taro.chooseImage({ count: Math.max(1, 5 - form.imageUrls.length), sizeType: ['compressed'], sourceType: ['camera', 'album'] })
      Taro.showLoading({ title: '上传中' })
      const uploaded = await Promise.all(result.tempFilePaths.map(uploadEmployeeEvidence))
      update({ imageUrls: [...form.imageUrls, ...uploaded.map((item) => item.url)].slice(0, 5) })
    } catch (error) {
      if (error instanceof Error && error.message) Taro.showToast({ title: error.message.slice(0, 18), icon: 'none' })
    } finally { Taro.hideLoading() }
  }
  const submit = async () => {
    const name = form.name.trim()
    const productCode = form.productCode.trim().toUpperCase()
    const retailPrice = form.retailPrice.trim() ? Number(form.retailPrice) : null
    const wholesalePrice = form.wholesalePrice.trim() ? Number(form.wholesalePrice) : null
    if (!name || !productCode || (retailPrice === null && wholesalePrice === null) || (retailPrice !== null && (!Number.isFinite(retailPrice) || retailPrice < 0)) || (wholesalePrice !== null && (!Number.isFinite(wholesalePrice) || wholesalePrice < 0))) return Taro.showToast({ title: '请填写名称、货号和至少一个有效价格', icon: 'none' })
    setSaving(true)
    try {
      const payload = { name, product_code: productCode, category: form.category.trim() || null, description: form.description.trim() || null, image_urls: form.imageUrls, retail_price: retailPrice, wholesale_price: wholesalePrice, min_wholesale_qty: Math.max(1, Number(form.minWholesaleQty) || 1), is_active: form.isActive }
      const result = productId ? await updateEmployeeQuickProduct(productId, payload) : await createEmployeeQuickProduct(payload)
      Taro.showToast({ title: productId ? '已保存' : '已上架', icon: 'success' })
      setTimeout(() => Taro.redirectTo({ url: `/pages/products/index?focus=${result.id}` }), 450)
    } catch (error) { Taro.showToast({ title: error instanceof Error ? error.message.slice(0, 20) : '保存失败', icon: 'none' }) } finally { setSaving(false) }
  }

  return <View className="page quick-product-page" style={getSafeStyle()}>
    <EmployeeWatermark />
    <BackButton fallbackUrl="/pages/products/index" />
    <View className="quick-product-head"><Text>{productId ? '快速编辑' : '快速上架'}</Text><Text>单规格商品</Text></View>
    {!loading && <ScrollView scrollY className="quick-product-scroll"><View className="quick-product-content">
      <Text className="quick-product-label">商品照片</Text><ScrollView className="quick-product-images" scrollX enhanced showScrollbar={false}><View className="quick-product-image-row">{form.imageUrls.map((url, index) => <View className="quick-product-thumb" key={url}><Image src={resolveMediaUrl(url)} mode="aspectFill" onClick={() => Taro.previewImage({ current: resolveMediaUrl(url), urls: form.imageUrls.map(resolveMediaUrl) })} /><Text onClick={() => update({ imageUrls: form.imageUrls.filter((_, itemIndex) => itemIndex !== index) })}>×</Text></View>)}{form.imageUrls.length < 5 && <View className="quick-product-add" onClick={chooseImages}>+<Text>拍照/相册</Text></View>}</View></ScrollView>
      <View className="quick-product-form card"><Text className="quick-product-label">商品名称</Text><Input value={form.name} placeholder="例如：加厚抽取式面巾纸" onInput={(event) => update({ name: event.detail.value })} /><Text className="quick-product-label">货号</Text><Input value={form.productCode} maxlength={64} placeholder="例如：JP-MJZ-100-6" onInput={(event) => update({ productCode: event.detail.value })} /><Text className="quick-product-label">分类</Text><Picker mode="selector" range={['选择已有分类', ...categories, '新增分类']} value={categoryChoice + 1} onChange={(event) => { const index = Number(event.detail.value) - 1; setCategoryChoice(index); update({ category: index >= 0 && index < categories.length ? categories[index] : '' }) }}><View className="quick-product-picker">{categoryChoice >= 0 && categoryChoice < categories.length ? categories[categoryChoice] : '选择已有分类或新增'}</View></Picker>{categoryChoice === categories.length && <Input value={form.category} placeholder="填写新分类名称" onInput={(event) => update({ category: event.detail.value })} />}<Text className="quick-product-label">零售价（元）</Text><Input type="digit" value={form.retailPrice} placeholder="可留空，仅批发时不填" onInput={(event) => update({ retailPrice: event.detail.value })} /><Text className="quick-product-label">批发价（元）</Text><Input type="digit" value={form.wholesalePrice} placeholder="可留空，仅零售时不填" onInput={(event) => update({ wholesalePrice: event.detail.value })} />{form.wholesalePrice.trim() && <><Text className="quick-product-label">批发起订数量</Text><Input type="number" value={form.minWholesaleQty} onInput={(event) => update({ minWholesaleQty: event.detail.value })} /></>}<Text className="quick-product-price-mode">{form.retailPrice.trim() && form.wholesalePrice.trim() ? '当前为双价商品' : form.retailPrice.trim() ? '当前仅零售' : form.wholesalePrice.trim() ? '当前仅批发' : '至少填写一个价格'}</Text><Text className="quick-product-label">商品说明</Text><Textarea value={form.description} maxlength={1000} autoHeight placeholder="可简短填写商品卖点或注意事项" onInput={(event) => update({ description: event.detail.value })} /><View className="quick-product-switch"><View><Text>立即上架</Text><Text>关闭后仅后台可见</Text></View><Switch checked={form.isActive} color="#2b755a" onChange={(event) => update({ isActive: event.detail.value })} /></View></View>
      <View className={`quick-product-submit ${saving ? 'disabled' : ''}`} onClick={submit}>{saving ? '保存中...' : productId ? '保存修改' : '确认上架'}</View><Text className="quick-product-note">复杂规格、批量 SKU 和分类维护请在管理后台处理。</Text>
    </View></ScrollView>}
  </View>
}
