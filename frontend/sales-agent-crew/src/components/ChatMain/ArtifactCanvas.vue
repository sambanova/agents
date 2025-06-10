<template>
  <div v-if="isOpen" class="fixed inset-0 z-[99999] overflow-y-auto" style="z-index: 99999 !important;">
    <div class="flex min-h-screen items-center justify-center p-4" @click="handleBackdropClick">
      <!-- Backdrop -->
      <div class="fixed inset-0 bg-black bg-opacity-50 transition-opacity -z-10"></div>
      
      <!-- Modal -->
      <div class="relative w-full max-w-6xl bg-white rounded-lg shadow-xl z-10 pointer-events-auto opacity-100" 
           style="z-index: 100000 !important; pointer-events: auto !important; opacity: 1 !important;" 
           @click.stop @mousedown.stop @mouseup.stop>
        <!-- Header -->
        <div class="flex items-center justify-between p-4 border-b">
          <h3 class="text-lg font-semibold text-gray-900">
            {{ artifact?.title || 'Artifact View' }}
          </h3>
          <button 
            @click="$emit('close')"
            class="p-2 hover:bg-gray-100 rounded-full transition-colors"
            aria-label="Close"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
          </button>
        </div>
        
        <!-- Content -->
        <div class="p-6">
          <div v-if="artifact?.type === 'chart'" class="space-y-4">
            <!-- Chart Display -->
            <div class="bg-gray-50 rounded-lg p-4">
              <img 
                v-if="chartUrl"
                :src="chartUrl" 
                :alt="artifact.title"
                class="max-w-full h-auto mx-auto"
                @error="handleImageError"
              />
              <div v-else class="flex items-center justify-center h-64 text-gray-500">
                <div class="text-center">
                  <svg class="w-12 h-12 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                  </svg>
                  <p>Chart not available</p>
                </div>
              </div>
            </div>
            
            <!-- Chart Details -->
            <div v-if="artifact?.details" class="bg-blue-50 rounded-lg p-4">
              <h4 class="font-medium text-blue-900 mb-2">Analysis</h4>
              <p class="text-blue-800 text-sm">{{ artifact.details }}</p>
            </div>
          </div>
          
          <!-- HTML Content Display -->
          <div v-else-if="artifact?.type === 'html'" class="space-y-4">
            <div class="bg-gray-50 rounded-lg p-4">
              <iframe 
                v-if="htmlContent"
                :srcdoc="htmlContent"
                class="w-full h-96 border-0"
                sandbox="allow-scripts allow-same-origin"
              ></iframe>
              <div v-else class="flex items-center justify-center h-64 text-gray-500">
                <p>HTML content not available</p>
              </div>
            </div>
          </div>
          
          <!-- Code Display -->
          <div v-else-if="artifact?.type === 'code'" class="space-y-4">
            <div class="bg-gray-900 rounded-lg p-4 overflow-auto">
              <pre class="text-green-400 text-sm"><code>{{ artifact.content }}</code></pre>
            </div>
          </div>
          
          <!-- Generic Content -->
          <div v-else class="space-y-4">
            <div class="bg-gray-50 rounded-lg p-4">
              <p class="text-gray-600">{{ artifact?.content || 'No content available' }}</p>
            </div>
          </div>
        </div>
        
        <!-- Footer -->
        <div class="flex justify-end gap-2 p-4 border-t bg-gray-50">
          <button 
            @click="downloadArtifact"
            v-if="canDownload"
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Download
          </button>
          <button 
            @click="$emit('close')"
            class="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  },
  artifact: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close'])

const chartUrl = ref('')
const htmlContent = ref('')

// Watch for artifact changes to load content
watch(() => props.artifact, (newArtifact) => {
  if (newArtifact) {
    loadArtifactContent(newArtifact)
  }
}, { immediate: true })

const canDownload = computed(() => {
  return props.artifact?.type === 'chart' && chartUrl.value
})

function loadArtifactContent(artifact) {
  if (!artifact) return
  
  switch (artifact.type) {
    case 'chart':
      // Use the existing URL if available, otherwise try to construct from ID
      if (artifact.url) {
        chartUrl.value = artifact.url
      } else if (artifact.id) {
        chartUrl.value = `/api/files/${artifact.id}`
      }
      break
      
    case 'html':
      htmlContent.value = artifact.content || '<p>HTML content not available</p>'
      break
      
    default:
      // Other types are handled in template
      break
  }
}

function handleBackdropClick(event) {
  if (event.target === event.currentTarget) {
    emit('close')
  }
}

function handleImageError() {
  console.warn('Failed to load chart image')
}

function downloadArtifact() {
  if (props.artifact?.type === 'chart' && chartUrl.value) {
    const link = document.createElement('a')
    link.href = chartUrl.value
    link.download = `${props.artifact.title || 'chart'}.png`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }
}

// Close modal on Escape key
function handleKeydown(event) {
  if (event.key === 'Escape' && props.isOpen) {
    emit('close')
  }
}

// Add event listener for escape key
if (typeof window !== 'undefined') {
  document.addEventListener('keydown', handleKeydown)
}
</script>

<style scoped>
/* Ensure modal appears above everything */
.fixed {
  z-index: 9999;
}

/* Smooth transitions */
.transition-opacity {
  transition: opacity 0.2s ease-in-out;
}

.transition-colors {
  transition: background-color 0.2s ease-in-out, color 0.2s ease-in-out;
}

/* Code syntax highlighting */
pre code {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  line-height: 1.4;
}

/* Chart container styling */
img {
  max-height: 70vh;
  object-fit: contain;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .max-w-6xl {
    max-width: 95vw;
    margin: 1rem;
  }
}
</style> 