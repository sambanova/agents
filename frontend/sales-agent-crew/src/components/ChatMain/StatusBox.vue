<template>
  
  <!-- 1) If no streaming data, show placeholder -->
  <!-- <div
   
    class="p-6 text-center text-gray-500 dark:text-gray-400"
  >
    No streaming events to display.
  </div> -->

  <!-- 2) Otherwise render full timeline + audit log -->
  <div>
    <!-- Tool header & timeline -->
    <div class="flex flex-col p-4 border rounded mb-2">
      <span class="text-md  mb-2">
        <LoadingText
          v-if="props.isLoading"
        :key="props.isLoading"
          :isLoading="props.isLoading"
         :text="latestToolAction?.toolName || 'Thinking'"  
        />{{latestToolAction?.explanation}}
      </span>
      <div class="flex space-x-6 mb-2">
        <div
          v-for="(tool, idx) in toolTimeline"
          :key="idx"
          class="relative pl-4 text-gray-700"
        >
          <div
            class="absolute left-0 top-1/2 w-2 h-2 rounded-full border-2 border-gray-500 bg-white transform -translate-y-1/2"
          ></div>
          {{ tool }}
        </div>
      </div>
      <div
        ref="descContainer"
        class="p-2 overflow-y-auto bg-white dark:bg-gray-800 rounded"
        style="max-height: 150px;"
      >
        <!-- {{ description || 'Waiting for stream…' }} -->
                   <div class="markdown-content" v-html="renderMarkdown(description||'')"></div>

      </div>
    </div>

    <!-- Tool sources -->
    <div v-if="toolSources.length" class="px-4 py-2 mb-6">
      <div class="flex flex-wrap gap-2">
        <a
          v-for="src in toolSources"
          :key="src.url || src.title"
          :href="src.url"
          target="_blank"
          class="inline-flex items-center gap-1 px-2 py-1 bg-gray-50 dark:bg-gray-700 border dark:border-gray-600 rounded text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 transition"
        >
          <span v-if="src.type === 'web'">🌐</span>
          <span v-else-if="src.type === 'arxiv'">📚</span>
          <span class="truncate max-w-[120px]">{{ src.title }}</span>
        </a>
      </div>
    </div>

    <!-- Comprehensive Audit Log -->
    <div class="p-3 dark:bg-gray-700 border-b dark:border-gray-600 max-h-96 overflow-y-auto">
      <div class="text-xs font-medium text-gray-600 dark:text-gray-300 mb-3">
        Comprehensive Audit Log
      </div>
      <div class="relative space-y-3 pl-6">
        <div
          v-for="(event, idx) in auditLogEvents"
          :key="event.id"
          class="relative"
        >
          <div
            class="absolute left-0 top-0 w-3 h-3 bg-[#EAECF0] dark:bg-white rounded-full"
          ></div>
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
                <span class="bg-gray-100 dark:bg-gray-600 px-1 rounded"
                  >{{ event.event }}</span
                >
                <span
                  v-if="event.type"
                  class="bg-blue-100 dark:bg-blue-600 px-1 rounded ml-1"
                  >{{ event.type }}</span
                >
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import LoadingText from '@/components/ChatMain/LoadingText.vue'
import { marked } from 'marked'

const props = defineProps({
  streamData: { type: Array, default: () => [] },
  streamingEvents: { type: Array, default: () => [] },
  workflowData: { type: Array, default: () => [] },
  isLoading: { type: Boolean, default: false },
   
})


  function   renderMarkdown(mdText) {
  // marked.parse(...) converts Markdown → safe-ish HTML
  return marked.parse(mdText)
}
  

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
      ['stream_start', 'llm_stream_chunk', 'stream_complete'].includes(
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

// 5) audit log with safe stringify
const auditLogEvents = computed(() => {
  // synthetic if no streamingEvents but we have workflowData
  if ((!props.streamingEvents || !props.streamingEvents.length) && props.workflowData.length) {
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
  props.streamingEvents.forEach((evt, idx) => {
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

function formatEventTime(ts) {
  return new Date(ts).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit'
  })
}

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