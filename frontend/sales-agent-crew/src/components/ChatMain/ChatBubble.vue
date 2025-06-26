<template>
  <div v-if="showBubble">
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
                  <span class="text-xs text-white">◆</span>
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

        <!-- Model usage cards -->
        <div v-if="workflowData && workflowData.length" class="px-3 pt-3 pb-1 bg-gray-50 border-b">
          <div class="flex items-start justify-between">
            <div class="flex-1">
              <WorkflowDataItem :workflowData="workflowData" />
            </div>
          </div>
        </div>

        <!-- Actual Streaming Response Content -->
        <div class="p-4">
          <!-- Always use markdown rendering for text content to ensure consistent formatting -->
          <div class="prose prose-sm max-w-none">
            <div 
              v-if="streamingResponseContent && typeof streamingResponseContent === 'string'"
              class="text-gray-800"
              v-html="renderMarkdown(streamingResponseContent)"
            ></div>
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
                  <span v-if="source.type === 'web'">○</span>
                  <span v-else-if="source.type === 'arxiv'">▫</span>
                  <span v-else>•</span>
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
                  <span v-if="source.type === 'web'">○</span>
                  <span v-else-if="source.type === 'arxiv'">▫</span>
                  <span v-else>•</span>
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
          
          <!-- Final Response Component for specialized responses (financial_analysis_end, etc.) -->
          <div v-if="finalResponseComponent && finalResponseData">
            <component :is="finalResponseComponent" :parsed="finalResponseData" />
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

          <!-- PDF Download Button for Deep Research - Moved to bottom -->
          <div v-if="deepResearchPdfFileId" class="mt-4 flex justify-center">
            <button 
              @click="downloadPdf(deepResearchPdfFileId, deepResearchPdfFilename)"
              class="inline-flex items-center gap-2 px-4 py-2 bg-gray-600 hover:bg-gray-700 rounded-lg text-sm text-white font-medium transition-colors shadow-sm hover:shadow-md"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
              </svg>
              Download PDF Report
            </button>
          </div>
        </div>
      </div>
    </li>

    <!-- Human/User message -->
    <li
      v-else-if="isUserMessage" 
      class="flex px-4 items-center gap-x-2 sm:gap-x-4"
    >
      <div class="grow text-end space-y-3">
        <!-- Card -->
        <div class="inline-block flex justify-end">
          <div class="text-sm text-left color-primary-brandGray max-w-[80%] w-auto space-y-2">
            <!-- Handle content array format -->
            <template v-if="userMessageContent.length > 0">
              <template v-for="(item, index) in userMessageContent" :key="index">
                <!-- Text content -->
                <p v-if="item.type === 'text'">
                  {{ item.text }}
                </p>
                <!-- Image content -->
                <div v-else-if="item.type === 'image_url'">
                  <img 
                    :src="item.image_url.url" 
                    alt="User uploaded image"
                    class="max-w-xs max-h-48 rounded-lg shadow-sm object-contain mt-2"
                  />
                </div>
              </template>
            </template>
            <!-- Fallback for simple text format -->
            <p v-else>
              {{ parsedData.message || parsedData.content || props.data }}
            </p>
          </div>
        </div>
        <!-- End Card -->
      </div>
      <UserAvatar :type="'user'" />
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
                v-if="parsedData?.agent_type==='sales_leads'||parsedData?.agent_type==='financial_analysis'||parsedData?.agent_type==='deep_research'"
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
      <div v-if="selectedComponent" class="w-full bg-white">          
        <!-- Main response component -->
        <component :id="'chat-'+messageId" :is="selectedComponent" :parsed="parsedData" />
      </div>
    </li>

    <!-- Daytona Sidebar and Artifact Canvas now managed at ChatView level -->
  </div>
</template>
  
  <script setup>
  import { computed, defineProps, ref,watch,nextTick, provide, defineEmits } from 'vue'
  
  import UserAvatar from '@/components/Common/UIComponents/UserAvtar.vue'
  import AssistantComponent from '@/components/ChatMain/ResponseTypes/AssistantComponent.vue'
  import UserProxyComponent from '@/components/ChatMain/ResponseTypes/UserProxyComponent.vue'
  import SalesLeadComponent from '@/components/ChatMain/ResponseTypes/SalesLeadsComponent.vue'
  import EducationalComponent from '@/components/ChatMain/EducationalComponent.vue'
  import UnknownTypeComponent from '@/components/ChatMain/ResponseTypes/UnknownTypeComponent.vue'
  import FinancialAnalysisComponent from '@/components/ChatMain/ResponseTypes/FinancialAnalysisComponent.vue'
  import DeepResearchComponent from '@/components/ChatMain/ResponseTypes//DeepResearchComponent.vue'
  import ErrorComponent from '@/components/ChatMain/ResponseTypes/ErrorComponent.vue'
  import AssistantEndComponent from '@/components/ChatMain/ResponseTypes/AssistantEndComponent.vue'
  import FinancialAnalysisEndComponent from '@/components/ChatMain/ResponseTypes/FinancialAnalysisEndComponent.vue'
  import SalesLeadsEndComponent from '@/components/ChatMain/ResponseTypes/SalesLeadsEndComponent.vue'
  import WorkflowDataItem from '@/components/ChatMain/WorkflowDataItem.vue'

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
import { renderMarkdown } from '@/utils/markdownRenderer'
import { isFinalAgentType } from '@/utils/globalFunctions.js'


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
  
  function getTextAfterLastSlash(str) {
    if (!str) return ''
    if (!str.includes('/')) return str
    return str.substring(str.lastIndexOf('/') + 1)
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
  },
  
  isLoading: {
    type: Boolean,
    default: false
  },
  
  sidebarOpen: {
    type: Boolean,
    default: false
  },
  
  isInDeepResearch: {
    type: Boolean,
    default: false
  }
  
  })
  
  // Sidebar management moved to ChatView level
  
  // Define emits for communicating with parent ChatView
  const emit = defineEmits(['open-daytona-sidebar', 'open-artifact-canvas'])
  
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
    if (!props.data) return {}
    try {
      const parsed = JSON.parse(props.data)
      return parsed || {}
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
      case 'react_end':
        return AssistantEndComponent
      case 'error':
        return ErrorComponent
      case 'financial_analysis_end':
        return FinancialAnalysisEndComponent
      case 'sales_leads_end':
        return SalesLeadsEndComponent
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

// Sidebar state now managed at ChatView level

// Functions to communicate with ChatView for sidebar control
function openArtifact(artifact) {
  emit('open-artifact-canvas', artifact)
}

function reopenDaytonaSidebar() {
  console.log('ChatBubble: Reopening Daytona sidebar, emitting event...')
  // Pass the specific streaming events from this message
  emit('open-daytona-sidebar', props.streamingEvents)
  console.log('ChatBubble: Event emitted')
}

// Detect Daytona usage for showing controls - ENHANCED FOR LOADED CONVERSATIONS
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

// Get artifacts for display (keeping the existing computed property)
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

// Extract streaming response content with better parsing
const streamingResponseContent = computed(() => {
  if (!props.streamingEvents || !Array.isArray(props.streamingEvents)) return ''
  
  try {
    // First, look for the final completed response (react_end, financial_analysis_end, sales_leads_end, deep_research_interrupt)
    for (let i = props.streamingEvents.length - 1; i >= 0; i--) {
      const event = props.streamingEvents[i]
      if (!event || !event.data) continue
      
      const agentType = getAgentType(event)
      if (event.event === 'agent_completion' && 
          isFinalAgentType(agentType)) {
        // Special handling for final agent types that have specialized components
        // Don't show in streaming content as they have their own specialized components
        if (agentType === 'financial_analysis_end' || 
            agentType === 'sales_leads_end' || 
            agentType === 'react_end') {
          return ''
        }
        // For deep_research_interrupt and other final responses, ensure content is a string
        const content = event.data?.content || event.content || ''
        return typeof content === 'string' ? content : ''
      }
    }
  } catch (error) {
    console.error('Error processing streaming content:', error)
    return ''
  }
  
  // Default behavior for non-deep-research flows
  // If no completed response, find the largest streaming content that's not a tool call
  let bestContent = ''
  let maxLength = 0
  
  props.streamingEvents.forEach(event => {
    if (event.event === 'llm_stream_chunk' && 
        event.data.content && 
        !event.data.content.includes('<tool>') && 
        !event.data.content.includes('<subgraph>') &&
        event.data.content.trim()) {
      
      const content = event.data.content.trim()

      if (props.isInDeepResearch) {
        console.log('Deep research flow detected, hiding main content')
        return ''
      }

      // Prefer longer content as it's likely the main response
      if (content.length > maxLength) {
        maxLength = content.length
        bestContent = content
      }
    }
  })
  
  return bestContent
})

// Get the final response component based on the agent_type
const finalResponseComponent = computed(() => {
  if (!props.streamingEvents || !Array.isArray(props.streamingEvents)) return null
  
  try {
    // Look for the final agent_completion event with a specific agent_type
    for (let i = props.streamingEvents.length - 1; i >= 0; i--) {
      const event = props.streamingEvents[i]
      if (!event || event.event !== 'agent_completion') continue
      
      const agentType = getAgentType(event)
      
      switch (agentType) {
        case 'financial_analysis_end':
          return FinancialAnalysisEndComponent
        case 'sales_leads_end':
          return SalesLeadsEndComponent
        case 'react_end':
          return AssistantEndComponent
        default:
          continue
      }
    }
  } catch (error) {
    console.error('Error getting final response component:', error)
  }
  
  return null
})

// Get the final response data formatted for the component
const finalResponseData = computed(() => {
  if (!props.streamingEvents) return {}
  
  // Look for the final agent_completion event with the response data
  for (let i = props.streamingEvents.length - 1; i >= 0; i--) {
    const event = props.streamingEvents[i]
    // Robust agent_type detection to ensure real-time updates
    const agentType = getAgentType(event)
    if (event.event === 'agent_completion' &&
        isFinalAgentType(agentType)) {
      try {
        const content = event.data?.content || event.content || ''
        
        // If content is structured JSON, parse it and use specialized component
        if (typeof content === 'string' && content.trim().startsWith('{') && content.trim().endsWith('}')) {
          return { content: JSON.parse(content) }
        }
        
        // For markdown content, return it directly so AssistantEndComponent can render it
        return { content: content }
      } catch (error) {
        console.error('Error parsing final response data:', error)
        return { content: event.data?.content || event.content || '' }
      }
    }
  }
  
  return {}
})



// Extract sources from tool results with proper titles and domains
const toolSources = computed(() => {
  if (!props.streamingEvents || !Array.isArray(props.streamingEvents)) return []
  
  const sources = []
  
  props.streamingEvents.forEach(event => {
    // Handle Tavily sources - multiple formats for real-time vs persistence
    if (event.event === 'agent_completion') {
      // Format 1: LiberalFunctionMessage with name = 'search_tavily'
      if (event.data.type === 'LiberalFunctionMessage' && event.data.name === 'search_tavily') {
        let sourcesArray = []
        
        // Parse sources from different possible formats
        if (Array.isArray(event.data.content)) {
          sourcesArray = event.data.content
        } else if (typeof event.data.content === 'string') {
          sourcesArray = parsePythonStyleJSON(event.data.content)
          if (!Array.isArray(sourcesArray)) {
            sourcesArray = []
          }
        }
        
        if (sourcesArray.length > 0) {
          sourcesArray.forEach(source => {
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
        }
      }
      // Format 2: agent_type = 'tool_response' (for persistence)
      else if (event.data.agent_type === 'tool_response' && event.data.content) {
        let sourcesArray = []
        
        if (typeof event.data.content === 'string') {
          sourcesArray = parsePythonStyleJSON(event.data.content)
          if (!Array.isArray(sourcesArray)) {
            sourcesArray = []
          }
        }
        
        if (sourcesArray.length > 0) {
          sourcesArray.forEach(source => {
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
            
            sources.push({
              title: displayTitle || 'Untitled',
              domain: domain || '',
              url: source.url || '',
              content: source.content ? source.content.substring(0, 200) + '...' : '',
              type: 'web'
            })
          })
        }
      }
      // Handle arXiv sources
      else if (event.data.name === 'arxiv') {
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

// Modal state for artifact display already defined below

function formatEventTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString([], { 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit'
  })
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

// Helper function to parse Python-style JSON with single quotes
function parsePythonStyleJSON(jsonString) {
  try {
    // First try regular JSON parsing
    return JSON.parse(jsonString);
  } catch (e) {
    // If that fails, try to handle Python-style single quotes
    try {
      // Use a more sophisticated approach to handle Python-style JSON
      // This regex-based approach is more robust for handling nested quotes
      let processedString = jsonString;
      
      // Replace Python-style single quotes with double quotes, but preserve escaped quotes
      // This handles cases like: [{'url': 'https://example.com', 'content': 'The company\'s mission...'}]
      processedString = processedString
        .replace(/'/g, '"')  // Replace all single quotes with double quotes
        .replace(/\\"/g, "'") // Restore escaped quotes back to single quotes
        .replace(/"(\w+)":/g, '"$1":') // Ensure property names are double-quoted
        .replace(/:\s*"([^"]*)"(?=\s*[,}])/g, ':"$1"'); // Ensure string values are properly quoted
      
      return JSON.parse(processedString);
    } catch (e2) {
      // If still failing, try using eval as last resort (safer than before)
      try {
        // This is a controlled eval - we know the source is from our backend
        const result = eval('(' + jsonString + ')');
        return result;
      } catch (e3) {
        console.error('Failed to parse JSON with all methods:', e3);
        return null;
      }
    }
  }
}

// Helper to reliably extract agent_type from different possible locations in the event object
function getAgentType (event) {
  if (!event || typeof event !== 'object') return null
  try {
    return (
      event?.data?.agent_type ||
      event?.data?.additional_kwargs?.agent_type ||
      event?.additional_kwargs?.agent_type ||
      event?.agent_type ||
      null
    )
  } catch (error) {
    return null
  }
}

// Parse user message content array for mixed text/image content
const userMessageContent = computed(() => {
  try {
    if (props.event === 'agent_completion' && 
        (parsedData.value?.additional_kwargs?.agent_type === 'human' || 
         parsedData.value?.type === 'HumanMessage')) {
      
      // Check if content is an array (with text and images)
      if (Array.isArray(parsedData.value?.content)) {
        return parsedData.value.content
      }
    }
  } catch (error) {
    console.error('Error parsing user message content:', error)
  }
  
  return []
})

// Check if this is a user/human message
const isUserMessage = computed(() => {
  try {
    return (props.event === 'agent_completion' && 
           (parsedData.value?.additional_kwargs?.agent_type === 'human' ||
            parsedData.value?.type === 'HumanMessage'))
  } catch (error) {
    return false
  }
})



// Decide whether this bubble should be rendered (skip internal or debug-only messages)
const showBubble = computed(() => {
  try {
    // Always show if this bubble carries streamingEvents (status line)
    if (props.streamingEvents) return true

    // Always show user messages
    if (isUserMessage.value) return true

    // Empty or whitespace-only data – skip
    if (!props.data || String(props.data).trim() === '') return false

    // Raw subgraph payload – skip
    if (String(props.data).includes('<subgraph')) return false

    // Internal agent types we never surface
    const internalTypes = ['react_subgraph', 'react_tool', 'tool_response', 'routing']
    const agentType = parsedData.value?.agent_type
    if (internalTypes.includes(agentType)) return false

    // If component to be rendered is UnknownTypeComponent (and no streaming events), hide
    if (selectedComponent.value === UnknownTypeComponent) return false

    return true
  } catch (error) {
    console.error('Error in showBubble computed:', error)
    return false
  }
})

// Sidebar state management moved to ChatView level

 // Track if the sidebar should be shown (controlled by parent ChatView)
 const showDaytonaSidebar = computed(() => {
   return props.sidebarOpen
   })

// Streaming status and audit log properties that were accidentally removed
const currentStreamingStatus = computed(() => {
  // Handle cases with no streaming events
  if (!props.streamingEvents || props.streamingEvents.length === 0) {
    return props.workflowData?.length > 0 ? '✓ Response complete' : '○ Starting...';
  }
  
  const events = props.streamingEvents;
  let currentTool = null;
  let toolQuery = null;
  let latestCompletion = null;
  let hasStreamingContent = false;
  
  // Single pass through events to gather all necessary information
  events.forEach(event => {
    const data = event.data;
    
    // Track tool calls
    if (event.event === 'llm_stream_chunk' && data.content?.includes('<tool>')) {
      const toolMatch = data.content.match(/<tool>([^<]+)<\/tool>/);
      const inputMatch = data.content.match(/<tool_input>([^<\n\r]+)/);
      
      if (toolMatch) {
        currentTool = toolMatch[1];
        toolQuery = inputMatch?.[1]?.trim();
      }
    }
    
        // Track tool completions
    if (event.event === 'agent_completion' && data.type === 'LiberalFunctionMessage' && data.name) {
      const { name, content } = data;
      if (name === 'search_tavily' && Array.isArray(content)) {
        latestCompletion = `✓ Found ${content.length} web sources`;
      } else if (name === 'arxiv') {
        const papers = content?.includes('Title:') ? content.split('Title:').length - 1 : 1;
        latestCompletion = `✓ Found ${papers} arXiv papers`;
      } else if (name === 'DaytonaCodeSandbox') {
        latestCompletion = `✓ Code execution complete`;
      }
    }
    
    // Track deep research events
    if (event.event === 'agent_completion') {
      const agentType = data.additional_kwargs?.agent_type || data.agent_type;
      const agentTypeMap = {
        'deep_research_search_queries_plan': '◦ Planning search queries',
        'deep_research_search_queries_plan_fixed': '↻ Plan format corrected',
        'deep_research_search_sections': '▫ Creating research sections',
        'deep_research_interrupt': '○ User feedback required',
        'deep_research_search_queries_section': '• Section search queries',
        'deep_research_search_queries_section_fixed': '↻ Section format corrected',
        'deep_research_writer': '◆ Writing content',
        'deep_research_grader': '◈ Evaluating quality',
        'deep_research_end': '✓ Research complete',
        'react_subgraph_deep_research': '◐ Deep research started',
        'react_subgraph_financial_analysis': '◐ Financial analysis started',
        'react_end': '✓ Response complete',
        'financial_analysis_end': '✓ Financial analysis complete'
      };
      
      if (agentTypeMap[agentType]) {
        latestCompletion = agentTypeMap[agentType];
      }
    }
    
    // Check for streaming response content
    if (event.event === 'llm_stream_chunk' && 
        data.content?.trim() && 
        !data.content.includes('<tool>')) {
      hasStreamingContent = true;
    }
  });
  
  // Return status based on priority
  if (latestCompletion) return latestCompletion;
  if (hasStreamingContent) return '◆ Streaming response...';
  
  // Show current tool status
  if (currentTool) {
    const toolMap = {
      'search_tavily': `○ Searching web: "${toolQuery || 'query'}"`,
      'arxiv': `▫ Searching arXiv: "${toolQuery || 'query'}"`,
      'DaytonaCodeSandbox': `◐ Executing code in sandbox`
    };
    return toolMap[currentTool] || `• Using ${currentTool.replace('_', ' ')}: "${toolQuery || 'executing'}"`;
  }
  
  // Final fallbacks
  const lastEvent = events[events.length - 1];
  if (lastEvent?.event === 'stream_complete') return '✓ Response complete';
  
  return '◦ Processing...';
})

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
        return `✓ ${completedTasks.join(' • ')}`;
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
    return `✓ ${completedTools.join(' • ')}`
  }
  
  return 'Details'
})

const showSearchingAnimation = computed(() => {
  if (!props.streamingEvents || props.streamingEvents.length === 0) return false
  
  const status = currentStreamingStatus.value
  // Show bouncing dots specifically for search operations
  return status.includes('○ Searching') || status.includes('▫ Searching')
})

const hasCompletedEvents = computed(() => {
  if (!props.streamingEvents || props.streamingEvents.length === 0) {
    // For loaded conversations, check if we have any tool-related or completion events
    if (props.workflowData && props.workflowData.length > 0) return true;
    return false;
  }
  
  // Check for any completed tool executions, final responses, or tool-related events
  return props.streamingEvents.some(event => 
    (event.event === 'agent_completion' && event.data.type === 'LiberalFunctionMessage') ||
    (event.event === 'agent_completion' && event.data.name === 'DaytonaCodeSandbox') ||
    (event.event === 'agent_completion' && event.data.name === 'search_tavily') ||
    (event.event === 'agent_completion' && event.data.name === 'arxiv') ||
    (event.event === 'stream_complete') ||
    (event.event === 'agent_completion' && isFinalAgentType(event.data.agent_type)) ||
    (event.isToolRelated || event.isDaytonaRelated) || // Check our custom flags
    event.event === 'agent_completion' || event.event === 'stream_complete'
  )
})

const auditLogEvents = computed(() => {
  if (!props.streamingEvents || props.streamingEvents.length === 0) {
    // For loaded conversations without streaming events, create synthetic audit log from workflow data
    if (props.workflowData && props.workflowData.length > 0) {
      return props.workflowData.map((workflow, index) => ({
        id: `synthetic-audit-${index}`,
        title: `✓ ${workflow.agent_name || 'Agent'} - ${workflow.task || 'Task'}`,
        details: workflow.tool_name ? `Tool: ${workflow.tool_name}` : 'Completed successfully',
        subItems: [],
        dotClass: 'bg-gray-400',
        type: 'tool_result',
        event: 'workflow_item',
        timestamp: new Date().toISOString(),
        fullData: workflow
      }));
    }
    return [];
  }
  
  return props.streamingEvents
    .filter(event => {
      // Keep meaningful events
      if (event.event === 'stream_start') return false
      if (event.event === 'stream_complete') return false
      if (event.event === 'agent_completion' && event.data.agent_type === 'human') return false
      if (event.event === 'agent_completion' && isFinalAgentType(event.data.agent_type)) return false
      
      // Special handling for deep research events - include all phases except final in audit log
      const agentType = getAgentType(event)
      if (agentType === 'deep_research_search_queries_plan' || 
          agentType === 'deep_research_search_queries_plan_fixed' ||
          agentType === 'deep_research_search_sections' ||
          agentType === 'deep_research_search_queries_section' ||
          agentType === 'deep_research_search_queries_section_fixed' ||
          agentType === 'deep_research_writer' ||
          agentType === 'deep_research_grader' ||
          agentType === 'react_subgraph_deep_research') {
        return true // Include deep research phases in audit log
      }
      
      if (event.event === 'llm_stream_chunk' && event.data.content && !event.data.content.includes('<tool>')) return false
      
      return true
    })
    .map((event, index) => {
      const data = event.data
      let title = ''
      let details = ''
      let dotClass = 'bg-gray-400'
      let type = 'info'
      
      if (event.event === 'llm_stream_chunk' && data.content && data.content.includes('<tool>')) {
        const toolMatch = data.content.match(/<tool>([^<]+)<\/tool>/)
        const inputMatch = data.content.match(/<tool_input>([^<\n\r]+)/)
        
        if (toolMatch) {
          const tool = toolMatch[1]
          const query = inputMatch ? inputMatch[1].trim() : 'No query'
          
          if (tool === 'search_tavily') {
            title = `Search Tavily`
            details = `Query: "${query}"`
          } else if (tool === 'arxiv') {
            title = `Search arXiv`
            details = `Query: "${query}"`
          } else if (tool === 'DaytonaCodeSandbox') {
            title = `Execute Code`
            details = 'Running analysis in sandbox'
          } else {
            title = `${tool.replace('_', ' ')}`
            details = `Query: "${query}"`
          }
          dotClass = 'bg-gray-400'
          type = 'tool_call'
        }
      } else if (event.event === 'agent_completion' && data.type === 'LiberalFunctionMessage' && data.name) {
        if (data.name === 'search_tavily') {
          const resultCount = Array.isArray(data.content) ? data.content.length : 0
          title = `Found ${resultCount} web sources`
          details = resultCount > 0 ? 'Search completed successfully' : 'No sources found'
          dotClass = 'bg-gray-400'
          type = 'tool_result'
        } else if (data.name === 'arxiv') {
          const papers = data.content && data.content.includes('Title:') ? 
            data.content.split('Title:').length - 1 : 1
          title = `Found ${papers} arXiv papers`
          dotClass = 'bg-gray-400'
          type = 'tool_result'
        } else if (data.name === 'DaytonaCodeSandbox') {
          title = `Code execution complete`
          details = 'Generated charts and analysis'
          dotClass = 'bg-gray-400'
          type = 'tool_result'
        }
      } else if (event.event === 'agent_completion') {
        // Handle deep research agent types
        const agentType = getAgentType(event)
        if (agentType === 'react_subgraph_deep_research') {
          title = `Deep Research Started`
          details = 'Initializing comprehensive research workflow'
          dotClass = 'bg-gray-400'
          type = 'deep_research_start'
        } else if (agentType === 'deep_research_search_queries_plan') {
          title = 'Research Planning'
          details = 'Generating search queries and research strategy'
          dotClass = 'bg-gray-400'
          type = 'deep_research_planning'
        } else if (agentType === 'deep_research_search_queries_plan_fixed') {
          title = `Research Plan Refined`
          details = 'Optimizing search queries for better results'
          dotClass = 'bg-gray-400'
          type = 'deep_research_planning'
        } else if (agentType === 'deep_research_search_sections') {
          title = `▫ Research Sections Defined`
          details = 'Organizing research into structured sections'
          dotClass = 'bg-gray-400'
          type = 'deep_research_sections'
        } else if (agentType === 'deep_research_search_queries_section') {
          title = `Section Search Queries`
          details = 'Generating search queries for each section of the plan'
          dotClass = 'bg-gray-400'
          type = 'deep_research_section_queries'
        } else if (agentType === 'deep_research_search_queries_section_fixed') {
          title = `Section Queries Refined`
          details = 'Retrying section format that was incorrect'
          dotClass = 'bg-gray-400'
          type = 'deep_research_section_queries_fixed'
        } else if (agentType === 'deep_research_writer') {
          title = `Content Generation`
          details = 'Generating written content for a section'
          dotClass = 'bg-gray-400'
          type = 'deep_research_writer'
        } else if (agentType === 'deep_research_grader') {
          title = `Quality Evaluation`
          details = 'Evaluating section quality and completeness'
          dotClass = 'bg-gray-400'
          type = 'deep_research_grader'
        }
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

// Check if there's an auto-generated PDF file for deep research
const deepResearchPdfFileId = computed(() => {
  // Check streaming events first
  if (props.streamingEvents) {
    const event = props.streamingEvents.find(e => 
      e.event === 'agent_completion' && 
      e.additional_kwargs?.agent_type === 'deep_research_end' &&
      e.additional_kwargs?.deep_research_pdf_file_id
    );
    if (event) {
      return event.additional_kwargs.deep_research_pdf_file_id;
    }
    
    // Also check if the data is nested differently
    const eventWithData = props.streamingEvents.find(e => 
      e.event === 'agent_completion' && 
      e.data?.additional_kwargs?.agent_type === 'deep_research_end' &&
      e.data?.additional_kwargs?.deep_research_pdf_file_id
    );
    if (eventWithData) {
      return eventWithData.data.additional_kwargs.deep_research_pdf_file_id;
    }
  }
  
  // Check parsed data for non-streaming messages
  if (parsedData.value?.additional_kwargs?.deep_research_pdf_file_id) {
    return parsedData.value.additional_kwargs.deep_research_pdf_file_id;
  }
  
  return null;
})

const deepResearchPdfFilename = computed(() => {
  // Check streaming events first
  if (props.streamingEvents) {
    const event = props.streamingEvents.find(e => 
      e.event === 'agent_completion' && 
      e.additional_kwargs?.agent_type === 'deep_research_end' &&
      e.additional_kwargs?.deep_research_pdf_filename
    );
    if (event) {
      return event.additional_kwargs.deep_research_pdf_filename;
    }
    
    // Also check if the data is nested differently
    const eventWithData = props.streamingEvents.find(e => 
      e.event === 'agent_completion' && 
      e.data?.additional_kwargs?.agent_type === 'deep_research_end' &&
      e.data?.additional_kwargs?.deep_research_pdf_filename
    );
    if (eventWithData) {
      return eventWithData.data.additional_kwargs.deep_research_pdf_filename;
    }
  }
  
  // Check parsed data for non-streaming messages
  if (parsedData.value?.additional_kwargs?.deep_research_pdf_filename) {
    return parsedData.value.additional_kwargs.deep_research_pdf_filename;
  }
  
  return null;
})

// Function to download PDF with authentication
async function downloadPdf(fileId, filename) {
  try {
    // Get the auth token from Clerk
    const token = await window.Clerk.session.getToken();
    
    if (!token) {
      console.error('No authentication token found');
      return;
    }

    // Make authenticated request to download the PDF
    const response = await fetch(`/api/files/${fileId}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    // Get the PDF blob
    const blob = await response.blob();
    
    // Create download link
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename || 'deep_research_report.pdf';
    
    // Trigger download
    document.body.appendChild(link);
    link.click();
    
    // Cleanup
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    
  } catch (error) {
    console.error('Error downloading PDF:', error);
    // You could add a toast notification here if available
  }
}

function closeArtifactCanvas() {
  // Implementation of closeArtifactCanvas function
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