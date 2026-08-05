import { ref } from 'vue'

export type AppMessageType = 'success' | 'error' | 'warning' | 'info'

export interface AppMessageItem {
  id: number
  type: AppMessageType
  text: string
}

const itemsRef = ref<AppMessageItem[]>([])
let idSeed = 1

function normalizeText(input: unknown): string {
  if (typeof input === 'string') return input.trim() || '操作已完成'
  if (input == null) return '操作已完成'
  return String(input)
}

function remove(id: number) {
  itemsRef.value = itemsRef.value.filter((item) => item.id !== id)
}

function push(type: AppMessageType, message: unknown, duration = 1800) {
  const text = normalizeText(message)
  const id = idSeed++
  const next = [...itemsRef.value, { id, type, text }]
  itemsRef.value = next.slice(-4)
  window.setTimeout(() => remove(id), duration)
}

export function useAppMessages() {
  return {
    items: itemsRef,
    remove,
  }
}

export const ElMessage = {
  success(message: unknown) {
    push('success', message)
  },
  error(message: unknown) {
    push('error', message, 2200)
  },
  warning(message: unknown) {
    push('warning', message, 2000)
  },
  info(message: unknown) {
    push('info', message, 1600)
  },
}

