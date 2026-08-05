export function formatDateTime(value?: string | null) {
  if (!value) {
    return '-'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function formatMoney(value?: string | number | null) {
  if (value === undefined || value === null || value === '') {
    return '-'
  }
  const numberValue = typeof value === 'string' ? Number(value) : value
  if (Number.isNaN(numberValue)) {
    return String(value)
  }
  return `¥${numberValue.toFixed(2)}`
}

export function parseTextareaList(value: string) {
  return value
    .split(/[\n,，]/g)
    .map((item) => item.trim())
    .filter(Boolean)
}
