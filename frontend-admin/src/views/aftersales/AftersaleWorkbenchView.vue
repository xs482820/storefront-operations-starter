<template>
  <div class="aftersale-page">
    <AppPageHeader title="售后处理" description="登记、处理结论、证据与追踪。">
      <template #actions>
        <el-button :icon="Refresh" :loading="loading" @click="loadAftersales(true)">刷新</el-button>
      </template>
    </AppPageHeader>

    <el-card shadow="never" class="list-card">
      <template #header>
        <div class="list-header">
          <div class="filter-bar">
            <el-input v-model="searchText" :prefix-icon="Search" clearable placeholder="订单号、客户、售后原因" style="width:230px" />
            <el-button link type="primary" @click="searchText = ''">清除</el-button>
          </div>
          <ListSummary :items="[{ value: filteredItems.length, label: '笔售后' }, { value: pendingCount, label: '待处理', tone: 'warning' }, { value: resolvedCount, label: '已完结' }]" />
        </div>
      </template>

      <el-tabs v-model="currentTab" @tab-change="onTabChange">
        <el-tab-pane label="全部售后" name="all" />
        <el-tab-pane name="pending">
          <template #label>
            待处理
          </template>
        </el-tab-pane>
        <el-tab-pane label="已完结" name="resolved" />
      </el-tabs>

      <el-table v-loading="loading" :data="pagedItems" row-key="id" style="cursor:pointer" :row-class-name="rowClass" @row-click="(row: AftersaleItem) => openDrawer(row.status === 'pending' ? 'resolve' : 'detail', row)">
        <el-table-column label="订单" min-width="180">
          <template #default="{ row }">
            <div class="order-no">{{ row.order_no || `订单 #${row.order_id}` }}</div>
            <div class="muted">{{ formatDateTime(row.created_at) }}</div>
          </template>
        </el-table-column>

        <el-table-column label="客户" min-width="140">
          <template #default="{ row }">
            <div class="font-bold">{{ row.customer_name || '未命名客户' }}</div>
            <div class="muted">{{ buyerRoleLabel(row.buyer_role) }}</div>
          </template>
        </el-table-column>

        <el-table-column label="原因" min-width="150">
          <template #default="{ row }">
            <div class="font-bold">{{ reasonLabel(row.reason) }}</div>
            <div class="muted line-clamp">{{ row.custom_reason_text || row.note || '无补充说明' }}</div>
          </template>
        </el-table-column>

        <el-table-column label="处理结果" min-width="130">
          <template #default="{ row }">
            <div>{{ processTypeLabel(row.process_type) }}</div>
            <div class="muted">退款 {{ formatCurrency(row.refund_amount || 0) }}</div>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="96">
          <template #default="{ row }">
            <StatusTag kind="aftersale" :status="row.status" />
          </template>
        </el-table-column>

        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <div class="row-actions" @click.stop>
              <el-dropdown trigger="click" @command="(command: string) => handleMenu(command, row)">
                <el-button size="small" circle :icon="MoreFilled" title="更多操作" />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item :command="row.status === 'pending' ? 'resolve' : 'detail'">{{ row.status === 'pending' ? '处理售后' : '查看详情' }}</el-dropdown-item>
                    <el-dropdown-item command="notes">编辑说明</el-dropdown-item>
                    <el-dropdown-item command="delete" divided class="danger-item">删除售后</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty :description="searchText ? '没有符合条件的售后记录' : '该分类暂无售后记录'" :image-size="60">
            <el-button v-if="searchText" @click="searchText = ''">清除搜索</el-button>
          </el-empty>
        </template>
      </el-table>

      <div class="table-footer">
        <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :total="filteredItems.length" :page-sizes="[10, 20, 50]" layout="sizes, prev, pager, next" />
      </div>
    </el-card>

    <!-- 售后详情/处理抽屉 -->
    <el-drawer v-model="isDrawerOpen" :title="drawerTitle" size="560px" destroy-on-close>
      <template v-if="activeItem">
        <section class="drawer-section">
          <h3>售后概览</h3>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="订单号">{{ activeItem.order_no || `订单 #${activeItem.order_id}` }}</el-descriptions-item>
            <el-descriptions-item label="客户">{{ activeItem.customer_name || '未命名客户' }}</el-descriptions-item>
            <el-descriptions-item label="售后原因">{{ reasonLabel(activeItem.reason) }}</el-descriptions-item>
            <el-descriptions-item label="手机号">{{ toText(activeItem.customer_phone) }}</el-descriptions-item>
          </el-descriptions>
        </section>

        <section class="drawer-section">
          <h3>处理结果</h3>
          <template v-if="drawerMode === 'resolve'">
            <el-form label-position="top">
              <el-form-item label="处理方式">
                <el-select v-model="resolveForm.process_type" style="width:100%">
                  <el-option label="仅退款" value="refund_only" />
                  <el-option label="退货退款" value="refund_and_return" />
                  <el-option label="换货" value="exchange" />
                  <el-option label="拒绝" value="rejected" />
                </el-select>
              </el-form-item>
              <el-form-item v-if="resolveForm.process_type !== 'exchange' && resolveForm.process_type !== 'rejected'" label="退款金额">
                <el-input v-model="resolveForm.refund_amount" type="number" min="0" step="0.01" />
              </el-form-item>
              <el-form-item label="沟通截图 *">
                <ImageUploadField v-model="resolveForm.chat_proof_url" hint="支持拖拽、粘贴、选择图片，也可直接粘贴链接" />
              </el-form-item>
              <el-form-item label="客户可见说明">
                <el-input v-model="resolveForm.customer_note" type="textarea" :rows="3" placeholder="客户售后详情会显示" />
              </el-form-item>
              <el-form-item label="店内备注">
                <el-input v-model="resolveForm.internal_note" type="textarea" :rows="3" placeholder="仅后台与工作台可见" />
              </el-form-item>
            </el-form>
          </template>
          <template v-else-if="drawerMode === 'notes'">
            <el-alert type="info" :closable="false" title="客户说明会同步到客户售后页；店内备注仅供内部交接。" style="margin-bottom:16px" />
            <el-form label-position="top">
              <el-form-item label="客户可见说明"><el-input v-model="notesForm.customer_note" type="textarea" :rows="3" /></el-form-item>
              <el-form-item label="店内备注"><el-input v-model="notesForm.internal_note" type="textarea" :rows="3" /></el-form-item>
            </el-form>
          </template>
          <template v-else>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="处理方式">{{ processTypeLabel(activeItem.process_type) }}</el-descriptions-item>
              <el-descriptions-item label="退款金额">{{ formatCurrency(activeItem.refund_amount || 0) }}</el-descriptions-item>
              <el-descriptions-item label="处理人">{{ toText(activeItem.handler_name) }}</el-descriptions-item>
              <el-descriptions-item label="沟通截图">
                <a v-if="activeItem.chat_proof_url" :href="activeItem.chat_proof_url" target="_blank" rel="noopener">查看截图</a>
                <span v-else style="color:var(--text-tertiary)">未上传</span>
              </el-descriptions-item>
              <el-descriptions-item v-if="activeItem.customer_note || activeItem.note" :span="2" label="客户说明">{{ activeItem.customer_note || activeItem.note }}</el-descriptions-item>
              <el-descriptions-item v-if="activeItem.internal_note" :span="2" label="店内备注">{{ activeItem.internal_note }}</el-descriptions-item>
            </el-descriptions>
          </template>
        </section>
      </template>

      <template #footer>
        <div style="display:flex;justify-content:flex-end;gap:10px">
          <el-button @click="isDrawerOpen = false">关闭</el-button>
          <el-button v-if="drawerMode === 'resolve'" type="primary" :loading="submitting" @click="submitResolve">完结售后</el-button>
          <el-button v-if="drawerMode === 'notes'" type="primary" :loading="submitting" @click="submitNotes">保存说明</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, MoreFilled } from '@element-plus/icons-vue'
import AppPageHeader from '@/components/AppPageHeader.vue'
import StatusTag from '@/components/shared/StatusTag.vue'
import ListSummary from '@/components/shared/ListSummary.vue'
import ImageUploadField from '@/components/shared/ImageUploadField.vue'
import { deleteAdminAftersale, fetchAftersales, resolveAftersale, updateAftersaleNotes } from '@/api/modules'
import type { AftersaleItem } from '@/types/api'
import { formatCurrency, formatDateTime, toText } from '@/utils/adminFormat'

const route = useRoute()
const router = useRouter()
const items = ref<AftersaleItem[]>([])
const loading = ref(false)
const submitting = ref(false)
const searchText = ref('')
const currentTab = ref('all')
const currentPage = ref(1)
const pageSize = ref(10)
const isDrawerOpen = ref(false)
const drawerMode = ref<'detail' | 'resolve' | 'notes'>('detail')
const activeItem = ref<AftersaleItem | null>(null)
const focusedAftersaleId = ref<number | null>(null)
const resolveForm = reactive({ process_type: 'refund_only', refund_amount: '0.00', chat_proof_url: '', customer_note: '', internal_note: '' })
const notesForm = reactive({ customer_note: '', internal_note: '' })

const pendingCount = computed(() => items.value.filter((i) => i.status === 'pending').length)
const resolvedCount = computed(() => items.value.filter((i) => i.status === 'resolved').length)
const drawerTitle = computed(() => drawerMode.value === 'resolve' ? '处理售后' : drawerMode.value === 'notes' ? '编辑售后说明' : '售后详情')

const filteredItems = computed(() => {
  const kw = searchText.value.trim().toLowerCase()
  return items.value.filter((i) => !kw || (i.order_no || '').toLowerCase().includes(kw) || (i.customer_name || '').toLowerCase().includes(kw) || reasonLabel(i.reason).includes(kw))
    .sort((a, b) => b.id - a.id)
})

const pagedItems = computed(() => filteredItems.value.slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value))

watch(searchText, () => { currentPage.value = 1 })
watch(() => route.query.focus_aftersale_id, () => applyFocusFromRoute())
watch([filteredItems, focusedAftersaleId], () => {
  if (focusedAftersaleId.value === null) return
  const idx = filteredItems.value.findIndex((i) => i.id === focusedAftersaleId.value)
  if (idx >= 0) currentPage.value = Math.floor(idx / pageSize.value) + 1
})

onMounted(() => { applyFocusFromRoute(); void loadAftersales(false) })

function applyFocusFromRoute() {
  const focus = route.query.focus_aftersale_id; const search = route.query.search
  const focusId = typeof focus === 'string' ? Number(focus) : NaN
  focusedAftersaleId.value = Number.isFinite(focusId) ? focusId : null
  if (typeof search === 'string' && search.trim()) searchText.value = search.trim()
  if (focusedAftersaleId.value !== null) { currentTab.value = 'all'; currentPage.value = 1 }
}

function clearFocusedAftersale() {
  if (focusedAftersaleId.value === null) return
  focusedAftersaleId.value = null
  const q = { ...route.query }; delete q.focus_aftersale_id
  void router.replace({ path: route.path, query: q })
}

function rowClass({ row }: { row: AftersaleItem }) {
  return focusedAftersaleId.value !== null && row.id === focusedAftersaleId.value ? 'focused-row' : ''
}

function reasonLabel(reason: AftersaleItem['reason']) {
  const map: Record<string, string> = { quality_issue: '质量问题', wrong_item: '发错货', damaged: '破损', size_problem: '尺码问题', other: '其他' }
  return map[reason] || reason
}

function processTypeLabel(type?: AftersaleItem['process_type'] | null) {
  if (!type) return '待确认'
  const map: Record<string, string> = { refund_and_return: '退货退款', refund_only: '仅退款', exchange: '换货', rejected: '拒绝' }
  return map[type] || type
}

function buyerRoleLabel(role?: AftersaleItem['buyer_role'] | null) {
  return role === 'wholesale' ? '批发客户' : role === 'retail' ? '零售客户' : '未知身份'
}

function onTabChange() { currentPage.value = 1; void loadAftersales(false) }

async function loadAftersales(showLoading: boolean | Event = true) {
  const show = typeof showLoading === 'boolean' ? showLoading : true
  if (show) loading.value = true
  try { const res = await fetchAftersales(currentTab.value as AftersaleItem['status'] | 'all'); items.value = res.data }
  finally { if (show) loading.value = false }
}

function patchAftersaleLocal(id: number, patch: Partial<AftersaleItem>) {
  const idx = items.value.findIndex((i) => i.id === id)
  if (idx === -1) return
  const next = { ...items.value[idx], ...patch }
  if (currentTab.value !== 'all' && next.status !== currentTab.value) { items.value.splice(idx, 1); return }
  items.value[idx] = next
}

function openDrawer(mode: 'detail' | 'resolve' | 'notes', item: AftersaleItem) {
  if (mode === 'detail' && focusedAftersaleId.value !== null && item.id === focusedAftersaleId.value) clearFocusedAftersale()
  drawerMode.value = mode; activeItem.value = item
  resolveForm.process_type = item.process_type || 'refund_only'
  resolveForm.refund_amount = item.refund_amount || '0.00'
  resolveForm.chat_proof_url = item.chat_proof_url || ''
  resolveForm.customer_note = item.customer_note || item.note || ''
  resolveForm.internal_note = item.internal_note || ''
  notesForm.customer_note = item.customer_note || item.note || ''
  notesForm.internal_note = item.internal_note || ''
  isDrawerOpen.value = true
}

function handleMenu(command: string, item: AftersaleItem) {
  if (command === 'delete') return deleteAftersale(item)
  return openDrawer(command as 'detail' | 'resolve' | 'notes', item)
}

async function submitResolve() {
  if (!activeItem.value) return
  if (!resolveForm.chat_proof_url.trim()) { ElMessage.warning('请先上传或填写沟通截图'); return }
  submitting.value = true
  try {
    await resolveAftersale(activeItem.value.id, { process_type: resolveForm.process_type, refund_amount: resolveForm.refund_amount, chat_proof_url: resolveForm.chat_proof_url.trim(), customer_note: resolveForm.customer_note || undefined, internal_note: resolveForm.internal_note || undefined })
    patchAftersaleLocal(activeItem.value.id, { status: 'resolved', process_type: resolveForm.process_type as AftersaleItem['process_type'], refund_amount: resolveForm.refund_amount, chat_proof_url: resolveForm.chat_proof_url, note: resolveForm.customer_note, customer_note: resolveForm.customer_note, internal_note: resolveForm.internal_note })
    ElMessage.success('售后已完结')
    isDrawerOpen.value = false
  } catch { ElMessage.error('提交失败，请重试') }
  finally { submitting.value = false }
}

async function submitNotes() {
  if (!activeItem.value) return
  submitting.value = true
  try {
    await updateAftersaleNotes(activeItem.value.id, { customer_note: notesForm.customer_note || null, internal_note: notesForm.internal_note || null })
    patchAftersaleLocal(activeItem.value.id, { note: notesForm.customer_note, customer_note: notesForm.customer_note, internal_note: notesForm.internal_note })
    ElMessage.success('售后说明已保存')
    isDrawerOpen.value = false
  } catch { ElMessage.error('保存失败，请重试') }
  finally { submitting.value = false }
}

async function deleteAftersale(item: AftersaleItem) {
  try {
    const { value } = await ElMessageBox.prompt(`售后单 ${item.order_no || `#${item.id}`} 将从日常列表隐藏，但会保留删除记录。请输入“确认删除此售后”继续。`, '删除售后记录', {
      inputPattern: /^确认删除此售后$/,
      inputErrorMessage: '请输入完整确认文字',
      confirmButtonText: '删除售后',
      confirmButtonClass: 'el-button--danger',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await deleteAdminAftersale(item.id, value)
    isDrawerOpen.value = false
    ElMessage.success('售后记录已删除')
    await loadAftersales(true)
  } catch {
    // Cancel and confirmation mismatch both leave the record unchanged.
  }
}

// ponytail: kept for external reference compatibility
void ref(false) // batchLoading
void ref<number[]>([]) // selectedAftersaleIds
</script>

<style scoped>
.aftersale-page { display: grid; gap: 18px; }
.list-card { border-radius: 8px; }
.list-card :deep(.el-card__header) { padding: 14px 20px; }
.list-card :deep(.el-card__body) { padding: 0 20px 16px; }
.list-card :deep(.el-tabs__header) { margin: 0; }
.list-card :deep(.el-tabs__content) { display: none; }
.list-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.filter-bar { display: flex; align-items: center; gap: 8px; }
.list-stats { display: flex; gap: 8px; }
.tab-badge { margin-left: 4px; }
.order-no { font-weight: 600; color: var(--text-primary); font-variant-numeric: tabular-nums; }
.muted { font-size: 12px; color: var(--text-tertiary); margin-top: 3px; }
.font-bold { font-weight: 600; color: var(--text-primary); }
.line-clamp { display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden; }
.row-actions { display: flex; align-items: center; gap: 4px; }
.table-footer { display: flex; justify-content: flex-end; padding-top: 14px; }
.drawer-section { padding: 18px 0; border-bottom: 1px solid var(--border-light); }
.drawer-section:last-child { border-bottom: 0; }
.drawer-section h3 { margin: 0 0 12px; font-size: 14px; font-weight: 600; color: var(--text-primary); }
:deep(.focused-row > td) { background-color: var(--bg-highlight) !important; }
</style>
