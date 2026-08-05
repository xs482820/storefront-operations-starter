<template>
  <div class="storefront-page">
    <AppPageHeader title="经营设置" description="店铺、公告、配送、通知、安全与 AI 工具配置。" />

    <el-card shadow="never" class="main-card">
      <el-tabs v-model="activeTab" tab-position="left" class="storefront-tabs">

        <!-- 首页轮播 -->
        <el-tab-pane label="首页轮播" name="banner">
          <div class="tab-section">
            <div class="tab-header">
              <div>
                <h3>首页轮播装修</h3>
                <p>管理首页轮播图的展示、跳转方式、排序和启停状态。</p>
              </div>
              <div class="tab-header-actions">
                <el-button @click="openModal()">＋ 新增轮播</el-button>
                <el-button type="primary" :loading="savingSection === 'banner'" @click="saveSection">保存本节</el-button>
              </div>
            </div>

            <div v-if="form.home_banners.length === 0" class="section-empty">
              <el-empty description="暂无轮播配置" :image-size="60">
                <el-button @click="openModal()">新增轮播图</el-button>
              </el-empty>
            </div>

            <div v-else class="banner-grid">
              <div v-for="(item, idx) in form.home_banners" :key="`banner-${idx}`" class="banner-card" :class="{ disabled: !item.is_active }">
                <div class="banner-cover">
                  <img v-if="item.image_url" :src="item.image_url" :alt="item.title || '轮播图'" />
                  <div v-else class="empty-cover">暂无图片</div>
                </div>
                <div class="banner-info">
                  <div class="banner-title">{{ item.title || '未命名轮播' }}</div>
                  <div class="banner-meta">跳转：{{ formatLinkType(item.link_type) }}</div>
                  <el-tag :type="item.is_active ? 'success' : 'info'" effect="light" size="small">{{ item.is_active ? '展示中' : '已停用' }}</el-tag>
                </div>
                <div class="banner-actions">
                  <el-button link @click="openModal(idx)">编辑</el-button>
                  <el-popconfirm title="确定删除此轮播图吗？" @confirm="removeBanner(idx)">
                    <template #reference><el-button link type="danger">删除</el-button></template>
                  </el-popconfirm>
                </div>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- 公告 -->
        <el-tab-pane name="marquee">
          <template #label>
            公告
            <el-badge v-if="activeMarqueeCount > 0" :value="activeMarqueeCount" class="tab-badge" />
          </template>
          <div class="tab-section">
            <div class="tab-header">
              <div>
                <h3>跑马灯公告</h3>
                <p>展示在小程序选购页顶部，用于通知类信息。共 {{ marqueeNotices.length }} 条，{{ activeMarqueeCount }} 条启用。</p>
              </div>
              <div class="tab-header-actions">
                <el-button @click="addMarqueeNotice">新增公告</el-button>
                <el-button type="primary" :loading="marqueeSaving" @click="saveMarqueeNotices">保存公告</el-button>
              </div>
            </div>

            <el-empty v-if="marqueeNotices.length === 0" description="暂无公告" :image-size="60" />

            <div class="marquee-list">
              <el-card v-for="(notice, idx) in marqueeNotices" :key="notice.id || `n-${idx}`" shadow="never" class="marquee-card" :class="{ 'is-disabled': !notice.is_active }">
                <div class="marquee-head">
                  <div>
                    <el-tag size="small" effect="plain">公告 {{ idx + 1 }}</el-tag>
                    <strong class="marquee-title">{{ notice.title || '未命名公告' }}</strong>
                  </div>
                  <div class="marquee-actions">
                    <el-switch v-model="notice.is_active" size="small" />
                    <el-button link size="small" :disabled="idx === 0" @click="moveMarqueeNotice(idx, -1)">上移</el-button>
                    <el-button link size="small" :disabled="idx === marqueeNotices.length - 1" @click="moveMarqueeNotice(idx, 1)">下移</el-button>
                    <el-popconfirm title="确定删除？" @confirm="removeMarqueeNotice(idx)">
                      <template #reference><el-button link type="danger" size="small">删除</el-button></template>
                    </el-popconfirm>
                  </div>
                </div>
                <div class="marquee-form">
                  <el-form label-position="top" size="small">
                    <div class="form-row-2">
                      <el-form-item label="公告标题"><el-input v-model="notice.title" placeholder="例如：满 299 元免运费" /></el-form-item>
                      <el-form-item label="按钮文字"><el-input v-model="notice.action_label" placeholder="例如：去看看" /></el-form-item>
                    </div>
                    <el-form-item label="公告正文"><el-input v-model="notice.body" type="textarea" :rows="2" /></el-form-item>
                    <div class="form-row-2">
                      <el-form-item label="点击动作">
                        <el-select v-model="notice.action_type" style="width:100%">
                          <el-option label="仅展示" value="none" />
                          <el-option label="跳到分类" value="category" />
                          <el-option label="打开清单" value="cart" />
                          <el-option label="打开个人页" value="profile" />
                          <el-option label="小程序路径" value="url" />
                        </el-select>
                      </el-form-item>
                      <el-form-item v-if="notice.action_type !== 'none'" label="动作参数"><el-input v-model="notice.action_value" :placeholder="marqueeActionPlaceholder(notice.action_type)" /></el-form-item>
                    </div>
                  </el-form>
                </div>
              </el-card>
            </div>
          </div>
        </el-tab-pane>

        <!-- 配送与运费 -->
        <el-tab-pane label="配送与运费" name="shipping">
          <div class="tab-section">
            <div class="tab-header">
              <div><h3>配送与运费</h3><p>客户只选择配送或到店自提。快递、物流部和同城配送由店内发货时决定。</p></div>
              <el-button type="primary" :loading="savingSection === 'shipping'" @click="saveSection">保存本节</el-button>
            </div>
            <el-form label-position="top">
              <el-alert type="info" :closable="false" show-icon title="配送费用随货款一次支付；到店自提始终免运费。" />
              <el-form-item>
                <el-switch v-model="form.shipping_policy!.role_specific" active-text="零售与批发分别设置" inactive-text="零售与批发统一价格" />
              </el-form-item>
              <div class="form-row-2 shipping-policy-grid">
                <el-form-item label="统一配送费（元）"><el-input v-model="form.shipping_policy!.delivery_fee" type="number" /></el-form-item>
                <el-form-item label="满额包邮门槛（元）"><el-input v-model="form.shipping_policy!.free_shipping_threshold" type="number" /></el-form-item>
              </div>
              <div v-if="form.shipping_policy!.role_specific" class="form-row-2 shipping-policy-grid">
                <div>
                  <h4>零售</h4>
                  <el-form-item label="配送费（元）"><el-input v-model="form.shipping_policy!.retail!.delivery_fee" type="number" /></el-form-item>
                  <el-form-item label="包邮门槛（元）"><el-input v-model="form.shipping_policy!.retail!.free_shipping_threshold" type="number" /></el-form-item>
                </div>
                <div>
                  <h4>批发</h4>
                  <el-form-item label="配送费（元）"><el-input v-model="form.shipping_policy!.wholesale!.delivery_fee" type="number" /></el-form-item>
                  <el-form-item label="包邮门槛（元）"><el-input v-model="form.shipping_policy!.wholesale!.free_shipping_threshold" type="number" /></el-form-item>
                </div>
              </div>
            </el-form>
          </div>
        </el-tab-pane>

        <!-- 门店资料 -->
        <el-tab-pane label="门店资料" name="store">
          <div class="tab-section">
            <div class="tab-header">
              <div><h3>门店与客服信息</h3><p>门店地址、自提说明、客服微信和二维码。</p></div>
              <el-button type="primary" :loading="savingSection === 'store'" @click="saveSection">保存本节</el-button>
            </div>
            <el-form label-position="top">
              <div class="store-grid">
                <div>
                  <h4>门店信息</h4>
                  <el-form-item label="门店名称"><el-input v-model="form.store_info!.name" /></el-form-item>
                  <el-form-item label="门店电话"><el-input v-model="form.store_info!.phone" /></el-form-item>
                  <el-form-item label="门店地址"><el-input v-model="form.store_info!.address" /></el-form-item>
                  <el-form-item label="自提说明"><el-input v-model="form.store_info!.pickup_note" /></el-form-item>
                </div>
                <div>
                  <h4>客服配置</h4>
                  <el-form-item label="客服微信号"><el-input v-model="form.customer_service!.wechat_id" /></el-form-item>
                  <el-form-item label="客服二维码">
                    <ImageUploadField v-model="form.customer_service!.wechat_qr_url" />
                  </el-form-item>
                </div>
              </div>
            </el-form>
          </div>
        </el-tab-pane>

        <!-- 通知设置 -->
        <el-tab-pane label="通知设置" name="notify">
          <div class="tab-section">
            <div class="tab-header">
              <div><h3>消息推送</h3><p>小程序订阅消息的开关、模板与字段映射。</p></div>
              <div class="tab-header-actions">
                <el-switch v-model="form.notification_settings!.enabled" active-text="总开关" />
                <el-button type="primary" :loading="savingSection === 'notify'" @click="saveSection">保存本节</el-button>
              </div>
            </div>

            <el-form label-position="top">
              <el-form-item>
                <el-switch v-model="form.notification_settings!.miniapp_subscribe!.enabled" active-text="小程序订阅推送" />
              </el-form-item>

              <div class="notify-list">
                <el-card v-for="event in form.notification_settings!.miniapp_subscribe!.events" :key="event.key" shadow="never" class="notify-card">
                  <div class="notify-head">
                    <div>
                      <strong>{{ event.label }}</strong>
                      <p class="notify-desc">{{ event.desc }}</p>
                    </div>
                    <div class="notify-head-right">
                      <el-tag :type="isNotificationEditable(event) ? 'primary' : 'info'" effect="plain" size="small">{{ isNotificationEditable(event) ? '可编辑' : '固定模板' }}</el-tag>
                      <el-switch v-model="event.enabled" />
                    </div>
                  </div>
                  <div class="form-row-2">
                    <el-form-item label="模板 ID"><el-input v-model="event.template_id" placeholder="wxXXXXXXXXXXXXXXXX" /></el-form-item>
                    <el-form-item label="跳转页面"><el-input v-model="event.page" placeholder="pages/order/list" /></el-form-item>
                  </div>
                  <template v-if="isNotificationEditable(event)">
                    <div class="form-row-3">
                      <el-form-item label="标题键"><el-input v-model="event.field_keys.title" size="small" /></el-form-item>
                      <el-form-item label="时间键"><el-input v-model="event.field_keys.time" size="small" /></el-form-item>
                      <el-form-item label="状态键"><el-input v-model="event.field_keys.status" size="small" /></el-form-item>
                      <el-form-item label="金额键"><el-input v-model="event.field_keys.amount" size="small" /></el-form-item>
                      <el-form-item label="备注键"><el-input v-model="event.field_keys.note" size="small" /></el-form-item>
                    </div>
                  </template>
                </el-card>
              </div>
            </el-form>
          </div>
        </el-tab-pane>

        <!-- 安全水印 -->
        <el-tab-pane label="安全水印" name="watermark">
          <div class="tab-section">
            <div class="tab-header">
              <div><h3>安全水印</h3><p>以错落斜铺、低透明度方式覆盖已登录用户的页面，用于追溯截图来源；客户侧与店员侧可分别控制。</p></div>
              <el-button type="primary" :loading="savingSection === 'watermark'" @click="saveSection">保存本节</el-button>
            </div>
            <el-form label-position="top" style="max-width:480px">
              <el-form-item>
                <el-switch v-model="watermark.enabled" active-text="总开关" />
              </el-form-item>
              <el-form-item v-if="watermark.enabled" label="生效范围">
                <el-switch v-model="watermark.customerEnabled" active-text="客户侧（所有已登录用户）" />
                <el-switch v-model="watermark.employeeEnabled" active-text="店员侧" style="margin-left:24px" />
              </el-form-item>
              <template v-if="watermark.enabled">
                <el-form-item :label="`透明度：${(watermark.opacityRaw / 100).toFixed(2)}`">
                  <el-slider v-model="watermark.opacityRaw" :min="2" :max="12" :step="1" />
                </el-form-item>
                <el-form-item :label="`密度：${watermark.density}`">
                  <el-slider v-model="watermark.density" :min="1" :max="10" :step="1" />
                </el-form-item>
                <el-form-item :label="`倾斜角度：${watermark.angle}°`">
                  <el-slider v-model="watermark.angle" :min="15" :max="45" :step="1" />
                </el-form-item>
              </template>
            </el-form>
          </div>
        </el-tab-pane>

        <el-tab-pane label="排版" name="layout">
          <div class="tab-section">
            <div class="tab-header">
              <div>
                <h3>配货单排版</h3>
                <p>用纯文本编辑打印内容。保存后作为后续配货单的排版模板。</p>
              </div>
              <el-button type="primary" :loading="savingSection === 'layout'" @click="saveSection">保存本节</el-button>
            </div>

            <el-alert type="info" :closable="false" show-icon title="每行对应打印内容；动态字段会在打印时替换为订单数据。暂不填写不需要的字段即可。" />
            <el-input
              v-model="form.print_layout"
              class="print-layout-editor"
              type="textarea"
              :rows="20"
              resize="vertical"
              spellcheck="false"
              placeholder="请输入配货单排版"
            />
            <div class="print-layout-fields">
              <span>可用字段</span>
              <el-tag v-for="field in printLayoutFields" :key="field" size="small" effect="plain">{{ field }}</el-tag>
            </div>
          </div>
        </el-tab-pane>

      </el-tabs>
    </el-card>

    <!-- 轮播图编辑对话框 -->
    <el-dialog v-model="modalVisible" :title="modalTitle" width="540px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="展示图片 *">
          <ImageUploadField v-model="modalData.image_url" hint="建议比例 16:9" />
          <el-input v-model="modalData.image_url" placeholder="或直接输入图片链接 (https://...)" style="margin-top:8px" />
        </el-form-item>
        <el-form-item label="轮播标题（后台标识）">
          <el-input v-model="modalData.title" placeholder="例如：本周爆款活动" />
        </el-form-item>
        <div class="form-row-2">
          <el-form-item label="点击跳转动作">
            <el-select v-model="modalData.link_type" style="width:100%">
              <el-option label="不跳转（纯展示）" value="none" />
              <el-option label="商品详情（按货号）" value="product_code" />
              <el-option label="外部链接（H5）" value="url" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="modalData.link_type !== 'none'" label="跳转目标">
            <el-select v-if="modalData.link_type === 'product_code'" v-model="modalData.link_value" style="width:100%">
              <el-option label="请选择商品" value="" />
              <el-option v-for="p in productOptions" :key="p.code" :label="p.label" :value="p.code" />
            </el-select>
            <el-input v-else v-model="modalData.link_value" placeholder="https://..." />
          </el-form-item>
        </div>
        <div class="form-row-2">
          <el-form-item label="排序权重">
            <el-input v-model.number="modalData.sort_order" type="number" />
          </el-form-item>
          <el-form-item label="展示状态">
            <el-switch v-model="modalData.is_active" active-text="展示中" inactive-text="停用" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="modalVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmModal">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AppPageHeader from '@/components/AppPageHeader.vue'
import ImageUploadField from '@/components/shared/ImageUploadField.vue'
import {
  fetchProducts,
  fetchStorefrontConfig,
  fetchStorefrontMarqueeNotices,
  updateStorefrontConfig,
  updateStorefrontMarqueeNotices,
} from '@/api/modules'
import type {
  StorefrontConfigPayload,
  StorefrontMarqueeNoticeItem,
  StorefrontNotificationEventConfig,
  StorefrontNotificationSettings,
} from '@/types/api'

const activeTab = ref('banner')
const savingSection = ref<string | null>(null)
const marqueeSaving = ref(false)
const marqueeNotices = ref<StorefrontMarqueeNoticeItem[]>([])
const modalVisible = ref(false)
const modalEditIndex = ref(-1)
const modalData = ref<{ title: string; image_url: string; link_type: string; link_value: string; sort_order: number; is_active: boolean }>(
  { title: '', image_url: '', link_type: 'none', link_value: '', sort_order: 0, is_active: true }
)
const productOptions = ref<Array<{ code: string; label: string }>>([])

const watermark = reactive({
  enabled: true,
  customerEnabled: true,
  employeeEnabled: false,
  opacityRaw: 5,
  density: 5,
  angle: 45,
})

const form = reactive<StorefrontConfigPayload>({
  home_banners: [],
  store_info: { name: '', phone: '', address: '', pickup_note: '' },
  customer_service: { wechat_id: '', wechat_qr_url: '' },
  shipping_thresholds: { retail: '99.00', wholesale: '199.00' },
  shipping_rules: { retail: { express: '8.00', linehaul: '12.00', pickup: '0.00' }, wholesale: { express: '12.00', linehaul: '18.00', pickup: '0.00' } },
  shipping_policy: { role_specific: false, delivery_fee: '8.00', free_shipping_threshold: '99.00', retail: { delivery_fee: '8.00', free_shipping_threshold: '99.00' }, wholesale: { delivery_fee: '8.00', free_shipping_threshold: '99.00' } },
  notification_settings: { enabled: true, miniapp_subscribe: { enabled: true, events: [] } },
  print_layout: '',
  updated_at: null,
})

const printLayoutFields = ['{{order_no}}', '{{recipient}}', '{{phone}}', '{{shipping_channel}}', '{{lines}}', '{{total_summary}}', '{{total_quantity}}', '{{total_amount}}', '{{customer_note}}', '{{internal_note}}', '{{wechat_id}}', '{{printed_at}}']

const activeMarqueeCount = computed(() => marqueeNotices.value.filter((n) => n.is_active).length)
const modalTitle = computed(() => (modalEditIndex.value === -1 ? '新增首页幻灯片' : '编辑首页幻灯片'))

onMounted(() => void load())

function formatLinkType(type: string) {
  if (type === 'product_code') return '商品详情（货号）'
  if (type === 'url') return '外部网页'
  return '无'
}

function normalizeLinkType(type: string) {
  if (type === 'path') return 'product_code'
  if (['product_code', 'url', 'none'].includes(type)) return type
  return 'none'
}

function normalizeImageUrl(url?: string) {
  const v = String(url || '').trim()
  return v.startsWith('blob:') ? '' : v
}

function normalizeNotificationSettings(raw?: StorefrontConfigPayload['notification_settings']): StorefrontNotificationSettings {
  const events: StorefrontNotificationEventConfig[] = Array.isArray(raw?.miniapp_subscribe?.events)
    ? raw!.miniapp_subscribe!.events.map((e): StorefrontNotificationEventConfig => ({
        key: String(e.key || '').trim(), label: String(e.label || '').trim(), desc: String(e.desc || '').trim(),
        enabled: Boolean(e.enabled ?? true), template_id: String(e.template_id || '').trim(), page: String(e.page || '').trim(),
        field_keys: { ...(e.field_keys || {}), title: String(e.field_keys?.title || ''), time: String(e.field_keys?.time || ''), status: String(e.field_keys?.status || ''), amount: String(e.field_keys?.amount || ''), note: String(e.field_keys?.note || '') },
        field_mode: e.field_mode === 'fixed' ? 'fixed' : 'editable', field_note: String(e.field_note || ''),
      }))
    : []
  return { enabled: Boolean(raw?.enabled ?? true), miniapp_subscribe: { enabled: Boolean(raw?.miniapp_subscribe?.enabled ?? true), events } }
}

function normalizeMarqueeNotice(n?: Partial<StorefrontMarqueeNoticeItem>): StorefrontMarqueeNoticeItem {
  return { id: n?.id, title: String(n?.title || ''), body: String(n?.body || ''), action_label: String(n?.action_label || ''), action_type: String(n?.action_type || 'none'), action_value: n?.action_value ? String(n.action_value) : '', is_active: Boolean(n?.is_active ?? true), sort_order: Number(n?.sort_order ?? 0), starts_at: n?.starts_at || null, ends_at: n?.ends_at || null, created_at: n?.created_at, updated_at: n?.updated_at }
}

function newMarqueeNotice(): StorefrontMarqueeNoticeItem {
  return { title: '', body: '', action_label: '去看看', action_type: 'none', action_value: '', is_active: true, sort_order: marqueeNotices.value.length + 1, starts_at: null, ends_at: null }
}

function addMarqueeNotice() { marqueeNotices.value.unshift(newMarqueeNotice()) }
function removeMarqueeNotice(idx: number) { marqueeNotices.value.splice(idx, 1) }
function moveMarqueeNotice(idx: number, dir: -1 | 1) {
  const next = idx + dir
  if (next < 0 || next >= marqueeNotices.value.length) return
  const list = [...marqueeNotices.value]; const [item] = list.splice(idx, 1); list.splice(next, 0, item)
  marqueeNotices.value = list.map((n, i) => ({ ...n, sort_order: list.length - i }))
}

function marqueeActionPlaceholder(type: string) {
  if (type === 'category') return '例如：all 或分类编号'
  if (type === 'profile') return '例如：orders / notifications'
  if (type === 'url') return '例如：/pages/search/index'
  return '不需要填写'
}

function buildMarqueePayload() {
  return { notices: marqueeNotices.value.map((n, i) => ({ ...normalizeMarqueeNotice(n), sort_order: Number(n.sort_order ?? marqueeNotices.value.length - i) })) }
}

function isNotificationEditable(event: { field_mode?: string }) { return String(event.field_mode || 'editable') !== 'fixed' }

async function load() {
  try {
    const [configRes, productRes, marqueeRes] = await Promise.all([fetchStorefrontConfig(), fetchProducts(), fetchStorefrontMarqueeNotices()])
    marqueeNotices.value = (marqueeRes.data || []).map(normalizeMarqueeNotice)
    const d = configRes.data
    form.home_banners = (d.home_banners || []).map((i) => ({ title: String(i.title || ''), image_url: normalizeImageUrl(i.image_url), link_type: normalizeLinkType(String(i.link_type || 'none')), link_value: String(i.link_value || ''), sort_order: Number(i.sort_order || 0), is_active: Boolean(i.is_active ?? true), description: String(i.description || '') }))
    form.updated_at = d.updated_at || null
    form.store_info = { name: String(d.store_info?.name || ''), phone: String(d.store_info?.phone || ''), address: String(d.store_info?.address || ''), pickup_note: String(d.store_info?.pickup_note || '') }
    form.customer_service = { wechat_id: String(d.customer_service?.wechat_id || ''), wechat_qr_url: normalizeImageUrl(d.customer_service?.wechat_qr_url) }
    form.shipping_thresholds = { retail: String(d.shipping_thresholds?.retail ?? '99.00'), wholesale: String(d.shipping_thresholds?.wholesale ?? '199.00') }
    form.shipping_rules = { retail: { express: String(d.shipping_rules?.retail?.express ?? '8.00'), linehaul: String(d.shipping_rules?.retail?.linehaul ?? '12.00'), pickup: String(d.shipping_rules?.retail?.pickup ?? '0.00') }, wholesale: { express: String(d.shipping_rules?.wholesale?.express ?? '12.00'), linehaul: String(d.shipping_rules?.wholesale?.linehaul ?? '18.00'), pickup: String(d.shipping_rules?.wholesale?.pickup ?? '0.00') } }
    form.shipping_policy = {
      role_specific: Boolean(d.shipping_policy?.role_specific), delivery_fee: String(d.shipping_policy?.delivery_fee ?? '8.00'), free_shipping_threshold: String(d.shipping_policy?.free_shipping_threshold ?? '99.00'),
      retail: { delivery_fee: String(d.shipping_policy?.retail?.delivery_fee ?? d.shipping_policy?.delivery_fee ?? '8.00'), free_shipping_threshold: String(d.shipping_policy?.retail?.free_shipping_threshold ?? d.shipping_policy?.free_shipping_threshold ?? '99.00') },
      wholesale: { delivery_fee: String(d.shipping_policy?.wholesale?.delivery_fee ?? d.shipping_policy?.delivery_fee ?? '8.00'), free_shipping_threshold: String(d.shipping_policy?.wholesale?.free_shipping_threshold ?? d.shipping_policy?.free_shipping_threshold ?? '99.00') },
    }
    form.notification_settings = normalizeNotificationSettings(d.notification_settings)
    form.print_layout = String(d.print_layout || '')
    const wm = d.watermark
    if (wm && typeof wm === 'object') {
      watermark.enabled = Boolean(wm.enabled ?? true); watermark.customerEnabled = Boolean((wm as Record<string, unknown>).customer_enabled ?? true); watermark.employeeEnabled = Boolean((wm as Record<string, unknown>).employee_enabled ?? false)
      watermark.opacityRaw = Math.max(2, Math.min(12, Math.round(Number((wm as Record<string, unknown>).opacity ?? 0.05) * 100))); watermark.density = Math.max(1, Math.min(10, Number((wm as Record<string, unknown>).density ?? 5))); watermark.angle = Math.max(15, Math.min(45, Number((wm as Record<string, unknown>).angle ?? 45)))
    }
    productOptions.value = (productRes.data || []).map((p) => ({ code: String(p.product_code), label: `${p.product_code}｜${p.name}` }))
  } catch { ElMessage.error('加载配置失败') }
}

async function saveSection() {
  savingSection.value = activeTab.value
  try {
    const payload: Partial<StorefrontConfigPayload> = {}
    if (activeTab.value === 'banner') payload.home_banners = form.home_banners
    if (activeTab.value === 'shipping') {
      payload.shipping_policy = {
        role_specific: Boolean(form.shipping_policy?.role_specific), delivery_fee: String(form.shipping_policy?.delivery_fee || '0').trim(), free_shipping_threshold: String(form.shipping_policy?.free_shipping_threshold || '0').trim(),
        retail: { delivery_fee: String(form.shipping_policy?.retail?.delivery_fee || '0').trim(), free_shipping_threshold: String(form.shipping_policy?.retail?.free_shipping_threshold || '0').trim() },
        wholesale: { delivery_fee: String(form.shipping_policy?.wholesale?.delivery_fee || '0').trim(), free_shipping_threshold: String(form.shipping_policy?.wholesale?.free_shipping_threshold || '0').trim() },
      }
    }
    if (activeTab.value === 'store') {
      payload.store_info = { name: String(form.store_info?.name || '').trim(), phone: String(form.store_info?.phone || '').trim(), address: String(form.store_info?.address || '').trim(), pickup_note: String(form.store_info?.pickup_note || '').trim() }
      payload.customer_service = { wechat_id: String(form.customer_service?.wechat_id || '').trim(), wechat_qr_url: normalizeImageUrl(form.customer_service?.wechat_qr_url) }
    }
    if (activeTab.value === 'notify') payload.notification_settings = form.notification_settings
    if (activeTab.value === 'layout') payload.print_layout = String(form.print_layout || '').trim()
    if (activeTab.value === 'watermark') payload.watermark = { enabled: watermark.enabled, customer_enabled: watermark.customerEnabled, employee_enabled: watermark.employeeEnabled, opacity: watermark.opacityRaw / 100, density: watermark.density, angle: watermark.angle }
    await updateStorefrontConfig(payload)
    ElMessage.success('已保存')
    await load()
  } catch { ElMessage.error('保存失败，请重试') }
  finally { savingSection.value = null }
}

async function saveMarqueeNotices() {
  marqueeSaving.value = true
  try { const res = await updateStorefrontMarqueeNotices(buildMarqueePayload()); marqueeNotices.value = (res.data || []).map(normalizeMarqueeNotice); ElMessage.success('公告已保存') }
  catch { ElMessage.error('公告保存失败，请重试') }
  finally { marqueeSaving.value = false }
}

function openModal(index = -1) {
  modalEditIndex.value = index
  const src = index > -1 ? form.home_banners[index] : null
  modalData.value = { title: src?.title || '', image_url: src?.image_url || '', link_type: src?.link_type || 'none', link_value: src?.link_value || '', sort_order: src?.sort_order || 0, is_active: src?.is_active ?? true }
  modalVisible.value = true
}

function confirmModal() {
  const d = modalData.value
  if (!d.image_url) { ElMessage.warning('请提供展示图片'); return }
  if (d.link_type === 'product_code' && !d.link_value) { ElMessage.warning('请选择跳转商品'); return }
  if (d.link_type === 'url' && !d.link_value) { ElMessage.warning('请填写外部链接'); return }
  const banner = { title: d.title, image_url: d.image_url, link_type: d.link_type, link_value: d.link_value, sort_order: d.sort_order, is_active: d.is_active, description: '' }
  if (modalEditIndex.value > -1) form.home_banners[modalEditIndex.value] = banner
  else form.home_banners.unshift(banner)
  modalVisible.value = false
}

function removeBanner(idx: number) { form.home_banners.splice(idx, 1) }
</script>

<style scoped>
.storefront-page { display: grid; gap: 18px; }
.main-card { border-radius: 8px; }
.main-card :deep(.el-card__body) { padding: 0; }
.storefront-tabs { min-height: 600px; }
.storefront-tabs :deep(.el-tabs__nav-wrap) { padding: 16px 0; }
.storefront-tabs :deep(.el-tabs__item) { height: 44px; font-size: 14px; }
.storefront-tabs :deep(.el-tabs__content) { padding: 0; }
.tab-section { padding: 24px; }
.tab-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 20px; }
.tab-header h3 { margin: 0; font-size: 15px; font-weight: 600; color: var(--text-primary); }
.tab-header p { margin: 6px 0 0; font-size: 13px; color: var(--text-secondary); }
.tab-header-actions { display: flex; gap: 10px; flex-shrink: 0; }
.tab-badge { margin-left: 4px; }
.section-empty { padding: 40px 0; }
.banner-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; }
.banner-card { border: 1px solid var(--border-light); border-radius: 8px; overflow: hidden; transition: opacity .18s; }
.banner-card.disabled { opacity: 0.55; }
.banner-cover { height: 110px; background: var(--bg-canvas); overflow: hidden; }
.banner-cover img { width: 100%; height: 100%; object-fit: cover; }
.empty-cover { height: 100%; display: flex; align-items: center; justify-content: center; color: var(--text-tertiary); font-size: 13px; }
.banner-info { padding: 10px 12px; }
.banner-title { font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.banner-meta { font-size: 12px; color: var(--text-tertiary); margin-bottom: 6px; }
.banner-actions { padding: 8px 12px; border-top: 1px solid var(--border-light); display: flex; gap: 8px; }
.marquee-list { display: grid; gap: 16px; }
.marquee-card { border-radius: 8px; }
.marquee-card.is-disabled { opacity: 0.6; }
.marquee-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.marquee-title { font-weight: 600; font-size: 14px; margin-left: 8px; }
.marquee-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.marquee-form :deep(.el-form-item) { margin-bottom: 12px; }
.shipping-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.fee-card :deep(.el-form-item) { margin-bottom: 12px; }
.store-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.store-grid h4 { margin: 0 0 12px; font-size: 14px; font-weight: 600; color: var(--text-primary); }
.notify-list { display: grid; gap: 16px; }
.notify-card { border-radius: 8px; }
.notify-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.notify-desc { margin: 4px 0 0; font-size: 12px; color: var(--text-tertiary); }
.notify-head-right { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.form-row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0 16px; }
.form-row-3 { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0 12px; }
.image-history-collapse { margin-top: 20px; }
.image-template-editor { display: grid; grid-template-columns: 180px minmax(280px, 1fr) auto auto; align-items: start; gap: 10px; margin-bottom: 14px; }
.image-template-list { display: grid; gap: 10px; }
.image-template-row { display: flex; justify-content: space-between; gap: 16px; padding: 10px 0; border-bottom: 1px solid var(--border-light); }
.image-template-row > div:first-child { min-width: 0; }
.image-template-row strong { color: var(--text-primary); font-size: 13px; }
.image-template-row .el-tag { margin-left: 8px; }
.image-template-row p { max-width: 720px; margin: 5px 0 0; overflow: hidden; color: var(--text-secondary); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.image-template-actions { display: flex; flex: 0 0 auto; align-items: start; gap: 6px; }
.image-history-list { display: grid; gap: 12px; }
.image-history-row { display: flex; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--border-light); }
.image-history-row img { width: 64px; height: 64px; border-radius: 6px; object-fit: cover; }
.image-history-row img { cursor: zoom-in; }
.history-preview-image { display: block; max-width: 100%; max-height: 72vh; margin: 0 auto; object-fit: contain; }
.image-history-row div { min-width: 0; }
.image-history-row strong { font-size: 13px; color: var(--text-primary); }
.image-history-row span { margin-left: 8px; color: var(--text-tertiary); font-size: 12px; }
.image-history-row p { margin: 5px 0 0; color: var(--text-secondary); font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.image-history-row em { display: block; margin-top: 4px; color: var(--color-danger); font-size: 12px; font-style: normal; }
.print-layout-editor { margin-top: 16px; }
.print-layout-editor :deep(textarea) { min-height: 400px; font-family: "Cascadia Mono", "Microsoft YaHei Mono", monospace; font-size: 13px; line-height: 1.65; }
.print-layout-fields { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 12px; color: var(--text-secondary); font-size: 12px; }
@media (max-width: 860px) { .image-template-editor { grid-template-columns: 1fr; } }
</style>
