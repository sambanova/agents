<template>


    <!-- Handle streaming events -->
    <li v-if="props.streamingEvents" class="relative px-4 items-start gap-x-2 sm:gap-x-4">
      <div class="w-full relative flex items-center">
        <UserAvatar :type="provider" />   
        <div class="grow relative text-start space-y-3">
          <!-- Card -->
          <div class="inline-block">
            <div class="relative p-4 flex items-center capitalize space-y-3 font-inter font-semibold text-[16px] leading-[18px] tracking-[0px] text-center capitalize">
              {{ provider==="sambanova"?"SambaNova":provider }} Agent
            </div>
          </div>
        </div>
      </div>
      <div class="w-full bg-white">          
        <!-- Minimalist Real-time Status Line -->
        <div class="flex items-start justify-between p-3 bg-gray-50 rounded-t-lg border-b status-bar">
          <div class="flex items-start space-x-3 flex-1">
            <div class="flex items-center space-x-2">
              <div :class="currentStatusDot" class="w-2 h-2 rounded-full mt-1 flex-shrink-0"></div>
              <div v-if="showStatusAnimation" class="mt-0.5">
                <svg 
                  class="w-3 h-3 text-gray-500 animate-spin" 
                  viewBox="0 0 24 24" 
                  fill="none" 
                  stroke="currentColor"
                >
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </div>
            </div>
            <div v-if="isStreamingResponse" class="text-sm text-gray-700 transition-all duration-300">
              {{ finalStatusSummary }}
            </div>
            <div v-else class="text-sm text-gray-700 whitespace-pre-line transition-all duration-300">
              <span class="inline-flex items-start space-x-1">
                <span>{{ currentStreamingStatus }}</span>
                <span v-if="showSearchingAnimation" class="flex space-x-0.5 mt-1">
                  <div class="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0s"></div>
                  <div class="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0.1s"></div>
                  <div class="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
                </span>
              </span>
            </div>
          </div>
          
          <button
            v-if="hasCompletedEvents || isStreamingResponse"
            @click="toggleAuditLog"
            class="text-xs text-gray-500 hover:text-gray-700 flex items-center space-x-1 hover:bg-gray-200 px-2 py-1 rounded transition-all duration-200"
          >
            <span>{{ showAuditLog ? 'Hide' : 'Show' }} details</span>
            <svg
              :class="{ 'rotate-180': showAuditLog }"
              class="w-3 h-3 transition-transform duration-200"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
            >
              <path d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>



        <!-- Artifacts/Charts (if available and not using Daytona sidebar) -->
        <div 
          v-if="hasArtifacts && !isDaytonaActive"
          class="p-3 bg-purple-50 border-b"
        >
          <div class="text-xs font-medium text-purple-800 mb-2">Generated Artifacts</div>
          <div class="grid grid-cols-2 gap-2">
            <div
              v-for="artifact in artifacts"
              :key="artifact.id"
              class="p-2 bg-white rounded border border-purple-200 cursor-pointer hover:border-purple-400"
              @click="openArtifact(artifact)"
            >
              <div class="flex items-center space-x-2">
                <div class="w-8 h-8 bg-purple-500 rounded flex items-center justify-center">
                  <span class="text-xs text-white">📊</span>
                </div>
                <div>
                  <div class="text-xs font-medium text-gray-900">{{ artifact.title }}</div>
                  <div class="text-xs text-gray-500">Click to view</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Comprehensive Audit Log (collapsible) -->
        <div 
          v-if="showAuditLog && hasCompletedEvents"
          class="p-3 bg-gray-50 border-b max-h-96 overflow-y-auto"
        >
          <div class="text-xs font-medium text-gray-600 mb-3">Comprehensive Audit Log</div>
          <div class="space-y-3">
            <div
              v-for="event in auditLogEvents"
              :key="event.id"
              class="border-l-2 border-gray-200 pl-3"
            >
              <div class="flex items-start space-x-2">
                <div :class="event.dotClass" class="w-2 h-2 rounded-full mt-1 flex-shrink-0"></div>
                <div class="flex-1 min-w-0">
                  <div class="flex items-center justify-between">
                    <span class="text-xs font-medium text-gray-900">{{ event.title }}</span>
                    <span class="text-xs text-gray-400">{{ formatEventTime(event.timestamp) }}</span>
                  </div>
                  <div v-if="event.details" class="text-xs text-gray-600 mt-1">{{ event.details }}</div>
                  <!-- Sub-bullets for sources -->
                  <div v-if="event.subItems && event.subItems.length > 0" class="mt-2 ml-4 space-y-1">
                    <div
                      v-for="subItem in event.subItems"
                      :key="subItem.id"
                      class="flex items-start space-x-1"
                    >
                      <span class="text-xs text-gray-400 mt-0.5">•</span>
                      <div class="text-xs text-gray-600">
                        <span class="font-medium">{{ subItem.title }}</span>
                        <span v-if="subItem.domain" class="text-gray-500 ml-1">({{ subItem.domain }})</span>
                      </div>
                    </div>
                  </div>
                  <div class="text-xs text-gray-400 mt-1">
                    <span class="bg-gray-100 px-1 rounded">{{ event.event }}</span>
                    <span v-if="event.type" class="bg-blue-100 px-1 rounded ml-1">{{ event.type }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Actual Streaming Response Content -->
        <div class="p-4">
          <div class="prose prose-sm max-w-none">
            <div 
              v-if="streamingResponseContent"
              class="text-gray-800 whitespace-pre-wrap"
              v-html="renderMarkdown(streamingResponseContent)"
            ></div>
            <div 
              v-else-if="isCurrentlyStreaming && !streamingResponseContent"
              class="flex items-center space-x-2 text-gray-500"
            >
              <div class="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
              <span class="text-sm italic">Generating response...</span>
            </div>
          </div>

          <!-- Inline Sources (minimalist) - MOVED TO AFTER RESPONSE -->
          <div v-if="toolSources && toolSources.length > 0" class="mt-4">
            <div class="flex flex-wrap gap-2">
              <template v-for="source in toolSources" :key="source?.url || source?.title || 'unknown'">
                <a
                  v-if="source && source.url"
                  :href="source.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-gray-50 hover:bg-gray-100 rounded-lg text-xs text-gray-700 hover:text-gray-900 transition-colors border border-gray-200 hover:border-gray-300"
                >
                  <span v-if="source.type === 'web'">🌐</span>
                  <span v-else-if="source.type === 'arxiv'">📚</span>
                  <span v-else>📄</span>
                  <span class="truncate max-w-[180px]">{{ source.title || 'Untitled' }}</span>
                  <span v-if="source.domain && source.domain !== source.title && source.type === 'web'" class="text-gray-500 text-xs">
                    • {{ source.domain }}
                  </span>
                  <svg class="w-3 h-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                  </svg>
                </a>
                <div
                  v-else-if="source && !source.url"
                  class="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-gray-50 rounded-lg text-xs text-gray-700 border border-gray-200"
                >
                  <span v-if="source.type === 'web'">🌐</span>
                  <span v-else-if="source.type === 'arxiv'">📚</span>
                  <span v-else>📄</span>
                  <span class="truncate max-w-[180px]">{{ source.title || 'Untitled' }}</span>
                </div>
              </template>
            </div>
          </div>
          
          <!-- Artifacts Display (hidden when Daytona sidebar is active) -->
          <div v-if="artifacts.length > 0 && !isDaytonaActive" class="mt-4">
            <div class="flex flex-wrap gap-2">
              <button
                v-for="artifact in artifacts"
                :key="artifact.id"
                @click="openArtifact(artifact)"
                class="inline-flex items-center gap-2 px-3 py-2 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-lg text-sm text-blue-800 hover:text-blue-900 transition-colors"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                </svg>
                {{ artifact.title }}
              </button>
            </div>
          </div>
          
          <!-- Daytona Status Indicator and Controls -->
          <div v-if="isDaytonaActive" class="mt-4">
            <div class="inline-flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-200 rounded-lg text-sm text-blue-800">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
              </svg>
              <span class="font-medium">{{ showDaytonaSidebar ? 'Code analysis running in Canvas' : 'Data analysis available' }}</span>
              
              <!-- Reopen button when sidebar is closed -->
              <button
                v-if="!showDaytonaSidebar"
                @click="reopenDaytonaSidebar"
                class="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 hover:bg-blue-200 rounded text-xs font-medium transition-colors"
                title="Open Daytona Sandbox"
              >
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                </svg>
                Open
              </button>
              
              <!-- Sidebar active indicator -->
              <svg v-else class="w-3 h-3 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
              </svg>
            </div>
          </div>
        </div>
      </div>
    </li>

    <!-- Check if event is 'user_message' -->
    <li
      v-else-if="props.event === 'user_message'" 
      class="flex px-4 items-start gap-x-2 sm:gap-x-4"
    >
      <div class="grow text-end space-y-3">
        <!-- Card -->
        <div class="inline-block flex justify-end">
          <p class="text-[16px] text-left color-primary-brandGray max-w-[80%] w-auto">
            {{ parsedData.message || props.data }}
          </p>
        </div>
        <!-- End Card -->
      </div>
      <UserAvatar :type="user" />
    </li>
    
    <!-- For all other cases -->
    <li v-else class="relative px-4 items-start gap-x-2 sm:gap-x-4">
      <div class="w-full relative flex items-center">
        <UserAvatar :type="provider" />   
        <div class="grow relative text-start space-y-3">
          <!-- Card -->
          <div class="inline-block">
            <div class="relative p-4 flex items-center capitalize space-y-3 font-inter font-semibold text-[16px] leading-[18px] tracking-[0px] text-center capitalize">
              {{ provider==="sambanova"?"SambaNova":provider }} Agent
              <!-- Menu button: visible on hover -->
              <button
                v-if="parsedData.agent_type==='sales_leads'||parsedData.agent_type==='financial_analysis'||parsedData.agent_type==='deep_research'"
                type="button"
                class="group-hover:opacity-100 transition-opacity duration-200"
                @click.stop="toggleMenu"
                @mousedown.stop
                aria-label="Open menu"
              >
                <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="#667085" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="5" r="1" />
                  <circle cx="12" cy="12" r="1" />
                  <circle cx="12" cy="19" r="1" />
                </svg>
              </button>
              
              <!-- Popover menu -->
              <div
                v-if="activeMenu"
                class="absolute right-1 top-8 bg-white border border-gray-200 shadow-lg rounded z-30"
                @click.stop
              >
                <button
                  class="flex items-center w-full px-4 py-2 hover:bg-gray-100 text-left"
                  @click="generatePDFFromHtml"
                >
                  <svg class="w-5 h-5 mr-2" viewBox="0 0 24 24" fill="none" stroke="#667085" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                  Download PDF
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="w-full bg-white">          
        <AnalysisTimeline 
          :isLoading="isLoading" 
          :parsedData="parsedData" 
          :workflowData="workflowData" 
          :presentMetadata="parsedData.metadata" 
          :plannerText="plannerText" 
        />
        <component :id="'chat-'+messageId" :is="selectedComponent" :parsed="parsedData" />
      </div>
    </li>

    <!-- Daytona Sidebar (replaces Artifact Canvas for Daytona operations) -->
    <DaytonaSidebar 
      :isOpen="showDaytonaSidebar"
      :streamingEvents="streamingEvents"
      @close="closeDaytonaSidebar"
      @expand-chart="openArtifact"
    />
    
    <!-- Artifact Canvas Modal (fallback for non-Daytona artifacts) -->
    <ArtifactCanvas 
      :isOpen="showArtifactCanvas"
      :artifact="selectedArtifact"
      @close="closeArtifactCanvas"
    />
  </template>
  
  <script setup>
  import { computed, defineProps, ref,watch,nextTick, provide } from 'vue'
  
  import UserAvatar from '@/components/Common/UIComponents/UserAvtar.vue'
  import AssistantComponent from '@/components/ChatMain/ResponseTypes/AssistantComponent.vue'
  import UserProxyComponent from '@/components/ChatMain/ResponseTypes/UserProxyComponent.vue'
  import SalesLeadComponent from '@/components/ChatMain/ResponseTypes/SalesLeadsComponent.vue'
  import EducationalComponent from '@/components/ChatMain/EducationalComponent.vue'
  import UnknownTypeComponent from '@/components/ChatMain/ResponseTypes/UnknownTypeComponent.vue'
  import FinancialAnalysisComponent from '@/components/ChatMain/ResponseTypes/FinancialAnalysisComponent.vue'
  import DeepResearchComponent from '@/components/ChatMain/ResponseTypes//DeepResearchComponent.vue'
  import ErrorComponent from '@/components/ChatMain/ResponseTypes/ErrorComponent.vue'
  import AnalysisTimeline from '@/components/ChatMain/AnalysisTimeline.vue'
import ArtifactCanvas from '@/components/ChatMain/ArtifactCanvas.vue'
import DaytonaSidebar from '@/components/ChatMain/DaytonaSidebar.vue'

// Icons for streaming timeline
import {
  ClockIcon,
  MagnifyingGlassIcon,
  ChatBubbleLeftRightIcon,
  CheckCircleIcon
} from '@heroicons/vue/24/outline'


  import html2canvas from "html2canvas";
  import jsPDF from "jspdf";
  import html2pdf from 'html2pdf.js'


  function fetchProvider() {
    // Check if workflowData is an array and has elements
    if (!props.workflowData || !Array.isArray(props.workflowData)) {
      return null;
    }
    for (let i = 0; i < props.workflowData.length; i++) {
      if (props.workflowData[i].hasOwnProperty('llm_provider')) {
        return props.workflowData[i].llm_provider;
      }
    }
    // Return null if no object with 'llm_provider' is found
    return null;
  }
  
 

  const formattedDuration=(duration) =>{
      // Format duration to 2 decimal places
      return duration?.toFixed(2);
    }
  
  // Define props
  const props = defineProps({
    data: {
      type: String,
      required: true
    },
    event: {
      type: String,
      required: true
    },
    plannerText: {
      type: String,
      required: true
    },
    metadata: {
      type: Object,
      required: false,
      default: () => ({})
    },
    provider: {
      type: String,
      required: true
    },
    messageId: {
      type: String,
      required: true
    },
    currentMsgId: {
      type: String,
      required: false,
      default: ''
    },
  
  workflowData: {
    type: Array,
    required: false,
    default: () => []
  },
  
  streamingEvents: {
    type: Array,
    default: null
  }
  
  })
  const presentMetadata = computed(() => {


if (!parsedData.metadata) return null;

return parsedData.metadata;
});

  const presentMetadataOld = computed(() => {


  if (!props.metadata) return null;

  return props.metadata;
});







  
  // Parse the JSON string safely
  const parsedData = computed(() => {
    try {
      return JSON.parse(props.data)
    } catch (error) {
      console.error('Error parsing data in ChatBubble:', error)
      return {}
    }
  })
  
  // Choose which sub-component to display based on agent_type
  const selectedComponent = computed(() => {
    switch (parsedData.value.agent_type) {
      case 'assistant':
        return AssistantComponent
      case 'educational_content':
        return EducationalComponent
      case 'user_proxy':
        return UserProxyComponent
      case 'sales_leads':
        return SalesLeadComponent
      case 'financial_analysis':
        return FinancialAnalysisComponent
      case 'deep_research':
        return DeepResearchComponent
      case 'error':
        return ErrorComponent
      default:
        return UnknownTypeComponent
    }
  })
  
  // Define isOpen; if not passed as prop, define it as a ref
  const isOpen = ref(false)  // adjust as needed; for instance, based on statusText or other logic
  const collapsed = ref(true)
function toggleCollapse() {
  collapsed.value = !collapsed.value
}

// Add refs for UI state
const activeMenu = ref(false)
const showAuditLog = ref(false)

// Toggle functions
function toggleMenu() {
  activeMenu.value = !activeMenu.value
}

function toggleAuditLog() {
  showAuditLog.value = !showAuditLog.value
}

const selectedArtifact = ref(null)
const showArtifactCanvas = ref(false)
const showDaytonaSidebar = ref(false)
const daytonaSidebarClosed = ref(false) // Track if user manually closed it

function openArtifact(artifact) {
  selectedArtifact.value = artifact
  showArtifactCanvas.value = true
}

function closeArtifactCanvas() {
  showArtifactCanvas.value = false
  selectedArtifact.value = null
}

function closeDaytonaSidebar() {
  showDaytonaSidebar.value = false
  daytonaSidebarClosed.value = true // Mark as manually closed
}

function reopenDaytonaSidebar() {
  showDaytonaSidebar.value = true
  daytonaSidebarClosed.value = false
}

// Detect Daytona usage and automatically open sidebar - ENHANCED FOR LOADED CONVERSATIONS
const isDaytonaActive = computed(() => {
  if (!props.streamingEvents || !Array.isArray(props.streamingEvents)) {
    // For loaded conversations, check if any workflow data indicates Daytona usage
    if (props.workflowData && props.workflowData.length > 0) {
      return props.workflowData.some(item => 
        item.tool_name === 'DaytonaCodeSandbox' || 
        item.task === 'code_execution' ||
        item.agent_name === 'Daytona Sandbox'
      );
    }
    return false;
  }
  
  return props.streamingEvents.some(event => {
    // Check for Daytona tool calls in streaming content
    if (event.event === 'llm_stream_chunk' && event.data?.content) {
      return event.data.content.includes('<tool>DaytonaCodeSandbox</tool>')
    }
    
    // Check for Daytona tool results
    if (event.event === 'agent_completion' && event.data?.name === 'DaytonaCodeSandbox') {
      return true
    }
    
    // Check our custom flag for loaded conversations
    if (event.isDaytonaRelated) {
      return true
    }
    
    return false
  })
})

// Watch for Daytona activity and automatically open sidebar
watch(isDaytonaActive, (isActive) => {
  if (isActive && !daytonaSidebarClosed.value) {
    showDaytonaSidebar.value = true
    // Close artifact canvas if it's open since we're using sidebar now
    showArtifactCanvas.value = false
  }
}, { immediate: true })

// Advanced streaming parsing and status
const currentStreamingStatus = computed(() => {
  if (!props.streamingEvents || props.streamingEvents.length === 0) {
    // For loaded conversations, show completion status if we have workflow data
    if (props.workflowData && props.workflowData.length > 0) {
      return '✅ Response complete';
    }
    return '⏳ Starting...';
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

const currentStatusDot = computed(() => {
  const status = currentStreamingStatus.value
  if (status.includes('✅')) return 'bg-green-500'
  if (status.includes('🔍') || status.includes('📚') || status.includes('⚡')) return 'bg-purple-500 animate-pulse'
  if (status.includes('📝')) return 'bg-blue-500 animate-pulse'
  if (status.includes('💭')) return 'bg-yellow-500 animate-pulse'
  return 'bg-gray-500 animate-pulse'
})

// Show spinning gear animation when tools are actively running
const showStatusAnimation = computed(() => {
  if (!props.streamingEvents || props.streamingEvents.length === 0) return false
  
  const status = currentStreamingStatus.value
  // Show animation when we're searching, executing, or processing (not when complete)
  return status.includes('🔍') || status.includes('📚') || status.includes('⚡') || 
         status.includes('💭') || status.includes('Processing')
})

// Show bouncing dots for searching operations
const showSearchingAnimation = computed(() => {
  if (!props.streamingEvents || props.streamingEvents.length === 0) return false
  
  const status = currentStreamingStatus.value
  // Show bouncing dots specifically for search operations
  return status.includes('🔍 Searching') || status.includes('📚 Searching')
})

const isCurrentlyStreaming = computed(() => {
  if (!props.streamingEvents || props.streamingEvents.length === 0) return true
  
  const lastEvent = props.streamingEvents[props.streamingEvents.length - 1]
  return lastEvent.event !== 'stream_complete'
})

const hasCompletedEvents = computed(() => {
  if (!props.streamingEvents || props.streamingEvents.length === 0) {
    // For loaded conversations, check if we have any tool-related or completion events
    if (props.workflowData && props.workflowData.length > 0) return true;
    if (props.metadata && Object.keys(props.metadata).length > 0) return true;
    return false;
  }
  
  // Check for any completed tool executions, final responses, or tool-related events
  return props.streamingEvents.some(event => 
    (event.event === 'agent_completion' && event.data.type === 'LiberalFunctionMessage') ||
    (event.event === 'agent_completion' && event.data.name === 'DaytonaCodeSandbox') ||
    (event.event === 'agent_completion' && event.data.name === 'search_tavily') ||
    (event.event === 'agent_completion' && event.data.name === 'arxiv') ||
    (event.event === 'stream_complete') ||
    (event.event === 'agent_completion' && event.data.agent_type === 'react_end') ||
    (event.isToolRelated || event.isDaytonaRelated) || // Check our custom flags
    event.event === 'agent_completion' || event.event === 'stream_complete'
  )
})

// Check if we're currently streaming the LLM response (not tools)
const isStreamingResponse = computed(() => {
  if (!props.streamingEvents || props.streamingEvents.length === 0) return false
  
  const events = props.streamingEvents
  
  // Check if we have completed tool execution AND have LLM response content
  const hasCompletedTools = events.some(event => 
    event.event === 'agent_completion' && 
    event.data.type === 'LiberalFunctionMessage'
  )
  
  const hasResponseContent = events.some(event => 
    event.event === 'llm_stream_chunk' && 
    event.data.content && 
    !event.data.content.includes('<tool>')
  )
  
  // We're in "streaming response" mode if tools are done and we have response content
  return hasCompletedTools && hasResponseContent
})

// Summary for when we've moved to response streaming - ENHANCED FOR LOADED CONVERSATIONS
const finalStatusSummary = computed(() => {
  if (!props.streamingEvents || props.streamingEvents.length === 0) {
    // For loaded conversations, generate summary from workflow data
    if (props.workflowData && props.workflowData.length > 0) {
      const completedTasks = props.workflowData.map(workflow => {
        if (workflow.tool_name === 'DaytonaCodeSandbox' || workflow.task === 'code_execution') {
          return 'Code execution complete';
        } else if (workflow.tool_name === 'search_tavily' || workflow.task === 'web_search') {
          return 'Web search complete';
        } else if (workflow.tool_name === 'arxiv' || workflow.task === 'arxiv_search') {
          return 'arXiv search complete';
        } else {
          return `${workflow.agent_name || 'Task'} complete`;
        }
      });
      
      if (completedTasks.length > 0) {
        return `✅ ${completedTasks.join(' • ')}`;
      }
    }
    return 'Details';
  }
  
  let completedTools = []
  
  props.streamingEvents.forEach(event => {
    if (event.event === 'agent_completion' && 
        event.data.type === 'LiberalFunctionMessage' && 
        event.data.name) {
      
      if (event.data.name === 'search_tavily' && Array.isArray(event.data.content)) {
        completedTools.push(`Found ${event.data.content.length} web sources`)
      } else if (event.data.name === 'arxiv') {
        const papers = event.data.content && event.data.content.includes('Title:') ? 
          event.data.content.split('Title:').length - 1 : 1
        completedTools.push(`Found ${papers} arXiv papers`)
      } else if (event.data.name === 'DaytonaCodeSandbox') {
        completedTools.push('Code execution complete')
      }
    }
  })
  
  if (completedTools.length > 0) {
    return `✅ ${completedTools.join(' • ')}`
  }
  
  return 'Details'
})

// Comprehensive audit log with filtered meaningful events - ENHANCED FOR LOADED CONVERSATIONS
const auditLogEvents = computed(() => {
  
  if (!props.streamingEvents || props.streamingEvents.length === 0) {
    // For loaded conversations without streaming events, create synthetic audit log from workflow data
    if (props.workflowData && props.workflowData.length > 0) {
      console.log('Creating synthetic audit log from workflow data');
      
      // Deduplicate workflow data based on task and tool name
      const uniqueWorkflows = [];
      const seenWorkflowKeys = new Set();
      
      props.workflowData.forEach(workflow => {
        const workflowKey = `${workflow.agent_name || 'Agent'}-${workflow.task || 'Task'}-${workflow.tool_name || 'NoTool'}`;
        if (!seenWorkflowKeys.has(workflowKey)) {
          seenWorkflowKeys.add(workflowKey);
          uniqueWorkflows.push(workflow);
        }
      });
      
      return uniqueWorkflows.map((workflow, index) => ({
        id: `synthetic-audit-${index}`,
        title: `✅ ${workflow.agent_name || 'Agent'} - ${workflow.task || 'Task'}`,
        details: workflow.tool_name ? `Tool: ${workflow.tool_name}` : 'Completed successfully',
        subItems: [],
        dotClass: workflow.task === 'code_execution' ? 'bg-purple-500' : 'bg-green-500',
        type: 'tool_result',
        event: 'workflow_item',
        timestamp: new Date().toISOString(),
        fullData: workflow
      }));
    }
    return [];
  }
  

  
  // First, deduplicate events to prevent duplicate audit log entries
  const uniqueEvents = [];
  const seenEventKeys = new Set();
  
  props.streamingEvents.forEach(event => {
    // Create a unique key based on event content for deduplication
    let eventKey = '';
    
    if (event.event === 'llm_stream_chunk' && event.data?.content?.includes('<tool>')) {
      // For tool calls, use tool name + timestamp
      const toolMatch = event.data.content.match(/<tool>([^<]+)<\/tool>/);
      if (toolMatch) {
        eventKey = `tool-${toolMatch[1]}-${event.data.timestamp || event.timestamp}`;
      }
    } else if (event.event === 'agent_completion' && event.data?.name) {
      // For tool responses, use tool name + content hash for deduplication
      const contentHash = event.data.content ? String(event.data.content).substring(0, 50) : '';
      eventKey = `completion-${event.data.name}-${contentHash}`;
    } else if (event.event === 'agent_completion' && event.data?.agent_type) {
      // For other agent completions, use agent_type + timestamp
      eventKey = `agent-${event.data.agent_type}-${event.data.timestamp || event.timestamp}`;
    } else {
      // For other events, use event type + timestamp
      eventKey = `${event.event}-${event.data?.timestamp || event.timestamp}`;
    }
    
    // Only add if we haven't seen this event key before
    if (!seenEventKeys.has(eventKey)) {
      seenEventKeys.add(eventKey);
      uniqueEvents.push(event);
    } else {
      console.log(`Skipping duplicate audit log event: ${eventKey}`);
    }
  });
  
  return uniqueEvents
    .filter(event => {
      // Keep meaningful events, remove clutter - but include tool-related events
      if (event.event === 'stream_start') return false
      if (event.event === 'stream_complete') return false
      if (event.event === 'agent_completion' && event.data.agent_type === 'human') return false
      if (event.event === 'agent_completion' && event.data.agent_type === 'react_end') return false
      if (event.event === 'llm_stream_chunk' && event.data.content && !event.data.content.includes('<tool>')) return false
      
      // Always include tool-related events
      if (event.isToolRelated || event.isDaytonaRelated) return true
      if (event.event === 'agent_completion' && (event.data.agent_type === 'react_tool' || event.data.agent_type === 'tool_response')) return true
      if (event.event === 'agent_completion' && event.data.name) return true // Tool responses
      
      return true
    })
    .map((event, index) => {
      const data = event.data
      let title = ''
      let details = ''
      let dotClass = 'bg-gray-400'
      let type = 'info'
      
      switch (event.event) {
        case 'llm_stream_chunk':
          if (data.content && data.content.includes('<tool>')) {
            const toolMatch = data.content.match(/<tool>([^<]+)<\/tool>/)
            // Fixed regex to handle missing closing tag
            const inputMatch = data.content.match(/<tool_input>([^<\n\r]+)/)
            
            if (toolMatch) {
              const tool = toolMatch[1]
              const query = inputMatch ? inputMatch[1].trim() : 'No query'
              
              if (tool === 'search_tavily') {
                title = `🔍 Search Tavily`
                details = `Query: "${query}"`
              } else if (tool === 'arxiv') {
                title = `📚 Search arXiv`
                details = `Query: "${query}"`
              } else if (tool === 'DaytonaCodeSandbox') {
                title = `⚡ Execute Code`
                details = 'Running analysis in sandbox'
              } else {
                title = `🔧 ${tool.replace('_', ' ')}`
                details = `Query: "${query}"`
              }
              dotClass = 'bg-purple-500'
              type = 'tool_call'
            }
          }
          break
          
        case 'agent_completion':
          if (data.type === 'LiberalFunctionMessage' && data.name) {
            if (data.name === 'search_tavily' && Array.isArray(data.content)) {
              title = `✅ Found ${data.content.length} web sources`
              
              // Extract actual domains/titles from sources for sub-bullets
              const subItems = data.content.slice(0, 5).map((source, idx) => {
                let displayTitle = 'Unknown Source'
                let domain = ''
                
                if (source.title && source.title.trim()) {
                  displayTitle = source.title.trim()
                } else if (source.url) {
                  try {
                    const url = new URL(source.url)
                    domain = url.hostname.replace('www.', '')
                    displayTitle = domain
                  } catch {
                    displayTitle = source.url
                  }
                }
                
                if (source.url) {
                  try {
                    domain = new URL(source.url).hostname.replace('www.', '')
                  } catch {
                    domain = 'web'
                  }
                }
                
                return {
                  id: `source-${idx}`,
                  title: displayTitle,
                  domain: domain
                }
              })
              
              // Keep the old details for backward compatibility
              const sourceNames = subItems.slice(0, 3).map(item => item.title)
              details = sourceNames.join(', ')
              if (data.content.length > 3) details += `, and ${data.content.length - 3} more...`
              
              dotClass = 'bg-green-500'
              type = 'tool_result'
              
              // Add subItems to the event
              return {
                id: `audit-${index}`,
                title,
                details,
                subItems,
                dotClass,
                type,
                event: event.event,
                timestamp: data.timestamp || event.timestamp || new Date().toISOString(),
                fullData: data
              }
            } else if (data.name === 'arxiv') {
              const papers = data.content && data.content.includes('Title:') ? 
                data.content.split('Title:').length - 1 : 1
              title = `✅ Found ${papers} arXiv papers`
              
              // Extract paper titles for sub-bullets
              const titleMatches = data.content.match(/Title: ([^\n]+)/g)
              let subItems = []
              
              if (titleMatches) {
                details = titleMatches.slice(0, 2).map(t => t.replace('Title: ', '').trim()).join(', ')
                if (titleMatches.length > 2) details += `, and ${titleMatches.length - 2} more...`
                
                subItems = titleMatches.slice(0, 5).map((titleMatch, idx) => ({
                  id: `paper-${idx}`,
                  title: titleMatch.replace('Title: ', '').trim(),
                  domain: 'arxiv.org'
                }))
              }
              
              dotClass = 'bg-green-500'
              type = 'tool_result'
              
              return {
                id: `audit-${index}`,
                title,
                details,
                subItems,
                dotClass,
                type,
                event: event.event,
                timestamp: data.timestamp || event.timestamp || new Date().toISOString(),
                fullData: data
              }
            } else if (data.name === 'DaytonaCodeSandbox') {
              title = `✅ Code execution complete`
              details = 'Generated charts and analysis'
              dotClass = 'bg-green-500'
              type = 'tool_result'
            }
          }
          break
      }
      
      return {
        id: `audit-${index}`,
        title,
        details,
        subItems: [],
        dotClass,
        type,
        event: event.event,
        timestamp: data.timestamp || event.timestamp || new Date().toISOString(),
        fullData: data
      }
    })
    .filter(event => event.title) // Only include events with titles
})

// Extract streaming response content with better parsing
const streamingResponseContent = computed(() => {
  if (!props.streamingEvents) return ''
  
  // First, look for the final completed response (react_end)
  for (let i = props.streamingEvents.length - 1; i >= 0; i--) {
    const event = props.streamingEvents[i]
    if (event.event === 'agent_completion' && event.data.agent_type === 'react_end') {
      return event.data.content || ''
    }
  }
  
  // If no completed response, find the largest streaming content that's not a tool call
  let bestContent = ''
  let maxLength = 0
  
  props.streamingEvents.forEach(event => {
    if (event.event === 'llm_stream_chunk' && 
        event.data.content && 
        !event.data.content.includes('<tool>') &&
        event.data.content.trim()) {
      
      const content = event.data.content.trim()
      // Prefer longer content as it's likely the main response
      if (content.length > maxLength) {
        maxLength = content.length
        bestContent = content
      }
    }
  })
  
  return bestContent
})



// Extract sources from tool results with proper titles and domains
const toolSources = computed(() => {
  if (!props.streamingEvents || !Array.isArray(props.streamingEvents)) return []
  
  const sources = []
  
  props.streamingEvents.forEach(event => {
    if (event.event === 'agent_completion' && 
        event.data.type === 'LiberalFunctionMessage' && 
        event.data.name === 'search_tavily' &&
        Array.isArray(event.data.content)) {
      
      event.data.content.forEach(source => {
        let displayTitle = 'Unknown Source'
        let domain = ''
        
        // Try to get title first, fallback to domain
        if (source.title && source.title.trim()) {
          displayTitle = source.title.trim()
        } else if (source.url) {
          try {
            const url = new URL(source.url)
            domain = url.hostname.replace('www.', '')
            displayTitle = domain
          } catch {
            displayTitle = source.url
          }
        }
        
        // Extract domain for icon/display
        if (source.url) {
          try {
            domain = new URL(source.url).hostname.replace('www.', '')
          } catch {
            domain = 'web'
          }
        }
        
        sources.push({
          title: displayTitle || 'Untitled',
          domain: domain || '',
          url: source.url || '',
          content: source.content ? source.content.substring(0, 200) + '...' : '',
          type: 'web'
        })
      })
    } else if (event.data.name === 'arxiv') {
      // Parse arXiv results - remove the broken URL construction
      const content = event.data.content || ''
      const papers = content.split('Published:').slice(1)
      
      papers.forEach(paper => {
        const titleMatch = paper.match(/Title: ([^\n]+)/)
        const authorsMatch = paper.match(/Authors: ([^\n]+)/)
        const urlMatch = paper.match(/URL: ([^\n]+)/)
        const publishedMatch = paper.match(/Published: ([^\n]+)/)
        
        if (titleMatch) {
          // Only use actual URLs from the content, don't construct fake ones
          const arxivUrl = urlMatch ? urlMatch[1].trim() : ''
          
          sources.push({
            title: titleMatch[1].trim() || 'Untitled Paper',
            authors: authorsMatch ? authorsMatch[1].trim() : '',
            domain: 'arxiv.org',
            url: arxivUrl, // This might be empty if no URL is provided
            content: paper.substring(0, 300) + '...',
            type: 'arxiv',
            published: publishedMatch ? publishedMatch[1].trim() : ''
          })
        }
      })
    }
  })
  
  return sources.slice(0, 5) // Limit to 5 sources for UI
})

// Check for charts/artifacts
const hasArtifacts = computed(() => {
  if (!props.streamingEvents) return false
  
  return props.streamingEvents.some(event => 
    event.event === 'agent_completion' && 
    event.data.name === 'DaytonaCodeSandbox' &&
    event.data.content &&
    event.data.content.includes('![Chart')
  )
})

const artifacts = computed(() => {
  if (!props.streamingEvents) return []
  
  const charts = []
  
  props.streamingEvents.forEach(event => {
    if (event.event === 'agent_completion' && 
        event.data.name === 'DaytonaCodeSandbox' &&
        event.data.content) {
      
      const content = event.data.content
      const chartMatches = content.match(/!\[Chart \d+\]\(attachment:([^)]+)\)/g)
      
      if (chartMatches) {
        chartMatches.forEach((match, index) => {
          const idMatch = match.match(/attachment:([^)]+)/)
          if (idMatch) {
            charts.push({
              id: idMatch[1],
              title: `Chart ${index + 1}`,
              type: 'chart',
              details: 'Generated from data analysis'
            })
          }
        })
      }
    }
  })
  
  return charts
})

// Modal state for artifact display already defined below

function formatEventTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString([], { 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit'
  })
}

function renderMarkdown(content) {
  if (!content) return ''
  
  // Enhanced markdown rendering with code syntax highlighting
  let html = content
    // Handle code blocks FIRST (before other processing)
    .replace(/```(\w+)?\n([\s\S]*?)```/g, (match, language, code) => {
      const lang = language || 'python'
      const highlightedCode = highlightCode(code.trim(), lang)
      return `<div class="my-4 bg-gray-900 rounded-lg overflow-hidden">
        <div class="bg-gray-800 px-4 py-2 text-xs text-gray-300 border-b border-gray-700 flex items-center space-x-2">
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
          </svg>
          <span>${lang.charAt(0).toUpperCase() + lang.slice(1)} Code</span>
        </div>
        <div class="p-4 overflow-auto">
          <pre class="text-sm"><code class="text-green-400">${highlightedCode}</code></pre>
        </div>
      </div>`
    })
    // Links MUST be processed after code blocks but before other formatting
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, text, url) => {
      // Clean the URL of any trailing characters
      const cleanUrl = url.trim()
      return `<a href="${cleanUrl}" target="_blank" rel="noopener noreferrer" class="text-blue-600 hover:text-blue-800 underline">${text}</a>`
    })
    // Bold and italic 
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    // Inline code (skip if inside existing code tags)
    .replace(/`([^`]+)`/g, '<code class="bg-gray-100 px-1 rounded text-sm font-mono">$1</code>')
    // Basic headers
    .replace(/^### (.*$)/gm, '<h3 class="text-lg font-semibold mt-4 mb-2 text-gray-900">$1</h3>')
    .replace(/^## (.*$)/gm, '<h2 class="text-xl font-semibold mt-4 mb-2 text-gray-900">$1</h2>')
    .replace(/^# (.*$)/gm, '<h1 class="text-2xl font-bold mt-4 mb-3 text-gray-900">$1</h1>')
    // Paragraphs and line breaks
    .replace(/\n\n/g, '</p><p class="mb-3">')
    .replace(/\n/g, '<br>')
  
  return `<p class="mb-3">${html}</p>`
}

function highlightCode(code, language) {
  if (!code) return ''
  
  switch (language.toLowerCase()) {
    case 'python':
      return highlightPython(code)
    case 'javascript':
    case 'js':
      return highlightJavaScript(code)
    default:
      return code // Return plain code for unsupported languages
  }
}

function highlightPython(code) {
  return code
    // Python keywords
    .replace(/(import|from|def|class|if|else|elif|for|while|try|except|with|as|return|yield|break|continue|pass|and|or|not|in|is|lambda|global|nonlocal)/g, '<span class="text-blue-400">$1</span>')
    // Python built-ins
    .replace(/(True|False|None|self|__init__|__name__|__main__)/g, '<span class="text-purple-400">$1</span>')
    // Strings (handle both single and double quotes)
    .replace(/(['"`])((?:(?!\1)[^\\]|\\.)*)(\1)/g, '<span class="text-yellow-400">$1$2$3</span>')
    // Numbers
    .replace(/\b(\d+\.?\d*)\b/g, '<span class="text-red-400">$1</span>')
    // Comments
    .replace(/(#.*$)/gm, '<span class="text-gray-500">$1</span>')
    // Function calls
    .replace(/\b(\w+)(?=\()/g, '<span class="text-cyan-400">$1</span>')
}

function highlightJavaScript(code) {
  return code
    // JavaScript keywords
    .replace(/(const|let|var|function|if|else|for|while|return|try|catch|finally|class|extends|import|export|from|default)/g, '<span class="text-blue-400">$1</span>')
    // JavaScript built-ins
    .replace(/(true|false|null|undefined|this|new|typeof|instanceof)/g, '<span class="text-purple-400">$1</span>')
    // Strings
    .replace(/(['"`])((?:(?!\1)[^\\]|\\.)*)(\1)/g, '<span class="text-yellow-400">$1$2$3</span>')
    // Numbers
    .replace(/\b(\d+\.?\d*)\b/g, '<span class="text-red-400">$1</span>')
    // Comments
    .replace(/(\/\/.*$)/gm, '<span class="text-gray-500">$1</span>')
    .replace(/(\/\*[\s\S]*?\*\/)/g, '<span class="text-gray-500">$1</span>')
}

function getStatusBadgeClass(status) {
  const classes = {
    'executing': 'bg-blue-100 text-blue-800',
    'completed': 'bg-green-100 text-green-800',
    'pending': 'bg-yellow-100 text-yellow-800',
    'error': 'bg-red-100 text-red-800'
  }
  return classes[status] || 'bg-gray-100 text-gray-800'
}


  const headerConfig = ref({
  // Replace with your actual SVG markup string or generate one dynamically
  SVGMarkup: `
    <svg
      class="logo shrink-0 p-1 rounded-sm"
      width="37"
      height="38"
      viewBox="0 0 37 38"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient
          id="brandGradient"
          gradientUnits="userSpaceOnUse"
          x1="0"
          y1="0"
          x2="1000"
          y2="0"
        >
          <!-- Animate x2 to create a moving effect -->
          <animate
            attributeName="x2"
            from="1000"
            to="0"
            dur="5s"
            repeatCount="indefinite"
          />
          <stop offset="0%" stop-color="#EE7624" />
          <stop offset="100%" stop-color="#EE7624" />
        </linearGradient>
      </defs>
      <path
        d="M36.0662 37.4535H34.0626V12.6172C34.0653 10.0763 33.0744 7.63742 31.3063 5.83311C29.5381 4.02879 27.1363 3.00558 24.6253 2.98684H11.441C8.96466 2.98684 6.58972 3.98224 4.83867 5.75407C3.08761 7.5259 2.10388 9.929 2.10388 12.4347C2.10388 14.9405 3.08761 17.3436 4.83867 19.1155C6.58972 20.8873 8.96466 21.8827 11.441 21.8827H12.6933C13.2616 21.8008 13.8407 21.8433 14.3912 22.0075C14.9419 22.1716 15.4512 22.4536 15.8848 22.8342C16.3184 23.2149 16.6661 23.6853 16.9044 24.2137C17.1427 24.7421 17.266 25.3162 17.266 25.897C17.266 26.4778 17.1427 27.0519 16.9044 27.5803C16.6661 28.1087 16.3184 28.5792 15.8848 28.9598C15.4512 29.3405 14.9419 29.6224 14.3912 29.7866C13.8407 29.9507 13.2616 29.9933 12.6933 29.9114H1.52588e-05V27.8839H12.7234C12.9897 27.9033 13.2571 27.8669 13.5089 27.7771C13.7606 27.6874 13.9915 27.546 14.1869 27.362C14.3824 27.1779 14.5383 26.9551 14.6449 26.7074C14.7514 26.4598 14.8064 26.1925 14.8064 25.9224C14.8064 25.6522 14.7514 25.3849 14.6449 25.1373C14.5383 24.8896 14.3824 24.6668 14.1869 24.4827C13.9915 24.2987 13.7606 24.1573 13.5089 24.0676C13.2571 23.9777 12.9897 23.9414 12.7234 23.9608H11.4711C8.44285 23.9716 5.53412 22.7661 3.38345 20.6089C1.23277 18.4517 0.0159207 15.5192 1.52588e-05 12.4551C0.0159198 9.39534 1.23035 6.46691 3.37697 4.31192C5.52359 2.15694 8.4272 0.951297 11.4511 0.959391H24.6453C27.6819 0.991395 30.5836 2.2331 32.7215 4.41533C34.8594 6.59757 36.0611 9.54446 36.0662 12.6172V37.4535Z"
        fill="url(#brandGradient)"
      />
      <path
        d="M32.2893 37.4537H30.2856V12.6174C30.2886 11.096 29.7014 9.63408 28.6505 8.546C27.5995 7.45791 26.1686 6.83051 24.6653 6.79865H11.441C9.95838 6.79865 8.53648 7.39461 7.4881 8.45542C6.43972 9.51624 5.85075 10.955 5.85075 12.4553C5.85075 13.9554 6.43972 15.3942 7.4881 16.455C8.53648 17.5158 9.95838 18.1118 11.441 18.1118H11.5512L12.7735 18.2436C14.7928 18.2517 16.7263 19.0711 18.1486 20.5217C19.5708 21.9722 20.3654 23.935 20.3574 25.9783C20.3494 28.0216 19.5396 29.978 18.106 31.4172C16.6725 32.8564 14.7327 33.6603 12.7134 33.6522H0V31.6247H12.7234C14.206 31.6247 15.628 31.0288 16.6763 29.968C17.7246 28.9072 18.3136 27.4684 18.3136 25.9681C18.3136 24.468 17.7246 23.0292 16.6763 21.9684C15.628 20.9076 14.206 20.3116 12.7234 20.3116H12.6132L11.401 20.1798C10.401 20.1798 9.41097 19.9805 8.4872 19.5933C7.56343 19.2062 6.72407 18.6386 6.01704 17.9233C5.31002 17.2079 4.74918 16.3585 4.36653 15.4238C3.9839 14.4891 3.78696 13.4873 3.78696 12.4755C3.78696 11.4638 3.9839 10.4619 4.36653 9.52719C4.74918 8.59247 5.31002 7.74315 6.01704 7.02774C6.72407 6.31233 7.56343 5.74484 8.4872 5.35766C9.41097 4.97048 10.401 4.7712 11.401 4.7712H24.6453C26.6845 4.80577 28.6286 5.6498 30.0586 7.12132C31.4885 8.59285 32.2896 10.574 32.2893 12.6377V37.4537Z"
        fill="url(#brandGradient)"
      />
      <path
        d="M12.7234 37.4535H0V35.426H12.7234C15.1998 35.426 17.5747 34.4306 19.3257 32.6588C21.0767 30.887 22.0605 28.4839 22.0605 25.9781C22.0605 23.4723 21.0767 21.0693 19.3257 19.2975C17.5747 17.5256 15.1998 16.5302 12.7234 16.5302H11.4711C10.9028 16.6121 10.3237 16.5696 9.77312 16.4054C9.22251 16.2412 8.71317 15.9593 8.27959 15.5787C7.84601 15.1981 7.49831 14.7276 7.26001 14.1992C7.02172 13.6707 6.8984 13.0966 6.8984 12.5158C6.8984 11.935 7.02172 11.3609 7.26001 10.8325C7.49831 10.3042 7.84601 9.83368 8.27959 9.45304C8.71317 9.0724 9.22251 8.79046 9.77312 8.62629C10.3237 8.46212 10.9028 8.41956 11.4711 8.5015H24.6453C25.7198 8.53061 26.7406 8.98378 27.4894 9.76418C28.2381 10.5446 28.6556 11.5903 28.6527 12.6781V37.4535H26.649V12.6172C26.6551 12.0793 26.4569 11.5595 26.0952 11.1652C25.7336 10.771 25.2359 10.5323 24.7054 10.4986H11.441C11.1747 10.4791 10.9073 10.5155 10.6555 10.6053C10.4037 10.6951 10.1729 10.8365 9.97744 11.0205C9.78207 11.2045 9.62616 11.4273 9.51958 11.675C9.413 11.9227 9.358 12.19 9.358 12.4601C9.358 12.7303 9.413 12.9975 9.51958 13.2452C9.62616 13.4929 9.78207 13.7157 9.97744 13.8997C10.1729 14.0838 10.4037 14.2252 10.6555 14.3149C10.9073 14.4047 11.1747 14.441 11.441 14.4217H12.6933C15.7117 14.4176 18.6081 15.627 20.7452 17.7838C22.8824 19.9407 24.0853 22.8681 24.0892 25.9223C24.0932 28.9766 22.898 31.9072 20.7665 34.0698C18.635 36.2322 15.7418 37.4494 12.7234 37.4535Z"
        fill="url(#brandGradient)"
      />
      <path
        d="M12.7234 37.4535H0V35.426H12.7234C15.1998 35.426 17.5747 34.4306 19.3257 32.6588C21.0767 30.887 22.0605 28.4839 22.0605 25.9781C22.0605 23.4723 21.0767 21.0693 19.3257 19.2975C17.5747 17.5256 15.1998 16.5302 12.7234 16.5302H11.4711C10.9028 16.6121 10.3237 16.5696 9.77312 16.4054C9.22251 16.2412 8.71317 15.9593 8.27959 15.5787C7.84601 15.1981 7.49831 14.7276 7.26001 14.1992C7.02172 13.6707 6.8984 13.0966 6.8984 12.5158C6.8984 11.935 7.02172 11.3609 7.26001 10.8325C7.49831 10.3042 7.84601 9.83368 8.27959 9.45304C8.71317 9.0724 9.22251 8.79046 9.77312 8.62629C10.3237 8.46212 10.9028 8.41956 11.4711 8.5015H24.6453C25.7198 8.53061 26.7406 8.98378 27.4894 9.76418C28.2381 10.5446 28.6556 11.5903 28.6527 12.6781V37.4535H26.649V12.6172C26.6551 12.0793 26.4569 11.5595 26.0952 11.1652C25.7336 10.771 25.2359 10.5323 24.7054 10.4986H11.441C11.1747 10.4791 10.9073 10.5155 10.6555 10.6053C10.4037 10.6951 10.1729 10.8365 9.97744 11.0205C9.78207 11.2045 9.62616 11.4273 9.51958 11.675C9.413 11.9227 9.358 12.19 9.358 12.4601C9.358 12.7303 9.413 12.9975 9.51958 13.2452C9.62616 13.4929 9.78207 13.7157 9.97744 13.8997C10.1729 14.0838 10.4037 14.2252 10.6555 14.3149C10.9073 14.4047 11.1747 14.441 11.441 14.4217H12.6933C15.7117 14.4176 18.6081 15.627 20.7452 17.7838C22.8824 19.9407 24.0853 22.8681 24.0892 25.9223C24.0932 28.9766 22.898 31.9072 20.7665 34.0698C18.635 36.2322 15.7418 37.4494 12.7234 37.4535Z"
        fill="url(#brandGradient)"
      />
    </svg>
  `,
  topHeading: parsedData.agent_type==='sales_leads'?"Sales Lead":parsedData.agent_type==='financial_analysis'?"Financial Report":"Research  Report",
  subHeading: 'Generated with SambaNova Agents'
})

async function generatePDFFromHtmOLd() {
  // Close the menu if open
  toggleMenu();

  // Get the content element to convert
  const contentElement = document.getElementById('chat-' + props.messageId);
  if (!contentElement) {
    console.error('Content element not found');
    return;
  }

  // Create a temporary wrapper element
  const wrapper = document.createElement('div');
  // Apply padding to match your PDF margins
  wrapper.style.padding = '10mm';

  // Create a header container for dynamic SVG logo and text
  const headerContainer = document.createElement('div');
  headerContainer.style.textAlign = 'center';
  headerContainer.style.marginBottom = '10mm';

  // Insert dynamic header content using template literals
  headerContainer.innerHTML = `
    <div style="display: flex; flex-direction: column; align-items: center;">
      ${headerConfig.value.SVGMarkup}
      <h1 style="margin: 5mm 0 0 0; font-size: 18pt;">${headerConfig.value.topHeading}</h1>
      <p style="margin: 0; font-size: 12pt;">${headerConfig.value.subHeading}</p>
    </div>
  `;

  // Append header and cloned content to the wrapper
  wrapper.appendChild(headerContainer);
  const clonedContent = contentElement.cloneNode(true);
  // Remove any extra top margin to avoid overlap
  clonedContent.style.marginTop = '0mm';
  wrapper.appendChild(clonedContent);

  // Define html2pdf options; margin is set to 0 because we're handling it in the wrapper
  const pdfOpts = {
    margin: 0,
    filename: 'financial_analysis.pdf',
    pagebreak: { mode: ['css', 'legacy'] },
    image: { type: 'jpeg', quality: 0.98 },
    html2canvas: { scale: 2, useCORS: true, letterRendering: true },
    jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
  };

  try {
    await html2pdf().set(pdfOpts).from(wrapper).save();
  } catch (e) {
    console.error('PDF error:', e);
  }
}


async function generatePDFFromHtml() {
  toggleMenu()
  const element = document.getElementById('chat-'+props.messageId)
  
 // Create a temporary wrapper element
 const wrapper = document.createElement('div');
  // Apply padding to match your PDF margins
  wrapper.style.padding = '10mm';

  // Create a header container for dynamic SVG logo and text
  const headerContainer = document.createElement('div');
  headerContainer.style.textAlign = 'center';
  headerContainer.style.marginBottom = '10mm';

  // Insert dynamic header content using template literals
  headerContainer.innerHTML = `
    <div style="display: flex; flex-direction: column; align-items: center;">
      ${headerConfig.value.SVGMarkup}
      <h1 style="margin: 5mm 0 0 0; font-size: 18pt;">${headerConfig.value.topHeading}</h1>
      <p style="margin: 0; font-size: 12pt;">${headerConfig.value.subHeading}</p>
    </div>
  `;


  // Append header and cloned content to the wrapper
  // wrapper.appendChild(headerContainer);
  // element.prepend(wrapper);
  // Remove any extra top margin to avoid overlap
  // clonedContent.style.marginTop = '0mm';
  // wrapper.appendChild(clonedContent);


  const pdfOpts = {
    margin: [10, 10],
    filename: 'download.pdf',
    pagebreak: { mode: ['css', 'legacy'] },
    image: { type: 'jpeg', quality: 0.98 },
    html2canvas: {
      scale: 2,
      useCORS: true,
      letterRendering: true
    },
    jsPDF: {
      unit: 'mm',
      format: 'a4',
      orientation: 'portrait'
    }
  }

  try {
    
    await html2pdf().set(pdfOpts).from(element).save()
  } catch(e) {
    console.error('PDF error:', e)
  }
  
}

async function generateSelectablePDF() {
  // For testing, we use the static element with id "pdf-content".
  const contentEl = document.getElementById('chat-'+props.messageId)
  if (!contentEl) {
    console.error('Content element not found')
    return
  }

  // Create a wrapper element to house the content with explicit styling.
  const wrapper = document.createElement('div')
  // Set a fixed width (in pixels) that approximates your intended PDF layout.
  // You may adjust this value (e.g., 800px) to better match your design.
  wrapper.style.width = '800px'
  wrapper.style.padding = '20px'
  wrapper.style.background = '#fff'
  // Inject the inner HTML from our test content.
  wrapper.innerHTML = contentEl.innerHTML
  
  // Append the wrapper offscreen so that html2canvas can fully render it.
  wrapper.style.position = 'absolute'
  wrapper.style.top = '-10000px'
  document.body.appendChild(wrapper)

  // Wait for the DOM to update and a short delay to ensure full rendering.
  await nextTick()
  setTimeout(() => {
    // Create a new jsPDF instance.
    // Using unit: 'px' here helps to more directly map from CSS pixels.
    const doc = new jsPDF({
      unit: 'px',
      format: 'a4',
      orientation: 'portrait'
    })

    // Render the wrapper using jsPDF's html() method.
    doc.html(wrapper, {
      callback: function (doc) {
        console.log('PDF rendering complete. Saving PDF...')
        doc.save('output.pdf')
        // Clean up the temporary wrapper.
        document.body.removeChild(wrapper)
      },
      // Set starting coordinates inside the PDF.
      x: 10,
      y: 10,
      // Specify the content width in the PDF (in px).
      width: 800,
      // Adjust html2canvas options.
      html2canvas: {
        scale: 1, // lower scale if text is too large; you can try 1 or 1.5
        useCORS: true,
        // This helps html2canvas know the intended width of the element.
        windowWidth: wrapper.scrollWidth
      }
    })
  }, 500) // A delay of 500ms; adjust if necessary
}





  </script>

<style scoped>
.inline-ref {
  @apply text-blue-600 hover:text-blue-800 text-xs font-medium no-underline;
  text-decoration: none !important;
}

.inline-ref:hover {
  @apply underline;
}

/* Status bar animations */
.animate-spin {
  animation: spin 1.5s linear infinite;
}

.animate-bounce {
  animation: bounce 1s infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@keyframes bounce {
  0%, 20%, 50%, 80%, 100% {
    transform: translateY(0);
  }
  40% {
    transform: translateY(-4px);
  }
  60% {
    transform: translateY(-2px);
  }
}

/* Smooth status transitions */
.status-transition {
  transition: all 0.3s ease-in-out;
}

/* Status bar hover effect */
.status-bar:hover {
  @apply bg-gray-100;
  transition: background-color 0.2s ease-in-out;
}
</style>