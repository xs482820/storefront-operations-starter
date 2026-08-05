<template>
  <div class="records-page">
    <AppPageHeader title="操作记录" description="仅保留删除操作，便于必要时追溯。">
      <template #actions>
        <el-button :icon="Refresh" :loading="loading" @click="loadRecords">刷新</el-button>
      </template>
    </AppPageHeader>

    <el-card shadow="never" class="records-card">
      <template #header>
        <div class="list-header">
          <div class="filter-bar">
            <el-input v-model="keyword" :prefix-icon="Search" clearable placeholder="对象编号、账号或操作者" style="width:240px" />
            <el-button link type="primary" @click="keyword = ''">清除</el-button>
          </div>
          <ListSummary :items="[{ value: filteredRecords.length, label: '条删除记录' }]" />
        </div>
      </template>

      <el-table v-loading="loading" :data="pagedRecords" row-key="id">
        <el-table-column label="时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作人" min-width="145">
          <template #default="{ row }">
            <strong>{{ row.actor_name_snapshot || '系统' }}</strong>
            <div class="muted">{{ roleLabel(row.actor_role) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="135">
          <template #default="{ row }"><StatusTag kind="operation" :status="row.action_code" /></template>
        </el-table-column>
        <el-table-column label="对象" min-width="210">
          <template #default="{ row }">
            <strong>{{ entityLabel(row.entity_type) }}</strong>
            <div class="muted">{{ row.entity_no || `#${row.entity_id || '-'}` }}</div>
          </template>
        </el-table-column>
        <el-table-column label="删除前信息" min-width="240">
          <template #default="{ row }"><span>{{ snapshotLabel(row) }}</span></template>
        </el-table-column>
        <template #empty>
          <el-empty :description="keyword ? '没有匹配的删除记录' : '暂无删除记录'" :image-size="60" />
        </template>
      </el-table>

      <div class="table-footer">
        <span>共 {{ filteredRecords.length }} 条</span>
        <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :total="filteredRecords.length" :page-sizes="[20, 50, 100]" layout="sizes, prev, pager, next" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import AppPageHeader from '@/components/AppPageHeader.vue'
import ListSummary from '@/components/shared/ListSummary.vue'
import StatusTag from '@/components/shared/StatusTag.vue'
import { fetchDeletionEvents } from '@/api/modules'
import type { BusinessEventItem } from '@/types/api'
import { formatDateTime } from '@/utils/adminFormat'

const records = ref<BusinessEventItem[]>([])
const loading = ref(false)
const keyword = ref('')
const currentPage = ref(1)
const pageSize = ref(20)

const filteredRecords = computed(() => {
  const query = keyword.value.trim().toLowerCase()
  if (!query) return records.value
  return records.value.filter((row) => [row.entity_no, row.actor_name_snapshot, row.action_label, row.before_data.username]
    .filter(Boolean).some((value) => String(value).toLowerCase().includes(query)))
})

const pagedRecords = computed(() => filteredRecords.value.slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value))

watch(keyword, () => { currentPage.value = 1 })
onMounted(() => void loadRecords())

async function loadRecords() {
  loading.value = true
  try {
    const response = await fetchDeletionEvents()
    records.value = response.data
  } catch {
    ElMessage.error('操作记录加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

function entityLabel(type: string) {
  return ({ order: '订单', aftersale: '售后记录', employee_account: '工作台账号' } as Record<string, string>)[type] || type
}

function roleLabel(role?: string | null) {
  return ({ admin: '管理员', employee: '店员', retail: '零售客户', wholesale: '批发客户' } as Record<string, string>)[role || ''] || '系统'
}

function snapshotLabel(row: BusinessEventItem) {
  const before = row.before_data
  if (row.entity_type === 'employee_account') return [before.display_name, before.username].filter(Boolean).join(' / ') || '工作台账号'
  if (row.entity_type === 'order') return before.status ? `原状态：${before.status}` : '订单记录'
  if (row.entity_type === 'aftersale') return [before.reason, before.status].filter(Boolean).join(' / ') || '售后记录'
  return row.note || '-'
}
</script>

<style scoped>
.records-page { display: grid; gap: 18px; }
.records-card { border-radius: 8px; }
.records-card :deep(.el-card__header) { padding: 14px 20px; }
.records-card :deep(.el-card__body) { padding: 0 20px 16px; }
.list-header, .filter-bar, .table-footer { display: flex; align-items: center; }
.list-header, .table-footer { justify-content: space-between; gap: 16px; }
.filter-bar { gap: 8px; }
.muted { margin-top: 3px; color: var(--text-tertiary); font-size: 12px; }
.table-footer { padding-top: 14px; color: var(--text-tertiary); font-size: 13px; }
</style>
