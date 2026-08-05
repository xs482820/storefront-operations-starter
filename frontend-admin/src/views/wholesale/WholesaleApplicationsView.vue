<template>
  <div class="page-container">
    <header class="page-header">
      <div>
        <h1 class="page-title">批发资格审核</h1>
        <p class="page-subtitle">零售用户升级为批发身份的申请审核</p>
      </div>
    </header>

    <div class="stat-grid">
      <div class="stat-card">
        <span class="stat-label">待审核申请</span>
        <div class="stat-number">{{ pendingCount }}</div>
      </div>
      <div class="stat-card">
        <span class="stat-label">已通过申请</span>
        <div class="stat-number">{{ approvedCount }}</div>
      </div>
      <div class="stat-card">
        <span class="stat-label">当前批发用户</span>
        <div class="stat-number">{{ wholesaleUsers.length }}</div>
      </div>
    </div>

    <div class="content-grid">
      <section class="content-panel panel-main">
        <BaseListToolbar
          v-model="searchText"
          v-model:currentSort="currentSort"
          placeholder="搜索申请人、门店、公司"
          :sortOptions="sortOptions"
        >
          <template #left>
            <div class="filter-tabs">
              <button
                v-for="tab in tabs"
                :key="tab.value"
                :class="['tab-btn', currentTab === tab.value ? 'active' : '']"
                @click="currentTab = tab.value"
              >
                {{ tab.label }}
              </button>
            </div>
          </template>
          <template #right>
            <button class="btn-outline btn-inline" :disabled="loading" @click="load">刷新</button>
          </template>
        </BaseListToolbar>

        <BaseBatchToolbar
          :selected-count="selectedApplications.length"
          hint="选中申请后可批量通过或驳回"
          :actions="applicationBatchActions"
          @clear="clearSelection"
          @action="handleApplicationBatchAction"
        />

        <div v-if="loading" class="table-empty">正在加载申请列表...</div>
        <div v-else class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th class="selection-col">
                  <input
                    type="checkbox"
                    class="row-checkbox"
                    :checked="isPageSelectedAll"
                    :indeterminate.prop="isPageSelectionIndeterminate"
                    @change="toggleSelectAllOnPage(($event.target as HTMLInputElement).checked)"
                  />
                </th>
                <th>申请人</th>
                <th>公司 / 门店</th>
                <th>联系方式</th>
                <th>状态</th>
                <th class="text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in pagedItems" :key="item.id" @click="openDrawer('detail', item)" style="cursor: pointer">
                <td class="selection-col" @click.stop>
                  <input
                    type="checkbox"
                    class="row-checkbox"
                    :checked="selectedApplicationIds.includes(item.id)"
                    @change="toggleSelectApplication(item.id, ($event.target as HTMLInputElement).checked)"
                  />
                </td>
                <td>
                  <div class="font-bold">{{ item.contact_name || item.username }}</div>
                  <div class="text-tertiary text-sm">{{ item.username }}</div>
                </td>
                <td>
                  <div>{{ item.store_name || item.company_name || '未填写' }}</div>
                  <div class="text-tertiary text-sm">{{ item.company_name || '无公司信息' }}</div>
                </td>
                <td>
                  <div>{{ toText(item.contact_phone) }}</div>
                  <div class="text-tertiary text-sm">{{ item.business_license_url ? '已上传执照' : '未上传执照' }}</div>
                </td>
                <td>
                  <span :class="['badge', statusClass(item.status)]">{{ statusLabel(item.status) }}</span>
                </td>
                <td>
                  <div class="actions-cell text-right" @click.stop>
                    <BaseMoreMenu
                      :items="applicationMoreActions(item)"
                      @select="(action) => handleApplicationMoreAction(action, item)"
                    />
                  </div>
                </td>
              </tr>
              <tr v-if="pagedItems.length === 0">
                <td colspan="6" class="table-empty">暂无符合条件的申请</td>
              </tr>
            </tbody>
          </table>
        </div>

        <BasePagination
          :total="filteredItems.length"
          v-model:currentPage="currentPage"
          v-model:pageSize="pageSize"
        />
      </section>

      <section class="content-panel panel-side">
        <div class="panel-block">
          <h3 class="section-title">当前批发用户</h3>
          <div class="user-list">
            <div v-for="user in wholesaleUsers.slice(0, 8)" :key="user.id" class="user-card">
              <div>
                <div class="font-bold">{{ user.display_name || user.username }}</div>
                <div class="text-tertiary text-sm">{{ user.store_name || user.company_name || '未补充门店' }}</div>
              </div>
              <span class="text-tertiary text-sm">{{ toText(user.phone) }}</span>
            </div>
            <div v-if="wholesaleUsers.length === 0" class="table-empty side-empty">当前还没有批发用户。</div>
          </div>
        </div>
      </section>
    </div>

    <BaseDrawer v-model="isDrawerOpen" :title="drawerTitle" width="560px">
      <div v-if="activeItem" class="drawer-content">
        <section class="detail-block">
          <h3 class="section-title">申请资料</h3>
          <div class="info-card">
            <div class="info-row"><span>申请用户</span><strong>{{ activeItem.username }}</strong></div>
            <div class="info-row"><span>联系人</span><strong>{{ toText(activeItem.contact_name) }}</strong></div>
            <div class="info-row"><span>联系电话</span><strong>{{ toText(activeItem.contact_phone) }}</strong></div>
            <div class="info-row"><span>门店</span><strong>{{ toText(activeItem.store_name) }}</strong></div>
            <div class="info-row"><span>公司</span><strong>{{ toText(activeItem.company_name) }}</strong></div>
          </div>
        </section>

        <section class="detail-block" v-if="activeItem.business_license_url">
          <h3 class="section-title">营业执照</h3>
          <a class="license-preview-link" :href="activeItem.business_license_url" target="_blank" rel="noopener noreferrer">
            <img class="license-preview-image" :src="activeItem.business_license_url" alt="营业执照" />
          </a>
        </section>

        <section class="detail-block">
          <h3 class="section-title">申请说明</h3>
          <div class="remark-box">{{ activeItem.remark || '暂无说明' }}</div>
        </section>

        <section class="detail-block">
          <h3 class="section-title">状态信息</h3>
          <div class="info-card">
            <div class="info-row"><span>申请状态</span><strong>{{ statusLabel(activeItem.status) }}</strong></div>
            <div class="info-row"><span>审核备注</span><strong>{{ activeItem.review_note || '暂无审核备注' }}</strong></div>
            <div class="info-row"><span>提交时间</span><strong>{{ formatDateText(activeItem.created_at) }}</strong></div>
            <div class="info-row"><span>处理时间</span><strong>{{ formatDateText(activeItem.reviewed_at) }}</strong></div>
          </div>
        </section>

        <section v-if="drawerMode === 'audit'" class="detail-block">
          <h3 class="section-title">审核动作</h3>
          <div class="field-grid">
            <label class="field-label">
              <span>审核结果</span>
              <select v-model="reviewStatus" class="field-input">
                <option value="approved">通过</option>
                <option value="rejected">驳回</option>
              </select>
            </label>
            <label class="field-label field-label-full">
              <span>审核备注</span>
              <textarea v-model="reviewNote" class="field-input textarea" rows="4" placeholder="补充审核结论或驳回原因"></textarea>
            </label>
          </div>
        </section>
      </div>

      <template #footer>
        <button class="btn-outline" @click="isDrawerOpen = false">关闭</button>
        <button v-if="drawerMode === 'audit'" class="btn-primary" :disabled="submitting || !activeItem" @click="submitReview">
          {{ submitting ? '提交中...' : '提交审核' }}
        </button>
      </template>
    </BaseDrawer>

    <CustomerDetailDrawer
      v-model="isCustomerDrawerOpen"
      :customer-id="activeCustomerId"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from '@/utils/message'

import BaseBatchToolbar from '@/components/BaseBatchToolbar.vue'
import BaseDrawer from '@/components/BaseDrawer.vue'
import BaseListToolbar from '@/components/BaseListToolbar.vue'
import BaseMoreMenu from '@/components/BaseMoreMenu.vue'
import BasePagination from '@/components/BasePagination.vue'
import CustomerDetailDrawer from '@/components/users/CustomerDetailDrawer.vue'
import { fetchUsers, fetchWholesaleApplications, reviewWholesaleApplication } from '@/api/modules'
import type { UserListItem, WholesaleApplicationItem } from '@/types/api'
import { toText } from '@/utils/adminFormat'

const tabs = [
  { label: '全部申请', value: 'all' },
  { label: '待审核', value: 'pending' },
  { label: '已通过', value: 'approved' },
]

const sortOptions = [
  { label: '最新申请', value: 'created_desc' },
  { label: '门店名称', value: 'store_asc' },
]

const loading = ref(false)
const batchLoading = ref(false)
const submitting = ref(false)
const applications = ref<WholesaleApplicationItem[]>([])
const wholesaleUsers = ref<UserListItem[]>([])
const searchText = ref('')
const currentSort = ref('created_desc')
const currentTab = ref('all')
const currentPage = ref(1)
const pageSize = ref(10)
const selectedApplicationIds = ref<number[]>([])
const drawerMode = ref<'detail' | 'audit'>('detail')
const isDrawerOpen = ref(false)
const activeItem = ref<WholesaleApplicationItem | null>(null)
const reviewStatus = ref<'approved' | 'rejected'>('approved')
const reviewNote = ref('')
const isCustomerDrawerOpen = ref(false)
const activeCustomerId = ref<number | string | null>(null)

const pendingCount = computed(() => applications.value.filter((item) => item.status === 'pending').length)
const approvedCount = computed(() => applications.value.filter((item) => item.status === 'approved').length)

const filteredItems = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  let result = applications.value.filter((item) => {
    const inTab = currentTab.value === 'all' || item.status === currentTab.value
    const inSearch =
      !keyword ||
      item.username.toLowerCase().includes(keyword) ||
      (item.company_name || '').toLowerCase().includes(keyword) ||
      (item.store_name || '').toLowerCase().includes(keyword)
    return inTab && inSearch
  })

  if (currentSort.value === 'store_asc') {
    result = [...result].sort((a, b) => (a.store_name || '').localeCompare(b.store_name || '', 'zh-CN'))
  } else {
    result = [...result].sort((a, b) => b.id - a.id)
  }
  return result
})

const pagedItems = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredItems.value.slice(start, start + pageSize.value)
})

const selectedApplications = computed(() => pagedItems.value.filter((item) => selectedApplicationIds.value.includes(item.id)))
const selectedPendingApplications = computed(() => selectedApplications.value.filter((item) => item.status === 'pending'))
const isPageSelectedAll = computed(() => pagedItems.value.length > 0 && pagedItems.value.every((item) => selectedApplicationIds.value.includes(item.id)))
const isPageSelectionIndeterminate = computed(() => selectedApplications.value.length > 0 && !isPageSelectedAll.value)
const applicationBatchActions = computed(() => [
  {
    key: 'approve',
    label: `批量通过 (${selectedPendingApplications.value.length})`,
    disabled: selectedPendingApplications.value.length === 0 || batchLoading.value,
  },
  {
    key: 'reject',
    label: `批量驳回 (${selectedPendingApplications.value.length})`,
    danger: true,
    disabled: selectedPendingApplications.value.length === 0 || batchLoading.value,
  },
])

const drawerTitle = computed(() => (drawerMode.value === 'audit' ? '批发资格审核' : '批发申请详情'))

watch([searchText, currentSort], () => {
  currentPage.value = 1
  clearSelection()
})

watch(currentTab, () => {
  currentPage.value = 1
  clearSelection()
  void load()
})

watch(currentPage, () => {
  clearSelection()
})

watch(pageSize, () => {
  currentPage.value = 1
  clearSelection()
})

onMounted(() => {
  void load()
})

function statusLabel(status: WholesaleApplicationItem['status']) {
  if (status === 'pending') return '待审核'
  if (status === 'approved') return '已通过'
  return '已驳回'
}

function statusClass(status: WholesaleApplicationItem['status']) {
  if (status === 'pending') return 'badge-warning'
  if (status === 'approved') return 'badge-success'
  return 'badge-muted'
}

function formatDateText(value?: string | null) {
  if (!value) return '暂无'
  return value.replace('T', ' ').slice(0, 16)
}

async function load() {
  loading.value = true
  try {
    const [applicationsResponse, usersResponse] = await Promise.all([
      fetchWholesaleApplications(),
      fetchUsers({ role: 'wholesale' }),
    ])
    applications.value = applicationsResponse.data
    wholesaleUsers.value = usersResponse.data
    clearSelection()
  } finally {
    loading.value = false
  }
}

function clearSelection() {
  selectedApplicationIds.value = []
}

function toggleSelectApplication(applicationId: number, checked: boolean) {
  const next = new Set(selectedApplicationIds.value)
  if (checked) {
    next.add(applicationId)
  } else {
    next.delete(applicationId)
  }
  selectedApplicationIds.value = Array.from(next)
}

function toggleSelectAllOnPage(checked: boolean) {
  const pageIds = pagedItems.value.map((item) => item.id)
  if (checked) {
    selectedApplicationIds.value = Array.from(new Set([...selectedApplicationIds.value, ...pageIds]))
  } else {
    const pageSet = new Set(pageIds)
    selectedApplicationIds.value = selectedApplicationIds.value.filter((id) => !pageSet.has(id))
  }
}

function openDrawer(mode: 'detail' | 'audit', item: WholesaleApplicationItem) {
  drawerMode.value = mode
  activeItem.value = item
  reviewStatus.value = item.status === 'rejected' ? 'rejected' : 'approved'
  reviewNote.value = item.review_note || ''
  isDrawerOpen.value = true
}

function applicationMoreActions(item: WholesaleApplicationItem) {
  return [
    { key: 'audit', label: '去审核', disabled: item.status !== 'pending' },
    { key: 'customer', label: '查看客户' },
  ]
}

async function openCustomerDrawerByUsername(username: string) {
  const trimmed = username.trim()
  if (!trimmed) {
    ElMessage.warning('当前申请没有可匹配的客户信息')
    return
  }

  try {
    const response = await fetchUsers({ keyword: trimmed })
    const target = response.data.find((item) => item.username === trimmed) || response.data[0]
    if (!target) {
      ElMessage.warning('未找到对应客户')
      return
    }
    activeCustomerId.value = target.id
    isCustomerDrawerOpen.value = true
  } catch {
    ElMessage.error('客户信息加载失败')
  }
}

async function handleApplicationMoreAction(action: string, item: WholesaleApplicationItem) {
  if (action === 'audit') {
    openDrawer('audit', item)
    return
  }
  if (action === 'customer') {
    await openCustomerDrawerByUsername(item.username)
  }
}

async function submitReview() {
  if (!activeItem.value) return
  submitting.value = true
  try {
    await reviewWholesaleApplication(activeItem.value.id, {
      status: reviewStatus.value,
      review_note: reviewNote.value || undefined,
    })
    ElMessage.success('批发申请已处理')
    isDrawerOpen.value = false
    await load()
  } finally {
    submitting.value = false
  }
}

async function batchReviewApplications(nextStatus: 'approved' | 'rejected') {
  const targets = selectedPendingApplications.value
  if (targets.length === 0) return
  if (!confirm(`确定要批量${nextStatus === 'approved' ? '通过' : '驳回'}当前页选中的 ${targets.length} 个待审核申请吗？`)) {
    return
  }

  batchLoading.value = true
  try {
    for (const item of targets) {
      await reviewWholesaleApplication(item.id, {
        status: nextStatus,
        review_note: nextStatus === 'rejected' ? '批量驳回' : undefined,
      })
    }
    ElMessage.success(`已批量${nextStatus === 'approved' ? '通过' : '驳回'} ${targets.length} 个申请`)
    await load()
  } catch {
    ElMessage.error('批量操作失败，请稍后重试')
  } finally {
    batchLoading.value = false
  }
}

async function handleApplicationBatchAction(action: string) {
  if (action === 'approve') {
    await batchReviewApplications('approved')
    return
  }
  if (action === 'reject') {
    await batchReviewApplications('rejected')
  }
}
</script>

<style scoped>
.page-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
  color: var(--text-primary);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
}

.page-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
}

.page-subtitle {
  margin: 8px 0 0;
  font-size: 14px;
  color: var(--text-tertiary);
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.stat-card {
  padding: 20px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  box-shadow: var(--shadow-sm);
}

.stat-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.stat-number {
  margin-top: 8px;
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
}

.content-grid {
  display: grid;
  grid-template-columns: 1.7fr 1fr;
  gap: 24px;
}

.content-panel {
  overflow: hidden;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  box-shadow: var(--shadow-sm);
}

.panel-main {
  min-width: 0;
}

.panel-side {
  padding: 20px;
}

.panel-block {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-tabs {
  display: flex;
  gap: 4px;
}

.tab-btn {
  padding: 6px 14px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}

.tab-btn.active {
  background: var(--bg-canvas);
  color: var(--text-primary);
  font-weight: 600;
}

.table-container {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  text-align: left;
  color: var(--text-primary);
}

.data-table th {
  padding: 14px 20px;
  background: var(--bg-table-header);
  color: var(--text-secondary);
  font-weight: 500;
  border-bottom: 1px solid var(--border-light);
  white-space: nowrap;
}

.data-table td {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-light);
  vertical-align: middle;
  color: var(--text-primary);
}

.selection-col {
  width: 44px;
}

.row-checkbox {
  width: 16px;
  height: 16px;
  accent-color: var(--color-primary);
}

.table-empty {
  padding: 32px 20px;
  text-align: center;
  color: var(--text-tertiary);
}

.side-empty {
  padding: 12px 0;
}

.actions-cell {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.badge {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
}

.badge-warning {
  background: rgba(245, 158, 11, 0.14);
  color: var(--color-warning);
}

.badge-success {
  background: rgba(34, 197, 94, 0.12);
  color: var(--color-success);
}

.badge-muted {
  background: var(--bg-canvas);
  color: var(--text-secondary);
}

.user-list {
  display: grid;
  gap: 12px;
}

.user-card {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-canvas);
}

.drawer-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.detail-block {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-title {
  margin: 0;
  padding-left: 8px;
  border-left: 4px solid var(--color-primary);
  font-size: 16px;
  font-weight: 600;
}

.info-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-canvas);
}

.info-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.remark-box {
  padding: 14px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-canvas);
  line-height: 1.6;
  color: var(--text-primary);
}

.field-grid {
  display: grid;
  gap: 12px;
}

.field-label {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 14px;
  color: var(--text-primary);
}

.field-label-full {
  grid-column: 1 / -1;
}

.field-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-primary);
  box-sizing: border-box;
}

.textarea {
  resize: vertical;
}

.btn-primary {
  padding: 10px 18px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: #fff;
  cursor: pointer;
}

.btn-primary:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.btn-outline {
  padding: 8px 18px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
}

.btn-inline {
  padding: 8px 12px;
}

.btn-link {
  padding: 0;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  text-decoration: underline;
  cursor: pointer;
  white-space: nowrap;
}

.font-bold {
  font-weight: 600;
  color: var(--text-primary);
}

.text-right {
  text-align: right;
}

.text-sm {
  font-size: 13px;
}

.text-tertiary {
  color: var(--text-tertiary);
}

.license-preview-link {
  display: block;
  max-width: 100%;
}

.license-preview-image {
  display: block;
  width: 100%;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  object-fit: cover;
}
</style>
