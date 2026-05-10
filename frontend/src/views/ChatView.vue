<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { marked } from 'marked'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
}

const messages = ref<Message[]>([])
const inputText = ref('')
const streaming = ref(false)
const streamingContent = ref('')
const webSearchEnabled = ref(false)
const messagesContainer = ref<HTMLDivElement>()

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

function renderMarkdown(text: string): string {
  return marked(text) as string
}

function renderAnswer(text: string): string {
  // Replace {VIEW_PROJECT:project_name} with clickable links
  const replaced = text.replace(
    /\{VIEW_PROJECT:([^}]+)\}/g,
    '<a href="/radar?project=$1" style="color: #409eff; cursor: pointer;" onclick="event.preventDefault(); window.__navigateToProject(\'$1\')">$1</a>'
  )
  return marked(replaced) as string
}

// Expose navigation function globally for onclick handlers
;(window as Record<string, unknown>).__navigateToProject = (name: string) => {
  router.push({ path: '/radar', query: { project: name } })
}

async function sendMessage() {
  if (!inputText.value.trim() || streaming.value) return

  const text = inputText.value.trim()
  inputText.value = ''

  messages.value.push({ role: 'user', content: text })
  scrollToBottom()

  streaming.value = true
  streamingContent.value = ''

  try {
    const token = auth.token
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        message: text,
        enable_web_search: webSearchEnabled.value,
      }),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let sources: string[] = []

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // Parse SSE events
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const payload = JSON.parse(line.slice(6))
            if (payload.content) {
              streamingContent.value += payload.content
              scrollToBottom()
            }
            if (payload.sources) {
              sources = payload.sources
            }
          } catch {
            // skip malformed data
          }
        }
      }
    }

    messages.value.push({
      role: 'assistant',
      content: streamingContent.value,
      sources,
    })
  } catch (e) {
    messages.value.push({
      role: 'assistant',
      content: `Request failed: ${e}`,
    })
  } finally {
    streaming.value = false
    streamingContent.value = ''
    scrollToBottom()
  }
}
</script>

<template>
  <div style="display: flex; flex-direction: column; height: calc(100vh - 60px);">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
      <div>
        <h2 style="margin: 0;">Chat</h2>
        <p style="color: #999; margin: 4px 0 0;">Query GitHub projects via knowledge graph</p>
      </div>
      <el-switch v-model="webSearchEnabled" active-text="Web Search" inactive-text="" />
    </div>

    <!-- Messages -->
    <div ref="messagesContainer" style="flex: 1; overflow-y: auto; padding: 12px; background: #fff; border-radius: 8px; border: 1px solid #e6e6e6;">
      <div v-for="(msg, idx) in messages" :key="idx" style="margin-bottom: 16px;">
        <div :style="{ textAlign: msg.role === 'user' ? 'right' : 'left' }">
          <div :style="{
            display: 'inline-block',
            maxWidth: '80%',
            padding: '8px 12px',
            borderRadius: '8px',
            background: msg.role === 'user' ? '#409eff' : '#f5f7fa',
            color: msg.role === 'user' ? '#fff' : '#333',
          }">
            <div v-if="msg.role === 'user'">{{ msg.content }}</div>
            <div v-else v-html="renderAnswer(msg.content)" style="text-align: left;" />
          </div>
          <div v-if="msg.sources?.length" style="font-size: 12px; color: #999; margin-top: 4px;">
            Sources: {{ msg.sources.join(', ') }}
          </div>
        </div>
      </div>

      <!-- Streaming content -->
      <div v-if="streaming" style="margin-bottom: 16px;">
        <div style="display: inline-block; max-width: 80%; padding: 8px 12px; border-radius: 8px; background: #f5f7fa;">
          <div v-html="renderMarkdown(streamingContent)" />
          <el-icon class="is-loading" style="margin-top: 4px;"><Loading /></el-icon>
        </div>
      </div>

      <el-empty v-if="messages.length === 0 && !streaming" description="Ask about GitHub projects..." />
    </div>

    <!-- Input -->
    <div style="margin-top: 12px; display: flex; gap: 8px;">
      <el-input v-model="inputText" placeholder="Ask about GitHub projects..." @keyup.enter="sendMessage" :disabled="streaming" />
      <el-button type="primary" @click="sendMessage" :loading="streaming" :disabled="!inputText.trim()">
        Send
      </el-button>
    </div>
  </div>
</template>
