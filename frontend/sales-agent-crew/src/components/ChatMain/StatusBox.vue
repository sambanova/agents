<template>
  
  <!-- 1) If no streaming data, show placeholder -->
  <div
    v-if="!streamingEvents || streamingEvents.length === 0"
    class="p-6 text-center text-gray-500 dark:text-gray-400"
  >
    No streaming events to display.
   
  </div>

  <!-- 2) Otherwise render full timeline + audit log -->
  <div v-else>
    <!-- Tool header & timeline -->
    <div class="flex flex-col p-4 border rounded mb-6">
      <span class="text-md font-bold mb-4">
         <LoadingText
    :isLoading="isLoading"
    text=" Current Tool: {{ currentToolName || '– none –' }}"
    />
       
      </span>
      <div class="flex space-x-6 mb-4">
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
        class="p-3 overflow-y-auto bg-gray-50 dark:bg-gray-800 rounded"
        style="max-height: 150px;"
      >
        {{ description || 'Waiting for stream…' }}
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
import LoadingText from '@/components/ChatMain/LoadingText.vue';

const props = defineProps({
  streamData: { type: Array, default: () => [] },
  streamingEvents: { type: Array, default: () => [] },
  workflowData: { type: Array, default: () => [] },
  isLoading: { type: Boolean, default: false },
})

// helper to pull <tool>NAME</tool>
function extractToolName(content) {
  const m = /<tool>(.*?)<\/tool>/.exec(content)
  return m ? m[1] : ''
}

// 1) tool timeline
const toolTimeline = computed(() =>
  props.streamingEvents
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
const description = computed(() =>
  props.streamingEvents
    .filter(i =>
      ['stream_start', 'llm_stream_chunk', 'stream_complete'].includes(
        i.event
      )
    )
    .map(i => i.content)
    .join('')
)

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

// 5) audit log (with safe `.details`)
const auditLogEvents = computed(() => {
  // synthetic if no streamData but we have workflowData
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

  // otherwise from streamData
  const out = []
  const seenKeys = new Set()
  props.streamingEvents.forEach((evt, idx) => {
    const key = `${evt.event}-${evt.timestamp}`
    if (!seenKeys.has(key)) {
      seenKeys.add(key)
      // safe stringify of content
      let raw = evt.content
      let detail = ''
      if (typeof raw === 'string') {
        detail = raw.length > 100 ? raw.slice(0, 100) + '…' : raw
      } else {
        // object or primitive fallback
        detail = JSON.stringify(raw).slice(0, 100) + '…'
      }
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
</script>

<style scoped>
/* optional styling tweaks */
</style>
