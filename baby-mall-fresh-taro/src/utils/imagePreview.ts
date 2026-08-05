import Taro from '@tarojs/taro'

export function previewImages(urls: Array<string | null | undefined>, current?: string) {
  const list = urls.filter((item): item is string => Boolean(item))
  if (list.length === 0) return
  Taro.previewImage({
    urls: list,
    current: current && list.includes(current) ? current : list[0],
  })
}
