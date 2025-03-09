<!-- src/components/chat/ChatView.vue -->
<template>
  <div class="relative h-full w-full ">
    <!-- Content -->
    <div  ref="container" class="relative    h-full flex flex-col overflow-x-hidden overflow-y-auto">
      <!-- Sticky Top Component -->
  <div v-if="chatName" class="sticky h-[62px] top-0 z-10 bg-white p-4 shadow">
    <div class="flex items-center justify-between">
  <!-- Left text -->
  <div  class="text-[16px]  w-80 font-medium text-gray-800 line-clamp-1 overflow-hidden">
    {{ chatName }}
  </div>
  <!-- Right buttons -->
  <div class="flex hidden space-x-2">
    <button 
    
    class=" text-sm h-[30px] py-1 px-2.5 bg-[#EE7624] text-white rounded">
      View full report
    </button>
    <button
    @click="genPDF"
    class=" text-sm h-[30px] py-1 px-2.5 bg-[#EAECF0] text-[#344054] rounded">
      Download PDF
    </button>
  </div>
</div>
  </div>
      <div
        class="flex-1  w-full  flex mx-auto "
        :class="messagesData.length == 0?'justify-center align-center flex-col':''"
      >
        <!-- Title -->
        <div v-if="messagesData.length == 0" class="w-full text-center">
  <h1 v-if="!isLoading" class="text-3xl font-bold sm:text-4xl">
    <span class="bg-clip-text text-primary-brandTextSecondary">Agents</span>
  </h1>
</div>
        <!-- End Title -->
        <!-- <ul class="mt-16  max-w-4xl w-full mx-auto space-y-5"> -->
          <transition-group name="chat" tag="ul" class="mt-16 max-w-4xl w-full mx-auto space-y-5">

          <!-- Chat Bubble -->
          <ChatBubble
            v-for="msgItem in messagesData"
            :metadata="completionMetaData"
            :workflowData="workflowData.filter(item => item.message_id === msgItem.message_id)"
            :plannerText="plannerTextData.filter(item => item.message_id === msgItem.message_id)[0]?.data"            
            :key="msgItem.conversation_id"
            :event="msgItem.event"
            :data="msgItem.data"
            :messageId="msgItem.message_id"
            :provider=provider
            :currentMsgId="currentMsgId"
          />
          <ChatLoaderBubble
            :workflowData="workflowData.filter(item => item.message_id === currentMsgId)"
            v-if="isLoading"
            :isLoading="isLoading"
            :statusText="'Planning...'"
            :plannerText="plannerTextData.filter(item => item.message_id === currentMsgId)[0]?.data"            
            :provider=provider
             :messageId="currentMsgId"
          />
          <!-- End Chat Bubble -->
        <!-- </ul> -->
      </transition-group>

      </div>

      <!-- Documents Section -->
      <div class="sticky z-1000 bottom-0 left-0 right-0 bg-white p-2">
        <div class="sticky bottom-0 z-10 ">
          <!-- Textarea -->
          <div class="max-w-4xl mx-auto lg:px-0">
            <!-- <div class="flex items-start mb-3">
              <StatusText v-if="isLoading" :text="statusText" />
            </div> -->

            <div v-if="uploadedDocuments.length > 0" class="mt-4">
              <!-- Collapsible header -->
              <button
                @click="toggleExpand"
                class="flex items-center justify-between focus:outline-none"
              >
                <h3 class="text-sm font-medium text-gray-700 mb-2">
                  Uploaded Documents ({{ uploadedDocuments.length }})
                </h3>
                <svg
                  :class="{ 'transform rotate-180': isExpanded }"
                  class="w-5 h-5 text-gray-500 transition-transform duration-200"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </button>

              <!-- Collapsible content -->
              <div v-if="isExpanded">
                <HorizontalScroll>
                  <div class="flex space-x-4">
                    <div
                      v-for="doc in uploadedDocuments"
                      :key="doc.id"
                      class="w-48 flex-shrink-0 p-2 bg-gray-50 rounded-lg border border-gray-200 hover:bg-gray-100 relative group"
                    >
                      <div class="flex items-center space-x-3">
                        <input
                          type="checkbox"
                          :checked="selectedDocuments.includes(doc.id)"
                          @change="toggleDocumentSelection(doc.id)"
                          class="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                        />
                        <div class="w-48 overflow-hidden">
                          <p class="text-sm font-medium text-gray-900 truncate">
                            {{ doc.filename }}
                          </p>
                          <p class="text-xs text-gray-500 truncate">
                            Uploaded {{ new Date(doc.upload_timestamp * 1000).toLocaleString() }} •
                            {{ doc.num_chunks }} chunks
                          </p>
                        </div>
                      </div>
                      <button
                        @click="removeDocument(doc.id)"
                        class="absolute top-1 right-1 bg-orange-300 text-white rounded-full p-1 transition-opacity opacity-0 group-hover:opacity-100"
                        title="Remove document"
                      >
                        <XMarkIcon class="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                </HorizontalScroll>
              </div>
            </div>

            <!-- Input -->
            <div class="relative">
              <textarea

              @focus="checkAndOpenSettings"

                @keydown="handleKeyDown"
                v-model="searchQuery"
                type="search"
                placeholder="Ask me about...companies to target, research topics, or company stocks and financials"
                :disabled="isLoading"
                class="p-4 pb-12 block w-full bg-primary-brandFrame border-primary-brandFrame rounded-lg text-sm focus:outline-none active:outline-none border focus:border-primary-brandColor disabled:opacity-50 disabled:pointer-events-none "
              ></textarea>

              <!-- Toolbar -->
              <div class="absolute bottom-px inset-x-px p-2 rounded-b-lg border-primary-brandFrame">
                <div class="flex justify-between items-center">
                  <!-- Button Group -->
                  <div class="flex items-center">
                   
                    <!-- Attach Button -->
                    <button
                      @click="$refs.fileInput.click()"
                      :disabled="isLoading"
                      type="button"
                      class="inline-flex shrink-0 justify-center items-center size-8 rounded-lg text-gray-500 hover:bg-gray-100 focus:z-1 focus:outline-none focus:bg-gray-100"
                    >
                      <input
                        type="file"
                        ref="fileInput"
                        @change="handleFileUpload"
                        class="hidden"
                        accept=".pdf,.doc,.docx,.csv,.xlsx,.xls"
                      />
                      <svg 
                        class="shrink-0 w-5 h-5" 
                        xmlns="http://www.w3.org/2000/svg" 
                        fill="none" 
                        viewBox="0 0 24 24" 
                        stroke="currentColor"
                      >
                        <path 
                          stroke-linecap="round" 
                          stroke-linejoin="round" 
                          stroke-width="2" 
                          d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" 
                        />
                      </svg>
                    </button>
                    <!-- End Attach Button -->
                      <!-- Mic Button -->
                    <button
                    type="button"
                        @click="toggleRecording"
                        :disabled="isLoading"
                        :class="{
                          'text-gray-500': !isRecording,
                          'text-orange-500': isRecording
                        }"
                      class="inline-flex  shrink-0 justify-center items-center size-8 rounded-lg text-gray-500 hover:bg-gray-100 focus:z-1 focus:outline-none focus:bg-gray-100"
                    >

                    <svg 
                      v-if="!isRecording"
                          class="shrink-0"
                    width="34" height="34" viewBox="0 0 34 34" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M17 8C12.03 8 8 12.03 8 17V24C8 25.1 8.9 26 10 26H14V18H10V17C10 13.13 13.13 10 17 10C20.87 10 24 13.13 24 17V18H20V26H24C25.1 26 26 25.1 26 24V17C26 12.03 21.97 8 17 8ZM12 20V24H10V20H12ZM24 24H22V20H24V24Z" fill="#667085"/>
</svg>

                  
                        <svg
                          v-else
                          class="w-6 h-6 text-gray-800 "
                          aria-hidden="true"
                          xmlns="http://www.w3.org/2000/svg"
                          width="24"
                          height="24"
                          fill="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path d="M7 5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H7Z" />
                        </svg>
                    </button>
                    <!-- End Mic Button -->
                  </div>
                  <!-- End Button Group -->
                  <!-- Button Group -->
                  <div class="flex items-center gap-x-1">
                    <!-- Mic Button -->
                    <Popover text="Use voice mode" position="top" color="bg-black text-white">
                      <button
                        type="button"
                        @click="toggleRecording"
                        :disabled="isLoading"
                        :class="{
                          'text-gray-500': !isRecording,
                          'text-orange-500': isRecording
                        }"
                        class="inline-flex hidden shrink-0 justify-center items-center size-8 rounded-lg text-gray-500 hover:bg-gray-100 focus:z-1 focus:outline-none focus:bg-gray-100"
                      >
                        <svg
                          v-if="!isRecording"
                          class="w-6 h-6 text-gray-800 "
                          aria-hidden="true"
                          xmlns="http://www.w3.org/2000/svg"
                          width="24"
                          height="24"
                          fill="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            fill-rule="evenodd"
                            d="M5 8a1 1 0 0 1 1 1v3a4.006 4.006 0 0 0 4 4h4a4.006 4.006 0 0 0 4-4V9a1 1 0 1 1 2 0v3.001A6.006 6.006 0 0 1 14.001 18H13v2h2a1 1 0 1 1 0 2H9a1 1 0 1 1 0-2h2v-2H9.999A6.006 6.006 0 0 1 4 12.001V9a1 1 0 0 1 1-1Z"
                            clip-rule="evenodd"
                          />
                          <path d="M7 6a4 4 0 0 1 4-4h2a4 4 0 0 1 4 4v5a4 4 0 0 1-4 4h-2a4 4 0 0 1-4-4V6Z" />
                        </svg>
                        <svg
                          v-else
                          class="w-6 h-6 text-gray-800 "
                          aria-hidden="true"
                          xmlns="http://www.w3.org/2000/svg"
                          width="24"
                          height="24"
                          fill="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path d="M7 5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H7Z" />
                        </svg>
                      </button>
                    </Popover>
                    <!-- End Mic Button -->
                    <!-- Send Button -->
                    <button
                      type="button"
                      @click="addMessage"
                      :disabled="isLoading || !searchQuery.trim()"
                      class="inline-flex shrink-0 justify-center items-center bg-transparent cursor-pointer"
                    >
                      <svg
                        v-if="!isLoading"
                        width="21"
                        height="18"
                        viewBox="0 0 21 18"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path d="M0.00999999 18L21 9L0.00999999 0L0 7L15 9L0 11L0.00999999 18Z" fill="#EE7624" />
                      </svg>
                      <svg
                        v-if="isLoading"
                        width="20"
                        height="20"
                        viewBox="0 0 20 20"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          d="M10 0C4.48 0 0 4.48 0 10C0 15.52 4.48 20 10 20C15.52 20 20 15.52 20 10C20 4.48 15.52 0 10 0ZM10 18C5.58 18 2 14.42 2 10C2 5.58 5.58 2 10 2C14.42 2 18 5.58 18 10C18 14.42 14.42 18 10 18ZM14 14H6V6H14V14Z"
                          fill="#667085"
                        />
                      </svg>
                    </button>
                    <!-- End Send Button -->
                  </div>
                  <!-- End Button Group -->
                </div>
              </div>
              <!-- End Toolbar -->
            </div>
            <!-- End Input -->
          </div>
          <!-- End Textarea -->
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick, onBeforeUnmount,onUnmounted, inject, computed } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import { useRoute, useRouter } from 'vue-router'
import SILogo from '@/components/icons/SILogo.vue'
import axios from 'axios'
import { v4 as uuidv4 } from 'uuid'
import ChatBubble from '@/components/ChatMain/ChatBubble.vue'
import ChatLoaderBubble from '@/components/ChatMain/ChatLoaderBubble.vue'
const router = useRouter()
const route = useRoute()
import { decryptKey } from '../../utils/encryption'
import ErrorModal from '../ErrorModal.vue'
import { uploadDocument } from '../../services/api'
import Popover from '@/components/Common/UIComponents/CustomPopover.vue'
import StatusText from '@/components/Common/StatusText.vue'
import { DocumentArrowUpIcon, XMarkIcon } from '@heroicons/vue/24/outline'
import HorizontalScroll from '@/components/Common/UIComponents/HorizontalScroll.vue'
import emitterMitt from '@/utils/eventBus.js';
import { data } from 'autoprefixer'

// Inject the shared selectedOption from MainLayout.vue.
const selectedOption = inject('selectedOption')
const eventData = ref(null);
function handleButtonClick(data) {
  eventData.value = data.message;
  
  chatName.value=''
  createNewChat()

}


async function genPDF() {
  try {
    const sampleContent = {
    report: [
      {
        title: 'Introduction',
        high_level_goal: 'Understand the basics of Vue 3',
        why_important: 'Vue 3 is a modern framework with reactivity features.',
        generated_content: '## Vue 3 Overview\nVue 3 introduces Composition API, better performance, and more...'
      }
    ]
  };

  downloadPDF(sampleContent);
  }catch(e){
console.log("PDF gen error",e)
  }
}

async function createNewChat() {
  try {
    const resp = await axios.post(
      `${import.meta.env.VITE_API_URL}/chat/init`, 
      {}, 
      {
        headers: {
          'Content-Type': 'application/json'
        }
      }
    )
    const cid = resp.data.conversation_id
    router.push(`/${cid}`)
  } catch (err) {
    console.error('Error creating new chat:', err)
    alert('Failed to create new conversation. Check keys or console.')
  }
}


// Watch for changes to the selection and load data accordingly.
const provider = ref('')
const chatName = ref('')
watch(
  selectedOption,
  (newVal) => {
    console.log('Selected option changed:', newVal)
    provider.value = newVal.value
  },
  { immediate: true }
)

const newMessage = ref('') // User input field
const socket = ref(null) // WebSocket reference
const container = ref(null)
const isExpanded = ref(false)
function toggleExpand() {
  isExpanded.value = !isExpanded.value
}

function handleKeyDown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    addMessage()
  }
}

function handleKeydownScroll(event) {
  const container = scrollContainer.value
  if (!container) return
  const scrollAmount = 100
  if (event.key === 'ArrowRight') {
    container.scrollBy({ left: scrollAmount, behavior: 'smooth' })
  } else if (event.key === 'ArrowLeft') {
    container.scrollBy({ left: -scrollAmount, behavior: 'smooth' })
  }
}

// function AutoScrollToBottom() {
//   nextTick(() => {
//     if (container.value) {
//       container.value.scrollTop = container.value.scrollHeight
//     }
//   })
// }


function AutoScrollToBottom(smoothScrollOff = false) {
  nextTick(() => {
    setTimeout(() => {
      if (container.value) {
        const targetScroll = container.value.scrollHeight - container.value.clientHeight;
        container.value.scrollTo({
          top: targetScroll,
          behavior: smoothScrollOff ? "auto" : "smooth"
        });
      }
    }, 100); // Adjust timeout as needed
  });
}



const emit = defineEmits([
  'searchStart',
  'metadataChanged',
  'searchComplete',
  'searchError',
  'openSettings',
  'agentThoughtsDataChanged'
])
const props = defineProps({
  conversationId: {
    type: String,
    default: ''
  },
  userId: {
    type: String,
    default: 'anonymous'
  },
  keysUpdated: {
    type: Number,
    default: 0
  },
  runId: {
    type: String,
    default: ''
  },
  sessionId: {
    type: String,
    default: ''
  }
})

const messages = ref([])
const draftMessage = ref('')
const assistantThinking = ref(false)
const isLoading = ref(false)
const messagesContainer = ref(null)

// Conversation change watcher:
watch(
  () => route.params.id,
  (newId, oldId) => {
    if (oldId && newId !== oldId) {
    completionMetaData.value = null;
    isLoading.value = false;
    messagesData.value = [];
    agentThoughtsData.value = [];
    searchQuery.value = '';
    loadPreviousChat(newId);
  }
  currentId.value = newId;
  
  if (socket.value) {
    socket.value.close();
  }
  connectWebSocket();
  }
)

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


const checkAndOpenSettings = () => {
  emitterMitt.emit('check-keys', { message: 'check keys!' });

}

async function loadPreviousChat(convId) {
  try {
    isLoading.value = true
    const resp = await axios.get(
      `${import.meta.env.VITE_API_URL}/chat/history/${convId}`,
      {
        headers: {
          'Content-Type': 'application/json'
        }
      }
    )
    isLoading.value = false
    console.log(resp)
    filterChat(resp.data)
    AutoScrollToBottom(true)
  } catch (err) {
    console.error('Error creating new chat:', err)
    alert('Failed to create new conversation. Check keys or console.')
  }
}
const currentId = ref(route.params.id || '')

const messagesData = ref([])
const workflowData = ref([])
const completionMetaData = ref(null)
const agentThoughtsData = ref([])

async function filterChat(msgData) {
  messagesData.value = msgData.messages
    .filter(message => message.event === "completion" || message.event === "user_message")
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))


    let plannerData = msgData.messages
    .filter(message => message.event === "planner")
    plannerData.forEach(planner => {
      console.log("planner",planner.message_id,JSON.parse(planner.data))
      addOrUpdateModel(JSON.parse(planner.data).metadata,planner.message_id)
});
let workData = msgData.messages
    .filter(message => message.event === "think")
    workData.forEach(work => {
      console.log("work",work.message_id,JSON.parse(work.data))
      addOrUpdateModel(JSON.parse(work.data).metadata,work.message_id)
});

    
  AutoScrollToBottom()


  agentThoughtsData.value = msgData.messages
    .filter(message => message.event === "think")
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
    .reduce((acc, message) => {
      try {
        const parsed = JSON.parse(message.data)
        acc.push(parsed)
      } catch (error) {
        console.error("Failed to parse JSON for message:", message, error)
      }
      return acc
    }, [])
  emit('agentThoughtsDataChanged', agentThoughtsData.value)



  if(messagesData?.value[0]?.data){
    chatName.value=messagesData.value[0].data
  }

  AutoScrollToBottom()
  await nextTick()
}

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
      { headers: { 'x-user-id': props.userId } }
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

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// Reactive state for voice and file uploads
const searchQuery = ref('')
const isRecording = ref(false)
const mediaRecorder = ref(null)
const audioChunks = ref([])
const sambanovaKey = ref(null)
const exaKey = ref(null)
const serperKey = ref(null)
const fireworksKey = ref(null)
const errorMessage = ref('')
const showErrorModal = ref(false)
const fileInput = ref(null)
const uploadStatus = ref(null)

// Document-related reactive state
const uploadedDocuments = ref([])
const selectedDocuments = ref([])

const userId = ref('anonymous_user')

async function loadKeys() {
  try {
    const encryptedSambanovaKey = localStorage.getItem(`sambanova_key_${userId.value}`)
    const encryptedExaKey = localStorage.getItem(`exa_key_${userId.value}`)
    const encryptedSerperKey = localStorage.getItem(`serper_key_${userId.value}`)
    const encryptedFireworksKey = localStorage.getItem(`fireworks_key_${userId.value}`)

    if (encryptedSambanovaKey) {
      sambanovaKey.value = await decryptKey(encryptedSambanovaKey)
    } else {
      sambanovaKey.value = null
    }

    if (encryptedExaKey) {
      exaKey.value = await decryptKey(encryptedExaKey)
    } else {
      exaKey.value = null
    }

    if (encryptedSerperKey) {
      serperKey.value = await decryptKey(encryptedSerperKey)
    } else {
      serperKey.value = null
    }

    if (encryptedFireworksKey) {
      fireworksKey.value = await decryptKey(encryptedFireworksKey)
    } else {
      fireworksKey.value = null
    }
  } catch (error) {
    console.error('Error loading keys:', error)
    errorMessage.value = 'Error loading API keys'
    showErrorModal.value = true
  }
}

onMounted(async () => {
  await loadKeys()  
  await loadUserDocuments()
  let newId = route.params.id
  if (newId) loadPreviousChat(newId)

  emitterMitt.on('new-chat', handleButtonClick);

})

onUnmounted(() => {
  emitterMitt.off('new-chat', handleButtonClick);
});

watch(
  () => props.keysUpdated,
  async () => {
    await loadKeys()
  },
  { immediate: true }
)

const missingKeys = computed(() => {
  const missing = []
  if (!sambanovaKey.value) missing.push('SambaNova')
  if (!exaKey.value) missing.push('Exa')
  if (!serperKey.value) missing.push('Serper')
  return missing
})

const statusText = ref('Loading...')
const plannerTextData = ref([])
async function performSearch() {
  try {
    emit('searchStart', 'routing_query')
    const routeResp = await axios.post(
      `${import.meta.env.VITE_API_URL}/route`,
      { query: searchQuery.value },
      {
        headers: {
          'Content-Type': 'application/json',
          'x-sambanova-key': sambanovaKey.value || '',
          'x-user-id': userId.value || '',
          'x-run-id': props.runId || ''
        }
      }
    )
    const detectedType = routeResp.data.type
    emit('searchStart', detectedType || 'unknown')
    const parameters = {
      ...routeResp.data.parameters,
      document_ids: selectedDocuments.value
    }
    const executeResp = await axios.post(
      `${import.meta.env.VITE_API_URL}/execute/${detectedType}`,
      parameters,
      {
        headers: {
          'Content-Type': 'application/json',
          'x-sambanova-key': sambanovaKey.value || '',
          'x-serper-key': serperKey.value || '',
          'x-exa-key': exaKey.value || '',
          'x-user-id': userId.value || '',
          'x-run-id': props.runId || '',
          'x-session-id': props.sessionId || ''
        }
      }
    )
    emit('searchComplete', {
      type: detectedType,
      query: searchQuery.value,
      results: executeResp.data
    })
    searchQuery.value = ''
  } catch (error) {
    console.error('[SearchSection] performSearch error:', error)
    emit('searchError', error)
  }
}

function toggleRecording() {
  if (isRecording.value) {
    stopRecording()
  } else {
    startRecordingFlow()
  }
}

async function startRecordingFlow() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    startRecording(stream)
  } catch (error) {
    console.error('Error accessing microphone:', error)
    alert('Unable to access microphone. Please check your permissions.')
  }
}

function startRecording(stream) {
  audioChunks.value = []
  const options = { mimeType: 'audio/webm' }
  if (!MediaRecorder.isTypeSupported(options.mimeType)) {
    console.warn(`${options.mimeType} is not supported, using default MIME type.`)
    delete options.mimeType
  }
  mediaRecorder.value = new MediaRecorder(stream, options)
  mediaRecorder.value.ondataavailable = (event) => {
    if (event.data.size > 0) {
      audioChunks.value.push(event.data)
    }
  }
  mediaRecorder.value.onstop = async () => {
    const audioBlob = new Blob(audioChunks.value, { type: 'audio/webm' })
    await transcribeAudio(audioBlob)
    stream.getTracks().forEach((track) => track.stop())
  }
  mediaRecorder.value.start()
  isRecording.value = true
}

function stopRecording() {
  if (mediaRecorder.value && mediaRecorder.value.state !== 'inactive') {
    mediaRecorder.value.stop()
    isRecording.value = false
  }
}

async function transcribeAudio(audioBlob) {
  try {
    if (!sambanovaKey.value) {
      throw new Error('SambaNova API key is missing. Please add it in the settings.')
    }
    const audioArrayBuffer = await audioBlob.arrayBuffer()
    const audioBase64 = btoa(
      new Uint8Array(audioArrayBuffer).reduce((data, byte) => data + String.fromCharCode(byte), '')
    )
    const requestBody = {
      model: 'Qwen2-Audio-7B-Instruct',
      messages: [
        {
          role: 'system',
          content: 'You are an Automatic Speech Recognition tool.'
        },
        {
          role: 'user',
          content: [
            {
              type: 'audio_content',
              audio_content: {
                content: `data:audio/webm;base64,${audioBase64}`
              }
            }
          ]
        },
        {
          role: 'user',
          content: 'Please transcribe the previous audio and only return the transcription.'
        }
      ],
      response_format: 'streaming',
      stream: true
    }
    const response = await fetch('https://api.sambanova.ai/v1/audio/reasoning', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${sambanovaKey.value}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(requestBody)
    })
    if (!response.ok) {
      const errorText = await response.text()
      console.error('API Error:', response.status, errorText)
      alert(`Transcription failed with status ${response.status}: ${errorText}`)
      throw new Error(`Transcription failed: ${errorText}`)
    }
    const streamReader = response.body.getReader()
    let transcribedText = ''
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await streamReader.read()
      if (done) break
      const chunk = decoder.decode(value)
      const lines = chunk.split('\n').filter(line => line.trim())
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6).trim()
          if (dataStr === '[DONE]') break
          try {
            const data = JSON.parse(dataStr)
            if (data.choices?.[0]?.delta?.content) {
              transcribedText += data.choices[0].delta.content
            }
          } catch (e) {
            console.error('Error parsing JSON:', e, 'Data string:', dataStr)
          }
        }
      }
    }
    const cleanedText = cleanTranscription(transcribedText)
    searchQuery.value = cleanedText.trim()
    if (searchQuery.value) {
      addMessage()
    }
  } catch (error) {
    console.error('Transcription error:', error)
    alert(error.message || 'Failed to transcribe audio. Please try again.')
  }
}

function cleanTranscription(transcribedText) {
  let cleanedText = transcribedText.trim()
  const prefixes = [
    'The transcription of the audio is:',
    'The transcription is:'
  ]
  for (const prefix of prefixes) {
    if (cleanedText.startsWith(prefix)) {
      cleanedText = cleanedText.slice(prefix.length).trim()
      break
    }
  }
  if (
    (cleanedText.startsWith("'") && cleanedText.endsWith("'")) ||
    (cleanedText.startsWith('"') && cleanedText.endsWith('"'))
  ) {
    cleanedText = cleanedText.slice(1, -1).trim()
  }
  return cleanedText
}

async function handleFileUpload(event) {
  const file = event.target.files[0]
  if (!file) return
  try {
    uploadStatus.value = { type: 'info', message: 'Uploading document...' }
    const formData = new FormData()
    formData.append('file', file)
    const response = await axios.post(
      `${import.meta.env.VITE_API_URL}/upload`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      }
    )
    // Store the uploaded document and update selection.
    const document = response.data.document
    uploadedDocuments.value.push(document)
    selectedDocuments.value.push(document.id)
    uploadStatus.value = { type: 'success', message: 'Document uploaded successfully!' }
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  } catch (error) {
    console.error('[SearchSection] Upload error:', error)
    uploadStatus.value = {
      type: 'error',
      message: error.response?.data?.error || 'Failed to upload document'
    }
  }
}

async function loadUserDocuments() {
  try {
    const response = await axios.get(
      `${import.meta.env.VITE_API_URL}/documents`,
      {
        headers: {
          'Content-Type': 'application/json'
        }
      }
    )
    uploadedDocuments.value = response.data.documents
  } catch (error) {
    console.error('[SearchSection] Error loading documents:', error)
  }
}

function toggleDocumentSelection(docId) {
  const index = selectedDocuments.value.indexOf(docId)
  if (index === -1) {
    selectedDocuments.value.push(docId)
  } else {
    selectedDocuments.value.splice(index, 1)
  }
}

onBeforeUnmount(() => {
  if (socket.value) {
    socket.value.close()
  }
})

function waitForSocketOpen(timeout = 5000) {
  return new Promise((resolve, reject) => {
    const interval = 50
    let elapsed = 0
    const checkInterval = setInterval(() => {
      if (socket.value && socket.value.readyState === WebSocket.OPEN) {
        clearInterval(checkInterval)
        resolve()
      }
      elapsed += interval
      if (elapsed >= timeout) {
        clearInterval(checkInterval)
        reject(new Error("Socket connection timeout"))
      }
    }, interval)
  })
}

const  currentMsgId=ref('')
const addMessage = async () => {


  workflowData.value=[]
 
    // If no conversation exists, create a new chat first.
    if (!route.params.id) {
    await createNewChat();
    await nextTick();
    // After createNewChat, the router push should update the conversation id.
    currentId.value = route.params.id; // update currentId from router params
  }

  if(messagesData.value.length===0){
    chatName.value=searchQuery.value
  }

  completionMetaData.value = null
  // plannerText.value = null
  statusText.value = 'Loading...'
  AutoScrollToBottom()
  agentThoughtsData.value = []
  // workflowData.value = []
  emit('agentThoughtsDataChanged', agentThoughtsData.value)
  emit('metadataChanged', completionMetaData.value)
  if (!searchQuery.value.trim()) return

  currentMsgId.value=uuidv4()
  const messagePayload = {
    event: "user_message",
    data: searchQuery.value,
    timestamp: new Date().toISOString(),
    provider: provider.value,
    planner_model: localStorage.getItem(`selected_model_${userId.value}`) || '',
    message_id:currentMsgId.value
  }

  if (selectedDocuments.value && selectedDocuments.value.length > 0) {
    messagePayload.document_ids = selectedDocuments.value.map(doc => {
      return typeof doc === 'string' ? doc : doc.id;
    });
  } else {
    messagePayload.document_ids = [];
  }
  messagesData.value.push(messagePayload)
  if (!socket.value || socket.value.readyState !== WebSocket.OPEN) {
    try {
      console.log("Socket not connected. Connecting...")
      connectWebSocket()
      await waitForSocketOpen()
      socket.value.send(JSON.stringify(messagePayload))
      isLoading.value = true
      console.log('Message sent after connecting:', messagePayload)
    } catch (error) {
      console.error('Failed to connect and send message:', error)
    }
  } else {
    try {
      isLoading.value = true
      socket.value.send(JSON.stringify(messagePayload))
      searchQuery.value = ''
    } catch (e) {
      console.error("ChatView error", e)
    }
  }

   searchQuery.value = ''
}

function addOrUpdateModel(newData, message_id) {
  // Determine which message_id to use.
  const idToUse = message_id ? message_id : currentMsgId.value;

  // Find an existing model with matching llm_name and message_id.
  const existingModel = workflowData.value.find(
    item => item.llm_name === newData.llm_name && item.message_id === idToUse
  );

  if (existingModel) {
    // Update existing model and increment count.
    Object.assign(existingModel, newData);
    existingModel.count = (existingModel.count || 1) + 1;
  } else {
    // Add new model entry with initial count of 1.
    workflowData.value.push({
      ...newData,
      count: 1,
      message_id: idToUse
    });


    console.log(workflowData.value)
  }
}


async function connectWebSocket() {
  try {
    await loadKeys()

    await axios.post(
      `${import.meta.env.VITE_API_URL}/set_api_keys`,
      {
        sambanova_key: sambanovaKey.value || '',
        serper_key: serperKey.value || '',
        exa_key: exaKey.value || '',
        fireworks_key: fireworksKey.value || ''
      },
      {
        headers: {
          'Content-Type': 'application/json'
        }
      }
    )
    
    // Use the same base URL pattern as API calls
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const baseUrl = import.meta.env.PROD 
      ? `${wsProtocol}//${window.location.host}/api`  // Use the current origin in production
      : (import.meta.env.VITE_WEBSOCKET_URL || 'ws://localhost:8000')
    
    const WEBSOCKET_URL = `${baseUrl}/chat`
    const token = await window.Clerk.session.getToken()
    const fullUrl = `${WEBSOCKET_URL}?conversation_id=${currentId.value}`
    socket.value = new WebSocket(fullUrl)
    socket.value.onopen = () => {
      console.log('WebSocket connection opened')
      const token = localStorage.getItem('access_token') || 'anonymous_user';
      socket.value.send(JSON.stringify({
        type: 'auth',
        token: `Bearer ${token}`
      }))
    }
    socket.value.onmessage = (event) => {
      try {
        const receivedData = JSON.parse(event.data)
        if(receivedData.event=="user_message" || receivedData.event=="completion"){
          try {
            if(receivedData.event=="completion"){
              let metaDataComplettion = JSON.parse(receivedData.data)
              completionMetaData.value = metaDataComplettion.metadata
              emit('metadataChanged', completionMetaData.value)
            }else{
              AutoScrollToBottom()
            }
          } catch (error) {
            console.log("completionMetaData.value",error)
          }
          messagesData.value.push(receivedData)
          isLoading.value = false
          
        }
        else if(receivedData.event==="think"){
          let dataParsed = JSON.parse(receivedData.data)
          agentThoughtsData.value.push(dataParsed)
          
          statusText.value = dataParsed.agent_name
          emit('agentThoughtsDataChanged', agentThoughtsData.value)
          try{
            
          addOrUpdateModel(dataParsed.metadata)
          
          AutoScrollToBottom()

          } catch(e){
            console.log("model error",e)
          }
        }
        else if(receivedData.event==="planner_chunk"){
          addOrUpdatePlannerText({message_id:currentMsgId.value,data:receivedData.data})
        }
        else if(receivedData.event==="planner"){
          let dataParsed = JSON.parse(receivedData.data)
          addOrUpdateModel(dataParsed.metadata)
          
          AutoScrollToBottom()
        }
        else{
          console.log("ping event fired: ", receivedData.event)
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error)
        isLoading.value = false
      }
    }
    socket.value.onerror = (error) => {
      console.error('WebSocket error:', error)
      isLoading.value = false
    }
    socket.value.onclose = () => {
      console.log('WebSocket closed, attempting to reconnect...')
    }
  } catch (error) {
    console.error('WebSocket connection error:', error)
    isLoading.value = false
  }
}


function addOrUpdatePlannerText(newEntry) {
  // Find the index of an existing entry with the same message_id
  const index = plannerTextData.value.findIndex(
    (entry) => entry.message_id === newEntry.message_id
  );

  if (index !== -1) {
    // Concatenate the new data with the existing data
    plannerTextData.value[index].data += newEntry.data;
  } else {
    // Add new entry
    plannerTextData.value.push(newEntry);
  }

}

async function removeDocument(docId) {
  try {
    await axios.delete(
      `${import.meta.env.VITE_API_URL}/documents/${docId}`,
      {
        headers: {
          'Content-Type': 'application/json'
        }
      }
    )
    const selectedIndex = selectedDocuments.value.indexOf(docId)
    if (selectedIndex !== -1) {
      selectedDocuments.value.splice(selectedIndex, 1)
    }
    uploadedDocuments.value = uploadedDocuments.value.filter(doc => doc.id !== docId)
    uploadStatus.value = { type: 'success', message: 'Document removed successfully!' }
    setTimeout(() => {
      uploadStatus.value = null
    }, 3000)
  } catch (error) {
    console.error('[SearchSection] Error removing document:', error)
    uploadStatus.value = { 
      type: 'error', 
      message: error.response?.data?.error || 'Failed to remove document' 
    }
  }
}

function scrollNewMessageToMiddle() {
  nextTick(() => {
    const containerEl = container.value
    if (!containerEl) return
    // Query the <ul> element inside the container
    const messageListEl = containerEl.querySelector('ul')
    if (!messageListEl) return
    // Get the last message element
    const lastMessageEl = messageListEl.lastElementChild
    if (!lastMessageEl) return

    // Calculate the new scrollTop:
    // lastMessageEl.offsetTop gives the distance from container top to the new message.
    // Add half its height, then subtract half the container height to center it.
    const targetScrollTop = lastMessageEl.offsetTop + lastMessageEl.offsetHeight / 2 - containerEl.clientHeight / 2

    containerEl.scrollTo({ top: targetScrollTop, behavior: 'smooth' })
  })
}
watch(
  () => messagesData.value.length,
  () => {
    scrollNewMessageToMiddle()
  }
)
</script>

<style scoped>
/* New message enter/leave transitions */
.chat-enter-from,
.chat-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
.chat-enter-active,
.chat-leave-active {
  transition: all 0.3s ease;
}
</style>
