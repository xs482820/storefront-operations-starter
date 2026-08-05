<template>
  <div class="print-jobs-page">
    <AppPageHeader title="打印任务" description="配货单打印请求与设备交接记录。">
      <template #actions><el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button></template>
    </AppPageHeader>
    <el-alert title="打印任务会交由店内打印网关处理；任务失败时会保留失败原因，避免静默丢单。" type="info" :closable="false" show-icon />
    <el-card shadow="never">
      <el-table v-loading="loading" :data="jobs" row-key="id">
        <el-table-column label="登记时间" width="180"><template #default="{ row }">{{ formatDateTime(row.created_at) }}</template></el-table-column>
        <el-table-column label="订单" min-width="160"><template #default="{ row }"><strong>{{ row.order_no }}</strong><div class="muted">{{ row.requested_by }}</div></template></el-table-column>
        <el-table-column label="内容" min-width="260"><template #default="{ row }">{{ lineSummary(row.payload) }}</template></el-table-column>
        <el-table-column label="状态" width="140"><template #default="{ row }"><el-tag type="info" effect="plain">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
        <template #empty><el-empty description="暂无打印任务" :image-size="60" /></template>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import AppPageHeader from '@/components/AppPageHeader.vue'
import { fetchPrintJobs } from '@/api/modules'
import { formatDateTime } from '@/utils/adminFormat'

type PrintJob = { id: number; order_no: string; status: string; requested_by: string; created_at: string; payload: Record<string, unknown> }
const jobs = ref<PrintJob[]>([])
const loading = ref(false)
onMounted(() => void load())
async function load() {
  loading.value = true
  try { jobs.value = (await fetchPrintJobs()).data } catch { ElMessage.error('打印任务加载失败') } finally { loading.value = false }
}
function statusLabel(status: string) {
  return ({ pending_device: '待打印', printing: '打印中', printed: '已打印', failed: '打印失败' } as Record<string, string>)[status] || status
}
function lineSummary(payload: Record<string, unknown>) {
  const lines = Array.isArray(payload.lines) ? payload.lines : []
  return lines.map((line) => `${String((line as Record<string, unknown>).name || '商品')} x${String((line as Record<string, unknown>).quantity || 0)}`).join('，') || '配货单内容待生成'
}
</script>

<style scoped>
.print-jobs-page { display: grid; gap: 18px; }
.muted { margin-top: 3px; color: var(--text-tertiary); font-size: 12px; }
</style>
