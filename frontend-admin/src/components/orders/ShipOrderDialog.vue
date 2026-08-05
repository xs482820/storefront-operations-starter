<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import { ElMessage } from '@/utils/message'

import ImageUploadField from '@/components/shared/ImageUploadField.vue'
import { shipOrder } from '../../api/modules'
import type { WorkbenchOrderItem } from '../../types/api'

const props = defineProps<{
  modelValue: boolean
  order: WorkbenchOrderItem | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  success: []
}>()

const loading = defineModel<boolean>('loading', { default: false })

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const form = reactive({
  shipping_mode: 'express' as 'express' | 'offline',
  shipping_proof_url: '',
  logistics_company: '',
  tracking_no: '',
  note: '',
})

watch(
  () => props.order,
  () => {
    Object.assign(form, {
      shipping_mode: 'express',
      shipping_proof_url: '',
      logistics_company: '',
      tracking_no: '',
      note: '',
    })
  },
)

async function submit() {
  if (!props.order) {
    return
  }
  if (!form.shipping_proof_url.trim()) {
    ElMessage.warning('请先上传或填写发货凭证图')
    return
  }

  loading.value = true
  try {
    await shipOrder(props.order.id, {
      shipping_mode: form.shipping_mode,
      shipping_proof_url: form.shipping_proof_url,
      logistics_company: form.shipping_mode === 'express' ? form.logistics_company || undefined : undefined,
      tracking_no: form.shipping_mode === 'express' ? form.tracking_no || undefined : undefined,
      note: form.note || undefined,
    })
    ElMessage.success('订单已发货')
    emit('success')
    visible.value = false
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="发货处理" width="680px">
    <div v-if="order" class="order-hint">
      <strong>{{ order.order_no }}</strong>
      <span>{{ order.shipping_recipient || '未填写收件人' }} / {{ order.shipping_phone || '未填写电话' }}</span>
    </div>

    <el-form label-position="top">
      <el-form-item label="发货模式">
        <el-radio-group v-model="form.shipping_mode">
          <el-radio-button label="express">正规快递</el-radio-button>
          <el-radio-button label="offline">线下托运</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="发货凭证图">
        <ImageUploadField v-model="form.shipping_proof_url" hint="支持拖拽、粘贴、选择图片，也可直接粘贴链接" />
      </el-form-item>

      <template v-if="form.shipping_mode === 'express'">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="物流公司">
              <el-input v-model="form.logistics_company" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="快递单号">
              <el-input v-model="form.tracking_no" />
            </el-form-item>
          </el-col>
        </el-row>
      </template>

      <el-form-item label="备注">
        <el-input v-model="form.note" type="textarea" :rows="3" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="submit">确认发货</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.order-hint {
  margin-bottom: 18px;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(219, 236, 255, 0.7);
  color: var(--text-soft);
}

.order-hint strong {
  margin-right: 10px;
  color: var(--text-main);
}
</style>
