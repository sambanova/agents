<template>
  <div class="streaming-message-viewer bg-white rounded-lg shadow-lg p-6 space-y-4">
    <div class="flex items-center justify-between border-b pb-4">
      <h2 class="text-lg font-semibold text-gray-800">Streaming Messages</h2>
      <div class="flex items-center space-x-2">
        <button
          @click="clearMessages"
          class="px-3 py-1 text-sm bg-gray-100 text-gray-600 rounded hover:bg-gray-200 transition-colors"
        >
          Clear
        </button>
        <button
          @click="$emit('close')"
          class="px-3 py-1 text-sm bg-red-100 text-red-600 rounded hover:bg-red-200 transition-colors"
        >
          Hide
        </button>
        <div class="text-sm text-gray-500">
          {{ streamingMessages.length }} messages
        </div>
      </div>
    </div>

    <div class="max-h-96 overflow-y-auto space-y-3">
      <div
        v-for="(message, index) in streamingMessages"
        :key="index"
        class="streaming-message border rounded-lg p-4 hover:bg-gray-50 transition-colors"
        :class="getEventTypeClass(message.event)"
      >
        <!-- Event Header -->
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center space-x-2">
            <span 
              class="inline-flex items-center px-2 py-1 text-xs font-medium rounded-full"
              :class="getEventBadgeClass(message.event)"
            >
              <div 
                class="w-2 h-2 rounded-full mr-1"
                :class="getEventDotClass(message.event)"
              ></div>
              {{ message.event }}
            </span>
            <span class="text-xs text-gray-500">
              {{ formatTimestamp(message.timestamp) }}
            </span>
          </div>
          <button
            @click="toggleMessageExpansion(index)"
            class="text-gray-400 hover:text-gray-600"
          >
            <svg
              :class="{ 'transform rotate-180': expandedMessages.includes(index) }"
              class="w-4 h-4 transition-transform"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>

        <!-- Message Content -->
        <div class="space-y-2">
          <!-- Data Content -->
          <div v-if="message.data">
            <div class="text-sm font-medium text-gray-700 mb-1">Content:</div>
            <div class="bg-gray-50 rounded p-2 text-sm">
              <!-- Handle different data types -->
              <div v-if="message.event === 'stream_start'">
                <span class="text-gray-600">Run ID:</span>
                <span class="font-mono text-blue-600 ml-1">{{ message.data.run_id }}</span>
              </div>
              
              <div v-else-if="message.event === 'stream_complete'" class="space-y-2">
                <div>
                  <span class="text-gray-600">Run ID:</span>
                  <span class="font-mono text-blue-600 ml-1">{{ message.data.run_id }}</span>
                </div>
                <!-- Display all additional agent data -->
                <div v-for="(value, key) in getAdditionalStreamCompleteData(message.data)" :key="key" class="space-y-1">
                  <div class="flex items-start space-x-2">
                    <span class="text-gray-600 font-medium capitalize min-w-0 flex-shrink-0">{{ formatDataKey(key) }}:</span>
                    <div class="flex-1 min-w-0">
                      <!-- Handle different value types -->
                      <div v-if="typeof value === 'string'" class="break-words">
                        <span v-if="isUrl(value)">
                          <a :href="value" target="_blank" class="text-blue-600 hover:text-blue-800 underline">{{ value }}</a>
                        </span>
                        <span v-else class="text-gray-800">{{ value }}</span>
                      </div>
                      <div v-else-if="typeof value === 'number'" class="text-purple-600 font-mono">{{ value }}</div>
                      <div v-else-if="typeof value === 'boolean'" class="text-green-600 font-mono">{{ value }}</div>
                      <div v-else-if="Array.isArray(value)" class="space-y-1">
                        <div class="text-gray-600 text-xs">Array ({{ value.length }} items):</div>
                        <div class="bg-white rounded border-l-4 border-purple-400 p-2 max-h-32 overflow-y-auto">
                          <div v-for="(item, index) in value" :key="index" class="text-sm">
                            <span class="text-gray-500">[{{ index }}]:</span>
                            <span v-if="typeof item === 'string'" class="ml-1">{{ item }}</span>
                            <pre v-else class="text-xs text-gray-600 whitespace-pre-wrap">{{ JSON.stringify(item, null, 2) }}</pre>
                          </div>
                        </div>
                      </div>
                      <div v-else-if="typeof value === 'object' && value !== null" class="space-y-1">
                        <div class="text-gray-600 text-xs">Object:</div>
                        <div class="bg-white rounded border-l-4 border-orange-400 p-2 max-h-32 overflow-y-auto">
                          <pre class="text-xs text-gray-600 whitespace-pre-wrap">{{ JSON.stringify(value, null, 2) }}</pre>
                        </div>
                      </div>
                      <div v-else class="text-gray-500 italic">{{ value }}</div>
                    </div>
                  </div>
                </div>
              </div>
              
              <div v-else-if="message.event === 'agent_completion'" class="space-y-1">
                <div>
                  <span class="text-gray-600">Type:</span>
                  <span class="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs ml-1">{{ message.data.type }}</span>
                </div>
                <div>
                  <span class="text-gray-600">Content:</span>
                  <div class="mt-1 p-2 bg-white rounded border-l-4 border-blue-400">
                    {{ message.data.content }}
                  </div>
                </div>
                <div>
                  <span class="text-gray-600">ID:</span>
                  <span class="font-mono text-xs text-gray-500 ml-1">{{ message.data.id }}</span>
                </div>
              </div>

              <div v-else-if="message.event === 'llm_stream_chunk'" class="space-y-1">
                <div class="flex items-center justify-between">
                  <div>
                    <span class="text-gray-600">Delta:</span>
                    <span class="ml-1" :class="message.data.is_delta ? 'text-green-600' : 'text-gray-600'">
                      {{ message.data.is_delta ? 'Yes' : 'No' }}
                    </span>
                  </div>
                  <span class="text-xs text-gray-500 font-mono">{{ message.data.id }}</span>
                </div>
                <div v-if="message.data.content">
                  <span class="text-gray-600">Content:</span>
                  <div class="mt-1 p-2 bg-white rounded border-l-4 border-green-400">
                    "{{ message.data.content }}"
                  </div>
                </div>
                <div v-else class="text-gray-500 italic">Empty content chunk</div>
              </div>

              <div v-else>
                <pre class="text-xs text-gray-600 whitespace-pre-wrap">{{ JSON.stringify(message.data, null, 2) }}</pre>
              </div>
            </div>
          </div>

          <!-- Expanded Details -->
          <div v-if="expandedMessages.includes(index)" class="space-y-2 pt-2 border-t border-gray-200">
            <div class="grid grid-cols-2 gap-4 text-xs">
              <div>
                <span class="text-gray-600">User ID:</span>
                <div class="font-mono text-gray-800 break-all">{{ message.user_id }}</div>
              </div>
              <div>
                <span class="text-gray-600">Conversation ID:</span>
                <div class="font-mono text-gray-800 break-all">{{ message.conversation_id }}</div>
              </div>
              <div>
                <span class="text-gray-600">Message ID:</span>
                <div class="font-mono text-gray-800 break-all">{{ message.message_id }}</div>
              </div>
              <div>
                <span class="text-gray-600">Timestamp:</span>
                <div class="text-gray-800">{{ message.timestamp }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="streamingMessages.length === 0" class="text-center text-gray-500 py-8">
        No streaming messages received yet
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const streamingMessages = ref([])
const expandedMessages = ref([])

// WebSocket connection
const socket = ref(null)

const props = defineProps({
  conversationId: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['close'])

function getEventTypeClass(event) {
  const classes = {
    'stream_start': 'border-blue-200 bg-blue-50',
    'stream_complete': 'border-purple-200 bg-purple-50',
    'agent_completion': 'border-green-200 bg-green-50',
    'llm_stream_chunk': 'border-orange-200 bg-orange-50'
  }
  return classes[event] || 'border-gray-200 bg-gray-50'
}

function getEventBadgeClass(event) {
  const classes = {
    'stream_start': 'bg-blue-100 text-blue-800',
    'stream_complete': 'bg-purple-100 text-purple-800',
    'agent_completion': 'bg-green-100 text-green-800',
    'llm_stream_chunk': 'bg-orange-100 text-orange-800'
  }
  return classes[event] || 'bg-gray-100 text-gray-800'
}

function getEventDotClass(event) {
  const classes = {
    'stream_start': 'bg-blue-500',
    'stream_complete': 'bg-purple-500',
    'agent_completion': 'bg-green-500',
    'llm_stream_chunk': 'bg-orange-500'
  }
  return classes[event] || 'bg-gray-500'
}

function formatTimestamp(timestamp) {
  return new Date(timestamp).toLocaleTimeString()
}

function getAdditionalStreamCompleteData(data) {
  // Extract all data except run_id to show additional agent output
  const { run_id, ...additionalData } = data
  return additionalData
}

function formatDataKey(key) {
  // Convert snake_case to Title Case
  return key.split('_').map(word => 
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ')
}

function isUrl(str) {
  try {
    new URL(str)
    return true
  } catch {
    return false
  }
}

onMounted(() => {
  connectStreamingWebSocket()
})

onUnmounted(() => {
  if (socket.value) {
    socket.value.close()
  }
})

// Expose function to add messages from parent component
defineExpose({
  handleStreamingMessage
})
</script>

<style scoped>
.streaming-message {
  transition: all 0.2s ease-in-out;
}

.streaming-message:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
</style> 