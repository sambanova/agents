<template>
    <div class="deep-research max-w-4xl mx-auto px-0 py-0">
  
      <!-- If there's no finalReport, show a placeholder -->
      <div v-if="!finalReport">
        <p class="text-center text-gray-500 italic">No research data available.</p>
      </div>
  
      <template v-else>
        <!-- Main Markdown-Rendered Content (larger font) -->
        <div class="report-content prose prose-lg  max-w-none mb-6">
          <div v-html="renderMarkdown(finalReport)"></div>
        </div>
  
        <!-- CITATIONS SECTION -->
        <!-- We do a quick check if '## Citations' existed at all (citationsBlockFound) -->
        <div v-if="citationsBlockFound" class="mt-4">
          <div v-if="citations.length === 0" class="text-sm text-red-500">
            Citations block found, but no bullet lines matched (check your format).
          </div>
        </div>
  
        <!-- If citations exist, show them in a smaller text size -->
        <div v-if="citations.length > 0" class="citations-container space-y-4">
          <!-- Smaller heading for "Sources & Citations" -->
          <h2 class="text-base font-semibold text-primary-brandTextPrimary ">
            Sources & Citations ({{ totalCitationsCount }})
          </h2>
  
          <!-- Minimal Search Input -->
          <div class="flex gap-2 items-center mb-2">
            <input
              type="text"
              v-model="searchQuery"
              placeholder="Search citations..."
              class="flex-1 px-2 py-1 rounded-md border border-gray-300
                     
                     outline-none focus:ring-1 focus:ring-blue-500 text-[16px]"
            />
          </div>
  
          <!-- Citation Cards + Pagination -->
          <div>
            <!-- Cards Grid -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              <div
                v-for="(cit, idx) in pagedCitations"
                :key="cit.id"
                class="citation-card flex flex-col bg-white 
                       p-3 rounded-md shadow-sm border border-gray-100 
                       hover:shadow-md transition-shadow"
              >
                <div class="flex items-start gap-2 mb-2">
                  <!-- Favicon -->
                  <img
                    :src="getFavicon(cit.url)"
                    class="w-5 h-5 object-cover rounded"
                    alt="favicon"
                  />
                  <!-- Citation Title -->
                  <h3 class="font-medium text-primary-brandTextPrimary  flex-1 leading-snug">
                    {{ cit.title }}
                  </h3>
                </div>
  
                <!-- Possibly a snippet/description if you have it, else skip -->
                <div class="mt-auto pt-2">
                  <!-- Citation Link -->
                  <a
                    v-if="cit.url"
                    :href="cit.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="inline-flex items-center text-blue-600
                            hover:underline text-xs break-all"
                  >
                    {{ getDomain(cit.url) }}
                    <svg
                      class="w-3 h-3 ml-1"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4m4-4V6m0 0h-4m4 0l-8 8"
                      />
                    </svg>
                  </a>
                  <span v-else class="text-[16px] text-gray-400 ">
                    No URL provided
                  </span>
                </div>
              </div>
            </div>
  
            <!-- Pagination Controls -->
            <div class="mt-4 flex items-center justify-center gap-2 text-[16px]">
              <button
                @click="prevPage"
                :disabled="currentPage === 1"
                class="px-2 py-1 bg-gray-100  rounded disabled:opacity-50"
              >
                Prev
              </button>
              <span>
                Page {{ currentPage }} of {{ totalPages }}
              </span>
              <button
                @click="nextPage"
                :disabled="currentPage === totalPages"
                class="px-2 py-1 bg-gray-100  rounded disabled:opacity-50"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      </template>
    </div>
  </template>
  
  <script setup>
  import { defineProps, computed, ref, onMounted } from 'vue'
  import { marked } from 'marked'
  
  // ---- PROPS ----
  const props = defineProps({
    parsed: {
      type: Object,
      default: () => ({})
    }
  })
  
  // ---- MARKED SETUP ----
  const renderer = new marked.Renderer()
  renderer.link = function (href, title, text) {
    return `<a href="${href}" target="_blank" rel="noopener noreferrer">${text}</a>`
  }
  marked.setOptions({
    renderer,
    gfm: true,
    breaks: false,
    mangle: false
  })
  function renderMarkdown(text) {
    return marked(text || '')
  }
  
  // ---- GET final_report (larger text for main body) ----
  const finalReport = computed(() => {
    const raw = props.parsed?.data?.final_report || ''
    if (!raw) return ''
  
    // Remove the "## Citations" section from the main body
    const headingRegex = /(^|\n)##\s*Citations\s*(\n|$)/i
    const idx = raw.search(headingRegex)
    if (idx === -1) return raw
  
    // Return everything before the heading
    return raw.slice(0, idx).trim()
  })
  
  // ---- CITATIONS PARSER ----
  const citationsBlockFound = ref(false)
  
  const citations = computed(() => {
    const text = props.parsed?.data?.final_report || ''
    if (!text) return []
  
    // Find "## Citations"
    const headingRegex = /(^|\n)##\s*Citations\s*(\n|$)/i
    const startIndex = text.search(headingRegex)
    if (startIndex === -1) return []
  
    citationsBlockFound.value = true
  
    // Slice from "## Citations" to end OR next heading
    let block = text.slice(startIndex)
    const subsequentHeading = block.slice(2).search(/\n#{1,6}\s+\w/)
    if (subsequentHeading > -1) {
      block = block.slice(0, subsequentHeading + 2)
    }
  
    // Convert to lines, skip the first line (## Citations)
    const lines = block.split('\n').slice(1).map(l => l.trim())
  
    // We'll allow lines that start with "* " or "- "
    let bulletLines = lines.filter(l => l.startsWith('*') || l.startsWith('-'))
  
    // Attempt a specialized parse for typical Markdown link syntax "[title](url)"
    let idCounter = 1
    const parsed = bulletLines.map(line => {
      // remove leading "* " or "- "
      line = line.replace(/^(\*|-)\s*/, '').trim()
  
      // 1) If we see markdown link style [title](url), parse that
      let match = line.match(/\[([^\]]+)\]\(([^\)]+)\)/)
      if (match) {
        const linkTitle = match[1].trim()
        const linkUrl = match[2].trim()
        return {
          id: idCounter++,
          title: linkTitle || 'Untitled citation',
          url: linkUrl
        }
      }
  
      // 2) Otherwise fallback to naive approach: find a URL
      const urlMatch = line.match(/(https?:\/\/[^\s]+)/)
      let url = ''
      if (urlMatch) {
        url = urlMatch[0]
      }
      let title = line.replace(url, '').trim()
      // remove trailing bracket or colon if present
      title = title.replace(/[:(]+$/, '').trim()
      if (!title) title = 'Untitled citation'
  
      return {
        id: idCounter++,
        title,
        url
      }
    })
    return parsed
  })
  
  // ---- CITATION PAGINATION & SEARCH ----
  const pageSize = 6
  const currentPage = ref(1)
  const searchQuery = ref('')
  
  const filteredCitations = computed(() => {
    if (!searchQuery.value) return citations.value
    const q = searchQuery.value.toLowerCase()
    return citations.value.filter(c =>
      c.title.toLowerCase().includes(q) || c.url.toLowerCase().includes(q)
    )
  })
  
  const totalCitationsCount = computed(() => citations.value.length)
  const totalPages = computed(() => {
    const total = filteredCitations.value.length
    return total > 0 ? Math.ceil(total / pageSize) : 1
  })
  
  const pagedCitations = computed(() => {
    if (currentPage.value > totalPages.value) currentPage.value = totalPages.value
    const start = (currentPage.value - 1) * pageSize
    return filteredCitations.value.slice(start, start + pageSize)
  })
  
  // Next / Prev Page
  function nextPage() {
    if (currentPage.value < totalPages.value) {
      currentPage.value++
    }
  }
  function prevPage() {
    if (currentPage.value > 1) {
      currentPage.value--
    }
  }
  
  // ---- HELPERS: FAVICON & DOMAIN ----
  function getFavicon(url) {
    if (!url) return 'https://via.placeholder.com/64?text=No+URL'
    try {
      const domain = new URL(url).hostname
      return `https://www.google.com/s2/favicons?domain=${domain}&sz=64`
    } catch {
      return 'https://via.placeholder.com/64?text=Err'
    }
  }
  function getDomain(url) {
    if (!url) return ''
    try {
      return new URL(url).hostname.replace(/^www\./, '')
    } catch {
      return url
    }
  }
  
  // Optional logs:
  onMounted(() => {
    // console.log("finalReport:", finalReport.value)
    // console.log("citations:", citations.value)
  })
  </script>
  
  
  <style scoped>
  .deep-research {
    /* Container styling, adjust as needed */
  }
  
  /* MAIN REPORT: Larger text sizes (matching 'prose-lg') */
  .report-content :deep(h1) {
    @apply text-[20px] font-semibold mt-4 mb-4;
  }
  .report-content :deep(h2) {
    @apply text-[16px] font-semibold mt-4 mb-4;
  }
  .report-content :deep(h3) {
    @apply text-[16px] font-semibold mt-4 mb-4;
  }
  .report-content :deep(p) {
    @apply text-base text-[16px] leading-relaxed mb-4 text-primary-brandTextPrimary ;
  }
  .report-content :deep(a) {
    @apply text-blue-600  underline;
  }
  
  /* CITATIONS: We do smaller text overall */
  .citations-container .citation-card {
    @apply text-[16px];
  }
  .citations-container .citation-card h3 {
    /* text-sm or smaller as needed */
    @apply text-[16px];
  }
  
  /* line-clamp utility if you want to clamp text somewhere */
  .line-clamp-3 {
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  ul,li{
    font-size: 16px!important;
  }
  </style>
  