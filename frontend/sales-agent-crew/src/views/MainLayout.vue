<template>
  <!-- Outer container uses flex so the sidebar, main area, and agent sidebar appear side-by-side -->
  <div
    class="min-h-screen transition-all bg-primary-bodyBg duration-300 flex flex-col"
  >
    <!-- PAGE HEADER -->
    <Header
      ref="headerRef"
      class="flex-none"
      @keysUpdated="handleKeysUpdated"
      @modeToggled="onModeToggled"
    />

    <!-- MAIN COLUMN -->
    <div class="flex gap-2 p-2 h-[calc(100vh-4rem)]">
      <!-- LEFT SIDEBAR -->
      <!-- If chatMode => <ChatSidebar>, else => <Sidebar>. 
         We reference them with JS variables chatSidebarComp, sideBarComp 
         so we do <component :is="chatSidebarComp" />. -->
      <component
        :is="chatMode ? chatSidebarComp : sideBarComp"
        @selectReport="handleSavedReportSelect"
        @selectConversation="handleSelectConversation"
        @new-chat="handleNewChat"
        ref="chatSideBarRef"
      />

      <!-- MAIN CONTENT WRAPPER -->
      <main
        class="overflow-hidden transition-all duration-300 border border-primary-brandFrame rounded-lg relative flex-1 flex flex-col h-full"
        :style="mainContentStyle"
      >
        <div class="flex-1 h-full bg-white">
          <!-- If chatMode => show chat UI, else show old workflow UI -->
          <div class="flex-1 h-full w-full">
            <div v-if="chatMode" class="flex h-full justify-center">
              <!-- ChatView for conversation -->
              <ChatView
                :conversationId="selectedConversationId"
                :userId="clerkUserId"
                class="flex-1"
                @agentThoughtsDataChanged="agentThoughtsDataChanged"
                @daytona-sidebar-state-changed="handleDaytonaSidebarStateChange"
                @stream-started="streamCompleted = false"
                @stream-completed="streamCompleted = true"
              />
            </div>

            <div
              v-else
              class="flex h-full w-full justify-center items-center overflow-y-auto"
            >
              <!-- OLD WORKFLOW MODE -->

              <!-- Pass currentRunId to <SearchSection> so it uses it in /execute calls -->

              <SearchNotification
                :show="showNotification"
                :time="searchTime"
                :resultCount="resultCount"
              />

              <!-- LOADING SPINNER -->
              <div v-if="isLoading && !chatMode" class="mt-8 w-full">
                <LoadingSpinner
                  :message="loadingMessage"
                  :subMessage="loadingSubMessage"
                />
              </div>

              <!-- ERROR MODAL -->
              <ErrorModal
                v-if="!chatMode"
                :show="showError"
                :errorMessage="errorMessage"
                @close="showError = false"
              />

              <!-- RESULTS SECTION -->
              <div v-if="hasResults" class="mt-6 w-full h-full space-y-6">
                <div class="grid grid-cols-1 pb-[200px] gap-6">
                  <!-- SALES LEADS Results -->
                  <template v-if="queryType === 'sales_leads'">
                    <CompanyResultCard
                      v-for="(result, index) in results.results"
                      :key="index"
                      :company="result"
                    />
                  </template>

                  <!-- EDUCATIONAL CONTENT (Research) Results -->
                  <template v-else-if="queryType === 'educational_content'">
                    <ResearchReport :report="results" />
                  </template>

                  <!-- FINANCIAL ANALYSIS Results -->
                  <template v-else-if="queryType === 'financial_analysis'">
                    <FinancialAnalysisReport :report="results" />
                  </template>
                </div>
              </div>

              <!-- FULL REPORT MODAL for "ResearchReport" only -->
              <FullReportModal
                v-if="selectedReport"
                :open="reportModalOpen"
                :report-data="selectedReport"
                @close="reportModalOpen = false"
              />
            </div>
          </div>
        </div>
        <div
          v-if="!chatMode"
          class="sticky bottom-0 left-0 right-0 bg-white border-t border-gray-200"
        >
          <SearchSection
            :keysUpdated="keysUpdateCounter"
            :isLoading="isLoading"
            :runId="currentRunId"
            :sessionId="sessionId"
            @searchStart="handleSearchStart"
            @searchComplete="handleSearchComplete"
            @searchError="handleSearchError"
            @openSettings="openSettings"
          />
        </div>
      </main>

      <!-- RIGHT SIDEBAR: Real-time Agent Logs for the current user + run ID -->
      <AgentSidebar
        v-if="!chatMode"
        :userId="clerkUserId"
        :runId="currentRunId"
      />

      <ChatAgentSidebar
        v-if="chatMode"
        :userId="clerkUserId"
        :runId="currentRunId"
        :agentData="agentData"
        :stream-completed="streamCompleted"
        ref="chatAgentSidebarRef"
      />
    </div>
  </div>
</template>

<script setup>
import {
  ref,
  onMounted,
  onUnmounted,
  computed,
  watch,
  onBeforeUnmount,
  provide,
} from 'vue';
import { useUser } from '@clerk/vue';
import { v4 as uuidv4 } from 'uuid';

/** We import both old + chat sidebars as local variables. */
import Header from '@/components/Header.vue';
import Sidebar from '@/components/Sidebar.vue';
import ChatSidebar from '@/components/ChatSidebar.vue';
import ChatView from '@/components/ChatMain/ChatView.vue';
import AgentSidebar from '@/components/AgentSidebar.vue';

import SearchSection from '@/components/SearchSection.vue';
import SearchNotification from '@/components/SearchNotification.vue';
import LoadingSpinner from '@/components/LoadingSpinner.vue';
import CompanyResultCard from '@/components/CompanyResultCard.vue';
import ResearchReport from '@/components/ResearchReport.vue';
import FinancialAnalysisReport from '@/components/FinancialAnalysisReport.vue';
import ErrorModal from '@/components/ErrorModal.vue';
import FullReportModal from '@/components/FullReportModal.vue';
import ChatAgentSidebar from '@/components/ChatMain/ChatAgentSidebar.vue';
import { useReportStore } from '@/stores/reportStore';
import emitterMitt from '@/utils/eventBus.js';

// Create a reactive property for the selected option.
const selectedOption = ref({ label: 'SambaNova', value: 'sambanova' });

// Provide the state so that descendant components can access it.
provide('selectedOption', selectedOption);

// *** Important *** We'll define local refs for the two components we want:
const sideBarComp = Sidebar;
const chatSidebarComp = ChatSidebar;

// Reactive states
const chatMode = ref(false); // Controls Chat vs Workflow mode
const selectedConversationId = ref(''); // If chatMode, which conversation is active?

// Daytona sidebar state management
const daytonaSidebarState = ref({
  isOpen: false,
  isCollapsed: false,
  width: 0
})

const isLoading = ref(false);
const loadingMessage = ref('');
const loadingSubMessage = ref('');
const showError = ref(false);
const errorMessage = ref('');
const queryType = ref('');
const results = ref(null);
const selectedReport = ref(null);
const reportModalOpen = ref(false);

// "Search Complete" toast
const showNotification = ref(false);
const searchTime = ref('0.0');
const resultCount = ref(0);

// Track how many times keys changed
const keysUpdateCounter = ref(0);

const reportStore = useReportStore();

// For dev
const isDev = ref(import.meta.env.DEV);

// Header ref
const headerRef = ref(null);

// Clerk user ID
const { user } = useUser();
const clerkUserId = computed(() => user.value?.id || 'anonymous_user');

const agentData = ref([]);
const chatSideBarRef = ref(null);
const streamCompleted = ref(false);

const handleNewChat = () => {
  agentData.value = [];
  streamCompleted.value = false;
};

const agentThoughtsDataChanged = (agentThoughtsData) => {
  agentData.value = agentThoughtsData;

  if (
    chatSideBarRef.value &&
    typeof chatSideBarRef.value.loadChats === 'function'
  ) {
    chatSideBarRef.value.loadChats();
  }
};
// The runId for SSE etc.
const currentRunId = ref('');
// The sessionId that remains consistent for document uploads and searches
const sessionId = ref('');

onMounted(() => {
  // Generate a new session ID
  sessionId.value = uuidv4();
  reportStore.loadSavedReports();

  // Listen for new chat events
  emitterMitt.on('new-chat', handleNewChat);
});

onUnmounted(() => {
  // Remove the listener
  emitterMitt.off('new-chat', handleNewChat);
});

// Called by Header => user updated keys
function handleKeysUpdated() {
  keysUpdateCounter.value++;
}

/**
 * Chat Mode toggling from the Header's 'modeToggled' event
 */
function onModeToggled(val) {
  chatMode.value = val;
}

/**
 * When ChatSidebar selects a conversation
 */
function handleSelectConversation(conv) {
  selectedConversationId.value = conv.conversation_id;
  streamCompleted.value = false;
}

/**
 * From the old Sidebar => user picks a saved report
 */
function handleSavedReportSelect(savedReport) {
  queryType.value = savedReport.type;
  results.value = savedReport.results;
  selectedReport.value = null;
  reportModalOpen.value = false;
}

////////////////////////////////////////////////////////////
// The below are from your workflow approach (SearchSection)
////////////////////////////////////////////////////////////
let searchStartTimestamp = 0;

// sub-message rotation
const subMessageInterval = ref(null);
const subMessageIndex = ref(0);
const currentSubMessages = ref([]);

function clearSubMessageInterval() {
  if (subMessageInterval.value) {
    clearInterval(subMessageInterval.value);
    subMessageInterval.value = null;
  }
  subMessageIndex.value = 0;
  currentSubMessages.value = [];
}

function startSubMessageCycle(messages) {
  clearSubMessageInterval();
  if (!messages || messages.length === 0) {
    loadingSubMessage.value = '';
    return;
  }
  currentSubMessages.value = messages;
  loadingSubMessage.value = messages[0];
  subMessageIndex.value = 1;

  subMessageInterval.value = setInterval(() => {
    loadingSubMessage.value = messages[subMessageIndex.value];
    subMessageIndex.value = (subMessageIndex.value + 1) % messages.length;
  }, 2000);
}

onBeforeUnmount(() => {
  clearSubMessageInterval();
});

/**
 * Called when SearchSection triggers "searchStart"
 * The first argument is the "detected route type"
 */
function handleSearchStart(type) {
  console.log('[MainLayout] handleSearchStart called with type:', type);

  // For document uploads, use the sessionId as the runId
  if (type === 'document_upload') {
    currentRunId.value = sessionId.value;
  }
  // For searches, generate a new runId
  else if (type === 'routing_query' || !currentRunId.value) {
    currentRunId.value = uuidv4();
  }

  // Only show spinner and clear results for actual searches
  if (type !== 'document_upload') {
    // Show spinner
    isLoading.value = true;
    results.value = null;
    queryType.value = type;
    searchStartTimestamp = performance.now();
  }
}

// Watch queryType => update loading messages
watch(queryType, (newVal, oldVal) => {
  clearSubMessageInterval();

  switch (newVal) {
    case 'routing_query':
      loadingMessage.value = 'Routing Query...';
      loadingSubMessage.value = '';
      break;
    case 'sales_leads':
      loadingMessage.value = 'Sales Leads Query...';
      startSubMessageCycle([
        'Searching for companies...',
        'Extracting data...',
        'Getting marketing info...',
      ]);
      break;
    case 'educational_content':
      loadingMessage.value = 'Research Generation...';
      startSubMessageCycle([
        'Searching for topics...',
        'Creating content plan...',
        'Writing content...',
      ]);
      break;
    case 'financial_analysis':
      loadingMessage.value = 'Financial Analysis...';
      startSubMessageCycle([
        'Gathering financial data...',
        'Performing competitor comparisons...',
        'Assessing risk...',
      ]);
      break;
    default:
      loadingMessage.value = 'Determining route...';
      loadingSubMessage.value = '';
      break;
  }
});

function handleSearchComplete(searchResults) {
  queryType.value = searchResults.type;
  results.value = searchResults.results;

  // Save final report
  reportStore.saveReport(
    searchResults.type,
    searchResults.query,
    searchResults.results
  );

  // Turn off spinner
  isLoading.value = false;

  // Show notification
  const elapsed = (performance.now() - searchStartTimestamp) / 1000;
  searchTime.value = elapsed.toFixed(1);

  if (Array.isArray(searchResults.results)) {
    resultCount.value = searchResults.results.length;
  } else if (
    searchResults.results?.results &&
    Array.isArray(searchResults.results.results)
  ) {
    resultCount.value = searchResults.results.results.length;
  } else {
    resultCount.value = Object.keys(searchResults.results || {}).length;
  }

  showNotification.value = true;
  setTimeout(() => {
    showNotification.value = false;
  }, 5000);
}

// searchError => hide spinner, show error
function handleSearchError(error) {
  console.error('[MainLayout] Search error:', error);
  isLoading.value = false;
  loadingMessage.value = '';
  loadingSubMessage.value = '';
  showError.value = true;
  errorMessage.value = error?.message || 'An unexpected error occurred';
}

// close error modal
function closeError() {
  showError.value = false;
  errorMessage.value = '';
}

// open settings
function openSettings() {
  if (headerRef.value) {
    headerRef.value.openSettings();
  }
}

const hasResults = computed(() => {
  if (queryType.value === 'sales_leads') {
    return (
      results.value?.results &&
      Array.isArray(results.value.results) &&
      results.value.results.length > 0
    );
  }
  if (queryType.value === 'educational_content') {
    return Array.isArray(results.value) && results.value.length > 0;
  }
  if (queryType.value === 'financial_analysis') {
    return !!(results.value && Object.keys(results.value).length > 0);
  }
  return false;
});

// Computed style for main content adjustment
const mainContentStyle = computed(() => {
  if (!daytonaSidebarState.value.isOpen) {
    return {}
  }
  
  const sidebarWidth = daytonaSidebarState.value.isCollapsed ? '64px' : '50%'
  return {
    marginRight: sidebarWidth
  }
})

// Handler for sidebar state changes
function handleDaytonaSidebarStateChange(sidebarState) {
  daytonaSidebarState.value = sidebarState
}
</script>

<style scoped>
/* Basic styling as needed. */
</style>
