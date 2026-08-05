<template>
  <div class="orders-page">
    <AppPageHeader title="订单与交接" description="收款、配货、交接和交付记录集中在这里。">
      <template #actions>
        <el-button :icon="Refresh" :loading="loading" @click="loadOrders">刷新</el-button>
      </template>
    </AppPageHeader>

    <el-card shadow="never" class="orders-card">
      <template #header>
        <div class="list-header">
          <h2>处理队列</h2>
          <ListSummary :items="orderSummary" />
        </div>
      </template>

      <div class="tabs-row">
        <el-tabs v-model="currentTab" class="queue-tabs">
          <el-tab-pane v-for="tab in tabs" :key="tab.value" :name="tab.value" :label="tab.label" />
        </el-tabs>
        <el-button link type="primary" @click="resetFilters">清除筛选</el-button>
      </div>

      <div class="filter-bar">
        <el-input v-model="searchText" :prefix-icon="Search" clearable placeholder="订单号、客户或手机号" style="width:220px" />
        <el-select v-model="fulfillmentFilter" clearable placeholder="交接方式" style="width:130px">
          <el-option v-for="option in fulfillmentOptions" :key="option.value" :label="option.label" :value="option.value" />
        </el-select>
        <el-date-picker v-model="dateRange" type="daterange" range-separator="~" start-placeholder="开始日期" end-placeholder="结束日期" value-format="YYYY-MM-DD" style="width:250px" />
        <div class="anomaly-toggle">
          <el-switch v-model="onlyAnomalies" />
          <span>仅看异常</span>
        </div>
        <el-button :icon="Refresh" :loading="loading" @click="loadOrders">刷新</el-button>
      </div>

      <el-table v-loading="loading" :data="pagedItems" row-key="id" class="orders-table" @row-click="openDetail">
        <el-table-column label="订单" min-width="206">
          <template #default="{ row }">
            <div class="order-number-row">
              <strong>{{ row.order_no }}</strong>
              <el-button link :icon="CopyDocument" title="复制订单号" @click.stop="copyOrderNo(row.order_no)" />
            </div>
            <span class="muted">{{ formatDateTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="客户" min-width="140">
          <template #default="{ row }">
            <strong>{{ row.customer_name || '未命名客户' }}</strong>
            <div class="muted">{{ maskPhone(row.customer_phone) }} · {{ buyerRoleLabel(row.buyer_role) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="商品" min-width="210">
          <template #default="{ row }">
            <div class="line-name">{{ productSummary(row) }}</div>
            <div class="muted">共 {{ row.item_count || 0 }} 件</div>
          </template>
        </el-table-column>
        <el-table-column label="金额" width="122" align="right">
          <template #default="{ row }">
            <strong>{{ formatCurrency(row.payable_amount) }}</strong>
            <div class="muted">{{ paymentMethodLabel(row.payment_method) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="履约" min-width="130">
          <template #default="{ row }">
            <span>{{ fulfillmentLabel(row) }}</span>
            <div class="muted">{{ handoffHint(row) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="126">
          <template #default="{ row }">
            <StatusTag kind="order" :status="row.status" :fulfillment-channel="fulfillmentKey(row)" />
          </template>
        </el-table-column>
        <el-table-column label="下一步" width="198" fixed="right">
          <template #default="{ row }">
            <div class="row-actions" @click.stop>
              <el-button v-if="primaryAction(row)" :type="primaryAction(row)?.type" size="small" @click="openAction(primaryAction(row)!.mode, row)">
                {{ primaryAction(row)?.label }}
              </el-button>
              <el-dropdown trigger="click" @command="(command: string) => handleMenu(command, row)">
                <el-button size="small" circle :icon="MoreFilled" title="更多操作" />
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="detail">查看详情</el-dropdown-item>
                    <el-dropdown-item command="copy">复制订单号</el-dropdown-item>
                    <el-dropdown-item v-if="row.status === 'awaiting_shipment'" command="print">打印配货单</el-dropdown-item>
                    <el-dropdown-item v-if="row.wechat_shipping_status === 'failed'" command="retry">重新上传微信发货信息</el-dropdown-item>
                    <el-dropdown-item v-if="row.status === 'pending_payment'" command="cancel" divided class="danger-item">取消订单</el-dropdown-item>
                    <el-dropdown-item v-if="row.status !== 'completed' && row.status !== 'canceled'" command="adjust">调整订单</el-dropdown-item>
                    <el-dropdown-item v-if="row.status !== 'completed' && row.status !== 'canceled'" command="terminate" divided class="danger-item">终止订单</el-dropdown-item>
                    <el-dropdown-item v-if="row.status === 'completed' || row.status === 'canceled'" command="delete" divided class="danger-item">删除订单</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty :description="emptyDescription">
            <el-button v-if="searchText || fulfillmentFilter" @click="resetFilters">清除筛选</el-button>
          </el-empty>
        </template>
      </el-table>

      <div class="table-footer">
        <span>共 {{ filteredItems.length }} 笔订单</span>
        <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :total="filteredItems.length" :page-sizes="[10, 20, 50]" layout="sizes, prev, pager, next" />
      </div>
    </el-card>

    <el-drawer v-model="drawerOpen" :title="drawerTitle" size="760px" destroy-on-close class="order-drawer" @closed="drawerMode = 'detail'">
      <template v-if="activeItem">
        <div class="drawer-status">
          <div>
            <span class="muted">订单号</span>
            <div class="drawer-order-number">{{ activeItem.order_no }} <el-button link :icon="CopyDocument" @click="copyOrderNo(activeItem.order_no)" /></div>
          </div>
          <StatusTag kind="order" :status="activeItem.status" :fulfillment-channel="fulfillmentKey(activeItem)" />
        </div>

        <template v-if="drawerMode === 'detail'">
          <section class="drawer-section">
            <h3>客户与交付</h3>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="客户">{{ activeItem.customer_name || '未命名客户' }}</el-descriptions-item>
              <el-descriptions-item label="身份">{{ buyerRoleLabel(activeItem.buyer_role) }}</el-descriptions-item>
              <el-descriptions-item label="联系电话">{{ activeItem.customer_phone || '未记录' }}</el-descriptions-item>
              <el-descriptions-item label="客户选择">{{ isPickup(activeItem) ? '到店自提' : '送货' }}</el-descriptions-item>
              <el-descriptions-item :span="2" label="地址 / 提货说明">{{ pickupDescription(activeItem) }}</el-descriptions-item>
            </el-descriptions>
          </section>

          <section class="drawer-section">
            <h3>商品</h3>
            <div class="order-lines">
              <div v-for="(line, index) in activeItem.lines || []" :key="`${line.sku_id}-${index}`" class="order-line">
                <img v-if="line.image_url" class="order-line-thumb" :src="line.image_url" :alt="line.product_name" />
                <div>
                  <strong>{{ line.product_name }}</strong>
                  <div class="muted">{{ [line.spec_value_1, line.spec_value_2].filter(Boolean).join(' / ') || '默认规格' }}</div>
                </div>
                <div class="line-price"><span>{{ formatCurrency(line.unit_price) }} × {{ line.quantity }}</span><strong>{{ formatCurrency(line.line_amount) }}</strong></div>
              </div>
              <el-empty v-if="!(activeItem.lines || []).length" :image-size="58" description="暂无商品明细" />
            </div>
          </section>

          <section class="drawer-section">
            <h3>金额与付款</h3>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="商品金额">{{ formatCurrency(activeItem.original_amount) }}</el-descriptions-item>
              <el-descriptions-item label="运费">{{ formatCurrency(activeItem.shipping_fee) }}</el-descriptions-item>
              <el-descriptions-item label="应收"><strong>{{ formatCurrency(activeItem.payable_amount) }}</strong></el-descriptions-item>
              <el-descriptions-item label="付款方式">{{ paymentMethodLabel(activeItem.payment_method) }}</el-descriptions-item>
              <el-descriptions-item :span="2" label="付款时间">{{ activeItem.paid_at ? formatDateTime(activeItem.paid_at) : '尚未确认收款' }}</el-descriptions-item>
            </el-descriptions>
          </section>

          <section v-if="hasHandoffInfo(activeItem)" class="drawer-section">
            <h3>交接记录</h3>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="实际方式">{{ fulfillmentLabel(activeItem) }}</el-descriptions-item>
              <el-descriptions-item label="交接时间">{{ activeItem.shipped_at ? formatDateTime(activeItem.shipped_at) : '未记录' }}</el-descriptions-item>
              <el-descriptions-item label="承运方 / 配送">{{ activeItem.logistics_company || '未填写' }}</el-descriptions-item>
              <el-descriptions-item label="单号 / 交接编号">{{ activeItem.tracking_no || '未填写' }}</el-descriptions-item>
              <el-descriptions-item v-if="activeItem.carrier_contact" label="承运方联系">{{ activeItem.carrier_contact }}</el-descriptions-item>
              <el-descriptions-item v-if="activeItem.payment_method === 'wechat_pay'" label="微信发货">{{ wechatShippingLabel(activeItem) }}</el-descriptions-item>
              <el-descriptions-item :span="2" label="店内备注">{{ activeItem.internal_note || activeItem.note || '无' }}</el-descriptions-item>
            </el-descriptions>
            <el-alert v-if="activeItem.wechat_shipping_error" class="shipping-alert" type="warning" :closable="false" :title="activeItem.wechat_shipping_error" />
          </section>

          <section class="drawer-section">
            <h3>订单时间线</h3>
            <el-timeline>
              <el-timeline-item v-for="event in lifecycle(activeItem)" :key="event.label" :timestamp="event.time ? formatDateTime(event.time) : event.empty" :type="event.time ? 'success' : 'info'" :hollow="!event.time">
                {{ event.label }}
              </el-timeline-item>
            </el-timeline>
          </section>

          <section class="drawer-section">
            <h3>操作记录</h3>
            <el-timeline v-if="orderEvents.length">
              <el-timeline-item v-for="event in orderEvents" :key="event.id" :timestamp="formatDateTime(event.created_at)" type="primary">
                <strong>{{ event.action_label }}</strong>
                <span v-if="event.actor_name_snapshot" class="event-meta">{{ event.actor_name_snapshot }}<template v-if="eventDisplayNote(event)"> · {{ eventDisplayNote(event) }}</template></span>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-else :image-size="48" description="暂无操作记录" />
          </section>
        </template>

        <el-form v-else label-position="top" class="action-form">
          <template v-if="drawerMode === 'payment'">
            <el-alert type="info" :closable="false" title="确认后订单将进入待配货或待备货队列。" />
            <el-form-item label="收款备注">
              <el-input v-model="paymentNote" type="textarea" :rows="4" placeholder="可记录线下转账、核对信息或人工确认说明" />
            </el-form-item>
          </template>

          <template v-else-if="drawerMode === 'ship' && isPickup(activeItem)">
            <el-alert type="info" :closable="false" title="标记可提货后，订单会进入“待提货”队列。货物实际交给客户时，再执行“确认交付”。" />
            <el-form-item label="备货 / 自提备注">
              <el-input v-model="shippingForm.note" type="textarea" :rows="4" placeholder="可填写提货核验、备货位置或交接说明；可留空" />
            </el-form-item>
          </template>

          <template v-else-if="drawerMode === 'ship'">
            <el-form-item label="实际交接方式">
              <el-radio-group v-model="shippingForm.fulfillment_channel">
                <el-radio-button label="courier">标准快递</el-radio-button>
                <el-radio-button label="linehaul">物流部交接</el-radio-button>
                <el-radio-button label="local_delivery">同城配送</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <div class="form-grid">
              <el-form-item v-if="shippingForm.fulfillment_channel !== 'local_delivery'" :label="shippingForm.fulfillment_channel === 'courier' ? '快递公司' : '物流部 / 承运方'" required>
                <el-input v-model="shippingForm.logistics_company" :placeholder="shippingForm.fulfillment_channel === 'courier' ? '例如：顺丰、中通' : '例如：某某物流部、个人承运方'" />
              </el-form-item>
              <el-form-item v-if="shippingForm.fulfillment_channel === 'courier'" label="快递单号" required>
                <el-input v-model="shippingForm.tracking_no" />
              </el-form-item>
              <el-form-item v-if="shippingForm.fulfillment_channel === 'linehaul'" label="承运方联系电话">
                <el-input v-model="shippingForm.carrier_contact" placeholder="内部追溯使用，可留空" />
              </el-form-item>
              <el-form-item v-if="shippingForm.fulfillment_channel === 'linehaul'" label="交接编号">
                <el-input v-model="shippingForm.tracking_no" placeholder="没有则留空" />
              </el-form-item>
              <el-form-item v-if="shippingForm.fulfillment_channel === 'local_delivery'" label="配送说明">
                <el-input v-model="shippingForm.note" placeholder="配送人、预计时间或补充说明" />
              </el-form-item>
            </div>
            <el-form-item label="交接凭证图">
              <ImageUploadField v-model="shippingForm.shipping_proof_url" hint="可上传交接照片或运费截图，支持拖拽、粘贴、选择图片" />
            </el-form-item>
            <el-form-item v-if="shippingForm.fulfillment_channel !== 'local_delivery'" label="内部备注">
              <el-input v-model="shippingForm.note" type="textarea" :rows="3" placeholder="车次、交接人或补充说明；可留空" />
            </el-form-item>
          </template>

          <template v-else-if="drawerMode === 'deliver'">
            <el-alert type="warning" :closable="false" :title="isPickup(activeItem) ? '请确认货物已经交给客户，再标记为已完成。' : '请确认已经实际送达或签收，再标记为已完成。'" />
            <el-form-item :label="isPickup(activeItem) ? '交付时间' : '送达 / 签收时间'">
              <el-date-picker v-model="signedAt" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" style="width: 100%" />
            </el-form-item>
          </template>

          <template v-else-if="drawerMode === 'cancel'">
            <el-alert type="error" :closable="false" title="取消后订单不能恢复，请确认已与客户沟通。" />
            <el-form-item label="取消原因">
              <el-input v-model="cancelNote" type="textarea" :rows="4" placeholder="请记录取消原因" />
            </el-form-item>
          </template>

          <template v-else-if="drawerMode === 'adjust'">
            <el-alert type="info" :closable="false" title="订单金额和商品明细一经创建即固定。如需变价，请终止原订单并由客户重新下单。" />
            <el-form-item label="收货人"><el-input v-model="adjustForm.shipping_recipient" /></el-form-item>
            <el-form-item label="联系电话"><el-input v-model="adjustForm.shipping_phone" /></el-form-item>
            <el-form-item label="收货地址"><el-input v-model="adjustForm.shipping_address" type="textarea" :rows="2" /></el-form-item>
            <el-form-item label="客户可见说明"><el-input v-model="adjustForm.customer_note" type="textarea" :rows="2" placeholder="客户订单详情会显示" /></el-form-item>
            <el-form-item label="店内备注"><el-input v-model="adjustForm.internal_note" type="textarea" :rows="2" placeholder="仅后台与工作台可见" /></el-form-item>
            <el-form-item label="调整原因"><el-input v-model="adjustForm.reason" type="textarea" :rows="2" placeholder="修改金额、地址或客户说明时必填" /></el-form-item>
          </template>

          <template v-else-if="drawerMode === 'terminate'">
            <el-alert type="warning" :closable="false" title="终止会结束订单，但保留完整记录。已付款订单的退款或补款须在“后续款项处理”中记录。" />
            <el-form-item label="终止原因" required><el-input v-model="terminationForm.reason" type="textarea" :rows="3" placeholder="例如：客户沟通后不再需要" /></el-form-item>
            <el-form-item label="后续款项处理"><el-input v-model="terminationForm.disposition" placeholder="例如：已线下退款 / 无需退款 / 待客服沟通" /></el-form-item>
            <el-form-item label="店内备注"><el-input v-model="terminationForm.internal_note" type="textarea" :rows="3" /></el-form-item>
          </template>
        </el-form>
      </template>

      <template #footer>
        <div class="drawer-footer">
          <el-button @click="drawerOpen = false">关闭</el-button>
          <el-button v-if="drawerMode === 'detail' && activeItem?.status === 'awaiting_shipment'" :loading="submitting" @click="createActivePrintJob">打印配货单</el-button>
          <el-button v-if="drawerMode === 'payment'" type="primary" :loading="submitting" @click="submitPayment">确认收款</el-button>
          <el-button v-if="drawerMode === 'ship'" type="primary" :loading="submitting" @click="submitShipment">{{ isPickup(activeItem) ? '标记可提货' : '确认交接' }}</el-button>
          <el-button v-if="drawerMode === 'deliver'" type="primary" :loading="submitting" @click="submitDelivered">{{ isPickup(activeItem) ? '确认交付' : '确认送达' }}</el-button>
          <el-button v-if="drawerMode === 'cancel'" type="danger" :loading="submitting" @click="submitCancel">确认取消</el-button>
          <el-button v-if="drawerMode === 'adjust'" type="primary" :loading="submitting" @click="submitAdjustment">保存调整</el-button>
          <el-button v-if="drawerMode === 'terminate'" type="danger" :loading="submitting" @click="submitTermination">终止订单</el-button>
        </div>
      </template>
    </el-drawer>

    <el-dialog v-model="deleteDialogOpen" title="删除订单" width="440px" destroy-on-close>
      <p class="delete-dialog-copy">订单将从日常列表隐藏，但会保留删除记录。请输入“确认删除此订单”继续。</p>
      <el-input v-model="deleteConfirmation" placeholder="确认删除此订单" />
      <template #footer>
        <el-button @click="deleteDialogOpen = false">取消</el-button>
        <el-button type="danger" :disabled="deleteConfirmation !== '确认删除此订单'" :loading="submitting" @click="confirmDeleteOrder">删除订单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { CopyDocument, MoreFilled, Refresh, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import AppPageHeader from '@/components/AppPageHeader.vue'
import StatusTag from '@/components/shared/StatusTag.vue'
import ListSummary from '@/components/shared/ListSummary.vue'
import ImageUploadField from '@/components/shared/ImageUploadField.vue'
import { adjustAdminOrder, cancelOrder, confirmOfflinePayment, confirmWechatPayment, createPickListPrintJob, deleteAdminOrder, fetchEntityEvents, fetchWorkbenchOrders, markDelivered, retryWechatShipping, shipOrder, terminateAdminOrder } from '@/api/modules'
import type { BusinessEventItem, WorkbenchOrderItem } from '@/types/api'
import { formatCurrency, formatDateTime } from '@/utils/adminFormat'

type TabKey = 'all' | WorkbenchOrderItem['status']
type DrawerMode = 'detail' | 'payment' | 'ship' | 'deliver' | 'cancel' | 'adjust' | 'terminate'

const tabs: Array<{ label: string; value: TabKey }> = [
  { label: '全部', value: 'all' },
  { label: '待支付', value: 'pending_payment' },
  { label: '待发货', value: 'awaiting_shipment' },
  { label: '已发货', value: 'shipped' },
  { label: '已完成', value: 'completed' },
  { label: '已取消', value: 'canceled' },
]

const fulfillmentOptions = [
  { label: '到店自提', value: 'pickup' },
  { label: '标准快递', value: 'courier' },
  { label: '物流部交接', value: 'linehaul' },
  { label: '同城配送', value: 'local_delivery' },
]

const orders = ref<WorkbenchOrderItem[]>([])
const loading = ref(false)
const submitting = ref(false)
const currentTab = ref<TabKey>('all')
const searchText = ref('')
const fulfillmentFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const drawerOpen = ref(false)
const drawerMode = ref<DrawerMode>('detail')
const activeItem = ref<WorkbenchOrderItem | null>(null)
const paymentNote = ref('')
const cancelNote = ref('')
const signedAt = ref('')
const dateRange = ref<[string, string] | null>(null)
const onlyAnomalies = ref(false)
const orderEvents = ref<BusinessEventItem[]>([])
const adjustForm = reactive({ shipping_recipient: '', shipping_phone: '', shipping_address: '', customer_note: '', internal_note: '', reason: '' })
const terminationForm = reactive({ reason: '', disposition: '', internal_note: '' })
const deleteDialogOpen = ref(false)
const deleteConfirmation = ref('')
const deleteTarget = ref<WorkbenchOrderItem | null>(null)
const shippingForm = reactive({
  fulfillment_channel: 'linehaul' as 'courier' | 'linehaul' | 'local_delivery',
  shipping_proof_url: '',
  logistics_company: '',
  carrier_contact: '',
  tracking_no: '',
  note: '',
})

const orderSummary = computed(() => [
  { value: orders.value.length, label: '笔订单' },
  { value: orders.value.filter((item) => item.status === 'pending_payment').length, label: '待支付', tone: 'warning' as const },
  { value: orders.value.filter((item) => item.status === 'awaiting_shipment').length, label: '待发货', tone: 'warning' as const },
  { value: orders.value.filter((item) => item.status === 'shipped').length, label: '已发货' },
])

const filteredItems = computed(() => {
  const keyword = searchText.value.trim().toLowerCase()
  const [from, to] = dateRange.value ?? [null, null]
  return orders.value.filter((item) => {
    const matchesKeyword = !keyword || [item.order_no, item.customer_name, item.customer_phone, item.item_summary].filter(Boolean).some((value) => String(value).toLowerCase().includes(keyword))
    const matchesFulfillment = !fulfillmentFilter.value || fulfillmentKey(item) === fulfillmentFilter.value
    const matchesDate = !from || !to || (item.created_at >= from && item.created_at <= to + 'T23:59:59')
    const matchesAnomaly = !onlyAnomalies.value || item.wechat_shipping_status === 'failed' || item.wechat_shipping_status === 'manual_required'
    return matchesKeyword && matchesFulfillment && matchesDate && matchesAnomaly
  })
})

const pagedItems = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredItems.value.slice(start, start + pageSize.value)
})

const drawerTitle = computed(() => ({ detail: '订单详情', payment: '确认收款', ship: isPickup(activeItem.value) ? '标记可提货' : '登记交接', deliver: isPickup(activeItem.value) ? '确认交付' : '确认送达', cancel: '取消订单', adjust: '调整订单', terminate: '终止订单' })[drawerMode.value])
const emptyDescription = computed(() => searchText.value || fulfillmentFilter.value ? '没有符合当前筛选的订单' : '这个队列暂时没有订单')

watch([currentTab, fulfillmentFilter, searchText, dateRange, onlyAnomalies], () => {
  currentPage.value = 1
})
watch(currentTab, () => void loadOrders())
onMounted(() => void loadOrders())

function isPickup(item?: WorkbenchOrderItem | null) {
  return item?.fulfillment_channel === 'pickup' || Boolean(item?.shipping_address?.includes('到店自提') || item?.shipping_recipient === '到店自提')
}

function fulfillmentKey(item: WorkbenchOrderItem) {
  if (isPickup(item)) return 'pickup'
  return item.fulfillment_channel || (item.shipping_mode === 'express' ? 'courier' : '')
}

function fulfillmentLabel(item: WorkbenchOrderItem) {
  const labels: Record<string, string> = { pickup: '到店自提', courier: '标准快递', linehaul: '物流部交接', local_delivery: '同城配送' }
  return labels[fulfillmentKey(item)] || (item.shipping_mode === 'offline' ? '线下交接' : '待确认')
}

function handoffHint(item: WorkbenchOrderItem) {
  if (item.status === 'awaiting_shipment') return isPickup(item) ? '待备货' : '待登记交接'
  if (item.status === 'shipped' && isPickup(item)) return '等待客户提货'
  if (item.status === 'shipped') return item.shipped_at ? `交接于 ${formatDateTime(item.shipped_at)}` : '已登记交接'
  return '—'
}

function buyerRoleLabel(role: WorkbenchOrderItem['buyer_role']) {
  return role === 'wholesale' ? '批发客户' : '零售客户'
}

function paymentMethodLabel(method: WorkbenchOrderItem['payment_method']) {
  return method === 'wechat_pay' ? '微信支付' : '线下转账'
}

function productSummary(item: WorkbenchOrderItem) {
  const first = item.lines?.[0]?.product_name || item.item_summary || '商品信息待补充'
  const additional = Math.max(0, (item.lines?.length || 0) - 1)
  return additional ? `${first} 等 ${additional + 1} 件商品` : first
}

function maskPhone(phone?: string | null) {
  return phone && phone.length >= 7 ? `${phone.slice(0, 3)}****${phone.slice(-4)}` : phone || '未留手机号'
}

function pickupDescription(item: WorkbenchOrderItem) {
  if (isPickup(item)) return item.shipping_address?.replace(/^到店自提：?/, '') || '客户到店提货，无需收货地址。'
  return item.shipping_address || '地址由客服确认或尚未填写。'
}

function wechatShippingLabel(item: WorkbenchOrderItem) {
  const labels: Record<NonNullable<WorkbenchOrderItem['wechat_shipping_status']>, string> = { pending: '正在上传', succeeded: '已提交微信', failed: '上传失败，需重试', skipped: '无需上传', manual_required: '需到微信后台补录' }
  return item.wechat_shipping_status ? labels[item.wechat_shipping_status] : '发货后更新'
}

function hasHandoffInfo(item: WorkbenchOrderItem) {
  return Boolean(item.shipping_mode || item.shipped_at || item.logistics_company || item.tracking_no || item.note)
}

function cancellationLabel(item: WorkbenchOrderItem) {
  if (item.terminated_at) return '订单终止'
  if (item.cancellation_source === 'auto_timeout') return '超时自动取消'
  if (item.cancellation_source === 'customer') return '客户手动取消'
  if (item.cancellation_source === 'staff') return '店内手动取消'
  return '订单已取消'
}

function cancellationReason(item: WorkbenchOrderItem) {
  const reason = item.terminated_at ? item.termination_reason : item.cancellation_reason
  return reason === 'payment timeout' ? '超过支付时限，订单已自动取消' : reason || ''
}

function lifecycle(item: WorkbenchOrderItem) {
  return [
    { label: '订单创建', time: item.created_at, empty: '' },
    ...(item.paid_at ? [{ label: '已确认收款', time: item.paid_at, empty: '' }] : []),
    ...(item.shipped_at ? [{ label: isPickup(item) ? '已标记可提货' : '已发货', time: item.shipped_at, empty: '' }] : []),
    ...(item.delivery_signed_at ? [{ label: isPickup(item) ? '已确认交付' : '已确认送达', time: item.delivery_signed_at, empty: '' }] : []),
    ...(item.completed_at ? [{ label: '订单已完成', time: item.completed_at, empty: '' }] : []),
    ...(item.canceled_at || item.terminated_at ? [{
      label: cancellationLabel(item) + (cancellationReason(item) ? ' · ' + cancellationReason(item) : ''),
      time: item.terminated_at || item.canceled_at,
      empty: '',
    }] : []),
  ]
}

function primaryAction(item: WorkbenchOrderItem): { label: string; mode: DrawerMode; type: 'primary' | 'warning' } | null {
  if (item.status === 'pending_payment') return { label: '确认收款', mode: 'payment', type: 'primary' }
  if (item.status === 'awaiting_shipment') return { label: isPickup(item) ? '标记可提货' : '登记交接', mode: 'ship', type: 'primary' }
  if (item.status === 'shipped') return { label: isPickup(item) ? '确认交付' : '确认送达', mode: 'deliver', type: 'warning' }
  return null
}

async function loadOrders() {
  loading.value = true
  try {
    const status = currentTab.value === 'all' ? 'all' : currentTab.value
    const response = await fetchWorkbenchOrders(status)
    orders.value = response.data
  } catch {
    ElMessage.error('订单加载失败，请检查网络后重试')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  searchText.value = ''
  fulfillmentFilter.value = ''
  dateRange.value = null
  onlyAnomalies.value = false
}

function openDetail(item: WorkbenchOrderItem) {
  openAction('detail', item)
}

function openAction(mode: DrawerMode, item: WorkbenchOrderItem) {
  activeItem.value = item
  drawerMode.value = mode
  paymentNote.value = item.note || ''
  cancelNote.value = item.note || ''
  signedAt.value = new Date().toISOString().slice(0, 19)
  shippingForm.fulfillment_channel = item.fulfillment_channel === 'courier' || item.fulfillment_channel === 'local_delivery' ? item.fulfillment_channel : 'linehaul'
  shippingForm.shipping_proof_url = item.shipping_proof_url || ''
  shippingForm.logistics_company = item.logistics_company || ''
  shippingForm.carrier_contact = item.carrier_contact || ''
  shippingForm.tracking_no = item.tracking_no || ''
  shippingForm.note = item.note || ''
  Object.assign(adjustForm, {
    shipping_recipient: item.shipping_recipient || '',
    shipping_phone: item.shipping_phone || '',
    shipping_address: item.shipping_address || '',
    customer_note: item.customer_note || item.note || '',
    internal_note: item.internal_note || '',
    reason: '',
  })
  Object.assign(terminationForm, { reason: '', disposition: '', internal_note: item.internal_note || '' })
  drawerOpen.value = true
  if (mode === 'detail') void loadOrderEvents(item.id)
}

async function handleMenu(command: string, item: WorkbenchOrderItem) {
  if (command === 'detail') return openAction('detail', item)
  if (command === 'copy') return copyOrderNo(item.order_no)
  if (command === 'print') return createPrintJob(item)
  if (command === 'cancel') return openAction('cancel', item)
  if (command === 'adjust') return openAction('adjust', item)
  if (command === 'terminate') return openAction('terminate', item)
  if (command === 'delete') return deleteOrder(item)
  if (command === 'retry') return retryWechatShippingUpload(item)
}

async function createPrintJob(item: WorkbenchOrderItem) {
  try {
    await ElMessageBox.confirm(`将为订单 ${item.order_no} 创建一张配货单打印任务。`, '确认打印', {
      type: 'warning',
      confirmButtonText: '创建打印任务',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  submitting.value = true
  try {
    await createPickListPrintJob(item.id)
    ElMessage.success('已进入打印队列')
    await loadOrders()
    if (drawerMode.value === 'detail') await loadOrderEvents(item.id)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '创建打印任务失败')
  } finally {
    submitting.value = false
  }
}

function createActivePrintJob() {
  if (activeItem.value) return createPrintJob(activeItem.value)
}

async function loadOrderEvents(orderId: number) {
  orderEvents.value = []
  try {
    const response = await fetchEntityEvents('order', orderId)
    orderEvents.value = response.data
  } catch {
    ElMessage.warning('操作记录加载失败')
  }
}

function eventSummary(event: BusinessEventItem) {
  const data = event.after_data
  return [data.status, data.reason, data.disposition].filter(Boolean).join(' · ')
}

function eventDisplayNote(event: BusinessEventItem) {
  const note = String(event.note || '').trim()
  if (/^\?+$/.test(note)) return eventSummary(event)
  if (note === 'payment timeout' || note === 'system auto cancel timeout') return '超过支付时限，订单已自动取消'
  return note || eventSummary(event)
}

async function deleteOrder(item: WorkbenchOrderItem) {
  deleteTarget.value = item
  deleteConfirmation.value = ''
  deleteDialogOpen.value = true
}

async function confirmDeleteOrder() {
  if (!deleteTarget.value || deleteConfirmation.value !== '确认删除此订单') return
  submitting.value = true
  try {
    await deleteAdminOrder(deleteTarget.value.id, deleteConfirmation.value)
    drawerOpen.value = false
    deleteDialogOpen.value = false
    ElMessage.success('订单已删除')
    await loadOrders()
  } finally { submitting.value = false }
}

async function copyOrderNo(orderNo: string) {
  await navigator.clipboard?.writeText(orderNo)
  ElMessage.success('订单号已复制')
}

async function submitPayment() {
  if (!activeItem.value) return
  submitting.value = true
  try {
    if (activeItem.value.payment_method === 'offline_transfer') await confirmOfflinePayment(activeItem.value.id, paymentNote.value || undefined)
    else await confirmWechatPayment(activeItem.value.id)
    ElMessage.success('收款已确认')
    drawerOpen.value = false
    await loadOrders()
  } finally {
    submitting.value = false
  }
}

async function submitShipment() {
  if (!activeItem.value) return
  const pickup = isPickup(activeItem.value)
  if (!pickup && shippingForm.fulfillment_channel === 'courier' && (!shippingForm.logistics_company.trim() || !shippingForm.tracking_no.trim())) {
    ElMessage.warning('标准快递需要填写快递公司和单号')
    return
  }
  submitting.value = true
  try {
    await shipOrder(activeItem.value.id, {
      shipping_mode: pickup || shippingForm.fulfillment_channel !== 'courier' ? 'offline' : 'express',
      fulfillment_channel: pickup ? 'pickup' : shippingForm.fulfillment_channel,
      shipping_proof_url: shippingForm.shipping_proof_url.trim() || undefined,
      logistics_company: shippingForm.logistics_company.trim() || undefined,
      carrier_contact: shippingForm.carrier_contact.trim() || undefined,
      tracking_no: shippingForm.tracking_no.trim() || undefined,
      note: shippingForm.note.trim() || undefined,
    })
    ElMessage.success(pickup ? '已标记可提货' : '交接信息已登记')
    drawerOpen.value = false
    await loadOrders()
  } finally {
    submitting.value = false
  }
}

async function submitDelivered() {
  if (!activeItem.value) return
  submitting.value = true
  try {
    await markDelivered(activeItem.value.id, new Date(signedAt.value || Date.now()).toISOString())
    ElMessage.success(isPickup(activeItem.value) ? '已确认交付' : '已确认送达')
    drawerOpen.value = false
    await loadOrders()
  } finally {
    submitting.value = false
  }
}

async function submitCancel() {
  if (!activeItem.value) return
  await ElMessageBox.confirm('取消后订单不能恢复，确定继续吗？', '确认取消', { type: 'warning', confirmButtonText: '取消订单', cancelButtonText: '返回' })
  submitting.value = true
  try {
    await cancelOrder(activeItem.value.id, cancelNote.value.trim() || undefined)
    ElMessage.success('订单已取消')
    drawerOpen.value = false
    await loadOrders()
  } finally {
    submitting.value = false
  }
}

async function submitAdjustment() {
  if (!activeItem.value) return
  const changingCustomerFields = ['shipping_recipient', 'shipping_phone', 'shipping_address', 'customer_note'].some((key) => adjustForm[key as keyof typeof adjustForm] !== String(activeItem.value?.[key as keyof WorkbenchOrderItem] || ''))
  if (changingCustomerFields && !adjustForm.reason.trim()) { ElMessage.warning('请填写调整原因'); return }
  const payload: Record<string, unknown> = {}
  for (const key of ['shipping_recipient', 'shipping_phone', 'shipping_address', 'customer_note', 'internal_note'] as const) {
    if (adjustForm[key] !== String(activeItem.value[key] || '')) payload[key] = adjustForm[key]
  }
  if (adjustForm.reason.trim()) payload.reason = adjustForm.reason.trim()
  if (!Object.keys(payload).length) { ElMessage.info('没有需要保存的调整'); return }
  submitting.value = true
  try {
    await adjustAdminOrder(activeItem.value.id, payload)
    ElMessage.success('订单调整已保存')
    drawerOpen.value = false
    await loadOrders()
  } finally { submitting.value = false }
}

async function submitTermination() {
  if (!activeItem.value || !terminationForm.reason.trim()) { ElMessage.warning('请填写终止原因'); return }
  submitting.value = true
  try {
    await terminateAdminOrder(activeItem.value.id, {
      reason: terminationForm.reason.trim(),
      disposition: terminationForm.disposition.trim() || undefined,
      internal_note: terminationForm.internal_note.trim() || undefined,
    })
    ElMessage.success('订单已终止')
    drawerOpen.value = false
    await loadOrders()
  } finally { submitting.value = false }
}

async function retryWechatShippingUpload(item: WorkbenchOrderItem) {
  submitting.value = true
  try {
    const response = await retryWechatShipping(item.id)
    const data = response.data as Partial<WorkbenchOrderItem>
    item.wechat_shipping_status = data.wechat_shipping_status || item.wechat_shipping_status
    item.wechat_shipping_error = data.wechat_shipping_error || null
    ElMessage.success(data.wechat_shipping_status === 'succeeded' ? '微信发货信息已提交' : '上传结果已更新')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.orders-page { display: grid; gap: 18px; }
.orders-card { border-radius: 8px; }
.orders-card :deep(.el-card__header) { padding: 14px 20px 0; border-bottom: 0; }
.orders-card :deep(.el-card__body) { padding: 0 20px 16px; }
.list-header { display: flex; align-items: center; justify-content: space-between; gap: 18px; }
.list-header h2 { margin: 0; color: var(--text-primary); font-size: 16px; }
.tabs-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 0 0; }
.queue-tabs { min-width: 0; }
.queue-tabs :deep(.el-tabs__header) { margin: 0; }
.queue-tabs :deep(.el-tabs__content) { display: none; }
.filter-bar { display: flex; align-items: center; gap: 10px; padding: 10px 0 14px; border-bottom: 1px solid var(--border-light); flex-wrap: nowrap; overflow-x: auto; }
.anomaly-toggle { display: flex; align-items: center; gap: 6px; color: var(--text-secondary); font-size: 13px; white-space: nowrap; flex-shrink: 0; }
.orders-table { margin-top: 2px; cursor: pointer; }
.orders-table :deep(.el-table__cell) { padding: 13px 0; }
.order-number-row, .row-actions { display: flex; align-items: center; gap: 4px; }
.order-number-row strong { font-variant-numeric: tabular-nums; }
.muted { display: block; margin-top: 4px; color: var(--text-tertiary); font-size: 12px; line-height: 1.35; }
.line-name { color: var(--text-primary); font-weight: 500; line-height: 1.4; }
.table-footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding-top: 16px; color: var(--text-tertiary); font-size: 13px; }
.drawer-status { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 0 0 18px; border-bottom: 1px solid var(--border-light); }
.drawer-order-number { display: flex; align-items: center; gap: 4px; margin-top: 4px; color: var(--text-primary); font-weight: 600; font-variant-numeric: tabular-nums; }
.drawer-section { padding: 20px 0; border-bottom: 1px solid var(--border-light); }
.drawer-section:last-child { border-bottom: 0; }
.drawer-section h3 { margin: 0 0 12px; color: var(--text-primary); font-size: 15px; }
.order-lines { display: grid; gap: 8px; }
.order-line { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 12px; border: 1px solid var(--border-light); border-radius: 6px; }
.order-line-thumb { width: 44px; height: 44px; flex: 0 0 auto; border-radius: 6px; object-fit: cover; background: var(--bg-muted); }
.line-price { display: grid; gap: 5px; text-align: right; color: var(--text-secondary); font-size: 13px; white-space: nowrap; }
.line-price strong { color: var(--text-primary); }
.shipping-alert { margin-top: 12px; }
.action-form { padding-top: 20px; }
.action-form :deep(.el-alert) { margin-bottom: 18px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 16px; }
.drawer-footer { display: flex; justify-content: flex-end; gap: 10px; }
.delete-dialog-copy { margin: 0 0 14px; color: var(--text-secondary); line-height: 1.6; }
:deep(.danger-item) { color: var(--el-color-danger); }
</style>
