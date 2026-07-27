<template>
  <div class="bg-white rounded-lg shadow-lg p-6">
    <!-- Iterate through chapters -->
    <div 
      v-for="(chapter, index) in report" 
      :key="index" 
      class="mb-6 border-b last:border-b-0 pb-6 last:pb-0"
    >
      <!-- Chapter Header -->
      <button
        @click="toggleChapter(index)"
        class="w-full text-left flex justify-between items-center py-3 px-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
      >
        <div class="flex items-center space-x-3">
          <BookOpenIcon class="w-5 h-5 text-primary-600" />
          <h2 class="font-semibold text-gray-900">{{ chapter.title }}</h2>
        </div>
        <ChevronDownIcon
          class="w-5 h-5 text-gray-500 transform transition-transform duration-200"
          :class="{ 'rotate-180': expandedChapters[index] }"
        />
      </button>

      <!-- Chapter Content -->
      <div
        v-show="expandedChapters[index]"
        class="mt-4 px-4 space-y-4"
      >
        <!-- High Level Goal -->
        <div class="flex items-start space-x-3 bg-blue-50 p-3 rounded-lg">
          <FlagIcon class="w-5 h-5 text-blue-600 mt-0.5" />
          <div>
            <h4 class="font-medium text-blue-900">High Level Goal</h4>
            <p class="text-blue-800">{{ chapter.high_level_goal }}</p>
          </div>
        </div>

        <!-- Why Important -->
        <div class="flex items-start space-x-3 bg-amber-50 p-3 rounded-lg">
          <LightBulbIcon class="w-5 h-5 text-amber-600 mt-0.5" />
          <div>
            <h4 class="font-medium text-amber-900">Why Important</h4>
            <p class="text-amber-800">{{ chapter.why_important }}</p>
          </div>
        </div>

        <!-- Generated Content -->
        <div class="prose max-w-none mt-6 text-gray-700"
             v-html="formatMarkdown(chapter.generated_content)">
        </div>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex justify-end space-x-4 mt-6">
      <button
        @click="showFullReport"
        class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
      >
        <DocumentTextIcon class="w-5 h-5 mr-2" />
        View Full Report
      </button>
      <button
        @click="downloadPDF"
        class="inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
      >
        <ArrowDownTrayIcon class="w-5 h-5 mr-2" />
        Download PDF
      </button>
    </div>

    <!-- Full Report Modal -->
    <FullReportModal
      :open="isFullReportOpen"
      :reportData="report"
      @close="isFullReportOpen = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import html2pdf from 'html2pdf.js'
import {
  ArrowDownTrayIcon,
  ChevronDownIcon,
  DocumentMagnifyingGlassIcon,
  BookOpenIcon,
  FlagIcon,
  LightBulbIcon,
  DocumentTextIcon
} from '@heroicons/vue/24/outline'
import FullReportModal from './FullReportModal.vue'

const props = defineProps({
  report: {
    type: Array,
    required: true
  }
})

// Track which chapters are expanded
const expandedChapters = ref({})

// Format the report data for the modal
const formattedReport = computed(() => {
  return props.report.map(chapter => ({
    title: chapter.title,
    content: chapter.generated_content,
    sources: chapter.sources || [],
    metadata: {
      high_level_goal: chapter.high_level_goal,
      why_important: chapter.why_important
    }
  }))
})

// Toggle a given chapter by index
function toggleChapter(index) {
  expandedChapters.value[index] = !expandedChapters.value[index]
}

// Convert markdown => safe HTML
function formatMarkdown(text = '') {
  const rawHtml = marked(text)
  return DOMPurify.sanitize(rawHtml)
}

// Replace the downloadPDF function with this new version
async function downloadPDF() {
  // Create a temporary div to hold our formatted content
  const tempDiv = document.createElement('div')
  tempDiv.style.padding = '40px'
  tempDiv.style.fontFamily = 'Arial, sans-serif'

  // Add CSS styles
  const styleSheet = document.createElement('style')
  styleSheet.textContent = `
    .chapter {
      margin-bottom: 40px;
      page-break-after: always;
    }
    .chapter:last-child {
      page-break-after: avoid;
    }
    .chapter-title {
      font-size: 24px;
      color: #1a1a1a;
      margin-bottom: 20px;
      font-weight: bold;
    }
    .section {
      margin: 15px 0;
      padding: 15px;
      border-radius: 8px;
    }
    .goal-section {
      background-color: #f0f7ff;
    }
    .important-section {
      background-color: #fff8e6;
    }
    .section-title {
      font-size: 16px;
      font-weight: bold;
      margin-bottom: 8px;
    }
    .content {
      margin-top: 20px;
      line-height: 1.6;
    }
    .content h1, .content h2, .content h3 {
      margin: 15px 0;
      color: #2c3e50;
    }
    .content p {
      margin: 10px 0;
    }
    .content ul, .content ol {
      margin: 10px 0;
      padding-left: 20px;
    }
    .content a {
      color: #2563eb;
      text-decoration: underline;
    }
  `
  tempDiv.appendChild(styleSheet)

  // Generate HTML content
  props.report.forEach((chapter) => {
    const chapterDiv = document.createElement('div')
    chapterDiv.className = 'chapter'

    // Chapter Title
    chapterDiv.innerHTML += `
      <h1 class="chapter-title">${chapter.title}</h1>
    `

    // High Level Goal
    chapterDiv.innerHTML += `
      <div class="section goal-section">
        <div class="section-title">High Level Goal</div>
        <div>${chapter.high_level_goal}</div>
      </div>
    `

    // Why Important
    chapterDiv.innerHTML += `
      <div class="section important-section">
        <div class="section-title">Why Important</div>
        <div>${chapter.why_important}</div>
      </div>
    `

    // Main Content
    chapterDiv.innerHTML += `
      <div class="content">
        ${DOMPurify.sanitize(marked(chapter.generated_content || ''))}
      </div>
    `

    tempDiv.appendChild(chapterDiv)
  })

  // PDF generation options
  const opt = {
    margin: [10, 10],
    filename: 'research_report.pdf',
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
    // Generate PDF
    await html2pdf().set(opt).from(tempDiv).save()
  } catch (error) {
    console.error('Error generating PDF:', error)
    // You might want to add some user feedback here
  }
}

const isFullReportOpen = ref(false)

const showFullReport = () => {
  isFullReportOpen.value = true
}

// Initialize with first chapter expanded
onMounted(() => {
  if (props.report?.length > 0) {
    expandedChapters.value[0] = true
  }
})
</script>

<style scoped>
.prose {
  @apply text-gray-700;
}
.prose p {
  @apply mb-4;
}
.prose ul {
  @apply list-disc list-inside mb-4;
}
.prose h3 {
  @apply text-lg font-semibold mb-2;
}
</style> 