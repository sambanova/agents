<template>
  <div
    class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700
           p-2 rounded-lg max-h-[200px] w-full flex flex-col overflow-hidden"
  >
    <!-- Top: sliding two-letter window over the title -->
    <div class="py-4 h-10 flex items-center overflow-hidden dark:text-white">
      <span
        v-for="(char, idx) in textChars"
        :key="idx"
        :class="[
          'transition-opacity duration-500',
          // if not loading, force full opacity; otherwise highlight only the active pair
          !props.isLoading
            ? 'opacity-100'
            : isActive(idx)
              ? 'opacity-100'
              : 'opacity-40'
        ]"
      >
        {{ char }}
      </span>
    </div>

    <!-- Log area: shows the evolving content -->
    <div
      ref="logRef"
      class="flex-1 text-gray-400 dark:text-gray-300 py-2 overflow-y-auto
             space-y-1 text-sm"
    >
      <div v-for="(line, i) in logLines" :key="i">
        {{ line }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  title: {
    type: String,
    default: ''
  },
  content: {
    type: String,
    default: ''
  },
  isLoading: {
    type: Boolean,
    default: false
  }
})

// Split title into characters
const textChars = computed(() => props.title.split(''))

// Index for the two-letter window
const pairIndex = ref(0)
let pairInterval = null

function startAnimation() {
  if (pairInterval !== null) return
  pairInterval = setInterval(() => {
    pairIndex.value = (pairIndex.value + 2) % textChars.value.length
  }, 150)
}

function stopAnimation() {
  clearInterval(pairInterval)
  pairInterval = null
}

// Watch isLoading: start when true, stop when false
watch(
  () => props.isLoading,
  (loading) => {
    if (loading) startAnimation()
    else stopAnimation()
  },
  { immediate: true }
)

onUnmounted(stopAnimation)

function isActive(idx) {
  return (
    idx === pairIndex.value ||
    idx === (pairIndex.value + 1) % textChars.value.length
  )
}

const logLines = computed(() =>
  props.content.split('\n').filter(line => line !== '')
)

const logRef = ref(null)
watch(
  () => props.content,
  async () => {
    await nextTick()
    if (logRef.value) {
      logRef.value.scrollTo({
        top: logRef.value.scrollHeight,
        behavior: 'smooth'
      })
    }
  }
)


const currentStreamingStatus = computed(() => {
  if (!props.streamingEvents || props.streamingEvents.length === 0) {
    // For loaded conversations, show completion status if we have workflow data
    if (props.workflowData && props.workflowData.length > 0) {
      return 'Response complete';
    }
    return 'Starting...';
  }
  
  const events = props.streamingEvents
  let currentTool = null
  let toolQuery = null
  
  // Process events chronologically to find the LATEST completion status
  let latestCompletionStatus = null
  
  for (let i = 0; i < events.length; i++) {
    const event = events[i]
    const data = event.data
    
    // Track current tool calls
    if (event.event === 'llm_stream_chunk' && data.content && data.content.includes('<tool>')) {
      const toolMatch = data.content.match(/<tool>([^<]+)<\/tool>/)
      const inputMatch = data.content.match(/<tool_input>([^<\n\r]+)/)
      
      if (toolMatch) {
        currentTool = toolMatch[1]
        toolQuery = inputMatch ? inputMatch[1].trim() : null
      }
    }
    
    // Update latest completion status when we find tool results
    if (event.event === 'agent_completion' && data.type === 'LiberalFunctionMessage' && data.name) {
      if (data.name === 'search_tavily' && Array.isArray(data.content)) {
        const resultCount = data.content.length
        const sources = data.content.slice(0, 3)
        const sourceNames = sources.map(source => {
          if (source.title && source.title.trim()) {
            return source.title.trim()
          } else if (source.url) {
            try {
              return new URL(source.url).hostname.replace('www.', '')
            } catch {
              return source.url
            }
          }
          return 'Unknown source'
        })
        
        let status = `✅ Found ${resultCount} web sources`
        if (sourceNames.length > 0) {
          status += `\n• ${sourceNames.join('\n• ')}`
          if (resultCount > 3) status += `\n• and ${resultCount - 3} more...`
        }
        latestCompletionStatus = status
      } else if (data.name === 'arxiv') {
        const papers = data.content && data.content.includes('Title:') ? 
          data.content.split('Title:').length - 1 : 1
        
        const titleMatches = data.content.match(/Title: ([^\n]+)/g)
        let status = `✅ Found ${papers} arXiv papers`
        if (titleMatches) {
          const titles = titleMatches.slice(0, 2).map(t => t.replace('Title: ', '').trim())
          status += `\n• ${titles.join('\n• ')}`
          if (titleMatches.length > 2) status += `\n• and ${titleMatches.length - 2} more...`
        }
        latestCompletionStatus = status
      } else if (data.name === 'DaytonaCodeSandbox') {
        latestCompletionStatus = `✅ Code execution complete\n• Generated charts and analysis`
      }
    }
  }
  
  // Return latest completion status if we have one
  if (latestCompletionStatus) {
    return latestCompletionStatus
  }
  
  // Check if we're streaming response
  for (let i = events.length - 1; i >= 0; i--) {
    const event = events[i]
    const data = event.data
    
    if (event.event === 'llm_stream_chunk' && 
        data.content && 
        data.content.trim() && 
        !data.content.includes('<tool>')) {
      return '📝 Streaming response...'
    }
  }
  
  // Return current tool status if we have one and no completion
  if (currentTool) {
    if (currentTool === 'search_tavily') {
      return `🔍 Searching web: "${toolQuery || 'query'}"`
    } else if (currentTool === 'arxiv') {
      return `📚 Searching arXiv: "${toolQuery || 'query'}"`
    } else if (currentTool === 'DaytonaCodeSandbox') {
      return `⚡ Executing code in sandbox`
    } else {
      return `🔧 Using ${currentTool.replace('_', ' ')}: "${toolQuery || 'executing'}"`
    }
  }
  
  // Check if we're done
  const lastEvent = events[events.length - 1]
  if (lastEvent?.event === 'stream_complete' || 
      (lastEvent?.event === 'agent_completion' && lastEvent.data.agent_type === 'react_end')) {
    return '✅ Response complete'
  }
  
  return '💭 Processing...'
})
</script>