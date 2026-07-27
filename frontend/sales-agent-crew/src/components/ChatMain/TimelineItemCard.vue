<template>
  <div
    class="timeline-item-card bg-white border rounded-lg shadow-sm hover:shadow-md transition-all duration-200"
    :class="getCardClass(item)"
  >
    <!-- Card Header -->
    <div class="flex items-center justify-between p-4 border-b bg-gray-50 rounded-t-lg">
      <div class="flex items-center space-x-3">
        <div
          class="flex items-center justify-center w-8 h-8 rounded-full"
          :class="getStatusClass(item.status)"
        >
          <component
            :is="getStatusIcon(item.status)"
            class="w-4 h-4 text-white"
          />
        </div>
        <div>
          <h3 class="font-medium text-gray-900">{{ item.title }}</h3>
          <p class="text-sm text-gray-500">{{ formatTimestamp(item.timestamp) }}</p>
        </div>
      </div>
      <div class="flex items-center space-x-2">
        <span
          class="px-2 py-1 text-xs font-medium rounded-full"
          :class="getTypeClass(item.type)"
        >
          {{ formatType(item.type) }}
        </span>
        <button
          @click="$emit('toggle-expand')"
          class="p-1 text-gray-400 hover:text-gray-600 rounded"
        >
          <ChevronDownIcon
            :class="{ 'transform rotate-180': isExpanded }"
            class="w-5 h-5 transition-transform"
          />
        </button>
      </div>
    </div>

    <!-- Card Content -->
    <div class="p-4">
      <!-- Tool Call Content -->
      <div v-if="item.type === 'tool_call'" class="space-y-3">
        <div class="flex items-center space-x-2">
          <component
            :is="getToolIcon(item.toolName)"
            class="w-5 h-5 text-blue-600"
          />
          <span class="font-medium text-gray-900">{{ item.toolName }}</span>
          <StatusBadge :status="item.status" />
        </div>

        <!-- Tool Input -->
        <div v-if="item.input" class="bg-gray-50 rounded p-3">
          <div class="text-sm font-medium text-gray-700 mb-1">Input:</div>
          <div class="text-sm text-gray-900">
            <pre v-if="isCodeInput(item.toolName)" class="whitespace-pre-wrap">{{ item.input }}</pre>
            <span v-else>{{ formatToolInput(item.toolName, item.input) }}</span>
          </div>
        </div>

        <!-- Search-specific UI -->
        <div v-if="isSearchTool(item.toolName) && item.sources" class="space-y-2">
          <div class="text-sm font-medium text-gray-700">
            Found {{ item.sourceCount || item.sources.length }} sources:
          </div>
          <div class="space-y-2">
            <div
              v-for="(source, index) in displayedSources"
              :key="index"
              class="bg-white border rounded p-3 hover:bg-gray-50"
            >
              <div class="flex items-start space-x-3">
                <img
                  :src="getFavicon(source.url)"
                  :alt="source.title"
                  class="w-4 h-4 mt-1 flex-shrink-0"
                  @error="$event.target.style.display = 'none'"
                />
                <div class="flex-1 min-w-0">
                  <a
                    :href="source.url"
                    target="_blank"
                    class="text-sm font-medium text-blue-600 hover:text-blue-800 line-clamp-1"
                  >
                    {{ source.title }}
                  </a>
                  <p class="text-xs text-gray-500 mt-1 line-clamp-2">
                    {{ source.snippet }}
                  </p>
                </div>
              </div>
            </div>
          </div>
          <button
            v-if="item.sources && item.sources.length > 3"
            @click="showAllSources = !showAllSources"
            class="text-sm text-blue-600 hover:text-blue-800"
          >
            {{ showAllSources ? 'Show Less' : `Show ${item.sources.length - 3} More` }}
          </button>
        </div>

        <!-- ArXiv-specific UI -->
        <div v-if="item.toolName === 'arxiv' && item.papers" class="space-y-3">
          <div class="text-sm font-medium text-gray-700">
            Found {{ item.papers.length }} papers:
          </div>
          <div class="space-y-3">
            <div
              v-for="(paper, index) in item.papers.slice(0, 2)"
              :key="index"
              class="bg-white border rounded p-3"
            >
              <h4 class="font-medium text-gray-900 mb-1">{{ paper.title }}</h4>
              <p class="text-sm text-gray-600 mb-2">{{ paper.authors }}</p>
              <p class="text-sm text-gray-700">{{ paper.summary }}</p>
            </div>
          </div>
        </div>

        <!-- Code Execution UI -->
        <div v-if="item.toolName === 'DaytonaCodeSandbox'" class="space-y-3">
          <div v-if="item.showCodeEditor && item.code" class="bg-gray-900 rounded-lg overflow-hidden">
            <div class="bg-gray-800 px-3 py-2 text-sm text-gray-300 border-b border-gray-700">
              Python Code
            </div>
            <pre class="p-3 text-sm text-green-400 overflow-x-auto"><code>{{ item.code }}</code></pre>
          </div>

          <div v-if="item.output" class="bg-gray-50 rounded p-3">
            <div class="text-sm font-medium text-gray-700 mb-2">Output:</div>
            <pre class="text-sm text-gray-900 whitespace-pre-wrap">{{ item.output }}</pre>
          </div>

          <div v-if="item.artifacts && item.artifacts.length > 0" class="space-y-2">
            <div class="text-sm font-medium text-gray-700">Artifacts Created:</div>
            <div class="grid grid-cols-1 gap-2">
              <div
                v-for="(artifact, index) in item.artifacts"
                :key="index"
                @click="$emit('open-artifact', artifact)"
                class="flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded cursor-pointer hover:bg-blue-100"
              >
                <div class="flex items-center space-x-2">
                  <ChartBarIcon class="w-5 h-5 text-blue-600" />
                  <span class="text-sm font-medium text-blue-900">{{ artifact.title }}</span>
                </div>
                <ArrowTopRightOnSquareIcon class="w-4 h-4 text-blue-600" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Tool Response Content -->
      <div v-else-if="item.type === 'tool_response'" class="space-y-3">
        <div class="flex items-center space-x-2">
          <CheckCircleIcon class="w-5 h-5 text-green-600" />
          <span class="font-medium text-gray-900">Response from {{ item.toolName }}</span>
        </div>
        
        <div class="bg-gray-50 rounded p-3">
          <div class="text-sm text-gray-900 max-h-32 overflow-y-auto">
            {{ truncateContent(item.content, 300) }}
          </div>
        </div>
      </div>

      <!-- LLM Stream Chunk Content -->
      <div v-else-if="item.type === 'llm_chunk'" class="space-y-3">
        <div class="flex items-center space-x-2">
          <ChatBubbleLeftRightIcon class="w-5 h-5 text-orange-600" />
          <span class="font-medium text-gray-900">AI Response</span>
          <div
            v-if="item.status === 'streaming'"
            class="w-2 h-2 bg-orange-500 rounded-full animate-pulse"
          ></div>
        </div>
        
        <div class="prose prose-sm max-w-none">
          <div v-html="renderMarkdown(item.content)"></div>
        </div>
      </div>

      <!-- Agent Completion Content -->
      <div v-else-if="item.type === 'agent_completion'" class="space-y-3">
        <div class="flex items-center space-x-2">
          <UserIcon class="w-5 h-5 text-green-600" />
          <span class="font-medium text-gray-900">{{ item.agentType || 'Agent' }}</span>
        </div>
        
        <div class="prose prose-sm max-w-none">
          <div v-html="renderMarkdown(item.content)"></div>
        </div>
      </div>

      <!-- Stream Events Content -->
      <div v-else-if="['stream_start', 'stream_complete'].includes(item.type)" class="space-y-2">
        <div class="text-sm text-gray-600">
          Run ID: <span class="font-mono text-xs">{{ item.data?.run_id || 'N/A' }}</span>
        </div>
        <div v-if="item.type === 'stream_complete'" class="text-sm text-gray-600">
          Total processing time: {{ calculateDuration() }}
        </div>
      </div>

      <!-- Generic Content -->
      <div v-else class="space-y-3">
        <div v-if="item.content" class="text-sm text-gray-900">
          {{ item.content }}
        </div>
        <div v-if="item.data && Object.keys(item.data).length > 0" class="bg-gray-50 rounded p-3">
          <details>
            <summary class="text-sm font-medium text-gray-700 cursor-pointer">Raw Data</summary>
            <pre class="mt-2 text-xs text-gray-600 overflow-auto">{{ JSON.stringify(item.data, null, 2) }}</pre>
          </details>
        </div>
      </div>

      <!-- Expanded Details -->
      <div v-if="isExpanded" class="mt-4 pt-4 border-t border-gray-200">
        <div class="grid grid-cols-2 gap-4 text-xs text-gray-500">
          <div>
            <strong>ID:</strong> {{ item.id }}
          </div>
          <div>
            <strong>Created:</strong> {{ formatTimestamp(item.createdAt) }}
          </div>
          <div>
            <strong>Updated:</strong> {{ formatTimestamp(item.updatedAt) }}
          </div>
          <div>
            <strong>Status:</strong> {{ item.status }}
          </div>
        </div>
        
        <div v-if="item.data && Object.keys(item.data).length > 0" class="mt-3">
          <details>
            <summary class="text-sm font-medium text-gray-700 cursor-pointer">Complete Data</summary>
            <pre class="mt-2 text-xs text-gray-600 overflow-auto bg-gray-50 p-2 rounded">{{ JSON.stringify(item.data, null, 2) }}</pre>
          </details>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { marked } from 'marked'
import {
  ChevronDownIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  PlayIcon,
  MagnifyingGlassIcon,
  DocumentTextIcon,
  CodeBracketIcon,
  ChatBubbleLeftRightIcon,
  UserIcon,
  ChartBarIcon,
  ArrowTopRightOnSquareIcon
} from '@heroicons/vue/24/outline'

import StatusBadge from '@/components/Common/StatusBadge.vue'

const props = defineProps({
  item: {
    type: Object,
    required: true
  },
  isExpanded: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['toggle-expand', 'update-item', 'open-artifact'])

const showAllSources = ref(false)

const displayedSources = computed(() => {
  if (!props.item.sources) return []
  return showAllSources.value ? props.item.sources : props.item.sources.slice(0, 3)
})

const getCardClass = (item) => {
  const classes = {
    'tool_call': 'border-l-4 border-purple-500',
    'tool_response': 'border-l-4 border-green-500',
    'llm_chunk': 'border-l-4 border-orange-500',
    'agent_completion': 'border-l-4 border-blue-500',
    'stream_start': 'border-l-4 border-gray-500',
    'stream_complete': 'border-l-4 border-gray-600',
    'error': 'border-l-4 border-red-500'
  }
  return classes[item.type] || 'border-l-4 border-gray-300'
}

const getStatusClass = (status) => {
  const classes = {
    'pending': 'bg-gray-500',
    'executing': 'bg-blue-500',
    'searching': 'bg-purple-500',
    'streaming': 'bg-orange-500',
    'completed': 'bg-green-500',
    'error': 'bg-red-500'
  }
  return classes[status] || 'bg-gray-400'
}

const getStatusIcon = (status) => {
  const icons = {
    'pending': ClockIcon,
    'executing': PlayIcon,
    'searching': MagnifyingGlassIcon,
    'streaming': ChatBubbleLeftRightIcon,
    'completed': CheckCircleIcon,
    'error': ExclamationTriangleIcon
  }
  return icons[status] || ClockIcon
}

const getTypeClass = (type) => {
  const classes = {
    'tool_call': 'bg-purple-100 text-purple-800',
    'tool_response': 'bg-green-100 text-green-800',
    'llm_chunk': 'bg-orange-100 text-orange-800',
    'agent_completion': 'bg-blue-100 text-blue-800',
    'stream_start': 'bg-gray-100 text-gray-800',
    'stream_complete': 'bg-gray-200 text-gray-800'
  }
  return classes[type] || 'bg-gray-100 text-gray-600'
}

const getToolIcon = (toolName) => {
  const icons = {
    'search_tavily': MagnifyingGlassIcon,
    'arxiv': DocumentTextIcon,
    'DaytonaCodeSandbox': CodeBracketIcon,
    'wikipedia': DocumentTextIcon
  }
  return icons[toolName] || MagnifyingGlassIcon
}

const formatType = (type) => {
  const labels = {
    'tool_call': 'Tool Call',
    'tool_response': 'Tool Response',
    'llm_chunk': 'AI Response',
    'agent_completion': 'Agent',
    'stream_start': 'Stream Start',
    'stream_complete': 'Complete'
  }
  return labels[type] || type.replace('_', ' ').toUpperCase()
}

const formatTimestamp = (timestamp) => {
  if (!timestamp) return 'N/A'
  
  const date = new Date(timestamp)
  if (isNaN(date.getTime())) return 'Invalid Date'
  
  return date.toLocaleTimeString()
}

const isSearchTool = (toolName) => {
  return ['search_tavily', 'search_tavily_answer', 'ddg_search'].includes(toolName)
}

const isCodeInput = (toolName) => {
  return toolName === 'DaytonaCodeSandbox'
}

const formatToolInput = (toolName, input) => {
  if (isSearchTool(toolName)) {
    // Extract search query from various formats
    try {
      const parsed = JSON.parse(input)
      return parsed.query || parsed.search_query || input
    } catch {
      return input.replace(/^["']|["']$/g, '').trim()
    }
  }
  return input
}

const getFavicon = (url) => {
  if (!url || url === '#') return '/favicon-placeholder.png'
  
  try {
    const domain = new URL(url).hostname
    return `https://www.google.com/s2/favicons?domain=${domain}&sz=32`
  } catch {
    return '/favicon-placeholder.png'
  }
}

const truncateContent = (content, maxLength = 200) => {
  if (!content) return ''
  if (content.length <= maxLength) return content
  return content.substring(0, maxLength) + '...'
}

const renderMarkdown = (content) => {
  if (!content) return ''
  try {
    return marked(content)
  } catch (error) {
    return content
  }
}

const calculateDuration = () => {
  // This would need to be calculated based on stream start/end times
  // For now, just return a placeholder
  return 'N/A'
}
</script>

<style scoped>
.timeline-item-card {
  @apply transition-all duration-200;
}

.timeline-item-card:hover {
  @apply shadow-md;
}

.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.prose {
  @apply text-gray-900;
}

.prose p {
  @apply mb-2;
}

.prose pre {
  @apply bg-gray-100 p-2 rounded text-sm overflow-x-auto;
}

.prose code {
  @apply bg-gray-100 px-1 rounded text-sm;
}
</style> 