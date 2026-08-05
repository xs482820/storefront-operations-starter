<template>
  <div class="ai-workspace">
    <AppPageHeader title="图片工作台" description="管理店员使用的商品宣传图服务、提示词模板和生成记录。" />

    <el-alert type="info" :closable="false" show-icon title="连接测试不会发起生图，也不会产生图片生成费用。" />

    <div class="workspace-grid">
      <el-card shadow="never">
        <template #header><div class="card-title"><span>图片服务</span><el-tag :type="serviceEnabled ? 'success' : 'info'">{{ serviceEnabled ? '已启用' : '未启用' }}</el-tag></div></template>
        <el-form label-position="top">
          <el-form-item><el-switch v-model="form.enabled" active-text="允许店员使用图片工具" /></el-form-item>
          <el-form-item label="接口地址"><el-input v-model="form.base_url" autocomplete="off" placeholder="https://api.example.com/v1" /></el-form-item>
          <el-form-item label="模型名称"><el-input v-model="form.model" autocomplete="off" placeholder="例如 gpt-image-1" /></el-form-item>
          <el-form-item :label="form.api_key_set ? '接口密钥（已配置）' : '接口密钥'"><el-input v-model="form.api_key" type="password" show-password autocomplete="new-password" placeholder="留空保存，不会覆盖已有密钥" /></el-form-item>
          <div class="form-split">
            <el-form-item label="最长等待（秒）"><el-input-number v-model="form.timeout_seconds" :min="15" :max="180" controls-position="right" /></el-form-item>
            <el-form-item label="参考图上限"><el-input-number v-model="form.max_input_images" :min="1" :max="5" controls-position="right" /></el-form-item>
          </div>
          <div class="service-actions"><el-button type="primary" :loading="saving" @click="save">保存配置</el-button><el-button :loading="testing" @click="testConnection">连接测试</el-button></div>
        </el-form>
        <div v-if="testResult" :class="['test-result', testResult.ok ? 'is-ok' : 'is-muted']">{{ testResult.message }}</div>
      </el-card>

      <el-card shadow="never">
        <template #header><div class="card-title"><span>共享提示词模板</span><el-button link type="primary" @click="resetDraft">新建</el-button></div></template>
        <div class="template-editor">
          <el-input v-model="draft.name" maxlength="64" placeholder="模板名称" />
          <el-input v-model="draft.prompt" type="textarea" :rows="3" maxlength="1500" show-word-limit placeholder="完整提示词" />
          <div><el-button type="primary" :disabled="!draft.name.trim() || !draft.prompt.trim()" @click="saveTemplate">{{ draft.id ? '保存修改' : '添加共享模板' }}</el-button><el-button v-if="draft.id" @click="resetDraft">取消</el-button></div>
        </div>
        <el-empty v-if="!templates.length" description="暂无共享模板" :image-size="54" />
        <div v-else class="template-list">
          <div v-for="item in templates" :key="item.id" class="template-row">
            <div><strong>{{ item.name }}</strong><p>{{ item.prompt }}</p><span>{{ item.is_shared ? '共享模板' : `店员模板 · ${item.username || '-'}` }}</span></div>
            <div><el-button link type="primary" @click="editTemplate(item)">编辑</el-button><el-popconfirm title="确认删除这个模板？" @confirm="removeTemplate(item.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm></div>
          </div>
        </div>
      </el-card>
    </div>

    <el-card shadow="never" class="history-card">
      <template #header><div class="card-title"><span>生成记录</span><el-button :icon="Refresh" :loading="loadingHistory" @click="loadHistory">刷新</el-button></div></template>
      <el-table v-loading="loadingHistory" :data="history" row-key="id">
        <el-table-column label="结果" width="96"><template #default="{ row }"><el-image v-if="row.result_url" class="result-image" :src="row.result_url" :preview-src-list="[row.result_url]" preview-teleported fit="cover" /><span v-else class="result-placeholder">{{ statusLabel(row.status) }}</span></template></el-table-column>
        <el-table-column label="状态" width="112"><template #default="{ row }"><el-tag :type="row.status === 'succeeded' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'">{{ statusLabel(row.status) }}</el-tag></template></el-table-column>
        <el-table-column label="提交人" min-width="110"><template #default="{ row }">{{ row.username || '店员' }}</template></el-table-column>
        <el-table-column label="提示词" min-width="300" show-overflow-tooltip><template #default="{ row }">{{ row.prompt }}</template></el-table-column>
        <el-table-column label="时间" width="170"><template #default="{ row }">{{ formatDate(row.created_at) }}</template></el-table-column>
        <el-table-column label="失败原因" min-width="210"><template #default="{ row }"><span class="error-text">{{ row.error_message || '-' }}</span></template></el-table-column>
        <template #empty><el-empty description="暂无图片生成记录" :image-size="64" /></template>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import AppPageHeader from '@/components/AppPageHeader.vue'
import { createImageAiTemplate, deleteImageAiTemplate, fetchImageAiHistory, fetchImageAiTemplates, fetchStorefrontConfig, testImageAiConnection, updateImageAiTemplate, updateStorefrontConfig } from '@/api/modules'
import type { ImageAiHistoryItem, ImagePromptTemplateItem } from '@/types/api'

const saving = ref(false)
const testing = ref(false)
const loadingHistory = ref(false)
const history = ref<ImageAiHistoryItem[]>([])
const templates = ref<ImagePromptTemplateItem[]>([])
const testResult = ref<{ ok: boolean; message: string } | null>(null)
const form = reactive({ enabled: false, provider: 'openai_compatible' as const, base_url: '', model: '', api_key: '', api_key_set: false, timeout_seconds: 180, max_input_images: 1 })
const draft = reactive<{ id?: number; name: string; prompt: string }>({ name: '', prompt: '' })
const serviceEnabled = computed(() => form.enabled && Boolean(form.base_url && form.model && (form.api_key_set || form.api_key)))

onMounted(() => { void loadAll() })

async function loadAll() {
  try {
    const [config, templateResponse] = await Promise.all([fetchStorefrontConfig(), fetchImageAiTemplates()])
    const settings = config.data.image_ai_settings
    Object.assign(form, { enabled: Boolean(settings?.enabled), provider: 'openai_compatible', base_url: String(settings?.base_url || ''), model: String(settings?.model || ''), api_key: '', api_key_set: Boolean(settings?.api_key_set), timeout_seconds: Number(settings?.timeout_seconds || 180), max_input_images: Number(settings?.max_input_images || 1) })
    templates.value = templateResponse.data
    await loadHistory()
  } catch { ElMessage.error('图片工作台加载失败') }
}

async function save() {
  saving.value = true
  try {
    await updateStorefrontConfig({ image_ai_settings: { ...form, api_key: form.api_key.trim() } })
    form.api_key = ''
    form.api_key_set = true
    ElMessage.success('图片服务配置已保存')
  } catch { ElMessage.error('保存失败，请检查配置') } finally { saving.value = false }
}

async function testConnection() {
  testing.value = true
  testResult.value = null
  try {
    const response = await testImageAiConnection()
    testResult.value = response.data
    ElMessage[response.data.ok ? 'success' : 'warning'](response.data.message)
  } catch (error: any) {
    const message = error?.response?.data?.detail || '连接测试失败'
    testResult.value = { ok: false, message }
    ElMessage.error(message)
  } finally { testing.value = false }
}

async function loadHistory() {
  loadingHistory.value = true
  try { history.value = (await fetchImageAiHistory()).data } catch { ElMessage.error('生成记录加载失败') } finally { loadingHistory.value = false }
}

function resetDraft() { Object.assign(draft, { id: undefined, name: '', prompt: '' }) }
function editTemplate(item: ImagePromptTemplateItem) { Object.assign(draft, { id: item.id, name: item.name, prompt: item.prompt }) }
async function saveTemplate() {
  try {
    if (draft.id) await updateImageAiTemplate(draft.id, { name: draft.name.trim(), prompt: draft.prompt.trim() })
    else await createImageAiTemplate({ name: draft.name.trim(), prompt: draft.prompt.trim() })
    templates.value = (await fetchImageAiTemplates()).data
    resetDraft()
    ElMessage.success('模板已保存')
  } catch { ElMessage.error('模板保存失败') }
}
async function removeTemplate(id: number) { try { await deleteImageAiTemplate(id); templates.value = templates.value.filter((item) => item.id !== id); ElMessage.success('模板已删除') } catch { ElMessage.error('模板删除失败') } }
function statusLabel(status: string) { return ({ succeeded: '已生成', failed: '失败', processing: '处理中' } as Record<string, string>)[status] || status }
function formatDate(value?: string | null) { return value ? value.replace('T', ' ').slice(0, 16) : '-' }
</script>

<style scoped>
.ai-workspace { display: grid; gap: 18px; }
.workspace-grid { display: grid; grid-template-columns: minmax(320px, .9fr) minmax(420px, 1.1fr); gap: 18px; }
.card-title, .service-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.form-split { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.service-actions { justify-content: flex-start; margin-top: 10px; }
.test-result { margin-top: 16px; padding: 10px 12px; border-radius: 5px; font-size: 13px; line-height: 1.5; }
.test-result.is-ok { color: var(--color-success); background: #edf5f0; }
.test-result.is-muted { color: var(--text-secondary); background: var(--bg-canvas); }
.template-editor { display: grid; gap: 10px; margin-bottom: 14px; }
.template-list { display: grid; gap: 8px; max-height: 340px; overflow-y: auto; }
.template-row { display: flex; justify-content: space-between; gap: 16px; padding: 11px 0; border-top: 1px solid var(--border-light); }
.template-row strong { color: var(--text-primary); font-size: 14px; }
.template-row p { margin: 5px 0; color: var(--text-secondary); font-size: 13px; line-height: 1.5; white-space: pre-wrap; }
.template-row span { color: var(--text-tertiary); font-size: 12px; }
.history-card :deep(.el-card__body) { padding-top: 6px; }
.result-image { width: 58px; height: 58px; border-radius: 5px; cursor: pointer; }
.result-placeholder { color: var(--text-tertiary); font-size: 12px; }
.error-text { color: var(--color-danger); font-size: 12px; }
@media (max-width: 980px) { .workspace-grid { grid-template-columns: 1fr; } }
</style>
