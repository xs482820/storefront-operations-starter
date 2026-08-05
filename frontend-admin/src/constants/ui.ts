export const roleTextMap: Record<string, string> = {
  admin: '管理员',
  employee: '店员',
  retail: '零售',
  wholesale: '批发',
}

export const orderStatusTextMap: Record<string, string> = {
  pending_payment: '待支付',
  awaiting_shipment: '待发货',
  shipped: '已发货',
  completed: '已完成',
  canceled: '已取消',
}

export const paymentMethodTextMap: Record<string, string> = {
  wechat_pay: '微信支付',
  offline_transfer: '线下转账',
}

export const shippingModeTextMap: Record<string, string> = {
  express: '正规快递',
  offline: '线下托运',
}

export const aftersaleReasonTextMap: Record<string, string> = {
  quality_issue: '质量问题',
  wrong_item: '发错货',
  damaged: '货物破损',
  size_problem: '规格问题',
  other: '其他',
}
