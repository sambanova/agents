<template>
  <div 
  :class="[
        ' h-full  p-1 border border-primary-brandFrame bg-white rounded-lg overflow-y-auto',
        isCollapsed ? 'w-18' : 'w-64'
      ]"
  >
  <div class="overflow-y-auto relative h-full">
    <!-- Toggle collapse button -->
    <button
      @click="isCollapsed = !isCollapsed"
      class=" absolute top-[10px] right-[10px] p-2 z-20  bg-white rounded-full shadow-md hover:bg-gray-50 transition-transform duration-300  "
      :title="isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'"
    >
      <ChevronLeftIcon
        :class="[
          'h-4 w-4 text-gray-600 transition-transform duration-300',
          isCollapsed ? 'rotate-180' : ''
        ]"
      />
    </button>

    <!-- Sidebar Container -->
    <div
    class=" "
    >
      <!-- Header with Filter and Bulk Actions -->
      <div class="p-4 border-b border-gray-200 space-y-3">
        <!-- Saved Searches title and filter on a new line -->
        <div class="space-y-2">
          <h2 
            :class="[
              'font-semibold text-gray-900 whitespace-nowrap flex items-center',
              isCollapsed ? 'justify-center' : ''
            ]"
          >
            <MagnifyingGlassIcon class="w-5 h-5 mr-2" />
            <span :class="{ 'hidden': isCollapsed }">Saved Searches</span>
          </h2>
          <!-- Filter Dropdown -->
          <div v-if="!isCollapsed" class="flex items-center space-x-2">
            <label for="filterType" class="text-sm text-gray-600">Filter:</label>
            <select
              id="filterType"
              v-model="filterType"
              class="border border-gray-300 rounded-md p-1 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
            >
              <option value="all">All</option>
              <option value="educational_content">Research</option>
              <option value="sales_leads">Sales Leads</option>
              <!-- NEW OPTION FOR FINANCIAL ANALYSIS -->
              <option value="financial_analysis">Financial Analysis</option>
            </select>
          </div>
        </div>

        <!-- Bulk Action Buttons -->
        <div v-if="!isCollapsed" class="flex items-center justify-between">
          <button
            @click="exportAllReports"
            class="flex items-center space-x-1 text-sm text-gray-700 hover:underline focus:outline-none"
          >
            <ArchiveBoxArrowDownIcon class="w-4 h-4" />
            <span>Export All (JSON)</span>
          </button>
          <button
            @click="clearAllConfirm"
            class="flex items-center space-x-1 text-sm text-red-600 hover:underline focus:outline-none"
          >
            <TrashIcon class="w-4 h-4" />
            <span>Clear All</span>
          </button>
        </div>
      </div>

      <!-- Saved Reports List -->
      <div class=" max-h-[calc(100vh-8rem)]">
        <div 
          v-for="report in filteredReports" 
          :key="report.id"
          :class="[
        'p-3 relative cursor-pointer border-b border-gray-100 transition-colors group',
        { 'bg-gray-200': isActive(report) }  
      ]"
              >
          <!-- Entire row clickable except the buttons -->
          <div
            class="flex items-start justify-between w-full"
            @click="selectReport(report)"
          >
            <!-- Collapsed View -->
            <div v-if="isCollapsed" class="flex flex-col items-center w-full">
              <component 
                :is="iconMapping[report.type]"
                :class="['w-6', 'h-6', 'mb-1', reportTextColor(report.type)]"
              />
              <span class="text-xs text-gray-500">
                {{ formatDate(report.timestamp) }}
              </span>
              <span class="text-xs text-gray-500">
                {{ formatTime(report.timestamp) }}
              </span>
            </div>

            <!-- Expanded View -->
            <div v-else class="w-full pr-2">
              <!-- Main query text (non-bold, slightly smaller) -->
              <div class="text-sm text-gray-700 break-words">
                {{ capitalizeFirstLetter(report.query) }}
              </div>
              <div class="flex items-center justify-between text-xs text-gray-500 mt-1">
                <span class="flex items-center space-x-1">
                  <component 
                    :is="iconMapping[report.type]"
                    :class="['w-4', 'h-4', reportTextColor(report.type)]"
                  />
                  <span :class="reportTextColor(report.type)">
                    {{ formatType(report.type) }}
                  </span>
                </span>
                <span>
                  {{ formatDate(report.timestamp) }} 
                  <span class="ml-1">| {{ formatTime(report.timestamp) }}</span>
                </span>
              </div>
            </div>
          </div>
          <ChatItemMoreMenu >
            <!-- Individual Action Buttons (only in expanded mode) -->
          <!-- <div 
            v-if="!isCollapsed" 
            class="p-0 flex flex-row"
          > -->
            <!-- Export Single -->
            <button
              @click.stop="exportReport(report)"
              class="flex flex-row  items-center justify-around p-1  w-full text-sm text-gray-700  focus:outline-none"
              title="Export to JSON"
            >
              <ArchiveBoxArrowDownIcon class="w-4 h-4 me-2" />
              <span>Export</span>
            </button>
            <!-- Delete Single -->
            <button
              @click.stop="deleteReport(report)"
              class="flex flex-row items-center justify-around w-full p-1  text-sm text-gray-700  focus:outline-none"
              title="Delete This Report"
            >
              <TrashIcon class="w-4 h-4" />
              <span>Delete</span>
            </button>
          <!-- </div> -->
            </ChatItemMoreMenu>

          
        </div>
      </div>
    </div>
  </div>
</div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useReportStore } from '../stores/reportStore'
import { useRoute, useRouter } from 'vue-router'
import { onMounted, watch } from 'vue'


import {
  ChevronLeftIcon,
  MagnifyingGlassIcon,
  BookOpenIcon,
  UserGroupIcon,
  ArchiveBoxArrowDownIcon,
  TrashIcon,
  BanknotesIcon
} from '@heroicons/vue/24/outline';

import ChatItemMoreMenu from '@/components/Common/UIComponents/MoreMenu.vue'

const reportStore = useReportStore()
const isCollapsed = ref(false)
const filterType = ref('all')
const emit = defineEmits(['selectReport'])
const router = useRouter()
const route = useRoute()
const iconMapping = {
  educational_content: BookOpenIcon,
  sales_leads: UserGroupIcon,
  financial_analysis: BanknotesIcon,
}
function isActive(report) {

  if(String(report.id) === String(route.params.id)){
    
     selectReport(report)
     return String(report.id) === String(route.params.id)
  }

}
function selectReport(report) {
  // Let the parent know which report was clicked
  emit('selectReport', {
    type: report.type,
    query: report.query,
    results: report.results
  })

  // let path = window.location.pathname
  // if (!path.endsWith('/')) {
  //   path += '/'
  // }
  // window.location.href = `${window.location.origin}${path}${report.id}`
  router.push(`/${report.id}`)

}

// Check on component mount
onMounted(() => {
  if (route.params.id) {
    // myFunction(route.params.id)
    // alert(route.params.id)

    console.log("reportStore",reportStore.savedReports)
    // let selectedReport=reportStore.savedReports.filter(r => r.id === route.params.id)

    // console.log(selectReport)
    
  //   if (selectedReport?.length) {
  //     return selectedReport[0]
  // } else {
  //   return null
  // }
  }
})

// Optionally, watch for changes in the route parameter
watch(
  () => route.params.id,
  (newId, oldId) => {
    if (newId) {
      // myFunction(newId)
    }
  }
)

function formatType(type) {
  if (type === 'educational_content') return 'Research'
  if (type === 'sales_leads') return 'Sales Leads'
  if (type === 'financial_analysis') return 'Financial Analysis'
  return 'Unknown'
}

function formatDate(timestamp) {
  return new Date(timestamp).toLocaleDateString()
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function capitalizeFirstLetter(str) {
  if (!str) return ''
  return str.charAt(0).toUpperCase() + str.slice(1)
}

// Color code based on type
function reportTextColor(type) {
  if (type === 'educational_content') return 'text-green-600'
  if (type === 'sales_leads') return 'text-blue-600'
  if (type === 'financial_analysis') return 'text-purple-600'
  return 'text-gray-600'
}

// Computed filtered reports
const filteredReports = computed(() => {
  if (filterType.value === 'all') {
    return reportStore.savedReports
  } else {
    return reportStore.savedReports.filter(r => r.type === filterType.value)
  }
})

// Export to JSON for a single report
function exportReport(report) {
  try {
    const fileName = `${report.query.replace(/\s+/g, '_')}.json`
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(report, null, 2))
    const dlAnchorElem = document.createElement('a')
    dlAnchorElem.setAttribute('href', dataStr)
    dlAnchorElem.setAttribute('download', fileName)
    dlAnchorElem.click()
  } catch (error) {
    console.error('Error exporting report:', error)
  }
}

// Export all reports to JSON
function exportAllReports() {
  try {
    const allReports = reportStore.savedReports
    const fileName = 'all_saved_reports.json'
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(allReports, null, 2))
    const dlAnchorElem = document.createElement('a')
    dlAnchorElem.setAttribute('href', dataStr)
    dlAnchorElem.setAttribute('download', fileName)
    dlAnchorElem.click()
  } catch (error) {
    console.error('Error exporting all reports:', error)
  }
}

// Delete a single report
function deleteReport(report) {
  if (confirm(`Are you sure you want to delete this report?`)) {
    reportStore.deleteReport(report.id)
  }
}

// Clear all reports
function clearAllConfirm() {
  if (confirm(`Are you sure you want to clear all saved reports? This cannot be undone.`)) {
    reportStore.clearAllReports()
  }
}
</script>

<style scoped>
/* Ensure the toggle button remains clickable */
button[title='Expand Sidebar'],
button[title='Collapse Sidebar'] {
  z-index: 9999;
}

::-webkit-scrollbar {
  width: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
}

::-webkit-scrollbar-thumb {
  background-color: #cccccc;
  border-radius: 9999px;
}
</style>
