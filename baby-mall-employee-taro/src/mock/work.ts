export type WorkStatus = '待收款' | '待核货' | '待发货' | '已发货' | '已完成' | '售后中'

export const workStats = [
  { label: '待收款', value: 3, tone: 'warning' },
  { label: '待核货', value: 8, tone: 'brand' },
  { label: '待发货', value: 6, tone: 'info' },
  { label: '售后待处理', value: 2, tone: 'danger' },
]

export const workOrders: Array<{
  id: string
  customer: string
  phone: string
  status: WorkStatus
  amount: number
  items: string
  createdAt: string
}> = [
  { id: 'DD20260705001', customer: '李女士', phone: '138****2601', status: '待核货', amount: 426, items: '云柔纸尿裤 L 码等 4 件', createdAt: '09:24' },
  { id: 'DD20260705002', customer: '周老板', phone: '186****9155', status: '待发货', amount: 1820, items: '奶瓶礼盒 12 套，湿巾 8 箱', createdAt: '10:18' },
  { id: 'DD20260705003', customer: '陈女士', phone: '159****3719', status: '待收款', amount: 219, items: '新生儿包被 1 件', createdAt: '11:02' },
  { id: 'DD20260704021', customer: '王先生', phone: '177****4200', status: '售后中', amount: 98, items: '安抚巾 2 件', createdAt: '昨日' },
]

export const pickItems = [
  { name: '云柔纸尿裤', spec: 'L 码 / 48 片', required: 2, checked: 1 },
  { name: '婴儿湿巾', spec: '80 抽 / 12 包', required: 1, checked: 1 },
  { name: '恒温奶瓶', spec: '240ml / 米白', required: 1, checked: 0 },
]

export const aftersaleItems = [
  { id: 'SH20260705001', customer: '王先生', reason: '规格拍错', status: '待处理', amount: 98 },
  { id: 'SH20260704005', customer: '赵女士', reason: '运输破损', status: '处理中', amount: 168 },
]
