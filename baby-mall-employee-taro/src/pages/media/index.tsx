import { useEffect, useState } from 'react'
import Taro from '@tarojs/taro'
import { Image, ScrollView, Text, Textarea, View } from '@tarojs/components'
import {
  EmployeeImageHistory,
  EmployeeImagePromptTemplate,
  createEmployeeImageAiTemplate,
  deleteEmployeeImageAiTemplate,
  fetchEmployeeImageAiHistory,
  fetchEmployeeImageAiStatus,
  fetchEmployeeImageAiTemplates,
  generateEmployeeImage,
  uploadEmployeeEvidence,
} from '../../api/employee'
import { BackButton } from '../../components/BackButton'
import { resolveMediaUrl } from '../../services/http'
import { getSafeStyle } from '../../utils/safeArea'
import { EmployeeWatermark } from '../../components/EmployeeWatermark'
import './index.scss'

const purposes = [
  ['商品主图', '以参考图中的商品为唯一主体，保持真实款式、颜色、图案、包装、文字和比例，不得臆造、替换或变形商品。生成干净、明亮、适合商品展示的主图；不得添加价格、促销文案、额外品牌标识或水印。'],
  ['朋友圈', '以参考图中的商品为唯一主体，保持真实款式、颜色、图案、包装、文字和比例，不得臆造、替换或变形商品。生成自然、整洁、有生活感的朋友圈宣传图；不得添加价格、促销文案、额外品牌标识或水印。'],
  ['群公告', '以参考图中的商品为唯一主体，保持真实款式、颜色、图案、包装、文字和比例，不得臆造、替换或变形商品。生成简洁、醒目、便于快速识别的群公告配图；不得添加价格、促销文案、额外品牌标识或水印。'],
] as const
const backgrounds = [['白底', '背景：纯净白色背景，减少多余物品。'], ['生活场景', '背景：自然生活场景，避免喧宾夺主。'], ['陈列台', '背景：干净的商品陈列台，画面整洁。']] as const
const layouts = [['方形', '构图：方形构图，商品完整居中。'], ['竖版', '构图：竖向构图，保留上下留白。'], ['横版', '构图：横向构图，商品位于视觉中心。']] as const

type Option = readonly [string, string]

function removeOptionLines(value: string, options: readonly Option[]) {
  return value.split('\n').filter((line) => !options.some(([, text]) => line === text)).join('\n').trim()
}

function addOptionLine(value: string, options: readonly Option[], next: string) {
  return [removeOptionLines(value, options), next].filter(Boolean).join('\n')
}

export default function MediaPage() {
  const [imagePaths, setImagePaths] = useState<string[]>([])
  const [prompt, setPrompt] = useState('')
  const [purpose, setPurpose] = useState<number | null>(null)
  const [background, setBackground] = useState<number | null>(null)
  const [layout, setLayout] = useState<number | null>(null)
  const [maxInputImages, setMaxInputImages] = useState(1)
  const [configured, setConfigured] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [history, setHistory] = useState<EmployeeImageHistory[]>([])
  const [templates, setTemplates] = useState<EmployeeImagePromptTemplate[]>([])
  const [savingTemplate, setSavingTemplate] = useState(false)

  const loadHistory = async () => {
    try { setHistory(await fetchEmployeeImageAiHistory()) } catch { /* ponytail: history must not block the creation tool. */ }
  }
  const loadTemplates = async () => {
    try { setTemplates(await fetchEmployeeImageAiTemplates()) } catch { /* ponytail: templates must not block the creation tool. */ }
  }

  useEffect(() => {
    fetchEmployeeImageAiStatus().then((status) => { setConfigured(status.enabled && status.configured); setMaxInputImages(status.max_input_images) }).catch(() => setConfigured(false))
    void loadHistory()
    void loadTemplates()
  }, [])

  const hasPending = history.some((item) => item.status === 'processing')
  useEffect(() => {
    if (!hasPending) return
    const timer = setInterval(() => void loadHistory(), 5000)
    return () => clearInterval(timer)
  }, [hasPending])

  const chooseImage = async () => {
    try {
      const result = await Taro.chooseImage({ count: Math.max(1, maxInputImages - imagePaths.length), sizeType: ['compressed'], sourceType: ['camera', 'album'] })
      setImagePaths((current) => [...current, ...result.tempFilePaths].slice(0, maxInputImages))
    } catch { /* ponytail: cancelling the picker needs no feedback. */ }
  }

  const selectPurpose = (index: number) => {
    if (purpose === index) {
      setPurpose(null)
      setBackground(null)
      setLayout(null)
      setPrompt((value) => removeOptionLines(value, [...purposes, ...backgrounds, ...layouts]))
      return
    }
    setPurpose(index)
    setPrompt((value) => [removeOptionLines(value, [...purposes, ...backgrounds, ...layouts]), purposes[index][1], background === null ? '' : backgrounds[background][1], layout === null ? '' : layouts[layout][1]].filter(Boolean).join('\n'))
  }

  const selectBackground = (index: number) => {
    if (purpose === null) return
    if (background === index) {
      setBackground(null)
      setPrompt((value) => removeOptionLines(value, backgrounds))
      return
    }
    setBackground(index)
    setPrompt((value) => addOptionLine(value, backgrounds, backgrounds[index][1]))
  }

  const selectLayout = (index: number) => {
    if (purpose === null) return
    if (layout === index) {
      setLayout(null)
      setPrompt((value) => removeOptionLines(value, layouts))
      return
    }
    setLayout(index)
    setPrompt((value) => addOptionLine(value, layouts, layouts[index][1]))
  }

  const applyTemplate = (template: EmployeeImagePromptTemplate) => {
    setPurpose(null)
    setBackground(null)
    setLayout(null)
    setPrompt(template.prompt)
  }

  const saveTemplate = async () => {
    if (!prompt.trim()) return Taro.showToast({ title: '请先填写提示词', icon: 'none' })
    const result = await Taro.showModal({ title: '保存模板', editable: true, placeholderText: '例如：白底日化主图' })
    const name = (result.content || '').trim()
    if (!result.confirm || !name) return
    setSavingTemplate(true)
    try {
      await createEmployeeImageAiTemplate({ name, prompt: prompt.trim() })
      await loadTemplates()
      Taro.showToast({ title: '已保存', icon: 'success' })
    } catch (error) {
      Taro.showToast({ title: error instanceof Error ? error.message.slice(0, 18) : '保存失败', icon: 'none' })
    } finally { setSavingTemplate(false) }
  }

  const removeTemplate = async (template: EmployeeImagePromptTemplate) => {
    const result = await Taro.showModal({ title: '删除模板', content: `确认删除“${template.name}”吗？` })
    if (!result.confirm) return
    try { await deleteEmployeeImageAiTemplate(template.id); await loadTemplates() } catch { Taro.showToast({ title: '删除失败', icon: 'none' }) }
  }

  const generate = async () => {
    if (!configured) return Taro.showToast({ title: '请先配置图片服务', icon: 'none' })
    if (!imagePaths.length) return Taro.showToast({ title: '请先添加参考图', icon: 'none' })
    if (!prompt.trim()) return Taro.showToast({ title: '请填写提示词或选择用途', icon: 'none' })
    setSubmitting(true)
    try {
      const uploads = await Promise.all(imagePaths.map(uploadEmployeeEvidence))
      await generateEmployeeImage({ prompt: prompt.trim(), reference_urls: uploads.map((item) => item.url) })
      setImagePaths([])
      await loadHistory()
      Taro.showToast({ title: '已提交生成', icon: 'success' })
    } catch (error) {
      Taro.showToast({ title: error instanceof Error ? error.message.slice(0, 18) : '提交失败', icon: 'none' })
    } finally { setSubmitting(false) }
  }

  const preview = (url: string) => Taro.previewImage({ current: resolveMediaUrl(url), urls: [resolveMediaUrl(url)] })
  const sharedTemplates = templates.filter((item) => item.is_shared)
  const personalTemplates = templates.filter((item) => !item.is_shared)

  return <View className="page media-page" style={getSafeStyle()}>
    <EmployeeWatermark />
    <BackButton fallbackUrl="/pages/profile/index" />
    <View className="media-header"><View><Text className="media-title">宣传图</Text><Text className="media-subtitle">上传实拍图，云端生成后可直接离开</Text></View><Text className="media-counter">{imagePaths.length}/{maxInputImages}</Text></View>
    <View className="media-source card"><View className="media-source-head"><Text>参考图片</Text><Text>最多 {maxInputImages} 张</Text></View><ScrollView className="media-strip" scrollX enhanced showScrollbar={false}><View className="media-strip-inner">
      {imagePaths.map((path, index) => <View key={path} className="media-thumb"><Image src={path} mode="aspectFill" onClick={() => preview(path)} /><Text className="media-remove" onClick={() => setImagePaths((items) => items.filter((_, i) => i !== index))}>×</Text></View>)}
      {imagePaths.length < maxInputImages && <View className="media-add" onClick={chooseImage}><Text>+</Text><Text>拍照或相册</Text></View>}
    </View></ScrollView></View>
    <View className="media-block card">
      <View className="media-block-head"><View><Text>生成设置</Text><Text>选择后写入提示词，可再次点击取消</Text></View><Text className="media-template-save" onClick={() => void saveTemplate()}>{savingTemplate ? '保存中' : '存模板'}</Text></View>
      {templates.length > 0 && <View className="media-template-block">
        <Text className="media-template-label">常用模板</Text>
        <ScrollView scrollX enhanced showScrollbar={false} className="media-template-scroll"><View className="media-template-list">
          {[...sharedTemplates, ...personalTemplates].map((item) => <View className={`media-template-chip ${item.is_shared ? 'is-shared' : ''}`} key={item.id} onClick={() => applyTemplate(item)}><Text>{item.name}</Text>{!item.is_shared && <Text className="media-template-delete" onClick={(event) => { event.stopPropagation(); void removeTemplate(item) }}>×</Text>}</View>)}
        </View></ScrollView>
      </View>}
      <View className="media-controls">
        <View><Text>用途</Text>{purposes.map(([name], index) => <Text key={name} className={purpose === index ? 'is-active' : ''} onClick={() => selectPurpose(index)}>{name}</Text>)}</View>
        <View className={purpose === null ? 'is-disabled' : ''}><Text>背景</Text>{backgrounds.map(([name], index) => <Text key={name} className={background === index ? 'is-active' : ''} onClick={() => selectBackground(index)}>{name}</Text>)}</View>
        <View className={purpose === null ? 'is-disabled' : ''}><Text>版式</Text>{layouts.map(([name], index) => <Text key={name} className={layout === index ? 'is-active' : ''} onClick={() => selectLayout(index)}>{name}</Text>)}</View>
      </View>
      <Textarea className="media-prompt" value={prompt} maxlength={1500} autoHeight placeholder="可直接写要求，或先选择用途自动填入完整提示词" onInput={(event) => setPrompt(event.detail.value)} />
      <View className={`media-submit ${submitting ? 'is-disabled' : ''}`} onClick={generate}><Text>{submitting ? '正在提交...' : '生成宣传图'}</Text></View>
    </View>
    {hasPending && <View className="media-pending"><View className="media-loader" /><Text>正在云端生成，可直接离开</Text></View>}
    <View className="media-history-head"><Text>生成记录</Text><Text onClick={() => void loadHistory()}>刷新</Text></View>
    <View className="media-history">{history.length === 0 ? <Text className="media-empty">提交后会在这里查看结果</Text> : history.map((item) => <View key={item.id} className="media-history-item"><View className={`media-history-preview ${item.status}`} onClick={() => item.result_url && preview(item.result_url)}>{item.result_url ? <Image src={resolveMediaUrl(item.result_url)} mode="aspectFill" /> : item.status === 'processing' ? <View className="media-loader" /> : <Text>!</Text>}</View><View className="media-history-copy"><View><Text>{item.status === 'succeeded' ? '已生成' : item.status === 'failed' ? '生成失败' : '处理中'}</Text><Text>{item.created_at?.slice(5, 16).replace('T', ' ') || ''}</Text></View><Text>{item.prompt}</Text>{item.error_message && <Text className="media-history-error">{item.error_message}</Text>}</View></View>)}</View>
  </View>
}
