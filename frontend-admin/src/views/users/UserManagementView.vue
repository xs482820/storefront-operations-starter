<template>
  <div class="users-page">
    <AppPageHeader title="客户与审核" description="查找客户、审身份、查订单，批发申请集中在待审核标签。">
      <template #actions>
        <el-button type="primary" @click="employeeAccountOpen = true">新建工作台账号</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="loadUsers(true)">刷新</el-button>
      </template>
    </AppPageHeader>

    <el-card shadow="never" class="list-card">
      <template #header>
        <div class="list-header">
          <div class="filter-bar">
            <el-input v-model="searchText" :prefix-icon="Search" clearable :placeholder="currentTab === 'employee' ? '登录账号' : '昵称、手机号、门店名'" style="width:220px" />
            <el-button link type="primary" @click="searchText = ''">清除</el-button>
          </div>
          <ListSummary :items="[{ value: filteredItems.length, label: currentTab === 'employee' || currentTab === 'admin' ? '个账号' : '位客户' }, { value: pendingCount, label: '待审核', tone: 'warning' }]" />
        </div>
      </template>

      <el-tabs v-model="currentTab" @tab-change="onTabChange">
        <el-tab-pane label="全部客户" name="all" />
        <el-tab-pane name="pending">
          <template #label>
            待审核
          </template>
        </el-tab-pane>
        <el-tab-pane label="批发客户" name="wholesale" />
        <el-tab-pane label="零售客户" name="retail" />
        <el-tab-pane label="店员" name="employee" />
        <el-tab-pane label="管理员" name="admin" />
      </el-tabs>

      <el-table v-loading="loading" :data="pagedItems" row-key="id" style="cursor:pointer" :row-class-name="rowClass" @row-click="openCustomer360">
        <el-table-column :label="currentTab === 'employee' || currentTab === 'admin' ? '账号' : '客户'" min-width="200">
          <template #default="{ row }">
            <div class="user-cell">
              <div class="user-avatar">{{ makeInitial(row.role === 'employee' ? row.username : (row.display_name || row.username)) }}</div>
              <div>
                <div class="user-name">{{ row.role === 'employee' ? row.username : (row.display_name || row.username) }}</div>
                <div class="user-meta">{{ row.role === 'employee' ? '工作台账号' : row.role === 'admin' ? '后台管理员' : (row.phone ? maskPhone(row.phone) : '未留手机号') }}</div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="身份" width="130">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row)" effect="light" size="small">{{ roleLabel(row) }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column v-if="currentTab !== 'employee' && currentTab !== 'admin'" label="来源" min-width="140">
          <template #default="{ row }">
            <div>{{ row.store_name || row.company_name || '—' }}</div>
            <div class="muted">{{ userSource(row) }}</div>
          </template>
        </el-table-column>

        <el-table-column v-if="currentTab !== 'employee' && currentTab !== 'admin'" label="订单" width="80" align="right">
          <template #default="{ row }">{{ row.order_count ?? 0 }}</template>
        </el-table-column>

        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.role === 'employee'" :type="row.is_active ? 'success' : 'info'" effect="plain" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
            <el-tag v-else-if="row.is_blacklisted" type="danger" effect="light" size="small">已拉黑</el-tag>
            <el-tag v-else-if="row.application_status === 'pending'" type="warning" effect="light" size="small">待审核</el-tag>
            <el-tag v-else-if="row.is_flagged" type="warning" effect="plain" size="small">已标记</el-tag>
            <el-tag v-else type="success" effect="plain" size="small">正常</el-tag>
          </template>
        </el-table-column>

        <el-table-column v-if="currentTab !== 'employee' && currentTab !== 'admin'" label="备注" width="64">
          <template #default="{ row }">
            <span v-if="row.application_remark" style="font-size:12px;color:var(--text-tertiary)" :title="row.application_remark">有</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <div class="row-actions" @click.stop>
              <el-button v-if="row.application_status === 'pending'" link type="primary" size="small" @click.stop="openDrawer(row)">审核</el-button>
              <el-dropdown trigger="click" @command="(cmd: string) => handleMenuAction(cmd, row)">
                <el-button link size="small" :icon="MoreFilled" @click.stop />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item :command="row.is_blacklisted ? 'unblacklist' : 'blacklist'" :class="row.is_blacklisted ? '' : 'danger-item'">{{ row.is_blacklisted ? '取消拉黑' : '拉黑' }}</el-dropdown-item>
                    <el-dropdown-item :command="row.is_flagged ? 'unflag' : 'flag'">{{ row.is_flagged ? '取消标记' : '标记' }}</el-dropdown-item>
                    <el-dropdown-item v-if="row.role === 'employee'" command="delete-account" divided class="danger-item">删除账号</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>

        <template #empty>
          <el-empty :description="searchText ? '没有符合条件的客户' : '该分类暂无客户'" :image-size="60">
            <el-button v-if="searchText" @click="searchText = ''">清除搜索</el-button>
          </el-empty>
        </template>
      </el-table>

      <div class="table-footer">
        <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :total="filteredItems.length" :page-sizes="[20, 50, 100]" layout="sizes, prev, pager, next" />
      </div>
    </el-card>

    <!-- 审核保留为独立操作；客户资料统一由 360 画像承载。 -->
    <el-drawer v-model="isDrawerOpen" title="批发资格审核" size="520px" destroy-on-close>
      <template v-if="activeItem">
        <section class="drawer-section">
          <h3>审核处理</h3>
          <el-skeleton v-if="auditLoading" :rows="4" animated />
          <template v-else>
            <el-alert v-if="!activeApplication" type="warning" :closable="false" title="未读取到完整申请材料，请先查看客户 360 详情后再决定。" />
            <el-descriptions v-else :column="2" border class="application-details">
              <el-descriptions-item label="申请人">{{ activeApplication.contact_name || '未填写' }}</el-descriptions-item>
              <el-descriptions-item label="联系电话">{{ activeApplication.contact_phone || '未填写' }}</el-descriptions-item>
              <el-descriptions-item label="公司 / 门店">{{ activeApplication.store_name || activeApplication.company_name || '未填写' }}</el-descriptions-item>
              <el-descriptions-item label="提交时间">{{ activeApplication.created_at || '未记录' }}</el-descriptions-item>
              <el-descriptions-item :span="2" label="营业执照">
                <a v-if="activeApplication.business_license_url" :href="activeApplication.business_license_url" target="_blank" rel="noopener noreferrer" class="license-link">查看营业执照</a>
                <span v-else>未上传</span>
              </el-descriptions-item>
              <el-descriptions-item :span="2" label="申请说明">{{ activeApplication.remark || '无' }}</el-descriptions-item>
            </el-descriptions>
            <el-alert type="info" :closable="false" title="请核对申请资料后再提交审核结论。" class="audit-reminder" />
          </template>
          <el-form label-position="top">
            <el-form-item label="审核结果">
              <el-radio-group v-model="reviewStatus">
                <el-radio-button value="approved">通过</el-radio-button>
                <el-radio-button value="rejected">驳回</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="审核备注">
              <el-input v-model="auditRemark" type="textarea" :rows="4" placeholder="填写审核结论或驳回原因" />
            </el-form-item>
          </el-form>
        </section>
      </template>

      <template #footer>
        <div style="display:flex;justify-content:flex-end;gap:10px">
          <el-button @click="isDrawerOpen = false">关闭</el-button>
          <el-button type="primary" :loading="submitting" @click="submitReview">提交审核</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 360 详情抽屉 -->
    <CustomerDetailDrawer v-model="isCustomerDrawerOpen" :customer-id="activeCustomerId" @role-changed="loadUsers(false)" />

    <el-drawer v-model="employeeDrawerOpen" title="工作台账号" size="440px" destroy-on-close>
      <template v-if="activeEmployee">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="账号">{{ activeEmployee.username }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDateTime(activeEmployee.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="状态"><el-tag :type="activeEmployee.is_active ? 'success' : 'info'">{{ activeEmployee.is_active ? '启用' : '停用' }}</el-tag></el-descriptions-item>
        </el-descriptions>
        <el-form label-position="top" class="employee-account-form">
          <el-form-item label="登录账号"><el-input v-model="employeeUpdate.username" placeholder="留空则不修改" /></el-form-item>
          <el-form-item label="重置密码"><el-input v-model="employeeUpdate.password" type="password" show-password placeholder="至少 8 位；留空则不修改" /></el-form-item>
          <el-form-item label="账号状态"><el-switch v-model="employeeUpdate.is_active" active-text="启用" inactive-text="停用" /></el-form-item>
          <el-form-item label="管理员确认密码"><el-input v-model="employeeUpdate.admin_confirm_password" type="password" show-password /></el-form-item>
        </el-form>
      </template>
      <template #footer><el-button @click="employeeDrawerOpen = false">取消</el-button><el-button type="primary" :loading="updatingEmployee" @click="saveEmployeeAccount">保存</el-button></template>
    </el-drawer>

    <el-dialog v-model="employeeAccountOpen" title="新建工作台账号" width="420px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="内部账号"><el-input v-model="employeeAccount.username" placeholder="仅字母、数字、点、横线或下划线" /></el-form-item>
        <el-form-item label="初始密码"><el-input v-model="employeeAccount.password" type="password" show-password placeholder="至少 8 位" /></el-form-item>
        <el-form-item label="管理员确认密码"><el-input v-model="employeeAccount.admin_confirm_password" type="password" show-password /></el-form-item>
      </el-form>
      <template #footer><el-button @click="employeeAccountOpen = false">取消</el-button><el-button type="primary" :loading="creatingEmployee" @click="createEmployee">创建账号</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, MoreFilled } from '@element-plus/icons-vue'
import AppPageHeader from '@/components/AppPageHeader.vue'
import CustomerDetailDrawer from '@/components/users/CustomerDetailDrawer.vue'
import ListSummary from '@/components/shared/ListSummary.vue'
import { createEmployeeAccount, deleteEmployeeAccount, fetchUsers, fetchWholesaleApplications, reviewWholesaleApplication, updateEmployeeAccount, updateUserRuntimeState } from '@/api/modules'
import type { UserListItem, WholesaleApplicationItem } from '@/types/api'
import { formatDateTime, makeInitial } from '@/utils/adminFormat'

const users = ref<UserListItem[]>([])
const route = useRoute()
const loading = ref(false)
const submitting = ref(false)
const searchText = ref('')
const currentTab = ref('all')
const currentPage = ref(1)
const pageSize = ref(20)
const isDrawerOpen = ref(false)
const isCustomerDrawerOpen = ref(false)
const activeCustomerId = ref<number | string | null>(null)
const activeItem = ref<UserListItem | null>(null)
const auditRemark = ref('')
const reviewStatus = ref<'approved' | 'rejected'>('approved')
const auditLoading = ref(false)
const activeApplication = ref<WholesaleApplicationItem | null>(null)
const employeeAccountOpen = ref(false)
const creatingEmployee = ref(false)
const employeeAccount = reactive({ username: '', password: '', display_name: '', admin_confirm_password: '' })
const employeeDrawerOpen = ref(false)
const updatingEmployee = ref(false)
const activeEmployee = ref<UserListItem | null>(null)
const employeeUpdate = reactive({ username: '', password: '', is_active: true, admin_confirm_password: '' })

const pendingCount = computed(() => users.value.filter((u) => u.application_status === 'pending').length)

const filteredItems = computed(() => {
  const kw = searchText.value.trim().toLowerCase()
  return users.value.filter((u) => !kw || (u.display_name || u.username).toLowerCase().includes(kw) || (u.phone || '').includes(kw) || (u.store_name || u.company_name || '').toLowerCase().includes(kw))
})

const pagedItems = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredItems.value.slice(start, start + pageSize.value)
})

watch(searchText, () => { currentPage.value = 1 })

onMounted(() => {
  if (route.query.tab === 'pending') currentTab.value = 'pending'
  void loadUsers(false)
})

function maskPhone(phone: string) { return phone.length >= 7 ? `${phone.slice(0, 3)}****${phone.slice(-4)}` : phone }

function roleLabel(item: UserListItem) {
  if (item.application_status === 'pending') return '申请批发中'
  const map: Record<string, string> = { wholesale: '批发客户', admin: '管理员', employee: '店员', retail: '零售客户' }
  return map[item.role] || '零售客户'
}

function roleTagType(item: UserListItem): '' | 'warning' | 'success' | 'info' | 'danger' {
  if (item.application_status === 'pending') return 'warning'
  if (item.role === 'wholesale') return 'success'
  if (item.role === 'admin' || item.role === 'employee') return 'info'
  return ''
}

function userSource(item: UserListItem) {
  if (item.application_status === 'pending') return '批发申请待审'
  if (item.is_verified_wholesale) return '人工审核通过'
  return '微信授权登录'
}

function rowClass({ row }: { row: UserListItem }) {
  return row.application_status === 'pending' ? 'pending-row' : ''
}

async function loadUsers(showLoading: boolean | Event = true) {
  const show = typeof showLoading === 'boolean' ? showLoading : true
  if (show) loading.value = true
  try {
    const tabParams: Record<string, Record<string, string>> = {
      pending: { applicationStatus: 'pending' },
      wholesale: { role: 'wholesale' },
      retail: { role: 'retail' },
      employee: { role: 'employee' },
      admin: { role: 'admin' },
    }
    const res = await fetchUsers(tabParams[currentTab.value] as Parameters<typeof fetchUsers>[0])
    users.value = res.data
  } finally { if (show) loading.value = false }
}

function onTabChange() { currentPage.value = 1; void loadUsers(false) }

function openCustomer360(item: UserListItem) {
  if (item.role === 'employee') {
    activeEmployee.value = item
    Object.assign(employeeUpdate, { username: item.username, password: '', is_active: item.is_active, admin_confirm_password: '' })
    employeeDrawerOpen.value = true
    return
  }
  if (item.role === 'admin') return
  activeCustomerId.value = item.id
  isCustomerDrawerOpen.value = true
}

async function openDrawer(item: UserListItem) {
  activeItem.value = item
  isDrawerOpen.value = true
  auditRemark.value = item.application_review_note || ''; reviewStatus.value = item.application_status === 'rejected' ? 'rejected' : 'approved'
  activeApplication.value = null
  auditLoading.value = true
  try {
    const response = await fetchWholesaleApplications()
    activeApplication.value = response.data.find((application) => application.id === item.latest_application_id) || null
  } catch {
    ElMessage.error('申请材料加载失败，请稍后重试')
  } finally {
    auditLoading.value = false
  }
}

function patchUserLocal(userId: number, patch: Partial<UserListItem>) {
  const idx = users.value.findIndex((u) => u.id === userId)
  if (idx !== -1) users.value[idx] = { ...users.value[idx], ...patch }
}

async function submitReview() {
  if (!activeItem.value?.latest_application_id) { ElMessage.warning('当前用户没有可审核的申请'); return }
  submitting.value = true
  try {
    await reviewWholesaleApplication(activeItem.value.latest_application_id, { status: reviewStatus.value, review_note: auditRemark.value || undefined })
    patchUserLocal(activeItem.value.id, { application_status: reviewStatus.value as 'approved' | 'rejected', application_review_note: auditRemark.value })
    ElMessage.success(reviewStatus.value === 'approved' ? '已通过申请' : '已驳回申请')
    isDrawerOpen.value = false
  } catch { ElMessage.error('提交失败，请重试') }
  finally { submitting.value = false }
}

async function createEmployee() {
  if (!employeeAccount.username || !employeeAccount.password || !employeeAccount.admin_confirm_password) { ElMessage.warning('请填写账号、初始密码和管理员确认密码'); return }
  creatingEmployee.value = true
  try {
    await createEmployeeAccount({ ...employeeAccount, display_name: employeeAccount.display_name || undefined })
    employeeAccountOpen.value = false
    Object.assign(employeeAccount, { username: '', password: '', display_name: '', admin_confirm_password: '' })
    ElMessage.success('工作台账号已创建')
    currentTab.value = 'employee'; await loadUsers(true)
  } catch { ElMessage.error('创建失败，请检查账号与管理员确认密码') }
  finally { creatingEmployee.value = false }
}

async function saveEmployeeAccount() {
  if (!activeEmployee.value || !employeeUpdate.admin_confirm_password) { ElMessage.warning('请输入管理员确认密码'); return }
  updatingEmployee.value = true
  try {
    await updateEmployeeAccount(activeEmployee.value.id, {
      username: employeeUpdate.username || undefined,
      password: employeeUpdate.password || undefined,
      is_active: employeeUpdate.is_active,
      admin_confirm_password: employeeUpdate.admin_confirm_password,
    })
    employeeDrawerOpen.value = false
    ElMessage.success('工作台账号已更新')
    await loadUsers(true)
  } catch { ElMessage.error('保存失败，请检查账号或管理员确认密码') }
  finally { updatingEmployee.value = false }
}

async function handleMenuAction(cmd: string, item: UserListItem) {
  if (cmd === 'delete-account') {
    try {
      const { value } = await ElMessageBox.prompt(`删除后，账号将无法登录，且仅能在“操作记录”中追溯。请输入“确认删除此账号”继续。`, '删除工作台账号', {
        inputPattern: /^确认删除此账号$/,
        inputErrorMessage: '请输入完整确认文字',
        confirmButtonText: '删除账号',
        confirmButtonClass: 'el-button--danger',
        cancelButtonText: '取消',
        type: 'warning',
      })
      await deleteEmployeeAccount(item.id, value)
      employeeDrawerOpen.value = false
      ElMessage.success('工作台账号已删除')
      await loadUsers(true)
    } catch {
      // Cancel and confirmation mismatch both leave the account unchanged.
    }
    return
  }
  if (cmd === 'blacklist' || cmd === 'unblacklist') {
    const val = cmd === 'blacklist'
    try { await updateUserRuntimeState(item.id, { is_blacklisted: val }); patchUserLocal(item.id, { is_blacklisted: val }); ElMessage.success(val ? '已拉黑' : '已取消拉黑') }
    catch { ElMessage.error('操作失败') }
  }
  if (cmd === 'flag' || cmd === 'unflag') {
    const val = cmd === 'flag'
    try { await updateUserRuntimeState(item.id, { is_flagged: val }); patchUserLocal(item.id, { is_flagged: val }); ElMessage.success(val ? '已标记' : '已取消标记') }
    catch { ElMessage.error('操作失败') }
  }
}
</script>

<style scoped>
.users-page { display: grid; gap: 18px; }
.list-card { border-radius: 8px; }
.list-card :deep(.el-card__header) { padding: 14px 20px; }
.list-card :deep(.el-card__body) { padding: 0 20px 16px; }
.list-card :deep(.el-tabs__header) { margin: 0 0 0; }
.list-card :deep(.el-tabs__content) { display: none; }
.list-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.filter-bar { display: flex; align-items: center; gap: 8px; }
.user-cell { display: flex; align-items: center; gap: 10px; }
.user-avatar { width: 32px; height: 32px; border-radius: 50%; background: var(--color-primary); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; flex-shrink: 0; }
.user-name { font-weight: 600; color: var(--text-primary); }
.user-meta { font-size: 12px; color: var(--text-tertiary); margin-top: 2px; }
.muted { font-size: 12px; color: var(--text-tertiary); margin-top: 3px; }
.row-actions { display: flex; align-items: center; gap: 4px; }
.table-footer { display: flex; justify-content: flex-end; padding-top: 14px; }
.drawer-section { padding: 18px 0; border-bottom: 1px solid var(--border-light); }
.application-details { margin-bottom: 14px; }
.license-link { color: var(--el-color-primary); text-decoration: underline; }
.audit-reminder { margin: 14px 0; }
.drawer-section:last-child { border-bottom: 0; }
.drawer-section h3 { margin: 0 0 12px; font-size: 14px; font-weight: 600; color: var(--text-primary); }
.remark-box { padding: 12px; background: var(--bg-canvas); border-radius: 6px; font-size: 14px; color: var(--text-secondary); white-space: pre-wrap; }
:deep(.pending-row) { background-color: var(--bg-highlight) !important; }
:deep(.pending-row:hover > td) { background-color: var(--bg-highlight-hover) !important; }
:deep(.danger-item) { color: var(--el-color-danger); }
</style>
