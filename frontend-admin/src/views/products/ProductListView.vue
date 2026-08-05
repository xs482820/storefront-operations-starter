<template>
  <div class="products-page">
    <AppPageHeader title="商品与价格" description="管理上架商品、规格矩阵和零批定价。">
      <template #actions>
        <el-button @click="showCatDrawer = true">管理分类</el-button>
        <el-button type="primary" @click="openCreateDrawer">新建商品</el-button>
      </template>
    </AppPageHeader>

    <el-card shadow="never" class="list-card">
      <template #header>
        <div class="list-header">
          <div class="filter-bar">
            <el-input v-model="searchText" :prefix-icon="Search" clearable placeholder="商品名、货号、分类" style="width:220px" />
            <el-select v-model="currentTab" style="width:120px">
              <el-option label="全部商品" value="all" />
              <el-option label="上架中" value="on" />
              <el-option label="低库存" value="low" />
            </el-select>
            <el-button :icon="Refresh" :loading="loading" @click="loadProducts">刷新</el-button>
          </div>
          <ListSummary :items="[{ value: filteredItems.length, label: '件商品' }, { value: activeProductCount, label: '件上架' }]" />
        </div>
      </template>

      <div v-if="selectedProducts.length" class="batch-bar">
        <span>已选择 {{ selectedProducts.length }} 件商品</span>
        <el-button size="small" type="primary" plain @click="setSelectedProductsActive(true)">批量上架</el-button>
        <el-button size="small" @click="setSelectedProductsActive(false)">批量下架</el-button>
        <el-button size="small" link @click="selectedProducts = []">取消选择</el-button>
      </div>
      <el-table v-loading="loading" :data="pagedItems" row-key="id" style="cursor:pointer" @selection-change="(rows: ProductListItem[]) => selectedProducts = rows" @row-click="(row: ProductListItem) => openDetailDrawer(row.id)">
        <el-table-column type="selection" width="46" @click.stop />
        <el-table-column label="商品" min-width="280">
          <template #default="{ row }">
            <div class="product-cell">
              <img v-if="row.image_urls?.[0]" :src="row.image_urls[0]" class="product-thumb" :alt="row.name" />
              <div v-else class="product-thumb placeholder">{{ makeInitial(row.name) }}</div>
              <div class="product-info">
                <div class="product-name">{{ row.name }}</div>
                <div class="product-meta">货号 {{ row.product_code }} · {{ row.sku_count }} SKU · {{ row.category || '未分类' }}</div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="库存" width="120" align="right">
          <template #default="{ row }">
            <span :class="{ 'text-warning': (row.low_stock_sku_count ?? 0) > 0 }">{{ row.total_online_stock ?? 0 }}</span>
            <div v-if="(row.low_stock_sku_count ?? 0) > 0" style="font-size:12px;color:var(--color-warning)">⚠ {{ row.low_stock_sku_count }} 低库存</div>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" effect="light" size="small">{{ row.is_active ? '上架' : '下架' }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="120" fixed="right" @click.stop>
          <template #default="{ row }">
            <div class="row-actions" @click.stop>
              <el-button link type="primary" size="small" @click.stop="openEditDrawer(row.id)">编辑</el-button>
              <el-dropdown trigger="click" @command="(cmd: string) => handleProductMenuAction(cmd, row)">
                <el-button link size="small" :icon="MoreFilled" @click.stop />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item :command="row.is_active ? 'deactivate' : 'activate'">{{ row.is_active ? '下架' : '上架' }}</el-dropdown-item>
                    <el-dropdown-item command="delete" divided class="danger-item">删除商品</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty description="暂无商品">
            <el-button v-if="searchText || currentTab !== 'all'" @click="searchText = ''; currentTab = 'all'">清除筛选</el-button>
          </el-empty>
        </template>
      </el-table>

      <div class="table-footer">
        <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :total="filteredItems.length" :page-sizes="[10, 20, 50]" layout="sizes, prev, pager, next" />
      </div>
    </el-card>

    <!-- 商品详情/编辑/新建 抽屉 -->
    <el-drawer v-model="isDrawerOpen" :title="drawerTitle" size="760px" destroy-on-close @closed="resetDrawer">
      <el-skeleton v-if="drawerLoading" :rows="6" animated />

      <template v-else-if="drawerMode === 'create' || drawerMode === 'edit'">
        <el-form label-position="top" class="product-form">
          <el-form-item label="商品图片（第一张为主图）">
            <div class="image-wall">
              <div v-for="(img, idx) in productImages" :key="img + idx" class="image-tile">
                <img :src="img" class="image-preview" alt="商品图" />
                <button class="image-remove" type="button" @click="removeImage(idx)">×</button>
              </div>
              <div class="image-add" @click="triggerUpload">
                <el-icon :size="20"><Plus /></el-icon>
                <span>添加图片</span>
              </div>
              <input ref="imageInputRef" type="file" accept="image/*" class="hidden-input" @change="handleImageFileChange" />
            </div>
          </el-form-item>

          <div class="form-grid">
            <el-form-item label="商品名称 *">
              <el-input v-model="form.name" placeholder="例如：婴幼儿薄绒护肚裤" />
            </el-form-item>
            <el-form-item label="货号 *">
              <el-input v-model="form.product_code" :disabled="drawerMode === 'edit'" placeholder="唯一编码" />
            </el-form-item>
            <el-form-item label="商品分类">
              <div class="field-with-action">
                <el-select v-if="!isAddingCategory" v-model="form.category" clearable placeholder="请选择...">
                  <el-option v-for="cat in categoryList" :key="cat" :label="cat" :value="cat" />
                </el-select>
                <template v-else>
                  <el-input v-model="newCategoryName" placeholder="输入新分类" />
                  <el-button type="primary" @click="saveNewCategory">保存</el-button>
                </template>
                <el-button :icon="isAddingCategory ? Close : Plus" link @click="isAddingCategory = !isAddingCategory" />
              </div>
            </el-form-item>
            <el-form-item label="品牌">
              <el-input v-model="form.brand" placeholder="例如：某品牌" />
            </el-form-item>
          </div>

          <el-collapse-item v-if="drawerMode === 'create'" title="更多字段（型号 / 描述）">
            <div class="form-grid">
              <el-form-item label="型号"><el-input v-model="form.model_name" /></el-form-item>
              <el-form-item label="描述"><el-input v-model="form.description" /></el-form-item>
            </div>
          </el-collapse-item>

          <el-form-item label="销售设置">
            <div class="toggle-row">
              <el-checkbox v-model="form.supports_retail">支持零售</el-checkbox>
              <el-checkbox v-model="form.supports_wholesale">支持批发</el-checkbox>
              <el-checkbox v-model="form.has_dual_price">双价商品</el-checkbox>
              <el-checkbox v-model="form.is_active">上架前台可见</el-checkbox>
            </div>
          </el-form-item>

          <el-form-item label="规格与库存（SKU 矩阵）">
            <div class="sku-generator">
              <div class="form-grid">
                <el-form-item :label="`${SKU_DIM_1_LABEL} 属性（逗号分隔）`">
                  <el-input v-model="dim1Input" placeholder="例如：红色, 蓝色" @keyup.enter="generateSKUs" />
                </el-form-item>
                <el-form-item :label="`${SKU_DIM_2_LABEL} 属性（逗号分隔）`">
                  <el-input v-model="dim2Input" placeholder="例如：73cm, 80cm" @keyup.enter="generateSKUs" />
                </el-form-item>
              </div>
              <el-button style="width:100%;margin-top:8px" @click="generateSKUs">⚡ 一键生成 / 刷新规格矩阵</el-button>
            </div>
            <el-table v-if="skuList.length > 0" :data="skuList" class="sku-table">
              <el-table-column :label="SKU_DIM_1_LABEL">
                <template #default="{ row }"><el-input v-model="row.spec_value_1" size="small" /></template>
              </el-table-column>
              <el-table-column :label="SKU_DIM_2_LABEL">
                <template #default="{ row }"><el-input v-model="row.spec_value_2" size="small" /></template>
              </el-table-column>
              <el-table-column label="零售价(元)" width="110">
                <template #default="{ row }"><el-input v-model="row.retail_price" size="small" type="number" :disabled="!form.supports_retail" /></template>
              </el-table-column>
              <el-table-column label="批发价(元)" width="110">
                <template #default="{ row }"><el-input v-model="row.wholesale_price" size="small" type="number" :disabled="!form.supports_wholesale" /></template>
              </el-table-column>
              <el-table-column label="库存" width="90">
                <template #default="{ row }"><el-input v-model="row.online_stock" size="small" type="number" /></template>
              </el-table-column>
              <el-table-column label="" width="60">
                <template #default="{ row }"><el-button link type="danger" @click="removeSkuRow(row.id)">删除</el-button></template>
              </el-table-column>
            </el-table>
            <el-button v-if="skuList.length > 0" size="small" style="margin-top:8px" @click="addSkuRow">新增规格行</el-button>
          </el-form-item>
        </el-form>
      </template>

      <template v-else-if="drawerMode === 'detail' && activeDetail">
        <div class="detail-images">
          <img v-for="(img, idx) in activeDetail.image_urls || []" :key="idx" :src="img" class="detail-thumb" :alt="`商品图${idx + 1}`" />
          <el-empty v-if="!(activeDetail.image_urls || []).length" :image-size="48" description="暂无图片" />
        </div>

        <el-descriptions :column="2" border class="detail-desc">
          <el-descriptions-item label="名称">{{ activeDetail.name }}</el-descriptions-item>
          <el-descriptions-item label="货号">{{ activeDetail.product_code }}</el-descriptions-item>
          <el-descriptions-item label="分类">{{ toText(activeDetail.category) }}</el-descriptions-item>
          <el-descriptions-item label="品牌">{{ toText(activeDetail.brand) || '无' }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="activeDetail.is_active ? 'success' : 'info'" effect="light" size="small">{{ activeDetail.is_active ? '上架' : '下架' }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="属性">
            <el-tag v-if="activeDetail.supports_retail" size="small" effect="plain">零售</el-tag>
            <el-tag v-if="activeDetail.supports_wholesale" size="small" effect="plain" type="warning">批发</el-tag>
            <el-tag v-if="activeDetail.has_dual_price" size="small" effect="plain" type="success">双价</el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <h4 style="margin:20px 0 10px;font-size:14px;color:var(--text-primary)">规格与库存矩阵</h4>
        <el-table :data="activeDetailMatrix" class="sku-table">
          <el-table-column :label="SKU_DIM_1_LABEL" prop="spec_value_1" />
          <el-table-column :label="SKU_DIM_2_LABEL" prop="spec_value_2" />
          <el-table-column label="零售价" prop="retail_price" width="100" align="right">
            <template #default="{ row }">{{ activeDetail.supports_retail ? '¥' + row.retail_price : '-' }}</template>
          </el-table-column>
          <el-table-column label="批发价" prop="wholesale_price" width="100" align="right">
            <template #default="{ row }">{{ activeDetail.supports_wholesale ? '¥' + row.wholesale_price : '-' }}</template>
          </el-table-column>
          <el-table-column label="库存" prop="online_stock" width="80" align="right" />
        </el-table>
        <div style="text-align:right;margin-top:10px;font-size:13px;color:var(--text-secondary)">
          总库存：<strong style="color:var(--text-primary)">{{ activeDetail.total_online_stock ?? 0 }}</strong>
        </div>
      </template>

      <template #footer>
        <div style="display:flex;justify-content:flex-end;gap:10px">
          <el-button v-if="drawerMode === 'detail'" @click="isDrawerOpen = false">关闭</el-button>
          <el-button v-if="drawerMode === 'detail'" type="primary" @click="startEditing">编辑资料</el-button>
          <el-button v-if="drawerMode === 'edit'" @click="cancelEditing">放弃修改</el-button>
          <el-button v-if="drawerMode === 'edit'" type="primary" :loading="saving" @click="submitProduct">保存修改</el-button>
          <el-button v-if="drawerMode === 'create'" @click="isDrawerOpen = false">取消</el-button>
          <el-button v-if="drawerMode === 'create'" type="primary" :loading="saving" @click="submitProduct">创建商品</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 分类管理抽屉 -->
    <el-drawer v-model="showCatDrawer" title="管理分类" size="380px" destroy-on-close>
      <div class="cat-add-row">
        <el-input v-model="newCatName" placeholder="输入新分类名称" @keyup.enter="saveCat" />
        <el-button type="primary" @click="saveCat">新建</el-button>
      </div>
      <el-empty v-if="categoryOptions.length === 0" description="暂无分类" :image-size="48" />
      <div v-for="cat in categoryOptions" :key="cat.id" class="cat-row">
        <div v-if="editingCat?.id === cat.id" class="cat-edit-inline">
          <el-input v-model="editingCat.name" size="small" />
          <el-button size="small" type="primary" @click="saveEditCat">保存</el-button>
          <el-button size="small" @click="editingCat = null">取消</el-button>
        </div>
        <template v-else>
          <div class="cat-info">
            <span>{{ cat.name }}</span>
            <span class="cat-count">{{ cat.product_count ?? 0 }} 件</span>
          </div>
          <div class="cat-actions">
            <el-button link type="primary" size="small" @click="startEditCat(cat)">编辑</el-button>
            <el-popconfirm title="确定删除该分类？" @confirm="deleteCat(cat.id)">
              <template #reference>
                <el-button link type="danger" size="small">删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh, MoreFilled, Plus, Close } from '@element-plus/icons-vue'
import AppPageHeader from '@/components/AppPageHeader.vue'
import {
  bulkCreateSku,
  createProduct,
  createProductCategory,
  deleteProduct,
  deleteProductCategory,
  fetchProductCategories,
  fetchProductDetail,
  fetchProducts,
  uploadProductImage,
  updateProduct,
  updateProductCategory,
  updateSku,
} from '@/api/modules'
import type {
  CreateProductPayload,
  ProductCategoryItem,
  ProductDetail,
  ProductListItem,
  ProductSkuItem,
  UpdateProductPayload,
} from '@/types/api'
import { makeInitial, toText } from '@/utils/adminFormat'
import ListSummary from '@/components/shared/ListSummary.vue'

const products = ref<ProductListItem[]>([])
const selectedProducts = ref<ProductListItem[]>([])
const categoryOptions = ref<ProductCategoryItem[]>([])
const loading = ref(false)
const saving = ref(false)
const searchText = ref('')
const currentTab = ref('all')
const currentPage = ref(1)
const pageSize = ref(10)
const isDrawerOpen = ref(false)
const drawerLoading = ref(false)
const drawerMode = ref<'create' | 'edit' | 'detail'>('detail')
const activeDetail = ref<ProductDetail | null>(null)
const showCatDrawer = ref(false)
const newCatName = ref('')
const editingCat = ref<ProductCategoryItem | null>(null)
const isAddingCategory = ref(false)
const newCategoryName = ref('')
const productImages = ref<string[]>([])
const imageInputRef = ref<HTMLInputElement | null>(null)
const dim1Input = ref('')
const dim2Input = ref('')

const SKU_DIM_1_LABEL = '颜色/形状'
const SKU_DIM_2_LABEL = '尺码/大小'

interface MatrixSKU { id: string; spec_value_1: string; spec_value_2: string; retail_price: string; wholesale_price: string; online_stock: string }
const skuList = ref<MatrixSKU[]>([])

const form = reactive<CreateProductPayload & { is_active: boolean }>({
  name: '', product_code: '', model_name: '', brand: '', category: '', description: '',
  spec_dim_1_name: SKU_DIM_1_LABEL, spec_dim_2_name: SKU_DIM_2_LABEL,
  supports_retail: true, supports_wholesale: true, has_dual_price: true, is_active: true,
})

const categoryList = computed(() => categoryOptions.value.filter((c) => c.is_active).map((c) => c.name))
const activeProductCount = computed(() => products.value.filter((p) => p.is_active).length)
const filteredItems = computed(() => {
  const kw = searchText.value.trim().toLowerCase()
  let result = products.value.filter((p) => {
    const inTab = currentTab.value === 'all' || (currentTab.value === 'on' && p.is_active) || (currentTab.value === 'low' && (p.low_stock_sku_count ?? 0) > 0)
    const inSearch = !kw || p.name.toLowerCase().includes(kw) || p.product_code.toLowerCase().includes(kw)
    return inTab && inSearch
  })
  return result.sort((a, b) => b.id - a.id)
})
const pagedItems = computed(() => filteredItems.value.slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value))
const activeDetailMatrix = computed(() => (activeDetail.value ? buildMatrixFromDetail(activeDetail.value) : []))
const drawerTitle = computed(() => ({ create: '新建商品', edit: '编辑商品', detail: '商品详情' })[drawerMode.value])

watch([searchText, currentTab], () => { currentPage.value = 1 })

onMounted(() => void Promise.all([loadProducts(), loadCategories()]))

function parseMatrixInput(input: string) { return Array.from(new Set(input.split(/[,，]/).map((v) => v.trim()).filter(Boolean))) }
function toNumberValue(value: string) { const n = Number(value); return Number.isFinite(n) ? n : 0 }
function toStockValue(value: string) { const n = parseInt(value, 10); return Number.isFinite(n) ? Math.max(n, 0) : 0 }
function matrixKey(s1?: string | null, s2?: string | null) { return `${s1 || ''}__${s2 || ''}` }

function buildMatrixFromDetail(detail: ProductDetail): MatrixSKU[] {
  const map = new Map<string, MatrixSKU>()
  detail.skus.forEach((sku: ProductSkuItem) => {
    const key = matrixKey(sku.spec_value_1, sku.spec_value_2)
    if (!map.has(key)) map.set(key, { id: String(sku.id), spec_value_1: sku.spec_value_1 || '', spec_value_2: sku.spec_value_2 || '', retail_price: sku.retail_price, wholesale_price: sku.wholesale_price, online_stock: String(sku.online_stock) })
  })
  return Array.from(map.values())
}

function generateSKUs() {
  const d1 = parseMatrixInput(dim1Input.value); const d2 = parseMatrixInput(dim2Input.value)
  if (!d1.length && !d2.length) { skuList.value = []; return }
  const fd1 = d1.length ? d1 : ['默认']; const fd2 = d2.length ? d2 : ['默认']
  const next: MatrixSKU[] = []
  fd1.forEach((v1) => fd2.forEach((v2) => { const ex = skuList.value.find((s) => s.spec_value_1 === v1 && s.spec_value_2 === v2); next.push(ex || { id: `${v1}-${v2}-${next.length}`, spec_value_1: v1, spec_value_2: v2, retail_price: '', wholesale_price: '', online_stock: '' }) }))
  skuList.value = next
}

function addSkuRow() { skuList.value.push({ id: `m-${skuList.value.length}`, spec_value_1: '', spec_value_2: '', retail_price: '', wholesale_price: '', online_stock: '' }) }
function removeSkuRow(id: string) { skuList.value = skuList.value.filter((r) => r.id !== id) }
function removeImage(idx: number) { productImages.value.splice(idx, 1) }
function triggerUpload() { imageInputRef.value?.click() }

async function handleImageFileChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  try { const res = await uploadProductImage(file); productImages.value.push(res.data.url); ElMessage.success('图片上传成功') }
  finally { (event.target as HTMLInputElement).value = '' }
}

async function loadCategories() {
  const res = await fetchProductCategories()
  categoryOptions.value = res.data
}

async function loadProducts() {
  loading.value = true
  try { const res = await fetchProducts(); products.value = res.data; selectedProducts.value = [] }
  finally { loading.value = false }
}

async function saveCat() {
  const n = newCatName.value.trim(); if (!n) return
  await createProductCategory({ name: n }); newCatName.value = ''; await loadCategories(); ElMessage.success('已创建')
}

async function deleteCat(id: number) {
  try { await deleteProductCategory(id); await loadCategories(); ElMessage.success('已删除') }
  catch { ElMessage.error('删除失败') }
}

function startEditCat(cat: ProductCategoryItem) { editingCat.value = { ...cat } }
async function saveEditCat() {
  if (!editingCat.value?.name.trim()) return
  try { await updateProductCategory(editingCat.value.id, { name: editingCat.value.name.trim() }); editingCat.value = null; await loadCategories(); ElMessage.success('已保存') }
  catch { ElMessage.error('保存失败') }
}

async function saveNewCategory() {
  const name = newCategoryName.value.trim(); if (!name) { ElMessage.warning('请输入分类名称'); return }
  const ex = categoryOptions.value.find((c) => c.name === name)
  if (ex) { form.category = ex.name; isAddingCategory.value = false; newCategoryName.value = ''; return }
  const res = await createProductCategory({ name })
  categoryOptions.value = [res.data, ...categoryOptions.value]; form.category = res.data.name; isAddingCategory.value = false; newCategoryName.value = ''; ElMessage.success('分类已创建')
}

function resetDrawer() { drawerMode.value = 'detail'; activeDetail.value = null; productImages.value = []; skuList.value = []; dim1Input.value = ''; dim2Input.value = '' }

async function openDetailDrawer(productId: number) {
  drawerLoading.value = true; isDrawerOpen.value = true; drawerMode.value = 'detail'
  try { const res = await fetchProductDetail(productId); activeDetail.value = res.data; productImages.value = [...(res.data.image_urls || [])] }
  catch { ElMessage.error('商品加载失败'); isDrawerOpen.value = false }
  finally { drawerLoading.value = false }
}

async function openEditDrawer(productId: number) {
  drawerLoading.value = true; isDrawerOpen.value = true
  try {
    const res = await fetchProductDetail(productId); activeDetail.value = res.data
    const d = res.data
    form.name = d.name; form.product_code = d.product_code; form.model_name = d.model_name || ''
    form.brand = d.brand || ''; form.category = d.category || ''; form.description = d.description || ''
    form.supports_retail = d.supports_retail; form.supports_wholesale = d.supports_wholesale; form.has_dual_price = d.has_dual_price; form.is_active = d.is_active
    productImages.value = [...(d.image_urls || [])]
    const matrix = buildMatrixFromDetail(d); skuList.value = matrix
    dim1Input.value = Array.from(new Set(matrix.map((s) => s.spec_value_1).filter(Boolean))).join(', ')
    dim2Input.value = Array.from(new Set(matrix.map((s) => s.spec_value_2).filter(Boolean))).join(', ')
    drawerMode.value = 'edit'
  }
  catch { ElMessage.error('商品加载失败'); isDrawerOpen.value = false }
  finally { drawerLoading.value = false }
}

function openCreateDrawer() {
  resetDrawer()
  form.name = ''; form.product_code = ''; form.model_name = ''; form.brand = ''; form.category = ''; form.description = ''
  form.supports_retail = true; form.supports_wholesale = true; form.has_dual_price = true; form.is_active = true
  drawerMode.value = 'create'; isDrawerOpen.value = true
}

function startEditing() {
  if (!activeDetail.value) return
  const d = activeDetail.value
  form.name = d.name; form.product_code = d.product_code; form.model_name = d.model_name || ''
  form.brand = d.brand || ''; form.category = d.category || ''; form.description = d.description || ''
  form.supports_retail = d.supports_retail; form.supports_wholesale = d.supports_wholesale; form.has_dual_price = d.has_dual_price; form.is_active = d.is_active
  productImages.value = [...(d.image_urls || [])]
  const matrix = buildMatrixFromDetail(d); skuList.value = matrix
  dim1Input.value = Array.from(new Set(matrix.map((s) => s.spec_value_1).filter(Boolean))).join(', ')
  dim2Input.value = Array.from(new Set(matrix.map((s) => s.spec_value_2).filter(Boolean))).join(', ')
  drawerMode.value = 'edit'
}

function cancelEditing() { drawerMode.value = 'detail' }

async function submitProduct() {
  if (!form.name.trim() || !form.product_code.trim()) { ElMessage.warning('请填写商品名称和货号'); return }
  saving.value = true
  try {
    const payload: UpdateProductPayload = {
      name: form.name.trim(), category: form.category || undefined, brand: form.brand || undefined,
      model_name: form.model_name || undefined, description: form.description || undefined,
      supports_retail: form.supports_retail, supports_wholesale: form.supports_wholesale, has_dual_price: form.has_dual_price,
      is_active: form.is_active, image_urls: productImages.value,
    }
    if (drawerMode.value === 'create') {
      const createPayload: CreateProductPayload = { name: form.name.trim(), product_code: form.product_code.trim(), spec_dim_1_name: form.spec_dim_1_name, spec_dim_2_name: form.spec_dim_2_name, supports_retail: form.supports_retail, supports_wholesale: form.supports_wholesale, has_dual_price: form.has_dual_price, category: form.category || undefined, brand: form.brand || undefined, model_name: form.model_name || undefined, description: form.description || undefined, image_urls: productImages.value }
      const res = await createProduct(createPayload)
      if (skuList.value.length > 0) {
        const skuPayload = { product_id: (res.data as { id: number }).id, sku_type: 'retail' as const, spec_values_1: skuList.value.map((s) => s.spec_value_1), spec_values_2: skuList.value.map((s) => s.spec_value_2), online_stock: toStockValue(skuList.value[0].online_stock), retail_price: toNumberValue(skuList.value[0].retail_price), wholesale_price: toNumberValue(skuList.value[0].wholesale_price), min_sale_qty: 1, min_wholesale_qty: 1, is_mixed_pack: false }
        await bulkCreateSku(skuPayload)
      }
      ElMessage.success('商品已创建')
    } else {
      if (!activeDetail.value) return
      await updateProduct(activeDetail.value.id, payload)
      for (const sku of skuList.value) {
        const id = Number(sku.id)
        if (!isNaN(id) && id > 0) await updateSku(id, { retail_price: toNumberValue(sku.retail_price), wholesale_price: toNumberValue(sku.wholesale_price), online_stock: toStockValue(sku.online_stock) })
      }
      ElMessage.success('已保存修改')
    }
    isDrawerOpen.value = false
    await loadProducts()
  } finally { saving.value = false }
}

async function handleProductMenuAction(cmd: string, item: ProductListItem) {
  if (cmd === 'activate' || cmd === 'deactivate') {
    try { await updateProduct(item.id, { is_active: cmd === 'activate' }); await loadProducts(); ElMessage.success(cmd === 'activate' ? '已上架' : '已下架') }
    catch { ElMessage.error('操作失败') }
  }
  if (cmd === 'delete') {
    try { await deleteProduct(item.id); await loadProducts(); ElMessage.success('已删除') }
    catch { ElMessage.error('删除失败') }
  }
}

async function setSelectedProductsActive(isActive: boolean) {
  const targets = selectedProducts.value.filter((product) => product.is_active !== isActive)
  if (!targets.length) { ElMessage.info(isActive ? '所选商品已全部上架' : '所选商品已全部下架'); return }
  try {
    await Promise.all(targets.map((product) => updateProduct(product.id, { is_active: isActive })))
    await loadProducts()
    ElMessage.success(`已${isActive ? '上架' : '下架'} ${targets.length} 件商品`)
  } catch { ElMessage.error('批量操作未完成，请刷新后核对商品状态') }
}

</script>

<style scoped>
.products-page { display: grid; gap: 18px; }
.list-card { border-radius: 8px; }
.list-card :deep(.el-card__header) { padding: 14px 20px; }
.list-card :deep(.el-card__body) { padding: 0 20px 16px; }
.list-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.batch-bar { display: flex; align-items: center; gap: 10px; min-height: 46px; padding: 0 12px; border-bottom: 1px solid var(--border-light); background: var(--bg-canvas); color: var(--text-secondary); font-size: 13px; }
.filter-bar { display: flex; align-items: center; gap: 10px; }
.product-cell { display: flex; align-items: center; gap: 12px; }
.product-thumb { width: 44px; height: 44px; object-fit: cover; border-radius: 6px; border: 1px solid var(--border-light); flex-shrink: 0; }
.product-thumb.placeholder { background: var(--bg-canvas); display: flex; align-items: center; justify-content: center; font-size: 16px; font-weight: 700; color: var(--text-tertiary); }
.product-name { font-weight: 600; color: var(--text-primary); line-height: 1.4; }
.product-meta { font-size: 12px; color: var(--text-tertiary); margin-top: 3px; }
.row-actions { display: flex; align-items: center; gap: 4px; }
.table-footer { display: flex; justify-content: flex-end; padding-top: 14px; }
.product-form :deep(.el-form-item) { margin-bottom: 18px; }
.product-form :deep(.el-collapse-item__header) { font-size: 14px; color: var(--text-secondary); }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 16px; }
.field-with-action { display: flex; gap: 8px; align-items: center; width: 100%; }
.field-with-action .el-select, .field-with-action .el-input { flex: 1; }
.toggle-row { display: flex; gap: 20px; flex-wrap: wrap; }
.sku-generator { margin-bottom: 12px; }
.sku-table { width: 100%; margin-top: 8px; }
.image-wall { display: flex; flex-wrap: wrap; gap: 10px; }
.image-tile { position: relative; width: 88px; height: 88px; border-radius: 6px; overflow: hidden; border: 1px solid var(--border-light); }
.image-preview { width: 100%; height: 100%; object-fit: cover; }
.image-remove { position: absolute; top: 4px; right: 4px; width: 20px; height: 20px; background: rgba(0,0,0,0.55); color: #fff; border: none; border-radius: 50%; cursor: pointer; font-size: 13px; line-height: 1; display: flex; align-items: center; justify-content: center; }
.image-add { width: 88px; height: 88px; border: 1px dashed var(--border-light); border-radius: 6px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; cursor: pointer; font-size: 12px; color: var(--text-tertiary); transition: border-color .18s ease; }
.image-add:hover { border-color: var(--color-primary); color: var(--color-primary); }
.hidden-input { display: none; }
.detail-images { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; }
.detail-thumb { width: 100px; height: 100px; object-fit: cover; border-radius: 8px; border: 1px solid var(--border-light); }
.detail-desc { margin-bottom: 12px; }
.cat-add-row { display: flex; gap: 8px; margin-bottom: 16px; }
.cat-row { display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--border-light); }
.cat-info { display: flex; gap: 8px; align-items: center; }
.cat-count { font-size: 12px; color: var(--text-tertiary); }
.cat-actions { display: flex; gap: 4px; }
.cat-edit-inline { display: flex; gap: 6px; align-items: center; flex: 1; }
:deep(.danger-item) { color: var(--el-color-danger); }
.text-warning { color: var(--color-warning); }
</style>
