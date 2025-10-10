<template>
  <!-- This entire sidebar is collapsible. The container must have enough height to scroll internally. -->
  <div
    v-if="userId && runId"
    class="flex flex-col h-full border-l border-gray-300 transition-all duration-300 bg-white"
    :class="collapsed ? 'w-16' : 'w-80'"
  >
    <!-- TOP HEADER ROW -->
    <div 
      class="flex items-center border-b border-gray-200 p-2"
      :class="collapsed ? 'justify-center' : 'justify-between'"
    >
      <div v-if="!collapsed" class="flex items-center space-x-2 text-gray-800 font-semibold">
        <!-- Agent Thoughts icon -->
        <svg class="h-5 w-5 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path 
            stroke-linecap="round" 
            stroke-linejoin="round" 
            stroke-width="2" 
            d="M15 8a3 3 0 00-6 0v1a3 3 0 00-3 3v1.17a2 2 0 01-.586 1.414l-1 1
               a1 1 0 001.414 1.414L7 16.414A2 2 0 008.414 17H15
               a3 3 0 003-3v-1a3 3 0 00-3-3V8z" 
          />
        </svg>
        <span>Agent Thoughts</span>
      </div>

      <!-- Collapse/Expand Button -->
      <button
        class="hover:bg-gray-100 p-1 rounded"
        @click="collapsed = !collapsed"
      >
        <span v-if="collapsed">
          <!-- Expand icon -->
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-gray-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path 
              stroke-linecap="round" 
              stroke-linejoin="round" 
              stroke-width="2"
              d="M9 5l7 7-7 7" 
            />
          </svg>
        </span>
        <span v-else>
          <!-- Collapse icon -->
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-gray-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path 
              stroke-linecap="round" 
              stroke-linejoin="round" 
              stroke-width="2"
              d="M15 19l-7-7 7-7" 
            />
          </svg>
        </span>
      </button>
    </div>

    <!-- MESSAGES SCROLL CONTAINER -->
    <div
      v-if="!collapsed"
      class="flex-1 overflow-y-auto p-2 space-y-2"
      ref="scrollContainer"
    >
      <!-- Each message card -->
      <div
        v-for="(msg, index) in messages"
        :key="index"
        class="flex flex-col rounded shadow-sm p-2"
        :style="getAgentStyle(msg.agent_name)"
      >
        <!-- Agent Name + Timestamp row -->
        <div class="flex justify-between items-center mb-2">
          <div class="flex items-center space-x-1 font-semibold text-sm">
            <!-- Agent icon -->
            <span v-html="getAgentIcon(msg.agent_name)" class="inline-block"></span>
            <span>{{ msg.agent_name }}</span>
          </div>
          <div class="text-xs text-gray-700">
            {{ new Date(msg.timestamp * 1000).toLocaleTimeString() }}
          </div>
        </div>

        <!-- Render each "segment" of the parsed message -->
        <div
          v-for="(segment, idx) in msg.parsedSegments"
          :key="idx"
          class="text-sm text-gray-800 mb-1"
        >
          <!-- Thought stage -->
          <template v-if="segment.type === 'thought'">
            <div class="flex items-start space-x-2">
              <span v-html="icons.thought" class="inline-block text-yellow-600"></span>
              <div class="whitespace-pre-wrap">
                <span class="italic text-yellow-600 mr-1">Thought:</span>
                {{ segment.content }}
              </div>
            </div>
          </template>

          <!-- Action stage -->
          <template v-else-if="segment.type === 'action'">
            <div class="flex items-start space-x-2">
              <span v-html="icons.action" class="inline-block text-indigo-700"></span>
              <div class="whitespace-pre-wrap">
                <span class="italic text-indigo-700 mr-1">Action:</span>
                {{ segment.content }}
              </div>
            </div>
          </template>

          <!-- Action Input stage -->
          <template v-else-if="segment.type === 'action_input'">
            <div class="flex flex-col space-y-1 ml-4">
              <div class="flex items-center space-x-2 text-indigo-400">
                <span v-html="icons.actionInput" class="inline-block"></span>
                <span class="italic">Action Input:</span>
              </div>
              <pre class="bg-gray-100 p-2 rounded whitespace-pre-wrap text-xs w-full">
                {{ segment.content }}
              </pre>
            </div>
          </template>

          <!-- Observation stage (truncate by default) -->
          <template v-else-if="segment.type === 'observation'">
            <div class="flex flex-col space-y-1 ml-4">
              <div class="flex items-center space-x-2 text-teal-700">
                <span v-html="icons.observation" class="inline-block"></span>
                <span class="italic">Observation:</span>
              </div>
              <div>
                <template v-if="segment.truncated && !segment.expanded">
                  <pre class="bg-gray-50 p-2 rounded whitespace-pre-wrap text-xs">
                    {{ segment.firstLines.join('\n') }}
                  </pre>
                  <!-- If there's more content, show a toggle -->
                  <button
                    v-if="segment.remainingLines.length"
                    class="text-xs text-blue-600 underline"
                    @click="segment.expanded = true"
                  >
                    Show more
                  </button>
                </template>
                <template v-else>
                  <pre class="bg-white border border-gray-300 rounded p-2 whitespace-pre-wrap text-xs">
                    {{ segment.content }}
                  </pre>
                  <button
                    v-if="segment.truncated"
                    class="text-xs text-blue-600 underline"
                    @click="segment.expanded = false"
                  >
                    Show less
                  </button>
                </template>
              </div>
            </div>
          </template>

          <!-- Final Answer stage -->
          <template v-else-if="segment.type === 'final_answer'">
            <div class="flex flex-col space-y-2">
              <div class="flex items-center space-x-2">
                <span v-html="icons.finalAnswer" class="inline-block text-purple-700"></span>
                <span class="italic text-purple-700">Final Answer:</span>
                <button
                  class="text-xs text-blue-600 underline"
                  @click="segment.show = !segment.show"
                >
                  {{ segment.show ? 'Hide' : 'Show' }}
                </button>
              </div>
              <div v-if="segment.show">
                <pre class="bg-white border border-gray-300 rounded p-2 whitespace-pre-wrap text-xs">
                  {{ segment.content }}
                </pre>
              </div>
            </div>
          </template>

          <!-- default fallback -->
          <template v-else>
            <div class="whitespace-pre-wrap">
              {{ segment.content }}
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'

// PROPS
const props = defineProps({
  userId: {
    type: String,
    default: ''
  },
  runId: {
    type: String,
    default: ''
  },
  isMobile: {
    type: Boolean,
    default: false,
  },
})

const collapsed = ref(true)

watch(
  () => props.isMobile,
  (isMobile) => {
    if (isMobile) {
      collapsed.value = true;
    }
  },
  { immediate: true }
);

// SSE
const messages = ref([])
let eventSource = null
let firstMessageArrived = false
let lastFinalAnswer = '' // for deduping repeated final answers

// Refs
const scrollContainer = ref(null)

// ICONS
const icons = {
  thought: `
    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4"
         fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M15 8a3 3 0 00-6 0v1a3 3 0 00-3 3v1.17
               a2 2 0 01-.586 1.414l-1 1
               a1 1 0 001.414 1.414L7 16.414
               A2 2 0 008.414 17H15
               a3 3 0 003-3v-1a3 3 0 00-3-3V8z"/>
    </svg>
  `,
  action: `
    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4"
         fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M13 10V3L4 14h7v7l9-11h-7z"/>
    </svg>
  `,
  actionInput: `
    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4"
         fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M12 20h9m-9-4h9m-9-4h9M3 4h1
               a2 2 0 012 2v12a2 2 0 01-2 2H3
               a2 2 0 01-2-2V6a2 2 0 012-2z"/>
    </svg>
  `,
  observation: `
    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4"
         fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M5 3c-1.1 0-2 .9-2 2v13
               a2 2 0 002 2h14
               a2 2 0 002-2V5
               a2 2 0 00-2-2H5zm2 10l3 3l7-7"/>
    </svg>
  `,
  finalAnswer: `
    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4"
         fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M19 9l-7 7-4-4"/>
    </svg>
  `
}

// Agent color mapping
const agentStyleMap = {
  'Aggregator Search Agent': { backgroundColor: '#F3E8FF' },
  'Data Extraction Agent': { backgroundColor: '#E7F9F1' },
  'Market Trends Analyst': { backgroundColor: '#FFFBEA' },
  'Outreach Specialist': { backgroundColor: '#E7F3FF' }
}

function getAgentStyle(agentName) {
  const style = agentStyleMap[agentName]
  if (style) {
    return { 'background-color': style.backgroundColor }
  }
  return { 'background-color': '#F1F5F9' }
}
function getAgentIcon(agentName) {
  return `
    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-gray-600"
         fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M12 4v16m8-8H4"/>
    </svg>
  `
}

/**
 * parseMessage => splits text into segments: Thought, Action, etc.
 * Also handles truncation for "observation" segments.
 */
function parseMessage(fullText) {
  const segments = []
  let lines = fullText.split('\n')
  let currentType = 'raw'
  let currentContent = ''

  function pushSegment(type, content) {
    if (type === 'final_answer') {
      if (content.trim() === lastFinalAnswer.trim()) return
      lastFinalAnswer = content.trim()
    }
    const segment = {
      type,
      content,
      show: (type !== 'final_answer'),
      truncated: false,
      expanded: false,
      firstLines: [],
      remainingLines: []
    }
    if (type === 'observation') {
      let obsLines = content.split('\n')
      if (obsLines.length > 3) {
        segment.truncated = true
        segment.firstLines = obsLines.slice(0, 3)
        segment.remainingLines = obsLines.slice(3)
      } else if (obsLines.length === 1 && content.length > 200) {
        segment.truncated = true
        segment.firstLines = [content.slice(0, 200)]
        segment.remainingLines = [content.slice(200)]
      }
    }
    segments.push(segment)
  }

  for (let line of lines) {
    let trimmed = line.trim()
    if (/^Thought:\s*/i.test(trimmed)) {
      if (currentContent.trim()) pushSegment(currentType, currentContent)
      currentType = 'thought'
      currentContent = trimmed.replace(/^Thought:\s*/i, '').trim()
    } else if (/^Action:\s*/i.test(trimmed)) {
      if (currentContent.trim()) pushSegment(currentType, currentContent)
      currentType = 'action'
      currentContent = trimmed.replace(/^Action:\s*/i, '').trim()
    } else if (/^Action Input:\s*/i.test(trimmed)) {
      if (currentContent.trim()) pushSegment(currentType, currentContent)
      currentType = 'action_input'
      currentContent = trimmed.replace(/^Action Input:\s*/i, '').trim()
    } else if (/^Observation:\s*/i.test(trimmed)) {
      if (currentContent.trim()) pushSegment(currentType, currentContent)
      currentType = 'observation'
      currentContent = trimmed.replace(/^Observation:\s*/i, '').trim()
    } else if (/^Final Answer:\s*/i.test(trimmed)) {
      if (currentContent.trim()) pushSegment(currentType, currentContent)
      currentType = 'final_answer'
      currentContent = trimmed.replace(/^Final Answer:\s*/i, '').trim()
    } else {
      if (!currentContent) currentContent = trimmed
      else currentContent += '\n' + trimmed
    }
  }

  // leftover
  if (currentContent.trim()) pushSegment(currentType, currentContent)
  return segments
}

/**
 * SSE connect
 */
function connectToSSE() {
  if (!props.userId || !props.runId) {
    console.log('[AgentSidebar] Missing userId or runId:', { userId: props.userId, runId: props.runId })
    return
  }
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }

  const baseUrl = import.meta.env.VITE_API_URL || ''
  const url = `${baseUrl}/stream/logs?user_id=${props.userId}&run_id=${props.runId}`
  console.log('[AgentSidebar] Connecting to SSE:', url)

  eventSource = new EventSource(url)

  eventSource.onopen = () => {
    console.log('[AgentSidebar] SSE opened successfully')
  }
  eventSource.onerror = (err) => {
    console.error('[AgentSidebar] SSE error:', err)
    if (eventSource.readyState === EventSource.CLOSED) {
      console.log('[AgentSidebar] SSE closed => reconnect in 5s')
      setTimeout(() => connectToSSE(), 5000)
    }
  }

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'connection_established') {
        console.log('[AgentSidebar] SSE connection established')
        return
      }
      if (data.type === 'ping') return

      // normal message
      const messageData = data
      if (!messageData.user_id || !messageData.run_id || !messageData.agent_name) {
        console.log('[AgentSidebar] Missing fields => ignoring:', messageData)
        return
      }
      if (messageData.user_id === props.userId && messageData.run_id === props.runId) {
        if (!firstMessageArrived) {
          firstMessageArrived = true
          collapsed.value = false // auto-expand on first message
        }

        let cleaned = messageData.text
          .replace(/\n{3,}/g, '\n\n')
          .replace(/You ONLY have access.*$/s, '')
          .trim()
        let segs = parseMessage(cleaned)

        messages.value.push({
          agent_name: messageData.agent_name,
          timestamp: messageData.timestamp,
          parsedSegments: segs
        })

        // Auto-scroll #1 (immediate)
        autoScrollToBottom()
      }
    } catch (err) {
      console.error('[AgentSidebar] SSE parse error:', err, 'Raw:', event.data)
    }
  }
}

/**
 * Actually scroll to bottom of the container
 */
function autoScrollToBottom() {
  if (!scrollContainer.value) return
  // nextTick => setTimeout => do scroll
  nextTick(() => {
    setTimeout(() => {
      scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
    }, 50)
  })
}

/**
 * Watch messages => autoScroll #2 (in case SSE immediate wasn't enough)
 */
watch(messages, () => {
  autoScrollToBottom()
})

// Lifecycle
onMounted(() => {
  connectToSSE()
})

onBeforeUnmount(() => {
  if (eventSource) {
    eventSource.close()
  }
})

// watch runId => if changes => reset + reconnect
watch(() => props.runId, (newVal, oldVal) => {
  if (newVal && newVal !== oldVal) {
    messages.value = []
    lastFinalAnswer = ''
    firstMessageArrived = false
    collapsed.value = false
    connectToSSE()
  }
})

// watch userId => reset + reconnect
watch(() => props.userId, (newVal, oldVal) => {
  if (newVal && newVal !== oldVal) {
    messages.value = []
    lastFinalAnswer = ''
    firstMessageArrived = false
    connectToSSE()
  }
})
</script>

<style scoped>
/* The container is "h-screen", ensuring the messages can scroll within "flex-1 overflow-y-auto". */
</style>
