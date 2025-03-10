<!-- src/components/chat/ChatView.vue -->
<template>
  <div class="relative h-full w-full">

    <!-- If no conversation => placeholder -->
    <div v-if="!conversationId" class="absolute inset-0 flex items-center justify-center text-gray-400 bg-white/70">
      <p>No conversation selected. Create or pick one in the sidebar.</p>
    </div>

    <!-- Scrollable messages area (top-> bottom minus input bar) -->
    <div
      ref="messagesContainer"
      class="absolute top-0 left-0 right-0 bottom-[90px] overflow-y-auto px-4 py-4 max-w-4xl mx-auto"
    >
      <!-- Each message -->
      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        class="mb-4"
      >
        <div
          :class="[
            'flex items-start',
            msg.role === 'user' ? 'justify-end' : 'justify-start'
          ]"
        >
          <!-- Avatar -->
          <div v-if="msg.role === 'assistant'" class="mr-2 flex-shrink-0">
            <img
              src="https://cdn-icons-png.flaticon.com/512/4712/4712139.png"
              alt="AI Avatar"
              class="w-8 h-8 rounded-full"
            />
          </div>
          <div v-else class="ml-2 flex-shrink-0">
            <img
              src="https://cdn-icons-png.flaticon.com/512/847/847969.png"
              alt="User Avatar"
              class="w-8 h-8 rounded-full"
            />
          </div>

          <!-- Message bubble -->
          <div v-if="msg.typing" class="bg-gray-100 text-gray-700 px-4 py-2 rounded-xl text-sm max-w-[70%]">
            <div class="flex items-center space-x-1">
              <div class="loader-dots"></div>
              <span class="text-xs text-gray-400">Thinking...</span>
            </div>
          </div>
          <div
            v-else
            class="px-4 py-2 rounded-xl text-sm max-w-[70%]"
            :class="msg.role === 'user'
              ? 'bg-primary-100 text-gray-800'
              : 'bg-gray-100 text-gray-800'"
          >
            <!-- Use 'prose' for nice markdown formatting -->
            <div
              class="prose prose-sm break-words"
              v-html="msg.formattedContent"
            ></div>
          </div>
        </div>
      </div>

      <!-- If assistant is thinking => spinner row -->
      <div
        v-if="assistantThinking"
        class="flex items-center justify-center py-2 text-sm text-gray-500"
      >
        <svg class="animate-spin h-5 w-5 mr-2 text-gray-400" viewBox="0 0 24 24">
          <circle
            class="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            stroke-width="4"
            fill="none"
          ></circle>
          <path
            class="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8v8H4z"
          ></path>
        </svg>
        Assistant is thinking...
      </div>
    </div>

    <!-- Input bar pinned at bottom -->
    <div
      class="absolute bottom-0 left-0 right-0 border-t border-gray-200 p-4 bg-white"
      style="height: 90px;"
    >
      <form
        @submit.prevent="sendMessage"
        class="flex space-x-2 w-full max-w-4xl mx-auto h-full"
      >
        <input
          v-model="draftMessage"
          type="text"
          class="flex-1 border border-gray-300 rounded-md p-2"
          placeholder="Type your message..."
        />
        <button
          type="submit"
          class="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
          :disabled="!conversationId || !draftMessage.trim() || assistantThinking"
        >
          Send
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import { useRoute, useRouter } from 'vue-router'
const router = useRouter()
const route = useRoute() 
import axios from 'axios'
const props = defineProps({
  conversationId: {
    type: String,
    default: ''
  },
  userId: {
    type: String,
    default: 'anonymous'
  }
})

const messages = ref([])
const draftMessage = ref('')
const assistantThinking = ref(false)
const messagesContainer = ref(null)

// Observe conversation changes => reload
// watch(() => props.conversationId, async (newVal, oldVal) => {
//   if (newVal && newVal !== oldVal) {
//     messages.value = []
//     await loadFullHistory()
//   }
// })

watch(
  () => route.params.id,
  (newId, oldId) => {
    if (newId) {
      loadPreviousChat(newId)
    }
  }
)

// On mount => load if we have conversation
onMounted(async () => {
  // if (props.conversationId) {
  //   await loadFullHistory()
  // }
})

async function loadFullHistory() {
  if (!props.conversationId) return
  try {
    const resp = await axios.get(
      `${import.meta.env.VITE_API_URL}/newsletter_chat/history/${props.conversationId}`,
      {
        headers: { 'x-user-id': props.userId }
      }
    )
    const data = resp.data
    if (Array.isArray(data.messages)) {
      messages.value = data.messages.map(parseMessage)
    } else {
      messages.value = []
    }
    await nextTick()
    scrollToBottom()
  } catch (err) {
    console.error('[ChatView] Error loading conversation history:', err)
    messages.value = []
  }
}
let userIdStatic="user_2sfDzHK9r5FkXrufqoAFjnjGNPk"
async function loadPreviousChat(convId) {
  try {
    // if (missingKeys.value.length > 0) {
    //   alert(`Missing required keys: ${missingKeys.value.join(', ')}`)
    //   return
    // }

    // const uid = userId.value || 'anonymous'
    const resp = await axios.get(
      `${import.meta.env.VITE_API_URL}/chat/history/${userIdStatic}/${convId}`, 
      {}, 
      
    )
    console.log(resp)
    
  } catch (err) {
    console.error('Error creating new chat:', err)
    alert('Failed to create new conversation. Check keys or console.')
  }
}

// Marked config => GFM, line breaks, highlight
function renderMarkdown(content) {
  marked.setOptions({
    gfm: true,
    breaks: true,
    smartypants: true,
    highlight(code, lang) {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value
      }
      return hljs.highlightAuto(code).value
    }
  })
  return marked(content || '')
}

function parseMessage(msg) {
  return {
    ...msg,
    typing: false,
    formattedContent: renderMarkdown(msg.content)
  }
}

// Submit user message => call API => push assistant reply
async function sendMessage() {
  const txt = draftMessage.value.trim()
  if (!txt || !props.conversationId) return

  const userMsg = {
    role: 'user',
    content: txt,
    typing: false,
    formattedContent: renderMarkdown(txt)
  }
  messages.value.push(userMsg)
  draftMessage.value = ''
  assistantThinking.value = true
  await nextTick()
  scrollToBottom()

  try {
    const resp = await axios.post(
      `${import.meta.env.VITE_API_URL}/newsletter_chat/message/${props.conversationId}`,
      { message: txt },
      {
        headers: { 'x-user-id': props.userId }
      }
    )
    const assistantReply = resp.data.assistant_response || ''
    const assistantMsg = {
      role: 'assistant',
      content: assistantReply,
      typing: false,
      formattedContent: renderMarkdown(assistantReply)
    }
    messages.value.push(assistantMsg)
  } catch (err) {
    console.error('[ChatView] Error sending message:', err)
    messages.value.push({
      role: 'assistant',
      content: 'Error: Could not process your message.',
      typing: false,
      formattedContent: 'Error: Could not process your message.'
    })
  } finally {
    assistantThinking.value = false
    await nextTick()
    scrollToBottom()
  }
}

// Scroll after rendering
function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}
</script>

<style scoped>
/* Loader animation for 'typing' placeholder */
.loader-dots {
  width: 15px;
  height: 3px;
  position: relative;
}
.loader-dots::before,
.loader-dots::after,
.loader-dots > div {
  content: '';
  display: block;
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: #9ca3af;
  position: absolute;
  animation: loader-dots 0.8s infinite ease-in-out;
}
.loader-dots::before {
  left: 0;
}
.loader-dots > div {
  left: 6px;
}
.loader-dots::after {
  left: 12px;
}
@keyframes loader-dots {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

/* Syntax highlighting background, code block style */
.hljs {
  background: #f9fafb;
  padding: 0.5em;
  border-radius: 4px;
  overflow-x: auto;
}

/* For <h1>, <h2>, <h3> etc. plus paragraphs, lists, etc. using tailwind typography */
.prose h1, .prose h2, .prose h3, .prose h4 {
  margin-top: 0.75rem;
  margin-bottom: 0.5rem;
}
.prose p {
  margin: 0.5rem 0;
}
.prose ul, .prose ol {
  margin: 0.5rem 0;
  padding-left: 1.25rem;
}
.prose li {
  margin: 0.25rem 0;
}

.hljs-keyword {
  color: #7c3aed;
  font-weight: bold;
}
.hljs-string {
  color: #15803d;
}
</style>
