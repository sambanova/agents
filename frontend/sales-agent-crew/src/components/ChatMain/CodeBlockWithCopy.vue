<template>
  <div class="bg-gray-900 rounded-lg overflow-hidden border my-2">
    <div class="bg-gray-800 px-3 py-2 text-xs text-gray-300 border-b border-gray-700 flex justify-between items-center">
      <span>{{ language || 'Code' }}</span>
      <button
        @click="copyCode"
        class="text-xs text-gray-400 hover:text-gray-200 flex items-center space-x-1 px-2 py-1 rounded hover:bg-gray-700 transition-colors"
        :title="copyStatus"
      >
        <svg v-if="!copied" class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
        </svg>
        <svg v-else class="w-3 h-3 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
        </svg>
        <span>{{ copied ? 'Copied!' : 'Copy' }}</span>
      </button>
    </div>
    <div class="p-3 overflow-auto max-h-64">
      <pre class="text-xs font-mono leading-relaxed text-gray-100 whitespace-pre-wrap"><code>{{ code }}</code></pre>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  code: {
    type: String,
    required: true
  },
  language: {
    type: String,
    default: 'Python'
  }
})

const copied = ref(false)
const copyStatus = ref('Copy code')

const copyCode = async () => {
  if (!props.code) return
  
  try {
    await navigator.clipboard.writeText(props.code)
    copied.value = true
    copyStatus.value = 'Copied!'
    
    // Reset after 2 seconds
    setTimeout(() => {
      copied.value = false
      copyStatus.value = 'Copy code'
    }, 2000)
  } catch (err) {
    console.error('Failed to copy code:', err)
    copyStatus.value = 'Failed to copy'
    
    // Reset after 2 seconds
    setTimeout(() => {
      copyStatus.value = 'Copy code'
    }, 2000)
  }
}
</script>

<style scoped>
/* Custom scrollbar for code blocks */
.overflow-auto::-webkit-scrollbar {
  width: 4px;
}

.overflow-auto::-webkit-scrollbar-track {
  background: #374151;
}

.overflow-auto::-webkit-scrollbar-thumb {
  background: #6b7280;
  border-radius: 2px;
}

.overflow-auto::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}
</style> 