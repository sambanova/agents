<template>

  <!-- isLoading {{ props.streamData }} -->
  <div class="flex flex-col p-4 border rounded">
    <!-- 1) Heading, updates to last tool name -->
    <h2 class="text-xl font-bold mb-4">
      Current Tool: {{ currentToolName || '– none –' }}
    </h2>

    <!-- 2) Timeline (static) -->
    <div class="flex space-x-6 mb-4">
      <div
        v-for="(tool, idx) in toolTimeline"
        :key="idx"
        class="relative pl-4 text-gray-700"
      >
        <!-- connector line -->
        <div class="absolute left-0 top-1/2 w-2 h-2 rounded-full border-2 border-gray-500 bg-white transform -translate-y-1/2"></div>
        {{ tool }}
      </div>
    </div>

    <!-- 3) Description box (scrollable, max-height 300px) -->
    <div
      ref="descContainer"
      class=" p-3 overflow-y-auto"
      style="max-height: 150px;"
    >
      {{ description }}
    </div>
  </div>
     <div v-if="toolSources.length" class="px-4 py-2">
          <div class="flex flex-wrap gap-2">
            <a
              v-for="src in toolSources"
              :key="src.url || src.title"
              :href="src.url"
              target="_blank"
              class="inline-flex items-center gap-1 px-2 py-1 bg-gray-50 dark:bg-gray-700 border dark:border-gray-600 rounded text-xs text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600 transition"
            >
              <span v-if="src.type==='web'">🌐</span>
              <span v-else-if="src.type==='arxiv'">📚</span>
              <span class="truncate max-w-[120px]">{{ src.title }}</span>
            </a>
          </div>
        </div>


  <div
    
    class="p-3 dark:bg-gray-700 border-b dark:border-gray-600 max-h-96 overflow-y-auto"
  >
    <div class="text-xs font-medium text-gray-600 dark:text-gray-300 mb-3">
      Comprehensive Audit Log
    </div>

    <!-- wrap everything in a relative container with left padding for dots -->
    <div class="relative space-y-3 pl-6">
      <div
        v-for="(event, idx) in auditLogEvents"
        :key="event.id"
        class="relative"
      >
        <!-- dot -->
        <div
          class="absolute left-0 top-0 w-3 h-3 bg-[#EAECF0] dark:bg-white rounded-full  "
        ></div>
        <!-- connector line (all but last) -->
        <div
          v-if="idx < auditLogEvents.length - 1"
          class="absolute left-1.5 top-5 bottom-0 border-l-2 border-gray-200 dark:border-gray-600"
        ></div>

        <!-- your existing content, indented to the right of the dot -->
        <div class="flex items-start space-x-2 ml-6">
          <div class="flex-1">
            <div class="flex justify-between">
              <span
                class="text-xs font-medium text-gray-900 dark:text-gray-100"
              >
                {{ event.title }}
              </span>
              <span class="text-xs text-gray-400 dark:text-gray-500">
                {{ formatEventTime(event.timestamp) }}
              </span>
            </div>

            <div
              v-if="event.details"
              class="text-xs text-gray-600 dark:text-gray-400 mt-1"
            >
              {{ event.details }}
            </div>

            <div
              v-if="event.subItems?.length"
              class="mt-2 ml-4 space-y-1 text-xs text-gray-600 dark:text-gray-400"
            >
              <div
                v-for="sub in event.subItems"
                :key="sub.id"
                class="flex items-start space-x-1"
              >
                <span>•</span>
                <span>
                  {{ sub.title }}
                  <span v-if="sub.domain">({{ sub.domain }})</span>
                </span>
              </div>
            </div>

            <div class="text-xs text-gray-400 dark:text-gray-600 mt-1">
              <span
                class="bg-gray-100 dark:bg-gray-600 px-1 rounded"
              >{{ event.event }}</span>
              <span
                v-if="event.type"
                class="bg-blue-100 dark:bg-blue-600 px-1 rounded ml-1"
              >{{ event.type }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'

const props = defineProps({
  streamData: {
    type: Array,
    default: () => []
  },
   isLoading: {
    type: Boolean,
    default: true
  }
})

// helper to pull tool name out of "<tool>NAME</tool>"
function extractToolName(content) {
  const m = /<tool>(.*?)<\/tool>/.exec(content)
  return m ? m[1] : ''
}

// 1) All tool names seen so far
const toolTimeline = computed(() =>
  props.streamData
    .filter(
      i =>
        i.event === 'agent_completion' &&
        i.additional_kwargs?.agent_type === 'react_tool'
    )
    .map(i => extractToolName(i.content))
)

// 2) Current (last) tool
const currentToolName = computed(() =>
  toolTimeline.value.length
    ? toolTimeline.value[toolTimeline.value.length - 1]
    : ''
)

// 3) Full concatenated description
const description = computed(() =>
  props.streamData
    .filter(i =>
      ['stream_start', 'llm_stream_chunk', 'stream_complete'].includes(
        i.event
      )
    )
    .map(i => i.content)
    .join('')
)

// 4) Auto‐scroll description to bottom on change
const descContainer = ref(null)
watch(description, () => {
  nextTick(() => {
    if (descContainer.value) {
      descContainer.value.scrollTop = descContainer.value.scrollHeight
    }
  })
})


const toolSources = computed(() => {
  if (!props.streamData || !Array.isArray(props.streamData)) return []
  
  const sources = []
  
  props.streamData.forEach(event => {
    if (event.event === 'agent_completion' && 
        event.type === 'LiberalFunctionMessage' && 
        event.name === 'search_tavily' &&
        Array.isArray(event.content)) {
      
      event.content.forEach(source => {
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
    } else if (event.name === 'arxiv') {
      // Parse arXiv results - remove the broken URL construction
      const content = event.content || ''
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


const auditLogEvents = computed(() => {
  if (!props.streamData || props.streamData.length === 0) {
   
    // For loaded conversations without streaming events, create synthetic audit log from workflow data
    if (props.workflowData && props.workflowData.length > 0) {
      console.log('Creating synthetic audit log from workflow data');
      
      // Deduplicate workflow data based on task and tool name
      const uniqueWorkflows = [];
      const seenWorkflowKeys = new Set();
      
      props.workflowData.forEach(workflow => {
         console.log("auditLogEvents",workflow)
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
  
  props.streamData.forEach(event => {
    // Create a unique key based on event content for deduplication
    let eventKey = '';
    
    if (event.event === 'llm_stream_chunk' && event?.content?.includes('<tool>')) {
      // For tool calls, use tool name + timestamp
      const toolMatch = event.content.match(/<tool>([^<]+)<\/tool>/);
      if (toolMatch) {
        eventKey = `tool-${toolMatch[1]}-${event.content.timestamp || event.timestamp}`;
      }
    } else if (event.event === 'agent_completion' && event.content?.name) {
      // For tool responses, use tool name + content hash for deduplication
      const contentHash = event.content.content ? String(event.content.content).substring(0, 50) : '';
      eventKey = `completion-${event.content.name}-${contentHash}`;
    } else if (event.event === 'agent_completion' && event.content?.agent_type) {
      // For other agent completions, use agent_type + timestamp
      eventKey = `agent-${event.content.agent_type}-${event.content.timestamp || event.timestamp}`;
    } else {
      // For other events, use event type + timestamp
      eventKey = `${event.event}-${event.content?.timestamp || event.timestamp}`;
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
      if (event.event === 'agent_completion' && event.content.agent_type === 'human') return false
      if (event.event === 'agent_completion' && event.content.agent_type === 'react_end') return false
      if (event.event === 'llm_stream_chunk' && event.content.content && !event.content.content.includes('<tool>')) return false
      
      // Always include tool-related events
      if (event.isToolRelated || event.isDaytonaRelated) return true
      if (event.event === 'agent_completion' && (event.content.agent_type === 'react_tool' || event.content.agent_type === 'tool_response')) return true
      if (event.event === 'agent_completion' && event.content.name) return true // Tool responses
      
      return true
    })
    .map((event, index) => {
      const data = event.content
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
                title = ` Search Tavily`
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
</script>

<style scoped>
/* you can adjust colors/sizing as you like */
</style>
