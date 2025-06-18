<template>
{{ props.streamData }}
<div class="max-w-4xl mx-auto">
    <!-- Collapsible Header -->
    <button
      @click="isOpen = !isOpen"
      class="w-full flex items-center justify-start p-3 0 dark:bg-gray-800 rounded-md focus:outline-none"
    >
      <span class="text-md text-primary-brandTextSecondary dark:text-gray-100">
        Analysis Conculed
      </span>
      <svg
        :class="{'transform rotate-180': isOpen}"
        class="w-5 h-5 text-gray-600 dark:text-gray-400 transition-transform duration-200"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <!-- Collapsible Body -->
    <transition
      enter-active-class="transition ease-out duration-200"
      enter-from-class="opacity-0 max-h-0"
      enter-to-class="opacity-100 max-h-screen"
      leave-active-class="transition ease-in duration-150"
      leave-from-class="opacity-100 max-h-screen"
      leave-to-class="opacity-0 max-h-0"
    >
      <div v-show="isOpen" class="mt-2 space-y-4 p-4 border rounded-md bg-white dark:bg-gray-900">
        <!-- Your existing content starts here -->
        <TimeLineAssitance/>


         <!-- Comprehensive Audit Log -->
    <div
      
      class="p-3 dark:bg-gray-700 border-b dark:border-gray-600 max-h-96 overflow-y-auto"
    >
      <div class="text-xs font-medium text-gray-600 dark:text-gray-300 mb-3">
        Comprehensive Audit Log
      </div>
      <div class="relative space-y-3 pl-6">
        <div
          v-for="(event, idx) in auditLogEvents"
          :key="event.id"
          class="relative"
        >
          <!-- dot -->
          <div
            class="absolute left-0 top-0 w-3 h-3 bg-[#EAECF0] dark:bg-white rounded-full"
          ></div>
          <!-- connector line (all but last) -->
          <div
            v-if="idx < auditLogEvents.length - 1"
            class="absolute left-1.5 top-5 bottom-0 border-l-2 border-gray-200 dark:border-gray-600"
          ></div>

          <div class="flex items-start space-x-2 ml-6">
            <div class="flex-1">
              <div class="flex justify-between">
                <span class="text-xs font-medium text-gray-900 dark:text-gray-100">
                  {{ event.title }}
                </span>
                <span class="text-xs text-gray-400 dark:text-gray-500">
                  {{ formatEventTime(event.timestamp) }}
                </span>
              </div>
              <div
                v-if="event.details"
                class="text-xs text-gray-600 dark:text-gray-400 mt-1"
              >
                {{ event.details }}
              </div>
              <div
                v-if="event.subItems?.length"
                class="mt-2 ml-4 space-y-1 text-xs text-gray-600 dark:text-gray-400"
              >
                <div
                  v-for="sub in event.subItems"
                  :key="sub.id"
                  class="flex items-start space-x-1"
                >
                  <span>•</span>
                  <span>
                    {{ sub.title }}
                    <span v-if="sub.domain">({{ sub.domain }})</span>
                  </span>
                </div>
              </div>
              <div class="text-xs text-gray-400 dark:text-gray-600 mt-1">
                <span class="bg-gray-100 dark:bg-gray-600 px-1 rounded">{{ event.event }}</span>
                <span
                  v-if="event.type"
                  class="bg-blue-100 dark:bg-blue-600 px-1 rounded ml-1"
                >{{ event.type }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
        <div v-if="props.workflowData && props.workflowData.length > 0" class="w-full p-2 mx-auto">
          <div class="flex my-2">
            <div class="flex space-x-4">
              <WorkflowDataItem :workflowData="props.workflowData" />
            </div>
          </div>
        </div>

        <div class="flex flex-wrap gap-2">
          <a
            v-for="src in allSources"
            :key="src.url + src.title"
            :href="src.url"
            target="_blank"
            rel="noopener"
            class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium 
                   bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200
                   hover:bg-blue-200 dark:hover:bg-blue-800 transition"
          >
            <span v-if="src.type==='link'" class="mr-1">🌐</span>
            <span v-else-if="src.type==='arxiv'" class="mr-1">📚</span>
            {{ src.title }}
          </a>
        </div>
        <!-- Your existing content ends here -->

  
      </div>

     
    </transition>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick, watchEffect } from 'vue'
import LoadingText from '@/components/ChatMain/LoadingText.vue'
import { marked } from 'marked'
import AnalysisTimeline from '@/components/ChatMain/AnalysisTimeline.vue'
import WorkflowDataItem from '@/components/ChatMain/WorkflowDataItem.vue'
import TimeLineAssitance from '@/components/ChatMain/TimeLineAssitance.vue'
import MetaDataH from '@/components/ChatMain/MetaDataH.vue'

const isOpen = ref(false)
const props = defineProps({
  streamData: { type: Array, default: () => [] },
  streamingEvents: { type: Array, default: () => [] },
  workflowData: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
    plannerText: {
    type: String,
    required: true,
  },
  metadata: {
    type: Object,
    required: true,
  },
  provider: {
    type: String,
    required: true,
  },
  messageId: {
    type: String,
    required: true,
  },

   
})


  function   renderMarkdown(mdText) {
  // marked.parse(...) converts Markdown → safe-ish HTML
  return marked.parse(mdText)
}
  

const isCurrentlyStreaming = computed(() => {
  if (!props.streamingEvents || props.streamingEvents.length === 0) return true
  
  const lastEvent = props.streamingEvents[props.streamingEvents.length - 1]
  return lastEvent.event !== 'stream_complete'
})

const hasCompletedEvents = computed(() => {
  if (!props.streamingEvents || props.streamingEvents.length === 0) {
    // For loaded conversations, check if we have any tool-related or completion events
    if (props.workflowData && props.workflowData.length > 0) return true;
    if (props.metadata && Object.keys(props.metadata).length > 0) return true;
    return false;
  }
  
  // Check for any completed tool executions, final responses, or tool-related events
  return props.streamingEvents.some(event => 
    (event.event === 'agent_completion' && event.data.type === 'LiberalFunctionMessage') ||
    (event.event === 'agent_completion' && event.data.name === 'DaytonaCodeSandbox') ||
    (event.event === 'agent_completion' && event.data.name === 'search_tavily') ||
    (event.event === 'agent_completion' && event.data.name === 'arxiv') ||
    (event.event === 'stream_complete') ||
    (event.event === 'agent_completion' && event.data.agent_type === 'react_end') ||
    (event.isToolRelated || event.isDaytonaRelated) || // Check our custom flags
    event.event === 'agent_completion' || event.event === 'stream_complete'
  )
})


// helper to pull <tool>NAME</tool>
function extractToolName(content) {
  const m = /<tool>(.*?)<\/tool>/.exec(content)
  return m ? m[1] : ''
}

// 1) tool timeline
const toolTimeline = computed(() =>
  props.streamData
    .filter(
      i =>
        i.event === 'agent_completion' &&
        i.additional_kwargs?.agent_type === 'react_tool'
    )
    .map(i => extractToolName(i.content))
)

// 2) current tool
const currentToolName = computed(() =>
  toolTimeline.value.length
    ? toolTimeline.value[toolTimeline.value.length - 1]
    : ''
)

// 3) description


const description = computed(() => {
 return props.streamData
    .filter(i =>
      i.content && ['stream_start', 'llm_stream_chunk', 'stream_complete'].includes(
        i.event
      )&&!(i?.content.includes('<tool>')||i?.content.includes('< tool>'))
    )
    .map(i => i.content)
    .join(' ')
})



// auto‐scroll description
const descContainer = ref(null)
watch(description, () => {
  nextTick(() => {
    if (descContainer.value) {
      descContainer.value.scrollTop = descContainer.value.scrollHeight
    }
  })
})

// 4) tool sources
const toolSources = computed(() => {
  const sources = []
  props.streamingEvents.forEach(event => {
    if (event.name === 'search_tavily' && Array.isArray(event.content)) {
      event.content.forEach(src => {
        let title = src.title?.trim() || ''
        let domain = ''
        if (!title && src.url) {
          try {
            domain = new URL(src.url).hostname.replace('www.', '')
            title = domain
          } catch {}
        }
        sources.push({
          title: title || 'Untitled',
          domain,
          url: src.url || '',
          type: 'web'
        })
      })
    }
    // extend for arxiv if needed…
  })
  return sources.slice(0, 5)
})



function formatEventTime(ts) {
  return new Date(ts).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit'
  })
}
const loading = ref(null)

// watch(
//   () => props.loading,
//   (newVal, oldVal) => {
//     console.log('⚡ loading changed:', oldVal, '→', newVal)
//   }
// )


watch(props.loading, () => {
  nextTick(() => {
   
      console.console.log(("loading changed",loading));
      
    
  })
})

const latestToolAction = computed(() => {
  // 1) Grab only the react_tool completions
  const calls = props.streamData.filter(i =>
    i.event === 'agent_completion' &&
    i.agent_type === 'react_tool' &&
    typeof i.content === 'string'
  )
  if (!calls.length) return ''

  // 2) Take the very last one
  const lastContent = calls[calls.length - 1].content

  // 3) Extract <tool>…</tool>
  const toolMatch  = lastContent.match(/<\s*tool>([\s\S]*?)<\/\s*tool>/i)
  // 4) Extract <tool_input>…</tool_input>
  const inputMatch = lastContent.match(/<\s*tool_input>([\s\S]*?)<\/\s*tool_input>/i)

  if (!toolMatch) return ''   // no tool tag → bail

  // 5) Normalize the name: replace underscores with spaces
  const rawName  = toolMatch[1].trim()              // e.g. "search_tavily"
  const toolName = rawName.replace(/_/g, ' ')       // → "search tavily"

  // 6) Pull out the explanation
  const explanation = inputMatch ? inputMatch[1].trim() : ''

  // 7) Format as "Tool Name: Explanation"
  return {toolName:toolName,explanation: explanation}
})




const allSources = computed(() => {
  const items = []
  const seen  = new Set()

  const pushIfNew = src => {
    if (!src.url || seen.has(src.url)) return
    seen.add(src.url)
    items.push(src)
  }

  function extractLinks(text, type = 'link') {
    if (!text) return
    let m

    // JSON-array
    if (text.trim().startsWith('[')) {
      try {
        const arr = JSON.parse(
          text.replace(/'url'/g, '"url"')
        )
        if (Array.isArray(arr)) {
          arr.forEach(o => {
            if (o.url) {
              const domain = new URL(o.url).hostname.replace(/^www\./,'')
              pushIfNew({
                title: o.title?.trim() || domain,
                url: o.url,
                domain,
                type,
              })
            }
          })
          return
        }
      } catch {}
    }

    // Named lines
    const nameRe = /([^:*]+):\s*(https?:\/\/\S+)/g
    while ((m = nameRe.exec(text))) {
      const url = m[2].trim()
      const domain = new URL(url).hostname.replace(/^www\./,'')
      pushIfNew({ title: m[1].trim(), url, domain, type })
    }

    // Python style
    const pyRe = /'url':\s*'(https?:\/\/[^']+)'/g
    while ((m = pyRe.exec(text))) {
      const url = m[1].trim()
      const domain = new URL(url).hostname.replace(/^www\./,'')
      pushIfNew({ title: domain, url, domain, type })
    }

    // Plain URLs
    const urlRe = /(https?:\/\/[^\s"'<>]+)/g
    while ((m = urlRe.exec(text))) {
      const url = m[1].trim()
      const domain = new URL(url).hostname.replace(/^www\./,'')
      pushIfNew({ title: domain, url, domain, type })
    }
  }

  // main message (if any)
  extractLinks(props.data?.content, 'link')

  // each streamData item
  props.streamData.forEach(evt => {
    const txt = evt.data?.content
    if (typeof txt === 'string') extractLinks(txt, 'link')
  })

  // merge in toolSources
  toolSources.value.forEach(src => pushIfNew(src))

  return items
})




// 5) audit log with safe stringify
const auditLogEvents = computed(() => {
  // synthetic if no streamingEvents but we have workflowData
  if ((!props.streamData || !props.streamData.length) && props.workflowData.length) {

    alert("steaming ")
    const unique = []
    const seen = new Set()
    props.workflowData.forEach((w, i) => {
      const key = `${w.agent_name}-${w.task}-${w.tool_name}`
      if (!seen.has(key)) {
        seen.add(key)
        unique.push({
          id: `synthetic-${i}`,
          title: `✅ ${w.agent_name} – ${w.task}`,
          details: w.tool_name ? `Tool: ${w.tool_name}` : 'Completed',
          subItems: [],
          event: 'workflow_item',
          type: 'tool_result',
          timestamp: new Date().toISOString()
        })
      }
    })
    return unique
  }




  // otherwise from streamingEvents
  const out = []
  const seenKeys = new Set()
  props.streamData.forEach((evt, idx) => {
    const key = `${evt.event}-${evt.timestamp}`
    if (!seenKeys.has(key)) {
      seenKeys.add(key)

      // SAFELY stringify or fallback
      let raw = evt.content
      let serialized = JSON.stringify(raw)
      if (serialized === undefined) {
        serialized = String(raw ?? '')
      }

      // truncate to 100 chars
      const detail = serialized.length > 100
        ? serialized.slice(0, 100) + '…'
        : serialized

      out.push({
        id: `audit-${idx}`,
        title: evt.event,
        details: detail,
        subItems: [],
        event: evt.event,
        type: 'info',
        timestamp: evt.timestamp
      })
    }
  })
  return out
})


const showAuditLog = ref(false)

function toggleAuditLog() {
  showAuditLog.value = !showAuditLog.value
}

</script>

<style scoped>
/* Styling for headings (lines ending with a colon) */
.md-heading {
  color: #101828;
  font-family: 'Inter', sans-serif;
  font-weight: 600; /* Semibold */
  font-size: 16px;
  line-height: 24px;
  letter-spacing: 0;
  margin-bottom: 1rem;
  text-align: left;
}

/* Styling for normal paragraphs */
.md-paragraph {
  color: #101828;
  font-family: 'Inter', sans-serif;
  font-weight: 400;
  font-size: 16px;
  line-height: 24px;
  letter-spacing: 0;
  /* margin-bottom: 1rem; */
}

/* Remove default list styles */
.markdown-content ul {
  list-style: none;
  padding: 0;
  margin-bottom: 1rem;
}

/* Styling for bullet list items */
.custom-bullet {
  display: flex;
  align-items: center;
  font-family: 'Inter', sans-serif;
  font-weight: 600;
  font-size: 16px;
  line-height: 24px;
  letter-spacing: 0;
  color: #101828;
  margin-bottom: 0.5rem;
  position: relative;
  padding-right: 1.5rem; /* Reserve space for the inline bullet marker */
}

/* Inline bullet marker positioned on the right */
.bullet-marker {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  color: #101828;
  font-weight: 600;
  font-size: 32px;
  line-height: 24px;
  letter-spacing: 0;
  margin-left: 0.5rem;
}

p{
  line-height: 24px;
}



</style>