<template>
  <BaseDrawer
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    title="客户 360° 画像"
    :width="sidePanelOpen ? '1240px' : '880px'"
    @close="handleClose"
  >
    <div v-if="loading" class="loading-state">数据加载中...</div>

    <div v-else-if="customerData" class="drawer-flex-layout">
      
      <aside v-if="sidePanelOpen" class="peek-panel">
        <header class="peek-header">
          <h4 class="peek-title">{{ sidePanelType === 'order' ? '订单快览' : '售后快览' }}</h4>
          <button class="peek-close" @click="closeSidePanel">×</button>
        </header>
        <div class="peek-body">
          <div v-if="sidePanelType === 'order' && activeOrder" class="peek-grid">
            <div class="peek-row"><span>订单号</span><strong class="text-mono">{{ activeOrder.order_no }}</strong></div>
            <div class="peek-row"><span>下单时间</span><strong>{{ formatDate(activeOrder.created_at) }}</strong></div>
            <div class="peek-row"><span>订单状态</span><StatusTag kind="order" :status="activeOrder.status" /></div>
            <div class="divider-line"></div>
            <div class="peek-row"><span>实付金额</span><strong class="text-danger text-lg">¥{{ activeOrder.amount }}</strong></div>
            <button class="btn-outline w-full mt-4" @click="goToOrder(activeOrder.order_no)">跳转至完整订单页</button>
          </div>

          <div v-if="sidePanelType === 'aftersale' && activeAftersale" class="peek-grid">
            <div class="peek-row"><span>售后单号</span><strong class="text-mono">#{{ activeAftersale.id }}</strong></div>
            <div class="peek-row"><span>关联订单</span><strong class="text-mono">{{ activeAftersale.order_no || '无' }}</strong></div>
            <div class="peek-row"><span>提交时间</span><strong>{{ formatDate(activeAftersale.created_at) }}</strong></div>
            <div class="peek-row"><span>售后类型</span><strong class="text-danger">{{ formatAftersaleType(activeAftersale.type) }}</strong></div>
            <div class="peek-row"><span>处理状态</span><StatusTag kind="aftersale" :status="activeAftersale.status" /></div>
            <div class="divider-line"></div>
            <div class="peek-row"><span>退款金额</span><strong class="text-danger text-lg">¥{{ activeAftersale.refund_amount }}</strong></div>
            <button class="btn-outline w-full mt-4" @click="goToAftersale(activeAftersale.id)">跳转至完整售后单</button>
          </div>
        </div>
      </aside>

      <div class="main-panel">
        <div class="customer-hero">
          <div class="hero-user">
            <div class="avatar">{{ makeInitial(customerData.name) }}</div>
            <div class="user-info">
              <div class="name-row">
                <h2 class="name" :title="customerData.name">{{ customerData.name }}</h2>
                <span :class="['badge', customerData.type === 'wholesale' ? 'badge-warning' : 'badge-retail']">
                  {{ formatCustomerType(customerData.type) }}
                </span>
              </div>
              <div class="meta-row text-tertiary text-sm">
                <span>{{ customerData.phone || '暂无手机号' }}</span>
                <span class="divider">|</span>
                <span>{{ customerData.location || '未知归属地' }}</span>
              </div>
            </div>
          </div>

          <div class="hero-stats">
            <div class="stat-item">
              <span class="stat-label">累计消费</span>
              <span class="stat-value">¥{{ customerData.total_spent || '0.00' }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">累计订单</span>
              <span class="stat-value">{{ customerData.total_orders || 0 }} <span class="text-sm text-tertiary">单</span></span>
            </div>
            <div class="stat-item">
              <span class="stat-label">最近下单</span>
              <span class="stat-value-text">{{ formatDate(customerData.last_order_time) }}</span>
            </div>
          </div>
        </div>

        <div class="drawer-tabs">
          <button :class="['tab-btn', currentTab === 'profile' ? 'active' : '']" @click="currentTab = 'profile'">基础资料</button>
          <button :class="['tab-btn', currentTab === 'orders' ? 'active' : '']" @click="currentTab = 'orders'">历史订单 ({{ customerData.orders?.length || 0 }})</button>
          <button :class="['tab-btn', currentTab === 'aftersales' ? 'active' : '']" @click="currentTab = 'aftersales'">售后记录 ({{ customerData.aftersales?.length || 0 }})</button>
          <button :class="['tab-btn', currentTab === 'cart' ? 'active' : '']" @click="currentTab = 'cart'">购物车内容 ({{ customerData.cart_items?.length || 0 }})</button>
          <button :class="['tab-btn', currentTab === 'addresses' ? 'active' : '']" @click="currentTab = 'addresses'">地址本 ({{ customerData.addresses?.length || 0 }})</button>
        </div>

        <div class="tab-content scrollable-area">
          <div v-show="currentTab === 'profile'" class="tab-panel">
            <h4 class="panel-title">账户与收件</h4>
            <div class="detail-grid">
              <div class="detail-item"><span class="detail-label">当前身份</span><span class="detail-value">{{ roleLabel(customerData.current_role) }}</span></div>
              <div class="detail-item"><span class="detail-label">绑定手机号</span><span class="detail-value">{{ customerData.phone || '未留手机号' }}</span></div>
              <div class="detail-item"><span class="detail-label">注册时间</span><span class="detail-value">{{ formatDate(customerData.created_at) }}</span></div>
              <div class="detail-item"><span class="detail-label">收件人信息</span><span class="detail-value">{{ customerData.default_receiver || '暂无默认收件人' }}</span></div>
            </div>

            <template v-if="customerData.current_role === 'wholesale' || customerData.type === 'wholesale'">
              <h4 class="panel-title mt-6">门店与资质</h4>
              <div class="detail-grid">
                <div class="detail-item"><span class="detail-label">门店 / 公司</span><span class="detail-value">{{ customerData.store_name || customerData.company_name || '未填写' }}</span></div>
                <div class="detail-item"><span class="detail-label">主营业务</span><span class="detail-value">{{ customerData.business_type || '未填写' }}</span></div>
                <div class="detail-item"><span class="detail-label">联系人</span><span class="detail-value">{{ customerData.contact_name || '未填写' }}</span></div>
                <div class="detail-item"><span class="detail-label">门店地址</span><span class="detail-value">{{ customerData.address || customerData.location || '未填写' }}</span></div>
                <div v-if="customerData.apply_note" class="detail-item detail-item-full"><span class="detail-label">申请说明</span><span class="detail-value">{{ customerData.apply_note }}</span></div>
              </div>
              <div v-if="customerData.business_license_url" class="license-preview-box mt-2">
                <div class="detail-label">营业执照（可查看）</div>
                <a class="license-preview-link" :href="customerData.business_license_url" target="_blank" rel="noopener noreferrer">
                  <img class="license-preview-image" :src="customerData.business_license_url" alt="营业执照" />
                </a>
              </div>
            </template>

            <h4 class="panel-title mt-6">微信通知设置</h4>
            <div class="notification-pref-card">
              <div class="notification-pref-main">
                <span :class="['table-badge', customerData.miniapp_notification_enabled ? 'tone-primary' : 'tone-muted']">
                  {{ customerData.miniapp_notification_enabled ? '总开关已开启' : '总开关已关闭' }}
                </span>
                <span class="text-tertiary text-sm">
                  已订阅 {{ customerData.miniapp_notification_event_keys?.length || 0 }} 项
                </span>
                <span class="text-tertiary text-sm">
                  更新于 {{ formatDate(customerData.miniapp_notification_updated_at) }}
                </span>
              </div>
              <div v-if="customerData.miniapp_notification_event_labels?.length" class="notification-pref-tags">
                <span
                  v-for="label in customerData.miniapp_notification_event_labels"
                  :key="label"
                  class="notification-pref-tag"
                >
                  {{ label }}
                </span>
              </div>
              <div v-else class="text-tertiary text-sm">该客户暂未选择任何小程序订阅事件。</div>
            </div>

            <h4 class="panel-title mt-6">内部备注 (仅管理员可见)</h4>
            <textarea
              v-model="internalNote"
              class="form-input textarea"
              rows="3"
              placeholder="填写客户合作习惯、补充说明等。"
            ></textarea>
            <div class="text-right mt-2">
              <button class="btn-primary-sm" @click="saveNote">保存备注</button>
            </div>

            <h4 class="panel-title mt-6">身份管理</h4>
            <div class="detail-grid role-grid">
              <label class="detail-item">
                <span class="detail-label">当前身份</span>
                <span class="detail-value">{{ roleLabel(customerData.current_role) }}</span>
              </label>
              <label class="detail-item">
                <span class="detail-label">调整为</span>
                <select v-model="roleForm.role" class="field-input">
                  <option value="retail">零售客户</option>
                  <option value="wholesale">批发客户</option>
                  <option value="employee">店员</option>
                </select>
              </label>
            </div>

            <div v-if="roleForm.role === 'wholesale'" class="field-grid mt-2">
              <label class="field-label">
                <span>门店 / 公司名称（必填）</span>
                <input v-model="roleForm.company_name" class="field-input" placeholder="例如：赵氏母婴供应链有限公司" />
              </label>
              <label class="field-label">
                <span>类型（必填）</span>
                <input v-model="roleForm.business_type" class="field-input" placeholder="例如：母婴门店 / 档口批发 / 社区团购" />
              </label>
              <label class="field-label">
                <span>联系人姓名（必填）</span>
                <input v-model="roleForm.contact_name" class="field-input" placeholder="请输入联系人姓名" />
              </label>
              <label class="field-label">
                <span>联系人手机号（必填）</span>
                <input v-model="roleForm.contact_phone" class="field-input" placeholder="请输入手机号" />
              </label>
              <label class="field-label field-label-full">
                <span>所在地区/地址（必填）</span>
                <input v-model="roleForm.address" class="field-input" placeholder="请输入门店地区或详细地址" />
              </label>
              <label class="field-label field-label-full">
                <span>营业执照（必填）</span>
                <div class="upload-row">
                  <button class="btn-outline" type="button" @click="triggerLicenseUpload">上传图片</button>
                  <span class="upload-tip">{{ roleForm.business_license_url ? '已上传，可预览' : '支持 JPG/PNG/WEBP' }}</span>
                </div>
                <input
                  ref="licenseInputRef"
                  class="hidden-file-input"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  @change="handleLicenseFileChange"
                />
                <a v-if="roleForm.business_license_url" class="license-preview-link mt-2" :href="roleForm.business_license_url" target="_blank" rel="noopener noreferrer">
                  <img class="license-preview-image" :src="roleForm.business_license_url" alt="营业执照预览" />
                </a>
              </label>
            </div>

            <div v-if="roleForm.role === 'employee'" class="field-grid mt-2">
              <label class="field-label field-label-full">
                <span>微信授权手机号（必填）</span>
                <input v-model="roleForm.contact_phone" class="field-input" placeholder="店员小程序将按此手机号授权" />
              </label>
              <label class="field-label field-label-full">
                <span>管理员确认密码（必填）</span>
                <input v-model="roleForm.admin_confirm_password" class="field-input" type="password" placeholder="请输入你当前管理员登录密码" />
              </label>
              <div class="detail-label">
                店员端不使用账号密码。变更手机号后，原手机号将无法进入店员小程序。
              </div>
            </div>

            <div class="text-right mt-2">
              <button class="btn-primary-sm" :disabled="roleSaving || customerData.current_role === 'admin'" @click="saveRole">
                {{ roleSaving ? '保存中...' : '保存身份' }}
              </button>
            </div>
          </div>

          <div v-show="currentTab === 'orders'" class="tab-panel">
            <table v-if="customerData.orders?.length" class="data-table mini-table">
              <thead>
                <tr>
                  <th>订单号 / 时间</th>
                  <th>实付金额</th>
                  <th>状态</th>
                  <th class="text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="order in customerData.orders" :key="order.order_no">
                  <td>
                    <div class="font-bold text-mono">{{ order.order_no }}</div>
                    <div class="text-tertiary text-sm">{{ formatDate(order.created_at) }}</div>
                  </td>
                  <td class="font-bold">¥{{ order.amount }}</td>
                  <td><StatusTag kind="order" :status="order.status" /></td>
                  <td class="text-right"><button class="btn-link" @click="openOrderPanel(order)">向左快览</button></td>
                </tr>
              </tbody>
            </table>
            <div v-else class="empty-state">该客户暂无历史订单</div>
          </div>

          <div v-show="currentTab === 'aftersales'" class="tab-panel">
            <table v-if="customerData.aftersales?.length" class="data-table mini-table">
              <thead>
                <tr>
                  <th>关联订单</th>
                  <th>售后类型</th>
                  <th>退款金额</th>
                  <th>状态</th>
                  <th class="text-right">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="aftersale in customerData.aftersales" :key="aftersale.id">
                  <td class="font-bold text-mono">{{ aftersale.order_no || '无' }}</td>
                  <td>{{ formatAftersaleType(aftersale.type) }}</td>
                  <td>¥{{ aftersale.refund_amount }}</td>
                  <td><StatusTag kind="aftersale" :status="aftersale.status" /></td>
                  <td class="text-right"><button class="btn-link" @click="openAftersalePanel(aftersale)">向左快览</button></td>
                </tr>
              </tbody>
            </table>
            <div v-else class="empty-state">该客户暂无售后记录</div>
          </div>

          <div v-show="currentTab === 'cart'" class="tab-panel">
            <table v-if="customerData.cart_items?.length" class="data-table mini-table">
              <thead>
                <tr>
                  <th>商品 / 规格</th>
                  <th>SKU</th>
                  <th>数量</th>
                  <th>单价</th>
                  <th>选中</th>
                  <th>更新时间</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in customerData.cart_items" :key="item.id">
                  <td>
                    <div class="font-bold">{{ item.product_name }}</div>
                    <div class="text-tertiary text-sm">{{ item.spec_text || '默认规格' }}</div>
                  </td>
                  <td class="font-bold text-mono">{{ item.sku_code }}</td>
                  <td>{{ item.quantity }}</td>
                  <td>¥{{ item.unit_price }}</td>
                  <td>
                    <span :class="['table-badge', item.selected ? 'tone-primary' : 'tone-warning']">
                      {{ item.selected ? '已选中' : '未选中' }}
                    </span>
                  </td>
                  <td class="text-tertiary text-sm">{{ formatDate(item.created_at) }}</td>
                </tr>
              </tbody>
            </table>
            <div v-else class="empty-state">该客户购物车暂无商品</div>
          </div>

          <div v-show="currentTab === 'addresses'" class="tab-panel">
            <table v-if="customerData.addresses?.length" class="data-table mini-table">
              <thead>
                <tr>
                  <th>收件信息</th>
                  <th>地址详情</th>
                  <th>标签</th>
                  <th>默认</th>
                  <th>更新时间</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in customerData.addresses" :key="item.id">
                  <td>
                    <div class="font-bold">{{ item.contact_name }}</div>
                    <div class="text-tertiary text-sm">{{ item.phone }}</div>
                  </td>
                  <td>
                    <div>{{ item.region }}</div>
                    <div class="text-tertiary text-sm">{{ item.detail }}</div>
                  </td>
                  <td>{{ item.tag || '-' }}</td>
                  <td>
                    <span :class="['table-badge', item.is_default ? 'tone-primary' : 'tone-warning']">
                      {{ item.is_default ? '默认' : '普通' }}
                    </span>
                  </td>
                  <td class="text-tertiary text-sm">{{ formatDate(item.created_at) }}</td>
                </tr>
              </tbody>
            </table>
            <div v-else class="empty-state">该客户暂无地址信息</div>
          </div>
        </div>
      </div>

    </div>
  </BaseDrawer>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import BaseDrawer from '@/components/BaseDrawer.vue'
import StatusTag from '@/components/shared/StatusTag.vue'
import { fetchCustomer360, updateCustomerNote, updateCustomerRole, uploadProductImage } from '@/api/modules'
import type { Customer360AftersaleItem, Customer360OrderItem, Customer360Payload } from '@/types/api'
import { ElMessage } from '@/utils/message'

const props = defineProps<{
  modelValue: boolean
  customerId: number | string | null
}>()

const emit = defineEmits(['update:modelValue', 'roleChanged'])
const router = useRouter()

const currentTab = ref<'profile' | 'orders' | 'aftersales' | 'cart' | 'addresses'>('profile')
const loading = ref(false)
const customerData = ref<Customer360Payload | null>(null)
const internalNote = ref('')
const roleSaving = ref(false)
const licenseInputRef = ref<HTMLInputElement | null>(null)
const roleForm = reactive({
  role: 'retail' as 'retail' | 'wholesale' | 'employee',
  company_name: '',
  store_name: '',
  business_type: '',
  contact_name: '',
  contact_phone: '',
  address: '',
  business_license_url: '',
  admin_confirm_password: '',
})

const triggerLicenseUpload = () => {
  licenseInputRef.value?.click()
}

const handleLicenseFileChange = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    const response = await uploadProductImage(file)
    roleForm.business_license_url = response.data.url
    ElMessage.success('营业执照上传成功')
  } catch {
    ElMessage.error('营业执照上传失败')
  } finally {
    input.value = ''
  }
}

const sidePanelOpen = ref(false)
const sidePanelType = ref<'order' | 'aftersale'>('order')
const activeOrder = ref<Customer360OrderItem | null>(null)
const activeAftersale = ref<Customer360AftersaleItem | null>(null)

watch([() => props.modelValue, () => props.customerId], ([isOpen, customerId]) => {
  if (isOpen && customerId) {
    currentTab.value = 'profile'
    closeSidePanel()
    void loadCustomer360(customerId)
  }
})

const handleClose = () => {
  customerData.value = null
  internalNote.value = ''
  closeSidePanel()
}

const makeInitial = (name: string) => (name ? name.charAt(0).toUpperCase() : '客')

const formatDate = (dateStr?: string | null) => {
  if (!dateStr) return '-'
  const parsed = new Date(dateStr)
  if (!Number.isNaN(parsed.getTime())) {
    const y = parsed.getFullYear()
    const m = `${parsed.getMonth() + 1}`.padStart(2, '0')
    const d = `${parsed.getDate()}`.padStart(2, '0')
    const hh = `${parsed.getHours()}`.padStart(2, '0')
    const mm = `${parsed.getMinutes()}`.padStart(2, '0')
    return `${y}-${m}-${d} ${hh}:${mm}`
  }
  if (dateStr.includes('T')) {
    const [datePart, timePart] = dateStr.split('T')
    return `${datePart} ${timePart.slice(0, 5)}`
  }
  return dateStr
}

const formatCustomerType = (type: Customer360Payload['type']) =>
  type === 'wholesale' ? '批发合作商' : '零售散客'

const roleLabel = (role: Customer360Payload['current_role']) => {
  if (role === 'wholesale') return '批发客户'
  if (role === 'employee') return '店员'
  if (role === 'admin') return '管理员'
  return '零售客户'
}

const formatAftersaleType = (type: string) => {
  const map: Record<string, string> = {
    quality_issue: '质量问题',
    wrong_item: '发错货',
    damaged: '破损',
    size_problem: '尺码问题',
    other: '其他',
  }
  return map[type] || type
}

const openOrderPanel = (order: Customer360OrderItem) => {
  activeOrder.value = order
  activeAftersale.value = null
  sidePanelType.value = 'order'
  sidePanelOpen.value = true
}

const openAftersalePanel = (aftersale: Customer360AftersaleItem) => {
  activeAftersale.value = aftersale
  activeOrder.value = null
  sidePanelType.value = 'aftersale'
  sidePanelOpen.value = true
}

const closeSidePanel = () => {
  sidePanelOpen.value = false
  setTimeout(() => {
    activeOrder.value = null
    activeAftersale.value = null
  }, 300)
}

const goToOrder = (orderNo: string) => {
  emit('update:modelValue', false)
  router.push({ path: '/orders', query: { search: orderNo, focus_order_no: orderNo } })
}

// 🌟 新增的售后跳转方法
const goToAftersale = (aftersaleId: number | string) => {
  emit('update:modelValue', false)
  router.push({
    path: '/aftersales',
    query: { search: String(aftersaleId), focus_aftersale_id: String(aftersaleId) },
  })
}

const saveNote = async () => {
  if (!props.customerId) return
  try {
    await updateCustomerNote(props.customerId, internalNote.value || '')
    if (customerData.value) customerData.value.note = internalNote.value || null
    ElMessage.success('备注保存成功')
  } catch {
    ElMessage.error('备注保存失败')
  }
}

const resetRoleForm = (data: Customer360Payload) => {
  const targetRole = data.current_role === 'admin' ? 'retail' : (data.current_role as 'retail' | 'wholesale' | 'employee')
  roleForm.role = targetRole
  roleForm.company_name = data.company_name || ''
  roleForm.store_name = data.store_name || ''
  roleForm.business_type = data.business_type || data.apply_note || ''
  roleForm.contact_name = data.contact_name || ''
  roleForm.contact_phone = data.phone || ''
  roleForm.address = data.address || data.location || ''
  roleForm.business_license_url = data.business_license_url || ''
  roleForm.admin_confirm_password = ''
}

const saveRole = async () => {
  if (!props.customerId || !customerData.value) return
  if (customerData.value.current_role === 'admin') {
    ElMessage.warning('管理员账号不允许在此变更身份')
    return
  }
  roleSaving.value = true
  try {
    await updateCustomerRole(props.customerId, {
      role: roleForm.role,
      company_name: roleForm.company_name || undefined,
      store_name: roleForm.store_name || undefined,
      business_type: roleForm.business_type || undefined,
      contact_name: roleForm.contact_name || undefined,
      contact_phone: roleForm.contact_phone || undefined,
      address: roleForm.address || undefined,
      business_license_url: roleForm.business_license_url || undefined,
      admin_confirm_password: roleForm.admin_confirm_password || undefined,
    })
    ElMessage.success('身份更新成功')
    emit('roleChanged')
    await loadCustomer360(props.customerId)
  } catch {
    ElMessage.error('身份更新失败，请检查输入信息')
  } finally {
    roleSaving.value = false
  }
}

const loadCustomer360 = async (id: number | string) => {
  loading.value = true
  try {
    const response = await fetchCustomer360(id)
    customerData.value = response.data
    internalNote.value = response.data.note || ''
    resetRoleForm(response.data)
  } catch {
    customerData.value = null
    internalNote.value = ''
    ElMessage.error('客户画像加载失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.drawer-flex-layout {
  display: flex;
  height: 100%;
  width: 100%;
  background: var(--bg-surface);
}

/* 🌟 强化小抽屉的视觉层级：加深阴影和边框，使其有明显的悬浮感 */
.peek-panel {
  width: 360px;
  flex-shrink: 0;
  border-right: 1px solid var(--border-light);
  background: var(--bg-canvas); /* 整体稍微暗一点，区分层级 */
  display: flex;
  flex-direction: column;
  box-shadow: 8px 0 16px rgba(0, 0, 0, 0.05); /* 添加向右的阴影，制造悬浮感 */
  z-index: 5;
  animation: slideRight 0.3s cubic-bezier(0.2, 0, 0, 1) forwards;
}

@keyframes slideRight {
  from { transform: translateX(30px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

.peek-header { 
  display: flex; align-items: center; justify-content: space-between; 
  padding: 16px 20px; border-bottom: 1px solid var(--border-light); 
  background: var(--bg-surface); /* 头部保持纯白，提升层次 */
}
.peek-title { margin: 0; font-size: 15px; color: var(--text-primary); font-weight: 600; }
.peek-close { border: none; background: transparent; color: var(--text-tertiary); cursor: pointer; font-size: 24px; line-height: 1; transition: color 0.2s; }
.peek-close:hover { color: var(--color-danger); }

/* 微调内部卡片的间距，更紧凑专业 */
.peek-body { padding: 16px; overflow-y: auto; flex: 1; }
.peek-grid { 
  display: flex; flex-direction: column; gap: 10px; 
  background: var(--bg-surface); padding: 16px; 
  border-radius: var(--radius-md); border: 1px solid var(--border-light); 
}
.peek-row { display: flex; justify-content: space-between; align-items: center; font-size: 13px; }
.peek-row span { color: var(--text-secondary); }
.peek-row strong { color: var(--text-primary); font-weight: 500; }
.divider-line { height: 1px; background: var(--border-light); margin: 6px 0; }
.text-lg { font-size: 18px; font-weight: 700; }

.main-panel {
  flex: 1;
  width: 880px; 
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  z-index: 1;
}

.customer-hero { display: flex; justify-content: space-between; align-items: center; padding: 20px 24px; background: var(--bg-canvas); border-bottom: 1px solid var(--border-light); gap: 24px; }
.hero-user { display: flex; align-items: center; gap: 16px; flex: 1; min-width: 0; }
.avatar { flex-shrink: 0; width: 56px; height: 56px; border-radius: 50%; background: var(--color-primary); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: 700; }
.user-info { flex: 1; min-width: 0; }
.name-row { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; flex-wrap: wrap; }
.name { margin: 0; font-size: 18px; color: var(--text-primary); font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.badge { white-space: nowrap; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 500; }
.badge-warning { background: #FEF3C7; color: #D97706; }
.badge-retail { background: var(--bg-table-header); color: var(--text-secondary); }
.meta-row { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.hero-stats { display: flex; gap: 24px; text-align: right; flex-shrink: 0; }
.stat-item { display: flex; flex-direction: column; gap: 4px; justify-content: center; }
.stat-label { font-size: 12px; color: var(--text-tertiary); white-space: nowrap; }
.stat-value { font-size: 22px; font-weight: 700; color: var(--text-primary); white-space: nowrap; }
.stat-value-text { font-size: 15px; font-weight: 600; color: var(--text-primary); white-space: nowrap; margin-top: 4px; }
.divider { color: var(--border-dark); opacity: 0.3; }

.drawer-tabs { display: flex; gap: 24px; padding: 0 24px; border-bottom: 1px solid var(--border-light); background: var(--bg-surface); }
.tab-btn { padding: 16px 0; border: none; background: transparent; color: var(--text-secondary); font-size: 15px; font-weight: 500; cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s; white-space: nowrap; }
.tab-btn:hover { color: var(--text-primary); }
.tab-btn.active { color: var(--color-primary); border-bottom-color: var(--color-primary); }

.scrollable-area { padding: 24px; overflow-y: auto; flex: 1; background: var(--bg-surface); }
.panel-title { margin: 0 0 16px 0; font-size: 15px; color: var(--text-primary); font-weight: 600; border-left: 3px solid var(--color-primary); padding-left: 8px; }

.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; background: var(--bg-canvas); padding: 16px; border-radius: var(--radius-md); border: 1px solid var(--border-light); }
.detail-item { display: flex; flex-direction: column; gap: 6px; }
.detail-item-full { grid-column: 1 / -1; }
.detail-label { font-size: 12px; color: var(--text-secondary); }
.detail-value { font-size: 14px; color: var(--text-primary); font-weight: 500; }
.role-grid { margin-bottom: 8px; }
.field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.field-label { display: flex; flex-direction: column; gap: 8px; font-size: 12px; color: var(--text-secondary); }
.field-label-full { grid-column: 1 / -1; }
.field-input { width: 100%; min-height: 38px; padding: 8px 10px; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-surface); color: var(--text-primary); box-sizing: border-box; }
.upload-row { display: flex; align-items: center; gap: 10px; }
.upload-tip { color: var(--text-tertiary); font-size: 12px; }
.hidden-file-input { display: none; }
.license-preview-box { border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-canvas); padding: 12px; }
.license-preview-link { display: inline-block; }
.license-preview-image { width: 220px; max-width: 100%; border-radius: var(--radius-md); border: 1px solid var(--border-light); background: var(--bg-surface); }
.notification-pref-card { display: flex; flex-direction: column; gap: 12px; background: var(--bg-canvas); padding: 14px 16px; border: 1px solid var(--border-light); border-radius: var(--radius-md); }
.notification-pref-main { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.notification-pref-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.notification-pref-tag { padding: 4px 9px; border-radius: 999px; background: var(--bg-surface); border: 1px solid var(--border-light); color: var(--text-secondary); font-size: 12px; }

.textarea { width: 100%; padding: 12px; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-surface); color: var(--text-primary); outline: none; resize: vertical; box-sizing: border-box; }
.textarea:focus { border-color: var(--color-primary); }
.mt-6 { margin-top: 24px; }
.mt-4 { margin-top: 16px; }
.mt-2 { margin-top: 8px; }
.text-right { text-align: right; }
.w-full { width: 100%; }

/* 🌟 统一按钮样式 */
.btn-outline { padding: 8px 16px; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-surface); color: var(--text-secondary); cursor: pointer; transition: all 0.2s; font-weight: 500;}
.btn-outline:hover { background: var(--bg-canvas); color: var(--text-primary); border-color: var(--border-dark); }
.btn-primary-sm { background: var(--color-primary); color: #fff; border: none; padding: 6px 16px; border-radius: var(--radius-sm); font-size: 13px; font-weight: 500; cursor: pointer; transition: transform 0.1s; }
.btn-primary-sm:active { transform: scale(0.97); }

.mini-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.mini-table th { background: var(--bg-table-header); color: var(--text-secondary); font-weight: 500; text-align: left; padding: 10px 16px; border-bottom: 1px solid var(--border-light); white-space: nowrap; }
.mini-table td { padding: 14px 16px; border-bottom: 1px solid var(--border-light); color: var(--text-primary); }
.font-bold { font-weight: 600; }
.text-mono { font-family: inherit; font-weight: 600; }
.text-tertiary { color: var(--text-tertiary); }
.text-danger { color: var(--color-danger); }
.table-badge { padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: 500; white-space: nowrap; }
.tone-primary { color: #2563eb; background-color: rgba(59, 130, 246, 0.12); }
.tone-warning { color: var(--color-warning); background-color: rgba(245, 158, 11, 0.14); }
.tone-muted { color: var(--text-tertiary); background-color: var(--bg-table-header); }
.btn-link { background: transparent; border: none; color: var(--color-primary); font-weight: 500; cursor: pointer; text-decoration: none; padding: 0; }
.btn-link:hover { text-decoration: underline; }
.empty-state { padding: 40px; text-align: center; color: var(--text-tertiary); font-size: 14px; }
.loading-state { padding: 40px; text-align: center; color: var(--text-secondary); }
</style>
