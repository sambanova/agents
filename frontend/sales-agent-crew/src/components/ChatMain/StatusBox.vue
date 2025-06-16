<template>

  isLoading {{ props.streamData }}
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
</script>

<style scoped>
/* you can adjust colors/sizing as you like */
</style>
