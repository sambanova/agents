<template>


     <div v-if="props.toolSources &&props.toolSources.length > 0" class="mt-4">
            <div class="flex flex-wrap gap-2">
              <template v-for="source in props.toolSources" :key="source?.url || source?.title || 'unknown'">
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
  <!-- 2) Otherwise render full timeline + audit log -->
  <div>
    <!-- Tool header & timeline -->
    <div class="flex flex-col p-4 border rounded mb-2">
      <!-- <span class="text-md flex capitalize inline-flex ">
        <LoadingText
          v-if="loading"
          :key="loading"
          :loading="loading"
          :text="latestToolAction?.toolName || 'Thinking'"
        />: {{ latestToolAction?.explanation }}
      </span> -->
 <span class="text-md flex items-center  first-letter:uppercase inline-flex ">
<IconsDisplay
  :text="toolCalls.length > 0 
            ? toolCalls[toolCalls.length - 1].title 
            : 'Thinking'"
/>    <LoadingText
          v-if="loading"
          :key="loading"
          :loading="loading"
          :text="(toolCalls.length > 0 
            ? toolCalls[toolCalls.length - 1].title 
    : 'Thinking')"
/>
:  <span class="details ml-2">
      {{ toolCalls.length > 0 
          ? toolCalls[toolCalls.length - 1].details 
          : '' 
      }}
    </span>
      </span>

     
      <div class="flex space-x-6 mb-2">
        <div
          v-for="(tool, idx) in toolTimeline"
          :key="idx"
          class="relative pl-4 text-gray-700"
        >
          <div
            class="absolute left-0 top-1/2 w-2 h-2 rounded-full border-2 border-gray-500 bg-white transform -translate-y-1/2"
          ></div>
          {{ tool }}
        </div>
      </div>
      <div
        ref="descContainer"
        class="overflow-y-auto text-sm bg-white text-gray-700 dark:text-gray-300 dark:bg-gray-800 rounded"
        style="max-height: 150px;"
      >
        <div class="markdown-content text-sm" v-html="renderMarkdown(description || '')"></div>
      </div>
    </div>
  <LinkChips :allSources="allSources" />
   

  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import LoadingText from '@/components/ChatMain/LoadingText.vue'
import IconsDisplay from '@/components/ChatMain/IconsDisplay.vue'
import LinkChips from '@/components/ChatMain/LinkChips.vue'

import { marked } from 'marked'

const props = defineProps({
  streamData:     { type: Array, default: () => [] },
  allSources:     { type: Array, default: () => [] },
  toolCalls:     { type: Array, default: () => [] },  
  toolSources:     { type: Array, default: () => [] },
  streamingEvents:{ type: Array, default: () => [] },
  workflowData:   { type: Array, default: () => [] },
 auditLogEvents:   { type: Array, default: () => [] },

  loading:        { type: Boolean, default: false },
  plannerText:    { type: String, required: true },
  metadata:       { type: Object, required: true },
  provider:       { type: String, required: true },
  messageId:      { type: String, required: true },
})

function renderMarkdown(mdText) {
  return marked.parse(mdText)
}

// 1) Are we still streaming?
const isCurrentlyStreaming = computed(() => {
  if (!props.streamingEvents.length) return true
  return props.streamingEvents[props.streamingEvents.length - 1].event !== 'stream_complete'
})

// 2) Completed Events?
const hasCompletedEvents = computed(() => {
  if (!props.streamingEvents.length) {
    return props.workflowData.length > 0 || Object.keys(props.metadata).length > 0
  }
  return props.streamingEvents.some(evt =>
    evt.event === 'agent_completion' ||
    evt.event === 'stream_complete'
  )
})

// 3) Timeline
function extractToolName(content) {
  return (/<tool>(.*?)<\/tool>/i.exec(content) || [,''])[1]
}
const toolTimeline = computed(() =>
  props.streamData
    .filter(i =>
      i.event === 'agent_completion' &&
      i.additional_kwargs?.agent_type === 'react_tool'
    )
    .map(i => extractToolName(i.content))
)

const currentToolName = computed(() =>
  toolTimeline.value[toolTimeline.value.length - 1] || ''
)

const description = computed(() =>
  props.streamData
    .filter(i =>
      i.content&&['stream_start','llm_stream_chunk','stream_complete'].includes(i.event) &&
      !i.content.includes('<tool>')
    )
    .map(i => i.content)
    .join(' ')
)

// auto-scroll
const descContainer = ref(null)
watch(description, () => {
  nextTick(() => {
    if (descContainer.value) {
      descContainer.value.scrollTop = descContainer.value.scrollHeight
    }
  })
})



// 5) ALL SOURCES (generic + toolSources)
// const allSources = computed(() => {
//   const items = []
//   const seen  = new Set()

//   const pushIfNew = src => {
//     if (!src.url || seen.has(src.url)) return
//     seen.add(src.url)
//     items.push(src)
//   }

//   function extractLinks(text, type = 'link') {
//     if (!text) return
//     let m

//     // JSON-array
//     if (text.trim().startsWith('[')) {
//       try {
//         const arr = JSON.parse(
//           text.replace(/'url'/g, '"url"')
//         )
//         if (Array.isArray(arr)) {
//           arr.forEach(o => {
//             if (o.url) {
//               const domain = new URL(o.url).hostname.replace(/^www\./,'')
//               pushIfNew({
//                 title: o.title?.trim() || domain,
//                 url: o.url,
//                 domain,
//                 type,
//               })
//             }
//           })
//           return
//         }
//       } catch {}
//     }

//     // Named lines
//     const nameRe = /([^:*]+):\s*(https?:\/\/\S+)/g
//     while ((m = nameRe.exec(text))) {
//       const url = m[2].trim()
//       const domain = new URL(url).hostname.replace(/^www\./,'')
//       pushIfNew({ title: m[1].trim(), url, domain, type })
//     }

//     // Python style
//     const pyRe = /'url':\s*'(https?:\/\/[^']+)'/g
//     while ((m = pyRe.exec(text))) {
//       const url = m[1].trim()
//       const domain = new URL(url).hostname.replace(/^www\./,'')
//       pushIfNew({ title: domain, url, domain, type })
//     }

//     // Plain URLs
//     const urlRe = /(https?:\/\/[^\s"'<>]+)/g
//     while ((m = urlRe.exec(text))) {
//       const url = m[1].trim()
//       const domain = new URL(url).hostname.replace(/^www\./,'')
//       pushIfNew({ title: domain, url, domain, type })
//     }
//   }

//   // main message (if any)
//   extractLinks(props.data?.content, 'link')

//   // each streamData item
//   props.streamData.forEach(evt => {
//     const txt = evt.data?.content
//     if (typeof txt === 'string') extractLinks(txt, 'link')
//   })

//   // merge in toolSources
//   toolSources.value.forEach(src => pushIfNew(src))

//   return items
// })


const latestToolAction = computed(() => {
  // 1) Grab only the react_tool completions
  const calls = props.streamData.filter(i =>
    i.event === 'agent_completion' &&
    i.agent_type === 'react_tool' &&
    typeof i.content === 'string'
  )
  if (!calls.length) return { toolName: '', explanation: '', sources: [] }

  // 2) Take the very last one
  const lastContent = calls[calls.length - 1].content

  // 3) Extract <tool>…</tool>
  const toolMatch  = lastContent.match(/<\s*tool>([\s\S]*?)<\/\s*tool>/i)
  // 4) Extract <tool_input>…</tool_input>
  const inputMatch = lastContent.match(/<\s*tool_input>([\s\S]*?)<\/\s*tool_input>/i)

  if (!toolMatch) return null

  // 5) Normalize the name: replace underscores with spaces
  const rawName     = toolMatch[1].trim()                // e.g. "search_tavily"
  const toolName    = rawName.replace(/_/g, ' ')         // → "search tavily"
  // 6) Pull out the explanation
  const explanation = inputMatch ? inputMatch[1].trim() : ''

  // 7) Now build the sources array by reusing your toolSources logic
  const sources = []
  props.streamingEvents.forEach(event => {
    const d = event.data
    if (!d) return

    // A) search_tavily → web sources
    if (
      event.event === 'agent_completion' &&
      d.type === 'LiberalFunctionMessage' &&
      d.name === 'search_tavily' &&
      Array.isArray(d.content)
    ) {
      d.content.forEach(src => {
        if (!src.url) return
        let title  = src.title?.trim() || ''
        let domain = ''
        if (!title && src.url) {
          try {
            domain = new URL(src.url).hostname.replace(/^www\./, '')
            title  = domain
          } catch {}
        }
        sources.push({
          title:   title || 'Untitled',
          url:     src.url,
          domain,
          content: typeof src.content === 'string'
                   ? src.content.slice(0,200) + '…'
                   : undefined,
          type:    'web'
        })
      })
    }

    // B) arXiv
    else if (d.name === 'arxiv' && typeof d.content === 'string') {
      d.content.split('Published:').slice(1).forEach(chunk => {
        const title = chunk.match(/Title:\s*([^\n]+)/)?.[1]?.trim() ?? 'Untitled Paper'
        const url   = chunk.match(/URL:\s*(https?:\/\/\S+)/)?.[1]?.trim() ?? ''
        const pub   = chunk.match(/Published:\s*([^\n]+)/)?.[1]?.trim() ?? 'Unknown date'
        sources.push({
          title,
          url,
          domain:  'arxiv.org',
          content: `Published: ${pub}`,
          type:    'arxiv'
        })
      })
    }
  })

  // 8) Return a single object with everything
  return {
    toolName,
    explanation,
    sources: sources.slice(0,5)
  }
})


// … your auditLogEvents, formatEventTime, latestToolAction, etc. all stay exactly as before …


// 5) audit log with safe stringify
const auditLogEvents = computed(() => {
  // synthetic if no streamingEvents but we have workflowData
  if ((!props.streamData || !props.streamData.length) && props.workflowData.length) {

    // alert("steaming ")
    const unique = []
    const seen = new Set()
    props.workflowData.forEach((w, i) => {
      const key = `${w.agent_name}-${w.task}-${w.tool_name}`
      if (!seen.has(key)) {
        seen.add(key)
        unique.push({
          id: `synthetic-${i}`,
          title: `✅ ${w.agent_name} – ${w.task}`,
          details: w.tool_name ? `Tool: ${w.tool_name}` : 'Completed',
          subItems: [],
          event: 'workflow_item',
          type: 'tool_result',
          timestamp: new Date().toISOString()
        })
      }
    })
    return unique
  }




  // otherwise from streamingEvents
  const out = []
  const seenKeys = new Set()
  props.streamingEvents.forEach((evt, idx) => {
    const key = `${evt.event}-${evt.timestamp}`
    if (!seenKeys.has(key)) {
      seenKeys.add(key)

      // SAFELY stringify or fallback
      let raw = evt.content
      let serialized = JSON.stringify(raw)
      if (serialized === undefined) {
        serialized = String(raw ?? '')
      }

      // truncate to 100 chars
      const detail = serialized.length > 100
        ? serialized.slice(0, 100) + '…'
        : serialized

      out.push({
        id: `audit-${idx}`,
        title: evt.event,
        details: detail,
        subItems: [],
        event: evt.event,
        type: 'info',
        timestamp: evt.timestamp
      })
    }
  })
  return out
})


const toolSources = computed(() => {
  if (!props.streamingEvents || !Array.isArray(props.streamingEvents)) return []
  
  const sources = []
  
  props.streamingEvents.forEach(event => {
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
/* your existing styles */
.md-heading {
  /* … */
}
.md-paragraph {
  /* … */
}
.custom-bullet { /* … */ }
.bullet-marker { /* … */ }

p {
  line-height: 24px;
}

.details {
  display: inline-block;       /* allow width constraints on inline element */
  max-width: 200ch;            /* about 200 average characters */
  white-space: nowrap;         /* prevent wrapping to next line */
  overflow: hidden;            /* hide overflow */
  text-overflow: ellipsis;     /* show “…” when clipped */
}
</style>
