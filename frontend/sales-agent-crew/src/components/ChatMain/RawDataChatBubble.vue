<template>
  <li class="flex px-4 items-start gap-x-2 sm:gap-x-4 mb-4">
    <!-- User message layout -->
    <template v-if="isUserMessage">
      <div class="grow text-end space-y-3">
        <div class="inline-block bg-blue-500 text-white px-4 py-2 rounded-lg max-w-[80%] text-left">
          <div class="text-xs text-blue-100 mb-1" v-if="event">{{ event }}</div>
          <div class="whitespace-pre-wrap text-sm" v-html="messageContent"></div>
          
          <!-- Toggle button for JSON view -->
          <div class="mt-2">
            <button
              @click="toggleJsonView"
              class="text-xs text-blue-100 hover:text-white flex items-center gap-1"
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
          <div v-if="showJson" class="mt-2 bg-blue-600 border border-blue-400 rounded p-3">
            <pre class="whitespace-pre-wrap text-xs font-mono text-blue-100 overflow-x-auto">{{ rawData }}</pre>
          </div>
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
          <div class="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-100" v-html="messageContent"></div>
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

// Helper function to escape HTML in text content
function escapeHtml(text) {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

const isUserMessage = computed(() => {
  // Check explicit isUser prop first
  if (props.isUser) return true
  
  try {
    let parsed = props.data
    
    // Parse string data to object if needed
    if (typeof props.data === 'string') {
      try {
        parsed = JSON.parse(props.data)
      } catch {
        return false
      }
    }
    
    // Check if additional_kwargs.agent_type is 'human'
    if (typeof parsed === 'object' && parsed !== null) {
      return parsed.additional_kwargs?.agent_type === 'human'
    }
    
    return false
  } catch (error) {
    return false
  }
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
      let contentValue = 
        parsed.content || 
        parsed.message || 
        parsed.text || 
        parsed.data?.content ||
        parsed.data?.message ||
        parsed.data?.text
      
      // Handle array content (like messages with text and images)
      if (Array.isArray(contentValue)) {
        const processedContent = contentValue.map(item => {
          if (typeof item === 'object' && item !== null) {
            if (item.type === 'text') {
              return escapeHtml(item.text || '[text content]')
            } else if (item.type === 'image_url' && item.image_url?.url) {
              const imageUrl = item.image_url.url
              if (imageUrl.startsWith('data:image/') || imageUrl.startsWith('https://')) {
                return `<div class="my-2"><img src="${imageUrl}" alt="Attached image" class="max-w-full h-auto rounded border" style="max-height: 300px;" /></div>`
              } else {
                return escapeHtml(`[image: ${imageUrl}]`)
              }
            } else {
              return escapeHtml(`[${item.type || 'content'}]`)
            }
          }
          return escapeHtml(String(item))
        }).join('')
        
        return processedContent || '[Mixed content - see JSON for details]'
      }
      
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
  
  // Function to truncate very long strings (like base64 images)
  const truncateLongStrings = (obj, maxLength = 200) => {
    if (typeof obj === 'string') {
      if (obj.length > maxLength) {
        return obj.substring(0, maxLength) + `... [truncated ${obj.length - maxLength} more characters]`
      }
      return obj
    }
    
    if (Array.isArray(obj)) {
      return obj.map(item => truncateLongStrings(item, maxLength))
    }
    
    if (typeof obj === 'object' && obj !== null) {
      const result = {}
      for (const [key, value] of Object.entries(obj)) {
        result[key] = truncateLongStrings(value, maxLength)
      }
      return result
    }
    
    return obj
  }
  
  const truncatedData = truncateLongStrings(props.data)
  return JSON.stringify(truncatedData, null, 2)
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