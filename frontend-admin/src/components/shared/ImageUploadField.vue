<template>
  <div class="image-upload-field">
    <div v-if="previewUrl" class="preview-wrap">
      <img class="preview-image" :src="previewUrl" alt="图片预览" />
      <button type="button" class="clear-btn" @click="clearValue">×</button>
    </div>

    <div
      v-else
      class="empty-upload"
      @click="triggerFileInput"
      @dragover.prevent
      @drop.prevent="handleDrop"
      @paste="handlePaste"
      tabindex="0"
    >
      <span class="upload-icon">＋</span>
      <span class="upload-text">点击 / 拖拽 / 粘贴图片</span>
    </div>

    <div class="upload-actions">
      <button type="button" class="btn-outline" @click="triggerFileInput">选择图片</button>
      <input
        ref="inputRef"
        class="hidden-file-input"
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        @change="handleFileChange"
      />
      <input
        :value="modelValue"
        type="text"
        class="url-input"
        placeholder="或粘贴图片链接"
        @input="handleTextInput"
      />
    </div>

    <p v-if="hint" class="hint-text">{{ hint }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from '@/utils/message'
import { uploadProductImage } from '@/api/modules'

const props = defineProps<{
  modelValue?: string
  hint?: string
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
}>()

const inputRef = ref<HTMLInputElement | null>(null)
const previewUrl = computed(() => (props.modelValue || '').trim())

function triggerFileInput() {
  inputRef.value?.click()
}

function clearValue() {
  emit('update:modelValue', '')
}

function handleTextInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:modelValue', target.value.trim())
}

async function uploadFile(file: File) {
  if (!file) return
  try {
    const response = await uploadProductImage(file)
    emit('update:modelValue', response.data.url)
    ElMessage.success('图片上传成功')
  } catch {
    ElMessage.error('图片上传失败')
  }
}

async function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) await uploadFile(file)
  target.value = ''
}

async function handleDrop(event: DragEvent) {
  const file = Array.from(event.dataTransfer?.files || []).find((item) => item.type.startsWith('image/'))
  if (file) await uploadFile(file)
}

async function handlePaste(event: ClipboardEvent) {
  const file = Array.from(event.clipboardData?.files || []).find((item) => item.type.startsWith('image/'))
  if (file) await uploadFile(file)
}
</script>

<style scoped>
.image-upload-field {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.preview-wrap {
  position: relative;
  width: 100%;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: var(--bg-canvas);
}

.preview-image {
  display: block;
  width: 100%;
  max-height: 220px;
  object-fit: cover;
}

.clear-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 50%;
  background: rgba(17, 24, 39, 0.72);
  color: #fff;
  cursor: pointer;
}

.empty-upload {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 8px;
  min-height: 140px;
  border: 1px dashed var(--border-dark);
  border-radius: var(--radius-md);
  background: var(--bg-canvas);
  color: var(--text-tertiary);
  cursor: pointer;
  outline: none;
  transition: border-color 0.2s, background-color 0.2s;
}

.empty-upload:hover,
.empty-upload:focus {
  border-color: var(--color-primary);
  background: var(--bg-highlight);
}

.upload-icon {
  font-size: 28px;
  line-height: 1;
}

.upload-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}

.url-input {
  flex: 1 1 280px;
  min-width: 220px;
  padding: 10px 12px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-primary);
  box-sizing: border-box;
}

.btn-outline {
  padding: 8px 14px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
}

.hidden-file-input {
  display: none;
}

.hint-text {
  margin: 0;
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>
