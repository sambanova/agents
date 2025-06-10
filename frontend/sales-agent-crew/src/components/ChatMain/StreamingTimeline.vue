<template>
  <div class="streaming-timeline bg-white rounded-lg p-4">
    <!-- Header with status and controls -->
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center space-x-2">
        <div :class="statusDotClass" class="w-2 h-2 rounded-full"></div>
        <span class="text-sm font-medium text-gray-700">{{ currentStatus }}</span>
        <span class="text-xs text-gray-500">{{ eventCount }} events</span>
      </div>
      
      <div class="flex items-center space-x-2">
        <button
          v-if="timelineItems.length > 0"
          @click="toggleExpandAll"
          class="text-xs text-gray-500 hover:text-gray-700"
        >
          {{ allExpanded ? 'Collapse All' : 'Expand All' }}
        </button>
      </div>
    </div>

    <!-- Compact Timeline -->
    <div class="relative">
      <!-- Timeline line -->
      <div class="absolute left-4 top-0 bottom-0 w-px bg-gray-200"></div>
      
      <!-- Timeline items -->
      <div class="space-y-1">
        <div
          v-for="(item, index) in timelineItems"
          :key="item.id"
          class="relative"
        >
          <!-- Timeline dot/icon -->
          <div
            class="absolute left-0 flex items-center justify-center w-8 h-8 rounded-full z-10"
            :class="getTimelineDotClass(item)"
          >
            <component
              :is="getTimelineIcon(item)"
              class="w-4 h-4 text-white"
            />
          </div>

          <!-- Content area -->
          <div class="ml-12 pb-2">
            <!-- Compact view (always visible) -->
            <div 
              class="flex items-center justify-between py-1 cursor-pointer hover:bg-gray-50 rounded px-2"
              @click="toggleItemExpanded(item.id)"
            >
              <div class="flex items-center space-x-2 flex-1 min-w-0">
                <span class="text-sm font-medium text-gray-700 truncate">
                  {{ item.title }}
                </span>
                <StatusBadge
                  v-if="item.status"
                  :status="item.status"
                  :text="item.status"
                  variant="subtle"
                  :showDot="false"
                />
                <span class="text-xs text-gray-400">{{ formatTime(item.timestamp) }}</span>
              </div>
              
              <ChevronDownIcon
                :class="{ 'rotate-180': expandedItems.includes(item.id) }"
                class="w-4 h-4 text-gray-400 transition-transform"
              />
            </div>

            <!-- Expanded content (conditionally visible) -->
            <div 
              v-if="expandedItems.includes(item.id)"
              class="mt-2 p-3 bg-gray-50 rounded-lg border border-gray-100"
            >
              <!-- Tool call content -->
              <div v-if="item.type === 'tool_call'">
                <div class="mb-2">
                  <span class="text-xs font-medium text-gray-600 uppercase tracking-wide">Input</span>
                  <div class="mt-1 text-sm text-gray-700 bg-white p-2 rounded border">
                    {{ item.input }}
                  </div>
                </div>
                
                <!-- Tool sources (for search results) -->
                <div v-if="item.sources && item.sources.length > 0" class="mt-3">
                  <span class="text-xs font-medium text-gray-600 uppercase tracking-wide">
                    Sources ({{ item.sources.length }})
                  </span>
                  <div class="mt-2 space-y-2">
                    <div
                      v-for="source in item.sources.slice(0, 3)"
                      :key="source.url"
                      class="p-2 bg-white rounded border border-gray-200 hover:border-gray-300 transition-colors"
                    >
                      <div class="flex items-start space-x-2">
                        <img
                          :src="`https://www.google.com/s2/favicons?domain=${new URL(source.url).hostname}`"
                          class="w-4 h-4 mt-0.5 flex-shrink-0"
                          :alt="source.title"
                        />
                        <div class="flex-1 min-w-0">
                          <a
                            :href="source.url"
                            target="_blank"
                            class="text-sm font-medium text-blue-600 hover:text-blue-800 line-clamp-1"
                          >
                            {{ source.title }}
                          </a>
                          <p class="text-xs text-gray-600 mt-1 line-clamp-2">
                            {{ source.snippet }}
                          </p>
                        </div>
                      </div>
                    </div>
                    <button
                      v-if="item.sources.length > 3"
                      class="text-xs text-blue-600 hover:text-blue-800"
                    >
                      Show {{ item.sources.length - 3 }} more sources
                    </button>
                  </div>
                </div>

                <!-- ArXiv papers -->
                <div v-if="item.papers && item.papers.length > 0" class="mt-3">
                  <span class="text-xs font-medium text-gray-600 uppercase tracking-wide">
                    Papers ({{ item.papers.length }})
                  </span>
                  <div class="mt-2 space-y-2">
                    <div
                      v-for="paper in item.papers.slice(0, 2)"
                      :key="paper.title"
                      class="p-2 bg-white rounded border border-gray-200"
                    >
                      <h4 class="text-sm font-medium text-gray-900 line-clamp-1">{{ paper.title }}</h4>
                      <p class="text-xs text-gray-600 mt-1">{{ paper.authors }}</p>
                      <p class="text-xs text-gray-500 mt-1 line-clamp-2">{{ paper.summary }}</p>
                    </div>
                  </div>
                </div>

                <!-- Code execution output -->
                <div v-if="item.output" class="mt-3">
                  <span class="text-xs font-medium text-gray-600 uppercase tracking-wide">Output</span>
                  <div class="mt-1 p-2 bg-gray-900 text-green-400 text-xs rounded font-mono">
                    <pre class="whitespace-pre-wrap">{{ item.output }}</pre>
                  </div>
                </div>
              </div>

              <!-- LLM content -->
              <div v-else-if="item.type === 'llm_chunk'">
                <div class="text-sm text-gray-700 whitespace-pre-wrap">{{ item.content }}</div>
              </div>

              <!-- Agent completion -->
              <div v-else-if="item.type === 'agent_completion'">
                <div class="text-sm text-gray-700">{{ item.content }}</div>
              </div>

              <!-- Raw data (for debugging) -->
              <div v-else>
                <span class="text-xs font-medium text-gray-600 uppercase tracking-wide">Data</span>
                <pre class="mt-1 text-xs text-gray-600 bg-white p-2 rounded border overflow-x-auto">{{ JSON.stringify(item.data, null, 2) }}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Current streaming indicator -->
      <div v-if="isStreaming" class="relative">
        <div class="absolute left-0 flex items-center justify-center w-8 h-8">
          <div class="w-3 h-3 bg-blue-500 rounded-full animate-pulse"></div>
        </div>
        <div class="ml-12 py-1">
          <span class="text-sm text-gray-500 italic">Processing...</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useStreamingParser } from '@/composables/useStreamingParser'
import { useTimelineManager } from '@/composables/useTimelineManager'
import StatusBadge from '@/components/Common/StatusBadge.vue'

// Icons
import {
  ChevronDownIcon,
  MagnifyingGlassIcon,
  DocumentTextIcon,
  CodeBracketIcon,
  CheckCircleIcon,
  ClockIcon,
  ChatBubbleLeftRightIcon,
  ExclamationTriangleIcon
} from '@heroicons/vue/24/outline'

const props = defineProps({
  conversationId: {
    type: String,
    default: ''
  },
  messageId: {
    type: String,
    required: true
  },
  provider: {
    type: String,
    default: 'sambanova'
  },
  streamingData: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['timeline-complete', 'tool-executed'])

// State
const timelineItems = ref([])
const expandedItems = ref([])
const allExpanded = ref(false)
const isStreaming = ref(false)

// Composables
const streamingParser = useStreamingParser()
const timelineManager = useTimelineManager()

// Computed properties
const eventCount = computed(() => timelineItems.value.length)

const currentStatus = computed(() => {
  if (isStreaming.value) return 'Processing'
  if (timelineItems.value.length === 0) return 'Starting'
  
  const lastItem = timelineItems.value[timelineItems.value.length - 1]
  if (lastItem.type === 'stream_complete') return 'Response Complete'
  if (lastItem.type === 'error') return 'Error'
  return 'In Progress'
})

const statusDotClass = computed(() => {
  if (isStreaming.value) return 'bg-blue-500 animate-pulse'
  
  const status = currentStatus.value
  if (status === 'Response Complete') return 'bg-green-500'
  if (status === 'Error') return 'bg-red-500'
  return 'bg-yellow-500'
})

// Timeline display methods
const getTimelineDotClass = (item) => {
  const classes = {
    'stream_start': 'bg-blue-500',
    'tool_call': 'bg-purple-500',
    'tool_response': 'bg-green-500',
    'llm_chunk': 'bg-orange-500',
    'agent_completion': 'bg-green-600',
    'stream_complete': 'bg-gray-500',
    'error': 'bg-red-500'
  }
  return classes[item.type] || 'bg-gray-400'
}

const getTimelineIcon = (item) => {
  const icons = {
    'stream_start': ClockIcon,
    'tool_call': getToolIcon(item.toolName),
    'tool_response': CheckCircleIcon,
    'llm_chunk': ChatBubbleLeftRightIcon,
    'agent_completion': CheckCircleIcon,
    'stream_complete': CheckCircleIcon,
    'error': ExclamationTriangleIcon
  }
  return icons[item.type] || ChatBubbleLeftRightIcon
}

const getToolIcon = (toolName) => {
  const toolIcons = {
    'search_tavily': MagnifyingGlassIcon,
    'arxiv': DocumentTextIcon,
    'DaytonaCodeSandbox': CodeBracketIcon,
    'wikipedia': DocumentTextIcon
  }
  return toolIcons[toolName] || MagnifyingGlassIcon
}

const formatTime = (timestamp) => {
  return new Date(timestamp).toLocaleTimeString([], { 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit'
  })
}

// Timeline interaction methods
const toggleItemExpanded = (itemId) => {
  const index = expandedItems.value.indexOf(itemId)
  if (index > -1) {
    expandedItems.value.splice(index, 1)
  } else {
    expandedItems.value.push(itemId)
  }
}

const toggleExpandAll = () => {
  if (allExpanded.value) {
    expandedItems.value = []
    allExpanded.value = false
  } else {
    expandedItems.value = timelineItems.value.map(item => item.id)
    allExpanded.value = true
  }
}

// Stream processing methods
const handleStreamingMessage = async (data) => {
  const { event } = data
  
  switch (event) {
    case 'stream_start':
      handleStreamStart(data)
      break
    case 'llm_stream_chunk':
      await handleLLMChunk(data)
      break
    case 'agent_completion':
      handleAgentCompletion(data)
      break
    case 'stream_complete':
      handleStreamComplete(data)
      break
    default:
      console.log('Unknown event type:', event)
  }
}

const handleStreamStart = (data) => {
  isStreaming.value = true
  timelineItems.value = [] // Clear previous items
}

const handleLLMChunk = async (data) => {
  const { content } = data
  if (!content) return

  // Parse for tool calls
  const toolCall = streamingParser.parseToolCall(content)
  
  if (toolCall) {
    await handleToolCall(toolCall, data)
  } else {
    // Regular LLM content - find or create chunk item
    let chunkItem = timelineItems.value.find(item => item.type === 'llm_chunk')
    
    if (chunkItem) {
      chunkItem.content += content
    } else {
      const item = timelineManager.createTimelineItem({
        type: 'llm_chunk',
        title: 'AI Response',
        content: content,
        data: data,
        timestamp: data.timestamp || new Date().toISOString()
      })
      timelineItems.value.push(item)
    }
  }
}

const handleToolCall = async (toolCall, originalData) => {
  const { toolName, input } = toolCall
  
  const toolCallItem = timelineManager.createTimelineItem({
    type: 'tool_call',
    title: `${toolName.replace('_', ' ')} Search`,
    toolName,
    input,
    status: 'executing',
    data: originalData,
    timestamp: originalData.timestamp || new Date().toISOString()
  })
  
  timelineItems.value.push(toolCallItem)
  emit('tool-executed', { toolName, input })
}

const handleAgentCompletion = (data) => {
  const { type, content, name: toolName } = data
  
  if (type === 'LiberalFunctionMessage' && toolName) {
    // Tool response
    handleToolResponse(data)
  } else {
    // Regular agent completion
    handleStreamComplete(data)
  }
}

const handleToolResponse = (data) => {
  const { name: toolName, content } = data
  
  // Find the corresponding tool call item
  const toolCallItem = timelineItems.value
    .slice()
    .reverse()
    .find(item => item.type === 'tool_call' && item.toolName === toolName)
  
  if (toolCallItem) {
    toolCallItem.status = 'completed'
    toolCallItem.response = content
    
    // Handle tool-specific response processing
    handleToolResponseSpecific(toolName, content, toolCallItem)
  }
}

const handleToolResponseSpecific = (toolName, content, toolCallItem) => {
  switch (toolName) {
    case 'search_tavily':
      handleTavilyResponse(content, toolCallItem)
      break
    case 'arxiv':
      handleArxivResponse(content, toolCallItem)
      break
    case 'DaytonaCodeSandbox':
      handleSandboxResponse(content, toolCallItem)
      break
  }
}

const handleTavilyResponse = (content, toolCallItem) => {
  try {
    const results = Array.isArray(content) ? content : JSON.parse(content)
    toolCallItem.sources = results.map(result => ({
      title: result.title || 'Untitled',
      url: result.url || '#',
      content: result.content || '',
      snippet: (result.content || '').substring(0, 150) + '...'
    }))
    toolCallItem.sourceCount = results.length
  } catch (error) {
    console.error('Error parsing Tavily response:', error)
  }
}

const handleArxivResponse = (content, toolCallItem) => {
  try {
    const papers = typeof content === 'string' ? content.split('\n\n') : content
    toolCallItem.papers = papers.filter(paper => paper.trim()).map(paper => {
      const titleMatch = paper.match(/Title: (.+)/)
      const authorsMatch = paper.match(/Authors: (.+)/)
      const summaryMatch = paper.match(/Summary: (.+)/)
      
      return {
        title: titleMatch ? titleMatch[1] : 'Unknown Title',
        authors: authorsMatch ? authorsMatch[1] : 'Unknown Authors',
        summary: summaryMatch ? summaryMatch[1] : paper.substring(0, 150) + '...'
      }
    })
  } catch (error) {
    console.error('Error parsing arXiv response:', error)
  }
}

const handleSandboxResponse = (content, toolCallItem) => {
  toolCallItem.output = content
}

const handleStreamComplete = (data) => {
  isStreaming.value = false
  emit('timeline-complete', timelineItems.value)
}

// Watch for streaming data changes
watch(() => props.streamingData, (newData) => {
  // Process each streaming event
  newData.forEach(messageEvent => {
    handleStreamingMessage(messageEvent.data)
  })
}, { deep: true })

// Lifecycle
onMounted(() => {
  // Process any existing streaming data
  if (props.streamingData.length > 0) {
    props.streamingData.forEach(messageEvent => {
      handleStreamingMessage(messageEvent.data)
    })
  }
})
</script>

<style scoped>
.line-clamp-1 {
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
}

.line-clamp-2 {
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}
</style> 