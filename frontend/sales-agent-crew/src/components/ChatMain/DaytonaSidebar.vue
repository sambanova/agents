<template>
  <div v-if="isOpen" class="fixed inset-y-0 right-0 w-1/2 bg-white border-l border-gray-200 shadow-2xl z-50 overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between p-4 border-b bg-gradient-to-r from-blue-50 to-purple-50">
      <div class="flex items-center space-x-3">
        <div class="w-8 h-8 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
          <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
          </svg>
        </div>
        <div>
          <h3 class="text-lg font-semibold text-gray-900">Daytona Sandbox</h3>
          <p class="text-sm text-gray-600">Code Analysis & Visualization</p>
        </div>
      </div>
      <button 
        @click="$emit('close')"
        class="p-2 hover:bg-gray-100 rounded-full transition-colors"
        aria-label="Close sidebar"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
        </svg>
      </button>
    </div>

    <!-- Content Area -->
    <div class="flex-1 overflow-y-auto h-full">
      <!-- Status Section -->
      <div class="p-4 border-b bg-gray-50">
        <div class="flex items-center space-x-3">
          <div :class="statusDotClass" class="w-3 h-3 rounded-full flex-shrink-0"></div>
          <div class="flex-1">
            <div class="flex items-center space-x-2">
              <span class="text-sm font-medium text-gray-900">{{ currentStatus }}</span>
              <div v-if="isProcessing" class="animate-spin">
                <svg class="w-4 h-4 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                </svg>
              </div>
            </div>
            <div v-if="statusDetails" class="text-xs text-gray-600 mt-1">{{ statusDetails }}</div>
          </div>
        </div>
        
        <!-- Progress Bar -->
        <div v-if="showProgress" class="mt-3">
          <div class="w-full bg-gray-200 rounded-full h-2">
            <div 
              :class="progressBarClass" 
              class="h-2 rounded-full transition-all duration-500"
              :style="{ width: progressPercentage + '%' }"
            ></div>
          </div>
          <div class="text-xs text-gray-500 mt-1">{{ progressText }}</div>
        </div>
      </div>

      <!-- Code Section -->
      <div v-if="codeContent" class="border-b">
        <div class="p-4">
          <div class="flex items-center justify-between mb-3">
            <h4 class="font-medium text-gray-900 flex items-center space-x-2">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
              </svg>
              <span>Code Execution</span>
            </h4>
            <button
              @click="copyCode"
              class="text-xs text-gray-500 hover:text-gray-700 flex items-center space-x-1 px-2 py-1 rounded hover:bg-gray-100"
            >
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
              </svg>
              <span>Copy</span>
            </button>
          </div>
          
          <!-- Code Display with Syntax Highlighting -->
          <div class="bg-gray-900 rounded-lg overflow-hidden">
            <div class="bg-gray-800 px-4 py-2 text-xs text-gray-300 border-b border-gray-700">
              Python Code
            </div>
            <div class="p-4 overflow-auto max-h-80">
              <pre class="text-sm"><code v-html="highlightedCode" class="text-green-400"></code></pre>
            </div>
          </div>
        </div>
      </div>

      <!-- Charts Section -->
      <div v-if="charts.length > 0" class="border-b">
        <div class="p-4">
          <h4 class="font-medium text-gray-900 mb-3 flex items-center space-x-2">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
            </svg>
            <span>Generated Charts</span>
          </h4>
          
          <div class="space-y-4">
            <div 
              v-for="(chart, index) in charts" 
              :key="chart.id"
              class="bg-gray-50 rounded-lg overflow-hidden border"
            >
              <div class="p-3 border-b bg-white">
                <div class="flex items-center justify-between">
                  <h5 class="font-medium text-sm text-gray-900">{{ chart.title }}</h5>
                  <div class="flex items-center space-x-2">
                    <button
                      @click="downloadChart(chart)"
                      class="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100"
                    >
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                      </svg>
                    </button>
                    <button
                      @click="expandChart(chart)"
                      class="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100"
                    >
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"></path>
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
              
              <div class="p-4">
                <div v-if="chart.loading" class="flex items-center justify-center h-40">
                  <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                </div>
                <img 
                  v-else-if="chart.url"
                  :src="chart.url" 
                  :alt="chart.title"
                  class="w-full h-auto rounded"
                  @load="chart.loading = false"
                  @error="handleChartError(chart)"
                />
                <div v-else class="flex items-center justify-center h-40 text-gray-500">
                  <div class="text-center">
                    <svg class="w-8 h-8 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                    </svg>
                    <p class="text-sm">Chart loading...</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Analysis Results -->
      <div v-if="analysisResults" class="p-4">
        <h4 class="font-medium text-gray-900 mb-3 flex items-center space-x-2">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
          </svg>
          <span>Analysis Results</span>
        </h4>
        
        <div class="bg-blue-50 rounded-lg p-4">
          <div class="prose prose-sm max-w-none text-blue-900" v-html="formattedAnalysis"></div>
        </div>
      </div>

      <!-- Execution Log -->
      <div v-if="executionLog.length > 0" class="p-4 border-t bg-gray-50">
        <h4 class="font-medium text-gray-900 mb-3 text-sm">Execution Log</h4>
        <div class="space-y-2 max-h-40 overflow-y-auto">
          <div 
            v-for="log in executionLog" 
            :key="log.id"
            class="text-xs text-gray-600 flex items-start space-x-2"
          >
            <span class="text-gray-400">{{ formatLogTime(log.timestamp) }}</span>
            <span :class="getLogClass(log.type)">{{ log.message }}</span>
          </div>
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
  streamingEvents: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['close'])

// Reactive state
const currentStatus = ref('Initializing...')
const statusDetails = ref('')
const isProcessing = ref(false)
const showProgress = ref(false)
const progressPercentage = ref(0)
const progressText = ref('')
const codeContent = ref('')
const analysisResults = ref('')
const executionLog = ref([])
const charts = ref([])

// Computed properties
const statusDotClass = computed(() => {
  if (isProcessing.value) return 'bg-blue-500 animate-pulse'
  if (charts.value.length > 0) return 'bg-green-500'
  return 'bg-yellow-500'
})

const progressBarClass = computed(() => {
  if (progressPercentage.value === 100) return 'bg-green-500'
  return 'bg-blue-500'
})

const highlightedCode = computed(() => {
  if (!codeContent.value) return ''
  return highlightPythonCode(codeContent.value)
})

const formattedAnalysis = computed(() => {
  if (!analysisResults.value) return ''
  return formatMarkdown(analysisResults.value)
})

// Watch for streaming events changes
watch(() => props.streamingEvents, (newEvents) => {
  if (newEvents && newEvents.length > 0) {
    processStreamingEvents(newEvents)
  }
}, { deep: true, immediate: true })

// Methods
function processStreamingEvents(events) {
  if (!events || !Array.isArray(events)) return

  // Reset state when processing new events
  charts.value = []
  executionLog.value = []
  isProcessing.value = false
  showProgress.value = false
  
  let codeDetected = false
  let toolCallDetected = false
  let chartCount = 0

  events.forEach((event, index) => {
    const timestamp = event.data?.timestamp || event.timestamp || new Date().toISOString()
    
    switch (event.event) {
      case 'llm_stream_chunk':
        // Check for code content and Daytona tool calls
        if (event.data?.content) {
          const content = event.data.content
          
          // Extract Python code blocks
          const codeMatch = content.match(/```python\n([\s\S]*?)```/)
          if (codeMatch && codeMatch[1]) {
            codeContent.value = codeMatch[1].trim()
            codeDetected = true
            updateStatus('📝 Writing code...', 'Generating Python analysis script')
            addToLog('Code generation detected', 'info', timestamp)
          }
          
          // Check for tool calls
          if (content.includes('<tool>DaytonaCodeSandbox</tool>')) {
            toolCallDetected = true
            updateStatus('🔧 Executing code...', 'Running analysis in sandbox')
            addToLog('Tool call to DaytonaCodeSandbox detected', 'info', timestamp)
            startProgress()
          }
        }
        break
        
      case 'agent_completion':
        if (event.data?.name === 'DaytonaCodeSandbox') {
          // Extract charts from Daytona response
          const content = event.data.content || ''
          
          // Look for chart attachments
          const chartMatches = content.match(/!\[Chart \d+\]\(attachment:([^)]+)\)/g)
          if (chartMatches) {
            chartMatches.forEach((match, idx) => {
              const idMatch = match.match(/attachment:([^)]+)/)
              if (idMatch) {
                const chartId = idMatch[1]
                charts.value.push({
                  id: chartId,
                  title: `AI Model Performance Analysis - Chart ${idx + 1}`,
                  url: `https://api.example.com/charts/${chartId}`, // Use proper backend URL
                  loading: false, // Set to false since we have the URL
                  downloadUrl: `https://api.example.com/charts/${chartId}/download`
                })
                chartCount++
              }
            })
          }
          
          // For demo purposes, create mock chart data with the actual IDs from your example
          if (chartCount === 0 && content.includes('Key Insights:')) {
            // Add mock charts based on the example data
            const mockCharts = [
              {
                id: '4a042217-cbb9-48de-8a7d-a5e76d08fd2f',
                title: 'TPS vs Batch Size Analysis',
                url: 'data:image/svg+xml;base64,' + btoa(`
                  <svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
                    <rect width="100%" height="100%" fill="#f8fafc"/>
                    <text x="300" y="30" text-anchor="middle" font-size="18" font-weight="bold" fill="#1f2937">Tokens Per Second vs Batch Size</text>
                    <text x="300" y="50" text-anchor="middle" font-size="14" fill="#6b7280">Comparative analysis across different models</text>
                    <g stroke="#e5e7eb" stroke-width="1" fill="none">
                      <line x1="80" y1="80" x2="80" y2="320"/>
                      <line x1="80" y1="320" x2="520" y2="320"/>
                    </g>
                    <g fill="#3b82f6" stroke="#3b82f6" stroke-width="2">
                      <circle cx="120" cy="280" r="4"/>
                      <circle cx="180" cy="240" r="4"/>
                      <circle cx="240" cy="180" r="4"/>
                      <circle cx="300" cy="160" r="4"/>
                      <circle cx="360" cy="120" r="4"/>
                      <circle cx="420" cy="140" r="4"/>
                      <path d="M120,280 L180,240 L240,180 L300,160 L360,120 L420,140" fill="none"/>
                    </g>
                    <text x="300" y="370" text-anchor="middle" font-size="12" fill="#6b7280">Batch Size</text>
                    <text x="30" y="200" text-anchor="middle" font-size="12" fill="#6b7280" transform="rotate(-90 30 200)">TPS</text>
                    <text x="500" y="340" font-size="10" fill="#3b82f6">AuroraSynth-X2</text>
                  </svg>
                `),
                loading: false
              },
              {
                id: 'b452652b-600e-48c4-bbd6-281df3410d95',
                title: 'TTFB vs Batch Size Analysis',
                url: 'data:image/svg+xml;base64,' + btoa(`
                  <svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
                    <rect width="100%" height="100%" fill="#f8fafc"/>
                    <text x="300" y="30" text-anchor="middle" font-size="18" font-weight="bold" fill="#1f2937">Time to First Byte vs Batch Size</text>
                    <text x="300" y="50" text-anchor="middle" font-size="14" fill="#6b7280">Latency analysis across different models</text>
                    <g stroke="#e5e7eb" stroke-width="1" fill="none">
                      <line x1="80" y1="80" x2="80" y2="320"/>
                      <line x1="80" y1="320" x2="520" y2="320"/>
                    </g>
                    <g fill="#ef4444" stroke="#ef4444" stroke-width="2">
                      <circle cx="120" cy="300" r="4"/>
                      <circle cx="180" cy="290" r="4"/>
                      <circle cx="240" cy="285" r="4"/>
                      <circle cx="300" cy="260" r="4"/>
                      <circle cx="360" cy="220" r="4"/>
                      <circle cx="420" cy="180" r="4"/>
                      <path d="M120,300 L180,290 L240,285 L300,260 L360,220 L420,180" fill="none"/>
                    </g>
                    <text x="300" y="370" text-anchor="middle" font-size="12" fill="#6b7280">Batch Size</text>
                    <text x="30" y="200" text-anchor="middle" font-size="12" fill="#6b7280" transform="rotate(-90 30 200)">TTFB (seconds)</text>
                    <text x="500" y="340" font-size="10" fill="#ef4444">TitanNova-200b-Guide</text>
                  </svg>
                `),
                loading: false
              }
            ]
            charts.value.push(...mockCharts)
            chartCount = mockCharts.length
          }
          
          // Extract analysis text (everything before the charts)
          const beforeCharts = content.split('![Chart')[0]
          if (beforeCharts.trim()) {
            analysisResults.value = beforeCharts.trim()
          }
          
          updateStatus('✅ Analysis complete', `Generated ${chartCount} charts`)
          addToLog(`Analysis completed with ${chartCount} charts`, 'success', timestamp)
          completeProgress()
        }
        break
    }
  })
  
  // Set initial status if no specific events detected
  if (!codeDetected && !toolCallDetected) {
    updateStatus('⏳ Waiting for analysis...', 'Ready to process code')
  }
}

function updateStatus(status, details = '') {
  currentStatus.value = status
  statusDetails.value = details
  isProcessing.value = status.includes('...') && !status.includes('✅')
}

function startProgress() {
  showProgress.value = true
  progressPercentage.value = 20
  progressText.value = 'Setting up environment...'
  
  // Simulate progress
  setTimeout(() => {
    progressPercentage.value = 60
    progressText.value = 'Executing analysis...'
  }, 1000)
  
  setTimeout(() => {
    progressPercentage.value = 80
    progressText.value = 'Generating visualizations...'
  }, 2000)
}

function completeProgress() {
  progressPercentage.value = 100
  progressText.value = 'Complete!'
  isProcessing.value = false
  
  setTimeout(() => {
    showProgress.value = false
  }, 2000)
}

function addToLog(message, type = 'info', timestamp) {
  executionLog.value.push({
    id: Date.now() + Math.random(),
    message,
    type,
    timestamp
  })
  
  // Keep only last 50 log entries
  if (executionLog.value.length > 50) {
    executionLog.value = executionLog.value.slice(-50)
  }
}

function highlightPythonCode(code) {
  // Basic Python syntax highlighting
  return code
    .replace(/(import|from|def|class|if|else|elif|for|while|try|except|with|as|return|yield|break|continue|pass|and|or|not|in|is|lambda)/g, '<span class="text-blue-400">$1</span>')
    .replace(/(True|False|None)/g, '<span class="text-purple-400">$1</span>')
    .replace(/(#.*$)/gm, '<span class="text-gray-500">$1</span>')
    .replace(/(['"].*?['"])/g, '<span class="text-yellow-400">$1</span>')
    .replace(/(\d+\.?\d*)/g, '<span class="text-red-400">$1</span>')
}

function formatMarkdown(content) {
  // Simple markdown to HTML conversion
  return content
    .replace(/### (.*$)/gm, '<h3 class="font-semibold text-lg mb-2">$1</h3>')
    .replace(/## (.*$)/gm, '<h2 class="font-semibold text-xl mb-2">$1</h2>')
    .replace(/# (.*$)/gm, '<h1 class="font-bold text-2xl mb-3">$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code class="bg-gray-200 px-1 rounded text-sm">$1</code>')
    .replace(/\n\n/g, '</p><p class="mb-2">')
    .replace(/\n/g, '<br>')
    .replace(/^/, '<p class="mb-2">')
    .concat('</p>')
}

function formatLogTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString([], { 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit'
  })
}

function getLogClass(type) {
  const classes = {
    'info': 'text-blue-600',
    'success': 'text-green-600', 
    'warning': 'text-yellow-600',
    'error': 'text-red-600'
  }
  return classes[type] || 'text-gray-600'
}

function copyCode() {
  if (codeContent.value) {
    navigator.clipboard.writeText(codeContent.value)
    // Could add a toast notification here
  }
}

function downloadChart(chart) {
  if (chart.url) {
    const link = document.createElement('a')
    link.href = chart.url
    link.download = `${chart.title.replace(/\s+/g, '_')}.png`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }
}

function expandChart(chart) {
  // Could emit an event to open chart in full screen
  emit('expand-chart', chart)
}

function handleChartError(chart) {
  chart.loading = false
  addToLog(`Failed to load chart: ${chart.title}`, 'error', new Date().toISOString())
}
</script>

<style scoped>
/* Custom scrollbar styling */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
}

::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

/* Animation for status updates */
.transition-colors {
  transition: color 0.3s ease;
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: .5;
  }
}
</style> 