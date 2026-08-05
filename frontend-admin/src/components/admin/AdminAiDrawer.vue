<template>
  <BaseDrawer v-model="open" title="AI 助手" width="560px">
    <div class="ai-drawer">
      <section ref="messageListRef" class="ai-message-list">
        <div v-for="message in messages" :key="message.id" class="ai-message-row" :class="message.role">
          <div class="ai-message-bubble">
            <div class="ai-message-meta">
              <strong>{{ message.role === 'user' ? '你' : 'AI' }}</strong>
              <span v-if="message.model" class="meta-tag">{{ message.model }}</span>
              <span v-if="message.disabled" class="meta-tag muted">本地摘要</span>
            </div>

            <p class="ai-message-text">{{ message.content }}</p>
          </div>
        </div>
      </section>

      <section class="ai-composer">
        <textarea
          v-model="draft"
          class="composer-input"
          rows="4"
          placeholder="直接问我，例如：今天先处理什么？"
          @keydown.enter.exact.prevent="sendDraft"
          @keydown.enter.shift.stop
        />
        <div class="composer-actions">
          <span class="composer-hint">Enter 发送，Shift + Enter 换行</span>
          <button class="btn-primary" :disabled="sending || !draft.trim()" @click="sendDraft">
            {{ sending ? '发送中...' : '发送' }}
          </button>
        </div>
      </section>
    </div>
  </BaseDrawer>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

import BaseDrawer from '@/components/BaseDrawer.vue'
import { chatAdminAssistant } from '@/api/modules'
import type { AdminAiPageContext, AdminAiToolResult } from '@/types/api'

interface AiMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  model?: string | null
  disabled?: boolean
  toolResults?: AdminAiToolResult[]
}

const open = defineModel<boolean>({ required: true })

const props = defineProps<{
  routeLabel: string
  pageContext: AdminAiPageContext
}>()

const draft = ref('')
const sending = ref(false)
const sessionId = ref<string | null>(null)
const messageSeed = ref(1)
const messageListRef = ref<HTMLElement | null>(null)
const messages = ref<AiMessage[]>([])

watch(
  () => open.value,
  (visible) => {
    if (visible && messages.value.length === 0) {
      appendAssistantMessage('我可以帮你梳理当前后台页面的待办和风险。你可以直接提问，我会按当前页面上下文给你建议。', {
        disabled: true,
      })
    }
  },
)

async function sendDraft() {
  const text = draft.value.trim()
  if (!text || sending.value) return
  draft.value = ''
  appendUserMessage(text)
  sending.value = true

  try {
    const response = await chatAdminAssistant({
      message: text,
      session_id: sessionId.value,
      page_context: props.pageContext,
    })
    sessionId.value = response.data.session_id
    appendAssistantMessage(response.data.answer, {
      model: response.data.model,
      disabled: response.data.disabled,
      toolResults: response.data.tool_results,
    })
  } catch {
    appendAssistantMessage('刚刚这条没有成功发出去，你可以再试一次。', { disabled: true })
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

function appendUserMessage(content: string) {
  messages.value.push({
    id: messageSeed.value++,
    role: 'user',
    content,
  })
}

function appendAssistantMessage(content: string, extra: Partial<Pick<AiMessage, 'model' | 'disabled' | 'toolResults'>> = {}) {
  messages.value.push({
    id: messageSeed.value++,
    role: 'assistant',
    content,
    model: extra.model,
    disabled: extra.disabled,
    toolResults: extra.toolResults,
  })
}

async function scrollToBottom() {
  await nextTick()
  const el = messageListRef.value
  if (el) {
    el.scrollTop = el.scrollHeight
  }
}
</script>

<style scoped>
.ai-drawer {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 100%;
}

.ai-message-list {
  flex: 1;
  min-height: 280px;
  max-height: 420px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-right: 2px;
}

.ai-message-row {
  display: flex;
}

.ai-message-row.user {
  justify-content: flex-end;
}

.ai-message-row.assistant {
  justify-content: flex-start;
}

.ai-message-bubble {
  max-width: 90%;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--border-light);
  background: var(--bg-surface);
  box-shadow: var(--shadow-sm);
}

.ai-message-row.user .ai-message-bubble {
  background: var(--color-primary);
  border-color: transparent;
  color: #fff;
}

.ai-message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 12px;
}

.meta-tag {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--bg-canvas);
  color: var(--text-secondary);
}

.meta-tag.muted {
  background: rgba(148, 163, 184, 0.14);
}

.ai-message-row.user .meta-tag {
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
}

.ai-message-text {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.7;
  font-size: 14px;
}

.ai-composer {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.composer-input {
  width: 100%;
  resize: vertical;
  min-height: 96px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: 12px;
  background: var(--bg-surface);
  color: var(--text-primary);
  font: inherit;
  line-height: 1.6;
}

.composer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.composer-hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

.btn-primary {
  min-width: 92px;
}
</style>
