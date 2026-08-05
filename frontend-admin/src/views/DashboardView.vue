<template>
  <div class="dashboard-page">
    <AppPageHeader title="今日经营" description="">
      <template #actions>
        <span class="updated-at">{{ loading ? '正在更新' : `更新于 ${updatedAt}` }}</span>
        <el-button :icon="Refresh" :loading="loading" @click="loadDashboard">刷新</el-button>
      </template>
    </AppPageHeader>

    <section class="metric-grid" aria-label="今日经营概况">
      <button class="metric-card" type="button" @click="go('/orders')">
        <span>今日已收款</span>
        <strong>{{ formatCurrency(data.snapshot.today_revenue) }}</strong>
      </button>
      <button class="metric-card attention" type="button" @click="go('/orders')">
        <span>待发货订单</span>
        <strong>{{ data.snapshot.pending_order_count }}</strong>
      </button>
      <button class="metric-card" type="button" @click="go('/products')">
        <span>上架商品</span>
        <strong>{{ data.snapshot.active_product_count }}</strong>
        <small v-if="data.stock_alerts.length">{{ data.stock_alerts.length }} 项需留意</small>
      </button>
      <button class="metric-card attention" type="button" @click="go('/users', { tab: 'pending' })">
        <span>待审核批发申请</span>
        <strong>{{ data.snapshot.pending_wholesale_count }}</strong>
      </button>
    </section>

    <div class="dashboard-grid">
      <el-card shadow="never" class="task-card">
        <template #header>
          <div class="card-title-row"><h2>待办</h2><el-button link type="primary" @click="go('/orders')">查看订单</el-button></div>
        </template>
        <div v-if="tasks.length" class="task-list">
          <button v-for="task in tasks" :key="task.id" type="button" class="task-row" @click="go(task.path)">
            <div><strong>{{ task.title }}</strong><span>{{ task.desc }}</span></div>
            <div class="task-meta"><el-tag v-if="task.count" type="warning" effect="light">{{ task.count }}</el-tag><span>{{ task.time }}</span><el-icon><ArrowRight /></el-icon></div>
          </button>
        </div>
        <div v-else class="compact-empty">当前没有需要处理的事项</div>
      </el-card>

      <el-card shadow="never" class="alert-card">
        <template #header>
          <div class="card-title-row"><h2>商品提醒</h2><el-button link type="primary" @click="go('/products')">管理商品</el-button></div>
        </template>
        <div v-if="data.stock_alerts.length" class="alert-list">
          <div v-for="item in data.stock_alerts.slice(0, 6)" :key="item.sku_id" class="alert-row"><div><strong>{{ item.product_name }}</strong><span>{{ item.spec || '默认规格' }}</span></div><el-tag type="warning" effect="light">{{ item.stock }}</el-tag></div>
        </div>
        <div v-else class="compact-empty">没有需要留意的商品</div>
      </el-card>
    </div>

    <el-card shadow="never" class="recent-card">
      <template #header>
        <div class="card-title-row"><h2>最近订单</h2><el-button link type="primary" @click="go('/orders')">全部订单</el-button></div>
      </template>
      <el-table v-if="data.recent_orders.length" :data="data.recent_orders" @row-click="(row: DashboardRecentOrder) => go('/orders', { focus_order_no: row.order_no })">
        <el-table-column label="订单" min-width="190"><template #default="{ row }"><strong>{{ row.order_no }}</strong><div class="muted">{{ row.item_summary || '商品信息待补充' }}</div></template></el-table-column>
        <el-table-column label="客户" min-width="130"><template #default="{ row }"><strong>{{ row.customer_name || '未命名客户' }}</strong><div class="muted">{{ row.identity || '客户' }}</div></template></el-table-column>
        <el-table-column label="金额" width="130" align="right"><template #default="{ row }"><strong>{{ formatCurrency(row.amount) }}</strong><div class="muted">{{ row.payment_method || '—' }}</div></template></el-table-column>
        <el-table-column label="状态" width="130"><template #default="{ row }"><StatusTag kind="order" :status="row.status" /></template></el-table-column>
        <el-table-column label="" width="58" align="right"><template #default><el-icon class="row-arrow"><ArrowRight /></el-icon></template></el-table-column>
      </el-table>
      <div v-else class="compact-empty">今日暂无订单记录</div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import AppPageHeader from '@/components/AppPageHeader.vue'
import StatusTag from '@/components/shared/StatusTag.vue'
import { fetchDashboardSummary } from '@/api/modules'
import type { DashboardPayload, DashboardRecentOrder } from '@/types/api'
import { formatCurrency } from '@/utils/adminFormat'

const router = useRouter()
const loading = ref(false)
const updatedAt = ref('刚刚')
const emptyDashboard: DashboardPayload = { snapshot: { today_revenue: '0.00', pending_order_count: 0, active_product_count: 0, pending_wholesale_count: 0 }, trend: { days: 0, points: [] }, customer_mix: { revenue: [], orders: [] }, rankings: { week: [], month: [] }, tasks: { urgent: [], follow: [] }, recent_orders: [], stock_alerts: [] }
const data = ref<DashboardPayload>(emptyDashboard)
const tasks = computed(() => [...(data.value.tasks.urgent || []), ...(data.value.tasks.follow || [])].filter((task) => (task.count ?? 0) > 0).slice(0, 8))

onMounted(() => void loadDashboard())

function go(path: string, query?: Record<string, string>) { void router.push({ path, query }) }
async function loadDashboard() {
  loading.value = true
  try { data.value = await fetchDashboardSummary(); updatedAt.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }
  catch { ElMessage.error('经营数据加载失败，请稍后重试') }
  finally { loading.value = false }
}
</script>

<style scoped>
.dashboard-page { display: grid; gap: 14px; }
.updated-at { color: var(--text-tertiary); font-size: 12px; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.metric-card { min-height: 92px; padding: 15px 16px; border: 1px solid var(--border-light); border-radius: 8px; background: var(--bg-surface); color: var(--text-primary); text-align: left; cursor: pointer; transition: border-color .18s ease, box-shadow .18s ease; }
.metric-card:hover { border-color: var(--el-color-primary-light-3); box-shadow: var(--shadow-sm); }
.metric-card.attention { border-top: 3px solid var(--color-warning); }
.metric-card span,.metric-card small { display: block; color: var(--text-secondary); font-size: 13px; }
.metric-card strong { display: block; margin-top: 10px; font-size: 25px; line-height: 1; font-variant-numeric: tabular-nums; }
.metric-card small { color: var(--text-tertiary); font-size: 12px; }
.dashboard-grid { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(320px, 1fr); gap: 14px; }
.task-card,.alert-card,.recent-card { border-radius: 8px; }
.card-title-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.card-title-row h2 { margin: 0; color: var(--text-primary); font-size: 16px; }
.task-list,.alert-list { display: grid; }
.task-row { display: flex; align-items: center; justify-content: space-between; gap: 18px; width: 100%; padding: 14px 0; border: 0; border-bottom: 1px solid var(--border-light); background: transparent; color: var(--text-primary); text-align: left; cursor: pointer; }
.task-row:last-child { border-bottom: 0; }
.task-row:hover strong { color: var(--el-color-primary); }
.task-row strong,.task-row span,.alert-row strong,.alert-row span { display: block; }
.task-row strong,.alert-row strong { font-size: 14px; }
.task-row span,.alert-row span,.muted { margin-top: 4px; color: var(--text-tertiary); font-size: 12px; }
.task-meta { display: flex; align-items: center; gap: 8px; color: var(--text-tertiary); font-size: 12px; white-space: nowrap; }
.alert-row { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 14px 0; border-bottom: 1px solid var(--border-light); }
.alert-row:last-child { border-bottom: 0; }
.compact-empty { padding: 24px 0; color: var(--text-tertiary); font-size: 13px; text-align: center; }
.row-arrow { color: var(--text-tertiary); }
.recent-card :deep(.el-card__body) { padding-top: 0; }
@media (max-width: 1350px) { .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .dashboard-grid { grid-template-columns: 1fr; } }
</style>
