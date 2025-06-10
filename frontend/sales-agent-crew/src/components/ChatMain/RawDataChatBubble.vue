<template>
  <li class="flex px-4 items-start gap-x-2 sm:gap-x-4 mb-4">
    <!-- User message layout -->
    <template v-if="isUserMessage">
      <div class="grow text-end space-y-3">
        <div class="inline-block bg-blue-500 text-white px-4 py-2 rounded-lg max-w-[80%] text-left">
          <div class="text-xs text-blue-100 mb-1" v-if="event">{{ event }}</div>
          <div class="whitespace-pre-wrap text-sm">{{ messageContent }}</div>
        </div>
      </div>
      <UserAvatar :type="'user'" />
    </template>

    <!-- System/Assistant message layout -->
    <template v-else>
      <UserAvatar :type="provider || 'assistant'" />
      <div class="grow ml-4 bg-gray-100 dark:bg-gray-700 rounded-lg p-4 max-w-[85%]">
        <!-- Header with event and provider info -->
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-medium text-gray-600 dark:text-gray-300 uppercase tracking-wide">
            {{ event || provider || 'System' }}
          </span>
          <span class="text-xs text-gray-500 dark:text-gray-400" v-if="timestamp">
            {{ formatTimestamp(timestamp) }}
          </span>
        </div>

        <!-- Message content -->
        <div class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded p-3">
          <div class="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-100">{{ messageContent }}</div>
        </div>

        <!-- Toggle button for JSON view -->
        <div class="mt-2">
          <button
            @click="toggleJsonView"
            class="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200 flex items-center gap-1"
          >
            {{ showJson ? 'Hide JSON' : 'Show JSON' }}
            <svg 
              :class="{ 'rotate-180': showJson }" 
              class="w-3 h-3 transition-transform" 
              viewBox="0 0 24 24" 
              fill="none" 
              stroke="currentColor" 
              stroke-width="2"
            >
              <path d="M19 9l-7 7-7-7"/>
            </svg>
          </button>
        </div>

        <!-- Raw JSON data (hidden by default) -->
        <div v-if="showJson" class="mt-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded p-3">
          <pre class="whitespace-pre-wrap text-xs font-mono text-gray-700 dark:text-gray-300 overflow-x-auto">{{ rawData }}</pre>
        </div>
      </div>
    </template>
  </li>
</template>

<script setup>
import { computed, ref } from 'vue'
import UserAvatar from '@/components/Common/UIComponents/UserAvtar.vue'

const props = defineProps({
  data: {
    type: [String, Object, Array],
    required: true,
  },
  provider: {
    type: String,
    default: 'system'
  },
  isUser: {
    type: Boolean,
    default: false
  },
  timestamp: {
    type: [String, Number, Date],
    default: null
  },
  event: {
    type: String,
    default: null
  }
})

const showJson = ref(false)

const isUserMessage = computed(() => {
  return props.isUser || 
         (typeof props.data === 'object' && props.data?.type === 'HumanMessage') ||
         (typeof props.data === 'string' && props.data.includes('"type":"HumanMessage"'))
})

const messageContent = computed(() => {
  try {
    let parsed = props.data
    
    // Parse string data to object if needed
    if (typeof props.data === 'string') {
      try {
        parsed = JSON.parse(props.data)
      } catch {
        // If not JSON, return as-is
        return props.data
      }
    }
    
    // If it's an object, try to extract content
    if (typeof parsed === 'object' && parsed !== null) {
      // Try different content properties in order of preference
      const contentValue = 
        parsed.content || 
        parsed.message || 
        parsed.text || 
        parsed.data?.content ||
        parsed.data?.message ||
        parsed.data?.text
      
      if (contentValue && typeof contentValue === 'string') {
        return contentValue
      }
      
      // For stream_complete and other events, don't show full JSON by default
      if (props.event === 'stream_complete' || props.event === 'stream_start') {
        return `[${props.event}] - Click "Show JSON" to view details`
      }
      
      // For other objects without clear content, show a summary
      return `[${props.event || 'data'}] - Click "Show JSON" to view details`
    }
    
    return String(props.data)
  } catch (error) {
    return String(props.data)
  }
})

const rawData = computed(() => {
  if (typeof props.data === 'string') {
    return props.data
  }
  return JSON.stringify(props.data, null, 2)
})

function toggleJsonView() {
  showJson.value = !showJson.value
}

function formatTimestamp(ts) {
  if (!ts) return ''
  try {
    const date = new Date(ts)
    return date.toLocaleTimeString()
  } catch {
    return String(ts)
  }
}
</script>

<style scoped>
pre {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  line-height: 1.4;
}

/* Custom scrollbar for better appearance */
pre::-webkit-scrollbar {
  height: 6px;
}

pre::-webkit-scrollbar-track {
  background: transparent;
}

pre::-webkit-scrollbar-thumb {
  background: #cbd5e0;
  border-radius: 3px;
}

.dark pre::-webkit-scrollbar-thumb {
  background: #4a5568;
}
</style> 