import Taro from '@tarojs/taro'
import { fetchStorefrontConfig } from '../api/catalog'

type SubscribeEvent = {
  key?: string
  label?: string
  desc?: string
  enabled?: boolean
  template_id?: string
}

const SUBSCRIBE_ENABLED_KEY = 'baby_mall_fresh_subscribe_enabled'

export function isSubscribeEnabled() {
  const value = Taro.getStorageSync(SUBSCRIBE_ENABLED_KEY)
  return value === '' || value === undefined ? true : value === true
}

export function setSubscribeEnabled(enabled: boolean) {
  Taro.setStorageSync(SUBSCRIBE_ENABLED_KEY, enabled)
}

export type MiniappSubscribeEvent = {
  key: string
  label: string
  desc: string
  templateId: string
}

export type SubscribePermissionResult = {
  acceptedEventKeys: string[]
  rejectedEventKeys: string[]
}

function getEnabledEvents(config: unknown): MiniappSubscribeEvent[] {
  const root = config as {
    notification_settings?: {
      enabled?: boolean
      miniapp_subscribe?: {
        enabled?: boolean
        events?: SubscribeEvent[]
      }
    }
  }
  const settings = root.notification_settings
  const miniapp = settings?.miniapp_subscribe
  if (!settings?.enabled || !miniapp?.enabled || !Array.isArray(miniapp.events)) return []
  return miniapp.events
    .filter((event) => event.enabled && event.key && event.template_id)
    .map((event) => ({
      key: String(event.key),
      label: String(event.label || event.key),
      desc: String(event.desc || ''),
      templateId: String(event.template_id).trim(),
    }))
    .filter((event) => event.key && event.templateId)
}

export async function fetchMiniappSubscribeEvents() {
  return getEnabledEvents(await fetchStorefrontConfig())
}

function eventTemplateIds(config: unknown, eventKeys: string[]) {
  return getEnabledEvents(config)
    .filter((event) => eventKeys.includes(event.key))
    .map((event) => event.templateId)
}

export async function requestOrderSubscribeMessages(eventKeys = ['order_created', 'order_shipped', 'order_completed']): Promise<SubscribePermissionResult> {
  if (!isSubscribeEnabled()) return { acceptedEventKeys: [], rejectedEventKeys: eventKeys }
  try {
    const config = await fetchStorefrontConfig()
    const events = getEnabledEvents(config).filter((event) => eventKeys.includes(event.key))
    const acceptedEventKeys: string[] = []
    const rejectedEventKeys: string[] = []

    // ponytail: WeChat accepts at most three template IDs per request; preserve the event-to-template mapping.
    for (let index = 0; index < events.length; index += 3) {
      const batch = events.slice(index, index + 3)
      try {
        const result = await Taro.requestSubscribeMessage({ tmplIds: batch.map((event) => event.templateId) } as unknown as Taro.requestSubscribeMessage.Option) as unknown as Record<string, string>
        batch.forEach((event) => (result[event.templateId] === 'accept' ? acceptedEventKeys : rejectedEventKeys).push(event.key))
      } catch {
        rejectedEventKeys.push(...batch.map((event) => event.key))
      }
    }
    return { acceptedEventKeys, rejectedEventKeys }
  } catch {
    return { acceptedEventKeys: [], rejectedEventKeys: eventKeys }
  }
}
