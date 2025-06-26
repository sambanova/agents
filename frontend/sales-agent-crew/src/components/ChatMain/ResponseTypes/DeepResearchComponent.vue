<template>
  <div class="deep-research max-w-4xl mx-auto px-0 py-0">
    <!-- If there's no finalReport, show a placeholder -->
    <div v-if="!finalReport">
      <p class="text-center text-gray-500 italic">
        No research data available.
      </p>
    </div>

    <template v-else>
      <!-- Main Markdown-Rendered Content (standard font size) -->
      <div class="report-content prose max-w-none mb-6">
        <div v-html="renderMarkdown(finalReport)"></div>
      </div>

      <!-- CITATIONS SECTION -->
      <!-- We do a quick check if '## Citations' existed at all (citationsBlockFound) -->
      <div v-if="citationsBlockFound" class="mt-4">
        <div v-if="citations.length === 0" class="text-sm text-red-500">
          Citations block found, but no bullet lines matched (check your
          format).
        </div>
      </div>

      <!-- If citations exist, show them in a smaller text size -->
      <div v-if="citations.length > 0" class="citations-container space-y-6">
        <!-- Enhanced heading for "Sources & Citations" -->
        <div class="border-b border-gray-200 pb-4">
          <div class="flex items-center gap-3 mb-2">
            <h2 class="text-xl font-bold text-gray-900">
              Sources & Citations
            </h2>
            <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
              {{ totalCitationsCount }} sources
            </span>
          </div>
          <p class="text-sm text-gray-600">
            Research sources and references used to compile this report
          </p>
        </div>

        <!-- Enhanced Search Input -->
        <div class="relative">
          <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <svg class="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
            </svg>
          </div>
          <input
            type="text"
            v-model="searchQuery"
            placeholder="Search citations by title or domain..."
            class="block w-full pl-10 pr-3 py-3 border border-gray-200 rounded-xl text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-gray-400 focus:border-transparent transition-all duration-200 bg-gray-50 hover:bg-white focus:bg-white"
          />
          <div v-if="searchQuery" class="absolute inset-y-0 right-0 pr-3 flex items-center">
            <button
              @click="searchQuery = ''"
              class="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
              </svg>
            </button>
          </div>
        </div>

        <!-- Citation Cards + Pagination -->
        <div>
          <!-- Results info -->
          <div v-if="searchQuery" class="mb-4 text-sm text-gray-600">
            {{ filteredCitations.length }} of {{ totalCitationsCount }} citations found
          </div>

          <!-- Compact Cards Grid -->
          <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 mb-6">
            <div
              v-for="cit in pagedCitations"
              :key="cit.id"
              class="citation-card group bg-white border border-gray-200 rounded-lg p-3 hover:shadow-sm hover:border-gray-300 transition-all duration-200"
            >
              <!-- Title -->
              <h3
                class="font-medium text-gray-900 leading-snug line-clamp-2 group-hover:text-gray-800 transition-colors duration-200 mb-2 text-sm break-words"
                :title="cit.title"
              >
                {{ cit.title }}
              </h3>

              <!-- Link section -->
              <div>
                <a
                  v-if="cit.url"
                  :href="cit.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center gap-1 text-gray-600 hover:text-gray-900 text-xs font-medium transition-colors duration-200 group/link"
                >
                  <span class="break-all">{{ getDomain(cit.url) }}</span>
                  <svg
                    class="w-3 h-3 flex-shrink-0 transform group-hover/link:translate-x-0.5 group-hover/link:-translate-y-0.5 transition-transform duration-200"
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
                <span v-else class="text-gray-400 text-xs">
                  No URL available
                </span>
              </div>
            </div>
          </div>

          <!-- Enhanced Pagination Controls -->
          <div v-if="totalPages > 1" class="flex items-center justify-center bg-gray-50 rounded-xl p-2">
            <div class="flex items-center gap-2">
              <button
                @click="prevPage"
                :disabled="currentPage === 1"
                class="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
                </svg>
                Previous
              </button>
              
              <div class="flex items-center gap-1">
                <template v-for="page in getVisiblePages()" :key="page">
                  <button
                    v-if="page !== '...'"
                    @click="currentPage = page"
                    :class="[
                      'w-10 h-10 text-sm font-medium rounded-lg transition-all duration-200',
                      page === currentPage
                        ? 'bg-gray-200 text-gray-800 shadow-sm'
                        : 'text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400'
                    ]"
                  >
                    {{ page }}
                  </button>
                  <span v-else class="px-2 text-gray-400">...</span>
                </template>
              </div>

              <button
                @click="nextPage"
                :disabled="currentPage === totalPages"
                class="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
              >
                Next
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { defineProps, computed, ref, onMounted } from 'vue';
import { marked } from 'marked';

// ---- PROPS ----
const props = defineProps({
  parsed: {
    type: Object,
    default: () => ({}),
  },
});

// ---- MARKED SETUP ----
const renderer = new marked.Renderer();
renderer.link = function (href, title, text) {
  return `<a href="${href}" target="_blank" rel="noopener noreferrer">${text}</a>`;
};
marked.setOptions({
  renderer,
  gfm: true,
  breaks: false,
  mangle: false,
});
function renderMarkdown(text) {
  return marked(text || '');
}

// ---- GET final_report (larger text for main body) ----
const finalReport = computed(() => {
  const raw = props.parsed?.content || '';
  
  if (!raw) {
    return '';
  }

  // Remove the "## Citations" section from the main body
  const headingRegex = /(^|\n)##\s*Citations\s*(\n|$)/i;
  const idx = raw.search(headingRegex);
  if (idx === -1) return raw;

  // Return everything before the heading
  return raw.slice(0, idx).trim();
});

// ---- CITATIONS PARSER ----
const citationsBlockFound = ref(false);

const citations = computed(() => {
  const text = props.parsed?.content || '';
  if (!text) return [];

  // Find "## Citations"
  const headingRegex = /(^|\n)##\s*Citations\s*(\n|$)/i;
  const startIndex = text.search(headingRegex);
  if (startIndex === -1) return [];

  citationsBlockFound.value = true;

  // Slice from "## Citations" to end OR next heading
  let block = text.slice(startIndex);
  const subsequentHeading = block.slice(2).search(/\n#{1,6}\s+\w/);
  if (subsequentHeading > -1) {
    block = block.slice(0, subsequentHeading + 2);
  }

  // Convert to lines, skip the first line (## Citations)
  const lines = block
    .split('\n')
    .slice(1)
    .map((l) => l.trim());

  // We'll allow lines that start with "* " or "- "
  let bulletLines = lines.filter((l) => l.startsWith('*') || l.startsWith('-'));

  // Attempt a specialized parse for typical Markdown link syntax "[title](url)"
  let idCounter = 1;
  const parsed = bulletLines.map((line) => {
    // remove leading "* " or "- "
    line = line.replace(/^(\*|-)\s*/, '').trim();

    // 1) If we see markdown link style [title](url), parse that
    let match = line.match(/\[([^\]]+)\]\(([^\)]+)\)/);
    if (match) {
      const linkTitle = match[1].trim();
      const linkUrl = match[2].trim();
      return {
        id: idCounter++,
        title: linkTitle || 'Untitled citation',
        url: linkUrl,
      };
    }

    // 2) Otherwise fallback to naive approach: find a URL
    const urlMatch = line.match(/(https?:\/\/[^\s]+)/);
    let url = '';
    if (urlMatch) {
      url = urlMatch[0];
    }
    let title = line.replace(url, '').trim();
    // remove trailing bracket or colon if present
    title = title.replace(/[:(]+$/, '').trim();
    if (!title) title = 'Untitled citation';

    return {
      id: idCounter++,
      title,
      url,
    };
  });
  return parsed;
});

// ---- CITATION PAGINATION & SEARCH ----
const pageSize = 8;
const currentPage = ref(1);
const searchQuery = ref('');

const filteredCitations = computed(() => {
  if (!searchQuery.value) return citations.value;
  const q = searchQuery.value.toLowerCase();
  return citations.value.filter(
    (c) => c.title.toLowerCase().includes(q) || c.url.toLowerCase().includes(q)
  );
});

const totalCitationsCount = computed(() => citations.value.length);
const totalPages = computed(() => {
  const total = filteredCitations.value.length;
  return total > 0 ? Math.ceil(total / pageSize) : 1;
});

const pagedCitations = computed(() => {
  if (currentPage.value > totalPages.value)
    currentPage.value = totalPages.value;
  const start = (currentPage.value - 1) * pageSize;
  return filteredCitations.value.slice(start, start + pageSize);
});

// Next / Prev Page
function nextPage() {
  if (currentPage.value < totalPages.value) {
    currentPage.value++;
  }
}
function prevPage() {
  if (currentPage.value > 1) {
    currentPage.value--;
  }
}

// ---- HELPERS: FAVICON & DOMAIN ----
function getFavicon(url) {
  if (!url) return 'https://via.placeholder.com/64?text=No+URL';
  try {
    const domain = new URL(url).hostname;
    return `https://www.google.com/s2/favicons?domain=${domain}&sz=64`;
  } catch {
    return 'https://via.placeholder.com/64?text=Err';
  }
}
function getDomain(url) {
  if (!url) return '';
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

// ---- HELPER: GET VISIBLE PAGES ----
function getVisiblePages() {
  const pages = [];
  const total = totalPages.value;
  const current = currentPage.value;

  if (total <= 5) {
    for (let i = 1; i <= total; i++) {
      pages.push(i);
    }
  } else {
    if (current <= 3) {
      pages.push(1, 2, 3, 4, 5);
    } else if (current >= total - 2) {
      pages.push(total - 4, total - 3, total - 2, total - 1, total);
    } else {
      pages.push(current - 2, current - 1, current, current + 1, current + 2);
    }
  }

  return pages;
}
</script>

<style scoped>
.deep-research {
  /* Container styling, adjust as needed */
}

/* MAIN REPORT: Standard text sizes (matching standard prose) */
.report-content :deep(h1) {
  @apply text-xl font-semibold mt-4 mb-4;
}
.report-content :deep(h2) {
  @apply text-lg font-semibold mt-4 mb-4;
}
.report-content :deep(h3) {
  @apply text-base font-semibold mt-4 mb-4;
}
.report-content :deep(p) {
  @apply text-sm leading-relaxed mb-4 text-primary-brandTextPrimary;
}
.report-content :deep(a) {
  @apply text-gray-700 underline;
}

/* CITATIONS: Standard small text */
.citations-container .citation-card {
  @apply text-sm;
}
.citations-container .citation-card h3 {
  @apply text-sm;
}

/* line-clamp utilities */
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

ul,
li {
  font-size: 14px !important;
}
</style>
