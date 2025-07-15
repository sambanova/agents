<template>
  <div v-if="isOpen" class="fixed inset-0 z-50 overflow-y-auto">
    <!-- Backdrop -->
    <div class="fixed inset-0 bg-black bg-opacity-50 transition-opacity" @click="closeModal"></div>
    
    <!-- Modal -->
    <div class="flex min-h-full items-center justify-center p-4">
      <div class="relative w-full max-w-4xl bg-white rounded-lg shadow-xl">
        <!-- Header -->
        <div class="flex items-center justify-between p-4 border-b border-gray-200">
          <div class="flex items-center space-x-3">
            <div class="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
              <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
              </svg>
            </div>
            <div>
              <h3 class="text-lg font-semibold text-gray-900">{{ title }}</h3>
              <p class="text-sm text-gray-600">{{ language }} Code</p>
            </div>
          </div>
          <button
            @click="closeModal"
            class="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
          </button>
        </div>
        
        <!-- Content -->
        <div class="p-6">
          <div class="bg-gray-900 rounded-lg border">
            <div class="bg-gray-800 px-4 py-3 text-sm text-gray-300 border-b border-gray-700 flex justify-between items-center">
              <span>{{ language }}</span>
              <button
                @click="copyCode"
                class="text-sm text-gray-400 hover:text-gray-200 flex items-center space-x-2 px-3 py-1 rounded hover:bg-gray-700 transition-colors"
                :title="copyStatus"
              >
                <svg v-if="!copied" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                </svg>
                <svg v-else class="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                </svg>
                <span>{{ copied ? 'Copied!' : 'Copy' }}</span>
              </button>
            </div>
            <div class="p-4 max-h-96 overflow-y-auto">
              <pre class="text-sm text-gray-100 leading-relaxed whitespace-pre-wrap"><code>{{ code }}</code></pre>
            </div>
          </div>
        </div>
        
        <!-- Footer -->
        <div class="flex justify-end p-4 border-t border-gray-200">
          <button
            @click="closeModal"
            class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 border border-gray-300 rounded-md hover:bg-gray-200 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  isOpen: {
    type: Boolean,
    required: true
  },
  code: {
    type: String,
    required: true
  },
  language: {
    type: String,
    default: 'Python'
  },
  title: {
    type: String,
    default: 'Data Science Tool Call'
  }
})

const emit = defineEmits(['close'])

const copied = ref(false)
const copyStatus = ref('Copy code')

const copyCode = async () => {
  try {
    await navigator.clipboard.writeText(props.code)
    copied.value = true
    copyStatus.value = 'Copied!'
    
    setTimeout(() => {
      copied.value = false
      copyStatus.value = 'Copy code'
    }, 2000)
  } catch (err) {
    console.error('Failed to copy code:', err)
    copyStatus.value = 'Failed to copy'
    
    setTimeout(() => {
      copyStatus.value = 'Copy code'
    }, 2000)
  }
}

const closeModal = () => {
  emit('close')
}
</script> 