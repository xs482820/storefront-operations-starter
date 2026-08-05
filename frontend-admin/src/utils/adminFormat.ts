export function formatDateTime(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function formatDateLabel(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
  }).format(date)
}

export function formatCurrency(value?: string | number | null) {
  const amount = Number(value ?? 0)
  if (Number.isNaN(amount)) return '¥0.00'
  return `¥${amount.toFixed(2)}`
}

export function toText(value?: string | number | null, fallback = '-') {
  if (value === undefined || value === null || value === '') return fallback
  return String(value)
}

export function makeInitial(text?: string | null) {
  if (!text) return '?'
  return text.slice(0, 1).toUpperCase()
}
