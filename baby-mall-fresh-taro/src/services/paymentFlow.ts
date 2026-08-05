import Taro from '@tarojs/taro'
import { fetchOrder } from '../api/order'
import { createCustomerWechatPay, syncWechatPayment } from '../api/payment'
import { adaptCustomerOrder } from '../domain/adapters'
import { type Order } from '../store/useCommerce'

export type WechatPaymentFlowResult =
  | { status: 'paid'; order: Order; message: string }
  | { status: 'pending_confirm'; message: string }
  | { status: 'canceled'; message: string }
  | { status: 'failed'; message: string }

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error || '')
}

function isPaymentCanceled(error: unknown) {
  const message = errorMessage(error).toLowerCase()
  return message.includes('cancel') || message.includes('fail cancel')
}

export async function runWechatPaymentFlow(orderId: number | string): Promise<WechatPaymentFlowResult> {
  try {
    const payment = await createCustomerWechatPay(orderId)
    if (!payment.jsapi_params) {
      return {
        status: 'pending_confirm',
        message: payment.message?.includes('mock')
          ? '当前是微信支付模拟模式，未调起真实扣款。订单仍保留待支付。'
          : '后端未返回微信支付参数，暂不能调起真实支付。',
      }
    }

    try {
      await Taro.requestPayment(payment.jsapi_params as unknown as Taro.requestPayment.Option)
    } catch (error) {
      if (isPaymentCanceled(error)) return { status: 'canceled', message: '支付已取消，订单已保留' }
      return { status: 'failed', message: errorMessage(error) || '微信支付未完成' }
    }

    try {
      const synced = await syncWechatPayment(orderId)
      if (synced.status !== 'paid') {
        return { status: 'pending_confirm', message: '微信支付尚未确认扣款成功，请稍后刷新订单' }
      }
      const latest = adaptCustomerOrder(await fetchOrder(orderId))
      return { status: 'paid', order: latest, message: '支付状态已更新' }
    } catch {
      return { status: 'pending_confirm', message: '支付结果确认中，请稍后刷新订单' }
    }
  } catch (error) {
    return { status: 'failed', message: errorMessage(error) || '支付发起失败' }
  }
}
