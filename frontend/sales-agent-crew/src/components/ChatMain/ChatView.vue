<template>
  <div class="relative h-full w-full">
    <!-- Content -->
    <div
      ref="container"
      class="relative h-full flex flex-col overflow-x-hidden overflow-y-auto"
    >
      <!-- Sticky Top Component -->
      <div
        class="sticky top-0 z-10 bg-white p-4 shadow"
      >
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-end gap-2 sm:gap-4 min-h-[2rem]">
          <!-- Token Usage Display -->
          <div v-if="cumulativeTokenUsage.total_tokens > 0" class="flex flex-wrap items-center gap-1 sm:gap-2 text-sm text-gray-600">
            <span class="font-medium whitespace-nowrap">Chat Usage Tokens:</span>
            <span class="bg-gray-100 text-gray-700 px-2 py-1 rounded text-xs whitespace-nowrap">
              {{ cumulativeTokenUsage.input_tokens.toLocaleString() }} input
            </span>
            <span class="bg-gray-200 text-gray-800 px-2 py-1 rounded text-xs whitespace-nowrap">
              {{ cumulativeTokenUsage.output_tokens.toLocaleString() }} output
            </span>
            <span class="bg-gray-300 text-gray-900 px-2 py-1 rounded text-xs whitespace-nowrap">
              {{ cumulativeTokenUsage.total_tokens.toLocaleString() }} total
            </span>
          </div>
          
          <!-- Right buttons -->
          <div class="flex hidden space-x-2">
            <button
              class="text-sm h-[30px] py-1 px-2.5 bg-[#EE7624] text-white rounded"
            >
              View full report
            </button>
            <button
              @click="genPDF"
              class="text-sm h-[30px] py-1 px-2.5 bg-[#EAECF0] text-[#344054] rounded"
            >
              Download PDF
            </button>
          </div>
        </div>
      </div>
      <div
        class="flex-1 w-full flex mx-auto"
        :class="
          messagesData.length == 0 ? 'justify-center align-center flex-col' : ''
        "
      >
        <!-- Title -->
        <div v-if="messagesData.length == 0" class="w-full text-center">
          <h1 v-if="!initialLoading" class="text-3xl font-bold sm:text-3xl">
            <span class="bg-clip-text text-primary-brandTextSecondary">
              What can I help you with?
            </span>
          </h1>
        </div>
        <!-- End Title -->
        
        <transition-group
          name="chat"
          tag="ul"
          class="mt-16 max-w-4xl w-full mx-auto space-y-5"
        >
          <!-- Chat Bubble -->
          <li v-for="msgItem in filteredMessages" :key="msgItem.conversation_id || msgItem.message_id || msgItem.timestamp || Math.random()">
            <ChatBubble
              :metadata="completionMetaData || {}"
              :workflowData="
                workflowData.filter(
                  (item) => item.message_id === (msgItem.message_id || msgItem.messageId)
                )
              "
              :plannerText="
                plannerTextData.filter(
                  (item) => item.message_id === (msgItem.message_id || msgItem.messageId)
                )[0]?.data || ''
              "
              :event="msgItem.event || 'unknown'"
              :data="formatMessageData(msgItem)"
              :messageId="msgItem.message_id || msgItem.messageId || msgItem.id"
              :streamingEvents="msgItem.type === 'streaming_group' ? msgItem.events : null"
              :provider="provider"
              :sidebarOpen="showDaytonaSidebar"
              :isInDeepResearch="isInDeepResearch"
              @open-daytona-sidebar="handleOpenDaytonaSidebar"
              @open-artifact-canvas="handleOpenArtifactCanvas"
            />
            
            <!-- Token Usage Display for Final Messages -->
            <div v-if="isFinalMessage(msgItem) && getRunSummary(msgItem)?.total_tokens > 0" class="mt-2">
              <!-- Run Summary Metrics -->
              <div class="bg-gradient-to-r from-gray-50 to-gray-100 border border-gray-200 rounded-lg px-3 py-2 block shadow-sm hover:shadow-md transition-shadow duration-200 max-w-full w-fit">
                <div class="flex flex-wrap items-center gap-2 sm:gap-3">
                  <!-- Run Summary Label -->
                  
                                      <!-- Input Tokens -->
                    <div class="flex flex-col items-center w-[50px] sm:w-[55px]">
                      <span class="text-xs font-semibold text-gray-800">{{ getRunSummary(msgItem).input_tokens.toLocaleString() }}</span>
                      <span class="text-2xs text-gray-600">input</span>
                    </div>
                    
                    <!-- Divider -->
                    <div class="h-4 w-px bg-gradient-to-b from-transparent via-gray-300 to-transparent hidden sm:block"></div>
                    
                    <!-- Output Tokens -->
                    <div class="flex flex-col items-center w-[50px] sm:w-[55px]">
                      <span class="text-xs font-semibold text-gray-800">{{ getRunSummary(msgItem).output_tokens.toLocaleString() }}</span>
                      <span class="text-2xs text-gray-600">output</span>
                    </div>
                    
                    <!-- Divider -->
                    <div class="h-4 w-px bg-gradient-to-b from-transparent via-gray-300 to-transparent hidden sm:block"></div>
                    
                    <!-- Total Tokens -->
                    <div class="flex flex-col items-center w-[50px] sm:w-[55px]">
                      <span class="text-xs font-semibold text-gray-800">{{ getRunSummary(msgItem).total_tokens.toLocaleString() }}</span>
                      <span class="text-2xs text-gray-600">total</span>
                    </div>

                  <!-- Performance Metrics Summary -->
                  <template v-if="getRunSummary(msgItem).total_latency > 0">
                    <!-- Performance Section Divider -->
                    <div class="h-4 w-px bg-gradient-to-b from-transparent via-gray-300 to-transparent hidden sm:block"></div>
                    
                    <!-- Total Latency -->
                    <div class="flex flex-col items-center w-[45px] sm:w-[50px]">
                      <span class="text-xs font-semibold text-gray-800">{{ getRunSummary(msgItem).total_latency.toFixed(2) }}s</span>
                      <span class="text-2xs text-gray-600">latency</span>
                    </div>

                    <!-- Divider -->
                    <div class="h-4 w-px bg-gradient-to-b from-transparent via-gray-300 to-transparent hidden sm:block"></div>
                    
                    <!-- Total Time to First Token -->
                    <div v-if="getRunSummary(msgItem).total_ttft > 0" class="flex flex-col items-center w-[45px] sm:w-[50px]">
                      <span class="text-xs font-semibold text-gray-800">{{ getRunSummary(msgItem).total_ttft.toFixed(2) }}s</span>
                      <span class="text-2xs text-gray-600">TTFT</span>
                    </div>
                    
                    <!-- Divider -->
                    <div v-if="getRunSummary(msgItem).total_ttft > 0 && getRunSummary(msgItem).avg_throughput > 0" class="h-4 w-px bg-gradient-to-b from-transparent via-gray-300 to-transparent hidden sm:block"></div>
                    
                    <!-- Average Throughput -->
                    <div v-if="getRunSummary(msgItem).avg_throughput > 0" class="flex flex-col items-center w-[45px] sm:w-[50px]">
                      <span class="text-xs font-semibold text-gray-800">{{ getRunSummary(msgItem).avg_throughput.toFixed(1) }}</span>
                      <span class="text-2xs text-gray-600">avg t/s</span>
                    </div>
                  </template>

                  <!-- Divider -->
                  <div class="h-4 w-px bg-gradient-to-b from-transparent via-gray-300 to-transparent hidden sm:block"></div>
                  
                  <!-- Event Count -->
                  <div class="flex flex-col items-center w-[40px] sm:w-[45px]">
                    <span class="text-xs font-semibold text-gray-800">{{ getRunSummary(msgItem).event_count }}</span>
                    <span class="text-2xs text-gray-600">events</span>
                  </div>
                </div>
              </div>
            </div>
          </li>
          
          <ChatLoaderBubble
            :workflowData="
              workflowData.filter((item) => item.message_id === currentMsgId)
            "
            v-if="isLoading && !hasActiveStreamingGroup && workflowData.length > 0"
            :isLoading="isLoading"
            :statusText="'Planning...'"
            :plannerText="
              plannerTextData.filter(
                (item) => item.message_id === currentMsgId
              )[0]?.data
            "
            :provider="provider"
            :messageId="currentMsgId"
          />
          
          <!-- End Chat Bubble -->
        </transition-group>
      </div>

      <!-- Single Daytona Sidebar at ChatView level (persistent across messages) -->
      <DaytonaSidebar 
        :isOpen="showDaytonaSidebar"
        :streamingEvents="currentDaytonaEvents"
        @close="closeDaytonaSidebar"
        @expand-chart="openArtifact"
        @sidebar-state-changed="emit('daytona-sidebar-state-changed', $event)"
      />
      
      <!-- Artifact Canvas Modal (fallback for non-Daytona artifacts) -->
      <ArtifactCanvas 
        :isOpen="showArtifactCanvas"
        :artifact="selectedArtifact"
        @close="closeArtifactCanvas"
      />

      <!-- Documents Section -->
      <div class="sticky z-1000 bottom-0 left-0 right-0 bg-white p-2">
        <div class="sticky bottom-0 z-10">
          <!-- Textarea -->
          <div class="max-w-4xl mx-auto lg:px-0">
            <div v-if="errorMessage" class="m-1 w-full mx-auto space-y-5">
              <ErrorComponent :parsed="{ data: { error: errorMessage } }" />
            </div>

            <div v-if="uploadedDocuments.length > 0" class="mt-4">
              <!-- Collapsible header -->
              <button
                @click="toggleExpand"
                class="flex items-center justify-between focus:outline-none mb-2"
              >
                <h3 class="text-sm font-medium text-gray-700">
                  Uploaded Documents ({{ uploadedDocuments.length }})
                </h3>
                <svg
                  :class="{ 'transform rotate-180': isExpanded }"
                  class="w-5 h-5 text-gray-500 transition-transform duration-200"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </button>

              <!-- Collapsible content -->
              <div v-if="isExpanded">
                <HorizontalScroll>
                  <div class="flex space-x-4">
                    <div
                      v-for="doc in uploadedDocuments"
                      :key="doc.file_id"
                      class="w-48 flex-shrink-0 p-2 bg-gray-50 rounded-lg border border-gray-200 hover:bg-gray-100 relative group"
                    >
                      <div class="flex items-center space-x-3">
                        <input
                          type="checkbox"
                          :checked="selectedDocuments.includes(doc.file_id)"
                          @change="toggleDocumentSelection(doc.file_id)"
                          class="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                        />
                        <div class="w-48 overflow-hidden">
                          <p class="text-sm font-medium text-gray-900 truncate">
                            {{ doc.filename }}
                          </p>
                          <p class="text-xs text-gray-500 truncate">
                            Uploaded
                            {{
                              new Date(
                                doc.created_at * 1000
                              ).toLocaleString()
                            }}
                            • {{ doc.num_chunks }} chunks
                          </p>
                        </div>
                      </div>
                      <button
                        @click="removeDocument(doc.file_id)"
                        class="absolute top-1 right-1 bg-orange-300 text-white rounded-full p-1 transition-opacity opacity-0 group-hover:opacity-100"
                        title="Remove document"
                      >
                        <XMarkIcon class="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                </HorizontalScroll>
              </div>
            </div>

            <!-- Upload Status -->
            <div
              v-if="uploadStatus"
              class="mt-2 text-sm text-center"
              :class="{
                'text-red-500': uploadStatus.type === 'error',
                'text-green-600': uploadStatus.type === 'success',
                'text-gray-500': uploadStatus.type === 'info',
              }"
            >
              {{ uploadStatus.message }}
            </div>

            <!-- Input -->
            <div class="relative">
              <textarea
                @focus="checkAndOpenSettings"
                @keydown="handleKeyDown"
                v-model="searchQuery"
                type="search"
                placeholder="Ask me about...companies to target, research topics, or company stocks and financials"
                :disabled="isLoading"
                class="p-4 pb-12 block min-h-[106px] w-full bg-primary-brandFrame border-primary-brandFrame rounded-lg text-sm focus:outline-none active:outline-none border focus:border-primary-brandColor disabled:opacity-50 disabled:pointer-events-none resize-y"
              ></textarea>

              <!-- Toolbar -->
              <div
                class="absolute bottom-px inset-x-px p-2 rounded-b-lg border-primary-brandFrame"
              >
                <div class="flex justify-between items-center">
                  <!-- Button Group -->
                  <div class="flex items-center">
                    <!-- Attach Button -->
                    <button
                      @click="$refs.fileInput.click()"
                      :disabled="isLoading || isUploading"
                      type="button"
                      class="inline-flex shrink-0 justify-center items-center size-8 rounded-lg text-gray-500 hover:bg-gray-100 focus:z-1 focus:outline-none focus:bg-gray-100"
                    >
                      <input
                        type="file"
                        ref="fileInput"
                        @change="handleFileUpload"
                        class="hidden"
                        accept=".pdf,.doc,.docx,.csv,.xlsx,.xls,.jpeg,.jpg,.png,.gif,.webp"
                      />
                      <svg
                        v-if="!isUploading"
                        class="shrink-0 w-5 h-5"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="2"
                          d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
                        />
                      </svg>

                      <svg
                        v-if="isUploading"
                        class="shrink-0 w-5 h-5 animate-spin"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="2"
                          d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"
                        />
                      </svg>
                    </button>
                    <!-- End Attach Button -->
                    <!-- Mic Button -->
                    <button
                      type="button"
                      @click="toggleRecording"
                      :disabled="isLoading"
                      :class="{
                        'text-gray-500': !isRecording,
                        'text-orange-500': isRecording,
                      }"
                      class="inline-flex shrink-0 justify-center items-center size-8 rounded-lg text-gray-500 hover:bg-gray-100 focus:z-1 focus:outline-none focus:bg-gray-100"
                    >
                      <svg
                        v-if="!isRecording"
                        class="shrink-0"
                        width="24"
                        height="20"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="#667085"
                        stroke-width="2"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          d="M12 2c-1.7 0-3 1.2-3 2.6v6.8c0 1.4 1.3 2.6 3 2.6s3-1.2 3-2.6V4.6C15 3.2 13.7 2 12 2z"
                        />
                        <path
                          d="M19 10v1a7 7 0 0 1-14 0v-1M12 18.4v3.3M8 22h8"
                        />
                      </svg>

                      <svg
                        v-else
                        class="w-6 h-6 text-gray-800"
                        aria-hidden="true"
                        xmlns="http://www.w3.org/2000/svg"
                        width="24"
                        height="24"
                        fill="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          d="M7 5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H7Z"
                        />
                      </svg>
                    </button>
                    <!-- End Mic Button -->
                  </div>
                  <!-- End Button Group -->
                  <!-- Button Group -->
                  <div class="flex items-center gap-x-1">
                    <!-- Mic Button -->
                    <Tooltip
                      text="Use voice mode"
                      position="top"
                      color="bg-black text-white"
                    >
                      <button
                        type="button"
                        @click="toggleRecording"
                        :disabled="isLoading"
                        :class="{
                          'text-gray-500': !isRecording,
                          'text-orange-500': isRecording,
                        }"
                        class="inline-flex hidden shrink-0 justify-center items-center size-8 rounded-lg text-gray-500 hover:bg-gray-100 focus:z-1 focus:outline-none focus:bg-gray-100"
                      >
                        <svg
                          v-if="!isRecording"
                          class="w-6 h-6 text-gray-800"
                          aria-hidden="true"
                          xmlns="http://www.w3.org/2000/svg"
                          width="24"
                          height="24"
                          fill="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            fill-rule="evenodd"
                            d="M5 8a1 1 0 0 1 1 1v3a4.006 4.006 0 0 0 4 4h4a4.006 4.006 0 0 0 4-4V9a1 1 0 1 1 2 0v3.001A6.006 6.006 0 0 1 14.001 18H13v2h2a1 1 0 1 1 0 2H9a1 1 0 1 1 0-2h2v-2H9.999A6.006 6.006 0 0 1 4 12.001V9a1 1 0 0 1 1-1Z"
                            clip-rule="evenodd"
                          />
                          <path
                            d="M7 6a4 4 0 0 1 4-4h2a4 4 0 0 1 4 4v5a4 4 0 0 1-4 4h-2a4 4 0 0 1-4-4V6Z"
                          />
                        </svg>
                        <svg
                          v-else
                          class="w-6 h-6 text-gray-800"
                          aria-hidden="true"
                          xmlns="http://www.w3.org/2000/svg"
                          width="24"
                          height="24"
                          fill="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            d="M7 5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H7Z"
                          />
                        </svg>
                      </button>
                    </Tooltip>
                    <!-- End Mic Button -->
                    <!-- Send Button -->
                    <button
                      type="button"
                      @click="addMessage"
                      :disabled="isLoading || !searchQuery.trim()"
                      class="inline-flex shrink-0 justify-center items-center bg-transparent cursor-pointer"
                    >
                      <svg
                        id="send-button"
                        v-if="!isLoading"
                        width="21"
                        height="18"
                        viewBox="0 0 21 18"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          d="M0.00999999 18L21 9L0.00999999 0L0 7L15 9L0 11L0.00999999 18Z"
                          fill="#EE7624"
                        />
                      </svg>
                      <svg
                        id="stop-button"
                        v-if="isLoading"
                        width="20"
                        height="20"
                        viewBox="0 0 20 20"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          d="M10 0C4.48 0 0 4.48 0 10C0 15.52 4.48 20 10 20C15.52 20 20 15.52 20 10C20 4.48 15.52 0 10 0ZM10 18C5.58 18 2 14.42 2 10C2 5.58 5.58 2 10 2C14.42 2 18 5.58 18 10C18 14.42 14.42 18 10 18ZM14 14H6V6H14V14Z"
                          fill="#667085"
                        />
                      </svg>
                    </button>
                    <!-- End Send Button -->
                  </div>
                  <!-- End Button Group -->
                </div>
              </div>
              <!-- End Toolbar -->
            </div>
            <!-- End Input -->
          </div>
          <!-- End Textarea -->
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  ref,
  watch,
  onMounted,
  nextTick,
  onBeforeUnmount,
  onUnmounted,
  inject,
  computed,
} from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';
import ChatBubble from '@/components/ChatMain/ChatBubble.vue';
import ChatLoaderBubble from '@/components/ChatMain/ChatLoaderBubble.vue';
const router = useRouter();
const route = useRoute();
import { useAuth } from '@clerk/vue';
import { decryptKey } from '../../utils/encryption';
import Tooltip from '@/components/Common/UIComponents/CustomTooltip.vue';

import { XMarkIcon } from '@heroicons/vue/24/outline';
import HorizontalScroll from '@/components/Common/UIComponents/HorizontalScroll.vue';
import emitterMitt from '@/utils/eventBus.js';
import ErrorComponent from '@/components/ChatMain/ResponseTypes/ErrorComponent.vue';
import DaytonaSidebar from '@/components/ChatMain/DaytonaSidebar.vue';
import ArtifactCanvas from '@/components/ChatMain/ArtifactCanvas.vue';
import { isFinalAgentType, shouldExcludeFromGrouping } from '@/utils/globalFunctions.js';

// Inject the shared selectedOption from MainLayout.vue.
const selectedOption = inject('selectedOption');
async function handleButtonClick(data) {
  chatName.value = '';
  
  // Create new chat instead of just going to home
  await createNewChat();
}

async function genPDF() {
  try {
    const sampleContent = {
      report: [
        {
          title: 'Introduction',
          high_level_goal: 'Understand the basics of Vue 3',
          why_important:
            'Vue 3 is a modern framework with reactivity features.',
          generated_content:
            '## Vue 3 Overview\nVue 3 introduces Composition API, better performance, and more...',
        },
      ],
    };

    downloadPDF(sampleContent);
  } catch (e) {
    console.log('PDF gen error', e);
  }
}

async function createNewChat() {
  try {
    const resp = await axios.post(
      `${import.meta.env.VITE_API_URL}/chat/init`,
      {},
      {
        headers: {
          Authorization: `Bearer ${await window.Clerk.session.getToken()}`,
        },
      }
    );
    const cid = resp.data.conversation_id;
    router.push(`/${cid}`);
  } catch (err) {
    console.error('Error creating new chat:', err);
    errorMessage.value =
      'Failed to create new conversation. Check keys or console.';
    isLoading.value = false;
  }
}

// Watch for changes to the selection and load data accordingly.
const provider = ref('');
const chatName = ref('');
watch(
  selectedOption,
  (newVal) => {
    console.log('Selected option changed:', newVal);
    provider.value = newVal.value;
  },
  { immediate: true }
);

const socket = ref(null); // WebSocket reference
const container = ref(null);
const isExpanded = ref(false);
let pingInterval = null;

function toggleExpand() {
  isExpanded.value = !isExpanded.value;
}

function handleKeyDown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();

    addMessage();
  }
}



function AutoScrollToBottom(smoothScrollOff = false) {
  nextTick(() => {
    setTimeout(() => {
      if (container.value) {
        const targetScroll =
          container.value.scrollHeight - container.value.clientHeight;
        container.value.scrollTo({
          top: targetScroll,
          behavior: smoothScrollOff ? 'auto' : 'smooth',
        });
      }
    }, 100); // Adjust timeout as needed
  });
}

const emit = defineEmits([
  'searchStart',
  'metadataChanged',
  'searchComplete',
  'searchError',
  'openSettings',
  'agentThoughtsDataChanged',
  'daytona-sidebar-state-changed',
]);
const props = defineProps({
  conversationId: {
    type: String,
    default: '',
  },
  userId: {
    type: String,
    default: 'anonymous',
  },
  keysUpdated: {
    type: Number,
    default: 0,
  },
  runId: {
    type: String,
    default: '',
  },
  sessionId: {
    type: String,
    default: '',
  },
});

const isLoading = ref(false);
const initialLoading = ref(false);

// Conversation change watcher:
watch(
  () => route.params.id,
  (newId, oldId) => {
    if (newId !== oldId) {
      // Clear all previous data
      initialLoading.value = true;
      errorMessage.value = '';
      completionMetaData.value = null;
      messagesData.value = [];
      agentThoughtsData.value = [];
      workflowData.value = [];
      plannerTextData.value = [];
      searchQuery.value = '';
      chatName.value = '';
      isLoading.value = false;
      cumulativeTokenUsage.value = {
        input_tokens: 0,
        output_tokens: 0,
        total_tokens: 0
      };
      
      // Clear run metrics for new conversation
      runMetrics.value.clear();
      
      // Reset deep research state for new conversation
      isInDeepResearch.value = false;
      
      // Reset sidebar state when switching conversations
      showDaytonaSidebar.value = false;
      currentDaytonaEvents.value = [];
      showArtifactCanvas.value = false;
      selectedArtifact.value = null;
      daytonaSidebarClosed.value = false; // Reset manual close flag for new conversation

      // Load new conversation data
      if (newId) {
        loadPreviousChat(newId);
      } else {
        // No conversation ID - clear everything and set to ready state
        initialLoading.value = false;
      }
    }
    currentId.value = newId || '';

    // Close existing socket and reconnect
    if (socket.value) {
      closeSocket();
    }
    if (newId) {
      connectWebSocket();
    }
  }
);



const checkAndOpenSettings = () => {
  emitterMitt.emit('check-keys', { message: 'check keys!' });
};

async function loadPreviousChat(convId) {
  if (!convId) {
    initialLoading.value = false;
    return;
  }

  try {
    initialLoading.value = true;
    console.log('Loading previous chat:', convId);
    
    const resp = await axios.get(
      `${import.meta.env.VITE_API_URL}/chat/history/${convId}`,
      {
        headers: {
          Authorization: `Bearer ${await window.Clerk.session.getToken()}`,
        },
      }
    );

    console.log('Chat history response:', resp.data);
    
    if (resp.data && resp.data.messages) {
      await filterChat(resp.data);

    } else {
      console.warn('No messages found in chat history response');
      messagesData.value = [];
    }
    
    AutoScrollToBottom(true);
  } catch (err) {
    console.error('Error loading previous chat:', err);
    // Don't show error message for specific DaytonaSidebar errors
    if (!err.message?.includes('content.match is not a function')) {
      errorMessage.value = 'Failed to load conversation history. Please try again.';
    }
    messagesData.value = [];
  } finally {
    initialLoading.value = false;
    isLoading.value = false;
    // Clear any status text that might be showing "generating" or "processing"
    statusText.value = '';
  }
}
const currentId = ref(route.params.id || '');

const messagesData = ref([]);
const workflowData = ref([]);
const completionMetaData = ref(null);
const agentThoughtsData = ref([]);
const cumulativeTokenUsage = ref({
  input_tokens: 0,
  output_tokens: 0,
  total_tokens: 0
});

// Track metrics per run_id
const runMetrics = ref(new Map());

// Track deep research state
const isInDeepResearch = ref(false);

async function filterChat(msgData) {
  // First pass: identify conversation turns for run grouping
  let currentRunId = null;
  const messageToRunMap = new Map();
  
  // Sort messages by timestamp to ensure proper ordering
  const sortedMessages = msgData.messages.sort((a, b) => 
    new Date(a.timestamp || 0).getTime() - new Date(b.timestamp || 0).getTime()
  );
  
  sortedMessages.forEach(message => {
    const isUserMessage = message.additional_kwargs?.agent_type === 'human' || message.type === 'HumanMessage';
    
    if (isUserMessage) {
      // Start a new conversation turn
      currentRunId = message.message_id;
    }
    
    // Map this message to the current run
    if (currentRunId) {
      messageToRunMap.set(message.message_id, currentRunId);
    }
  });
  


  // Second pass: track ALL metrics for ALL messages BEFORE filtering
  sortedMessages.forEach(message => {
    // Count events that contribute to the conversation run
    const shouldTrackEvent = ['agent_completion', 'think', 'planner', 'llm_stream_chunk', 'stream_complete'].includes(message.event);
    
    if (shouldTrackEvent) {
      const runId = messageToRunMap.get(message.message_id) || message.message_id;
      
      // Track metrics if they exist (for agent_completion events)
      if (message.event === 'agent_completion') {
        // Check if we have token usage or performance metrics to track
        const hasUsageMetadata = message.usage_metadata;
        const hasPerformanceMetrics = message.response_metadata?.usage;
        
        if (hasUsageMetadata || hasPerformanceMetrics) {
          trackRunMetrics(runId, message.usage_metadata, message.response_metadata);
        } else {
          // Still count the event even without usage metadata
          trackRunMetrics(runId, null, null);
        }
      } else {
        // For other events, still count the event even without usage metadata
        trackRunMetrics(runId, null, null);
      }
    }
  });

  messagesData.value = msgData.messages
    .map(message => {
      // For agent_completion events, handle LangGraph format
      if (message.event === 'agent_completion') {
        // For tool calls and tool results, preserve them for comprehensive audit log and Daytona sidebar
        // but only filter them from main chat display if they're tool-related
        const isToolCall = message.content && typeof message.content === 'string' && message.content.includes('<tool>');
        const isToolResult = Array.isArray(message.content) || (message.additional_kwargs?.agent_type === 'react_tool');
        const isToolResponse = message.additional_kwargs?.agent_type === 'tool_response';
        
        // For Daytona sandbox tool calls/results, always preserve them for sidebar processing
        const isDaytonaRelated = (isToolCall && message.content.includes('DaytonaCodeSandbox')) ||
                                 (message.type === 'LiberalFunctionMessage' && message.name === 'DaytonaCodeSandbox');
        
        if (isToolCall || isToolResult || isToolResponse || isDaytonaRelated) {
          // Preserve tool-related messages for comprehensive audit log and Daytona processing
          
          // Create structured data for tool events matching the live streaming format
          const toolData = {
            content: message.content || '',
            additional_kwargs: message.additional_kwargs || {},
            response_metadata: message.response_metadata || {},
            type: message.type || 'AIMessage',
            id: message.id || message.message_id,
            name: message.name || null,
            agent_type: message.additional_kwargs?.agent_type || 'tool'
          };
          
          return {
            event: 'agent_completion',
            data: toolData,
            message_id: message.message_id,
            conversation_id: message.conversation_id,
            timestamp: message.timestamp || new Date().toISOString(),
            isToolRelated: true, // Flag for filtering in chat display but preserving for audit
            isDaytonaRelated: isDaytonaRelated
          };
        }
        
        // Only show user messages and final responses in main chat bubbles
        const isUserMessage = message.additional_kwargs?.agent_type === 'human' || message.type === 'HumanMessage';
        const isFinalResponse = isFinalAgentType(message.additional_kwargs?.agent_type);
        const isRegularAIMessage = message.type === 'AIMessage' && !isToolCall && !isToolResult && !isToolResponse;
        const isReactSubgraph = message.additional_kwargs?.agent_type === 'react_subgraph';
        
        if (!isUserMessage && !isFinalResponse && !isRegularAIMessage && !isReactSubgraph) {
          return null; // Filter out intermediate agent responses that aren't tool-related
        }
        
        // For human messages, keep new format
        if (isUserMessage) {
          return {
            event: 'agent_completion',
            content: message.content || '',
            additional_kwargs: message.additional_kwargs || {},
            response_metadata: message.response_metadata || {},
            type: message.type || 'HumanMessage',
            name: message.name || null,
            id: message.id || message.message_id,
            message_id: message.message_id,
            conversation_id: message.conversation_id,
            timestamp: message.timestamp || new Date().toISOString()
          };
        }
        
        // For final responses, keep as agent_completion
        const messageContent = {
          content: message.content || '',
          additional_kwargs: message.additional_kwargs || {},
          response_metadata: message.response_metadata || {},
          type: message.type || 'AIMessage',
          id: message.id || message.message_id,
          agent_type: message.additional_kwargs?.agent_type || 'assistant'
        };
        
        const restoredMessage = {
          event: 'agent_completion',
          data: messageContent,
          message_id: message.message_id,
          conversation_id: message.conversation_id,
          timestamp: message.timestamp || new Date().toISOString()
        };
        
        // Metrics tracking is now done in the pre-filter pass above
        
        // Restore token usage data in the same structure as live messages
        if (message.usage_metadata || message.cumulative_usage_metadata || message.response_metadata) {
          if (!restoredMessage.response_metadata) {
            restoredMessage.response_metadata = {};
          }
          if (!restoredMessage.response_metadata.usage) {
            restoredMessage.response_metadata.usage = {};
          }
          
          // Store token usage data from historical message
          if (message.usage_metadata) {
            restoredMessage.response_metadata.usage.input_tokens = message.usage_metadata.input_tokens || 0;
            restoredMessage.response_metadata.usage.output_tokens = message.usage_metadata.output_tokens || 0;
            restoredMessage.response_metadata.usage.total_tokens = message.usage_metadata.total_tokens || 0;
          }
          
          // Store performance metrics if they exist
          if (message.response_metadata?.usage) {
            Object.assign(restoredMessage.response_metadata.usage, message.response_metadata.usage);
          }
          
          // Store cumulative usage separately for header display
          if (message.cumulative_usage_metadata) {
            restoredMessage.cumulative_usage_metadata = message.cumulative_usage_metadata;
          }
        }
        
        return restoredMessage;
      }

      // Handle completion events (legacy)
      else if (message.event === 'completion') {
        return {
          event: 'completion',
          data: message.data,
          message_id: message.message_id,
          conversation_id: message.conversation_id,
          timestamp: message.timestamp || new Date().toISOString()
        };
      }
      // Handle think events (agent thoughts)
      else if (message.event === 'think') {
        return {
          event: 'think',
          data: message.data,
          message_id: message.message_id,
          conversation_id: message.conversation_id,
          timestamp: message.timestamp || new Date().toISOString()
        };
      }
      // Handle planner events
      else if (message.event === 'planner') {
        return {
          event: 'planner',
          data: message.data,
          message_id: message.message_id,
          conversation_id: message.conversation_id,
          timestamp: message.timestamp || new Date().toISOString()
        };
      }
      // Handle streaming events that might be in stored data - CRITICAL FOR PERSISTENCE
      else if (['llm_stream_chunk', 'stream_complete', 'stream_start'].includes(message.event)) {
        return {
          event: message.event,
          data: message.data || message,
          message_id: message.message_id,
          conversation_id: message.conversation_id,
          timestamp: message.timestamp || new Date().toISOString()
        };
      }

      // For any other events, include them as well
      else {
        return {
          event: message.event,
          data: message.data || message,
          message_id: message.message_id,
          conversation_id: message.conversation_id,
          timestamp: message.timestamp || new Date().toISOString()
        };
      }
    })
    .filter(Boolean)  // Remove null values
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

  // Process planner data for workflow metadata
  let plannerData = msgData.messages.filter(
    (message) => message.event === 'planner'
  );
  plannerData.forEach((planner) => {
    try {
      const parsedData = JSON.parse(planner.data);
      if (parsedData.metadata) {
        addOrUpdateModel(parsedData.metadata, planner.message_id);
      }
    } catch (error) {
      console.error('Failed to parse planner data:', error);
    }
  });

  // Process think events for workflow metadata
  let workData = msgData.messages.filter(
    (message) => message.event === 'think'
  );
  workData.forEach((work) => {
    try {
      const parsedData = JSON.parse(work.data);
      if (parsedData.metadata) {
        addOrUpdateModel(parsedData.metadata, work.message_id);
      }
    } catch (error) {
      console.error('Failed to parse think data:', error);
    }
  });

  // Process agent_completion events for workflow metadata (tool calls/results) - ENHANCED FOR PERSISTENCE
  let agentCompletionData = msgData.messages.filter(
    (message) => message.event === 'agent_completion' && (
      (message.content && typeof message.content === 'string' && message.content.includes('<tool>')) ||
      Array.isArray(message.content) ||
      (message.type === 'LiberalFunctionMessage') ||
      (message.additional_kwargs?.agent_type === 'react_tool') ||
      (message.additional_kwargs?.agent_type === 'tool_response') ||
      (message.name === 'DaytonaCodeSandbox')
    )
  );
  agentCompletionData.forEach((completion) => {
    try {
      // Enhanced metadata for different tool types
      let metadata = {
        workflow_name: "Agent Workflow",
        agent_name: "Research Agent", 
        task: "tool_execution",
        llm_name: completion.response_metadata?.model_name || "Unknown",
        llm_provider: "agent",
        duration: 0
      };

      // Specific handling for different tool types
      if (completion.name === 'DaytonaCodeSandbox' || 
          (completion.content && completion.content.includes('DaytonaCodeSandbox'))) {
        metadata.task = "code_execution";
        metadata.agent_name = "Daytona Sandbox";
        metadata.tool_name = "DaytonaCodeSandbox";
      } else if (completion.name === 'search_tavily' || 
                 (completion.content && completion.content.includes('search_tavily'))) {
        metadata.task = "web_search";
        metadata.tool_name = "search_tavily";
      } else if (completion.name === 'arxiv' || 
                 (completion.content && completion.content.includes('arxiv'))) {
        metadata.task = "arxiv_search";
        metadata.tool_name = "arxiv";
      } else if (Array.isArray(completion.content)) {
        metadata.task = "search_results";
      } else if (completion.content && completion.content.includes('<tool>')) {
        metadata.task = "tool_call";
      }

      addOrUpdateModel(metadata, completion.message_id);
    } catch (error) {
      console.error('Failed to process agent completion data:', error);
    }
  });

  // Process completion events for metadata - ENHANCED FOR COMPREHENSIVE LOG SUMMARY PERSISTENCE
  let completionData = msgData.messages.filter(
    (message) => message.event === 'completion' || message.event === 'stream_complete'
  );
  completionData.forEach((completion) => {
    try {
      let parsedData;
      if (typeof completion.data === 'string') {
        parsedData = JSON.parse(completion.data);
      } else {
        parsedData = completion.data;
      }
      
      if (parsedData.metadata) {
        completionMetaData.value = parsedData.metadata;
        emit('metadataChanged', completionMetaData.value);
      }
      
      // Also check for stream_complete events that might contain final metadata
      if (completion.event === 'stream_complete' && parsedData) {
        // Create synthetic completion metadata if not present
        if (!completionMetaData.value && workflowData.value.length > 0) {
          const totalDuration = workflowData.value.reduce((sum, item) => sum + (item.duration || 0), 0);
          const uniqueProviders = [...new Set(workflowData.value.map(item => item.llm_provider))];
          const uniqueModels = [...new Set(workflowData.value.map(item => item.llm_name))];
          
          completionMetaData.value = {
            total_duration: totalDuration,
            providers_used: uniqueProviders,
            models_used: uniqueModels,
            total_tools: workflowData.value.length,
            completion_status: 'completed'
          };
          emit('metadataChanged', completionMetaData.value);
        }
      }
    } catch (error) {
      console.error('Failed to parse completion data:', error);
    }
  });

  // Process agent_completion events for cumulative token usage restoration
  let latestCumulativeUsage = null;
  
  msgData.messages
    .filter((message) => message.event === 'agent_completion')
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .forEach((completion) => {
      // Check for cumulative_usage_metadata for header display
      if (completion.cumulative_usage_metadata) {
        latestCumulativeUsage = completion.cumulative_usage_metadata;
      }
    });
  
  // Restore the latest cumulative token usage for header display
  if (latestCumulativeUsage) {
    cumulativeTokenUsage.value = {
      input_tokens: latestCumulativeUsage.input_tokens || 0,
      output_tokens: latestCumulativeUsage.output_tokens || 0,
      total_tokens: latestCumulativeUsage.total_tokens || 0
    };
  }

  // Restore deep research state by checking the last agent_completion message
  msgData.messages
    .filter((message) => message.event === 'agent_completion')
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .forEach((completion) => {
      const agentType = completion.additional_kwargs?.agent_type;
      if (agentType === 'deep_research_interrupt') {
        isInDeepResearch.value = true;
      } else if (agentType === 'deep_research_end') {
        isInDeepResearch.value = false;
      }
    });

  AutoScrollToBottom();

  // Process agent thoughts data
  agentThoughtsData.value = msgData.messages
    .filter((message) => message.event === 'think')
    .sort(
      (a, b) =>
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    )
    .reduce((acc, message) => {
      try {
        const parsed = JSON.parse(message.data);
        acc.push(parsed);
      } catch (error) {
        console.error('Failed to parse JSON for message:', message, error);
      }
      return acc;
    }, []);
  emit('agentThoughtsDataChanged', agentThoughtsData.value);

  // Process planner text data
  let plannerTextMessages = msgData.messages.filter(
    (message) => message.event === 'planner'
  );
  plannerTextMessages.forEach((planner) => {
    try {
      const parsedData = JSON.parse(planner.data);
      if (parsedData.content || parsedData.message) {
        addOrUpdatePlannerText({
          message_id: planner.message_id,
          data: parsedData.content || parsedData.message || ''
        });
      }
    } catch (error) {
      console.error('Failed to parse planner text data:', error);
    }
  });

  let userMessages = messagesData.value
    .filter((message) => 
      message.additional_kwargs?.agent_type === 'human' || 
      message.type === 'HumanMessage'
    )
    .sort(
      (a, b) =>
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );

  if (userMessages[0]?.content) {
    chatName.value = userMessages[0].content;
  }

  AutoScrollToBottom();
  await nextTick();
}





// Reactive state for voice and file uploads
const searchQuery = ref('');
const isRecording = ref(false);
const mediaRecorder = ref(null);
const audioChunks = ref([]);
const sambanovaKey = ref(null);
const exaKey = ref(null);
const serperKey = ref(null);
const fireworksKey = ref(null);
const errorMessage = ref('');
const fileInput = ref(null);
const uploadStatus = ref(null);
const isUploading = ref(false);

// Document-related reactive state
const uploadedDocuments = ref([]);
const selectedDocuments = ref([]);
const manualSocketClose = ref(false);

// Clerk
const { userId } = useAuth();

async function loadKeys() {
  try {
    const encryptedSambanovaKey = localStorage.getItem(
      `sambanova_key_${userId.value}`
    );
    const encryptedExaKey = localStorage.getItem(`exa_key_${userId.value}`);
    const encryptedSerperKey = localStorage.getItem(
      `serper_key_${userId.value}`
    );
    const encryptedFireworksKey = localStorage.getItem(
      `fireworks_key_${userId.value}`
    );

    if (encryptedSambanovaKey) {
      sambanovaKey.value = await decryptKey(encryptedSambanovaKey);
    } else {
      sambanovaKey.value = null;
    }

    if (encryptedExaKey) {
      exaKey.value = await decryptKey(encryptedExaKey);
    } else {
      exaKey.value = null;
    }

    if (encryptedSerperKey) {
      serperKey.value = await decryptKey(encryptedSerperKey);
    } else {
      serperKey.value = null;
    }

    if (encryptedFireworksKey) {
      fireworksKey.value = await decryptKey(encryptedFireworksKey);
    } else {
      fireworksKey.value = null;
    }
  } catch (error) {
    console.error('Error loading keys:', error);
    errorMessage.value = 'Error loading API keys';
    showErrorModal.value = true;
    isLoading.value = false;
  }
}

onMounted(async () => {
  await loadKeys();
  await loadUserDocuments();
  
  const conversationId = route.params.id;
  currentId.value = conversationId || '';
  
  if (conversationId) {
    console.log('Mounting with conversation ID:', conversationId);
    await loadPreviousChat(conversationId);
  } else {
    console.log('Mounting without conversation ID');
    initialLoading.value = false;
  }

  emitterMitt.on('new-chat', handleButtonClick);
});

onUnmounted(() => {
  emitterMitt.off('new-chat', handleButtonClick);
});

watch(
  () => props.keysUpdated,
  async () => {
    await loadKeys();
  },
  { immediate: true }
);



const statusText = ref('Loading...');
const plannerTextData = ref([]);


function toggleRecording() {
  if (isRecording.value) {
    stopRecording();
  } else {
    startRecordingFlow();
  }
}

async function startRecordingFlow() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    startRecording(stream);
  } catch (error) {
    console.error('Error accessing microphone:', error);
    alert('Unable to access microphone. Please check your permissions.');
  }
}

function startRecording(stream) {
  audioChunks.value = [];
  const options = { mimeType: 'audio/webm' };
  if (!MediaRecorder.isTypeSupported(options.mimeType)) {
    console.warn(
      `${options.mimeType} is not supported, using default MIME type.`
    );
    delete options.mimeType;
  }
  mediaRecorder.value = new MediaRecorder(stream, options);
  mediaRecorder.value.ondataavailable = (event) => {
    if (event.data.size > 0) {
      audioChunks.value.push(event.data);
    }
  };
  mediaRecorder.value.onstop = async () => {
    const audioBlob = new Blob(audioChunks.value, { type: 'audio/webm' });
    await transcribeAudio(audioBlob);
    stream.getTracks().forEach((track) => track.stop());
  };
  mediaRecorder.value.start();
  isRecording.value = true;
}

function stopRecording() {
  if (mediaRecorder.value && mediaRecorder.value.state !== 'inactive') {
    mediaRecorder.value.stop();
    isRecording.value = false;
  }
}

async function transcribeAudio(audioBlob) {
  try {
    if (!sambanovaKey.value) {
      throw new Error(
        'SambaNova API key is missing. Please add it in the settings.'
      );
    }
    const audioArrayBuffer = await audioBlob.arrayBuffer();
    const audioBase64 = btoa(
      new Uint8Array(audioArrayBuffer).reduce(
        (data, byte) => data + String.fromCharCode(byte),
        ''
      )
    );
    const requestBody = {
      model: 'Whisper-Large-v3',
      messages: [
        {
          role: 'user',
          content: [
          {
            type: 'text',
            text: 'Transcribe the following audio',
          },
          {
            type: 'audio_content',
            audio_content: {
              content: `data:audio/webm;base64,${audioBase64}`,
            },
          },
          ],
        },
      ],
      stream: true,
      max_tokens: 200,
    };
    const response = await fetch(
      'https://api.sambanova.ai/v1/audio/reasoning',
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${sambanovaKey.value}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      }
    );
    if (!response.ok) {
      const errorText = await response.text();
      console.error('API Error:', response.status, errorText);
      alert(
        `Transcription failed with status ${response.status}: ${errorText}`
      );
      throw new Error(`Transcription failed: ${errorText}`);
    }
    const streamReader = response.body.getReader();
    let transcribedText = '';
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await streamReader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      const lines = chunk.split('\n').filter((line) => line.trim());
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6).trim();
          if (dataStr === '[DONE]') break;
          try {
            const data = JSON.parse(dataStr);
            if (data.choices?.[0]?.delta?.content) {
              transcribedText += data.choices[0].delta.content;
            }
          } catch (e) {
            console.error('Error parsing JSON:', e, 'Data string:', dataStr);
          }
        }
      }
    }
    const cleanedText = cleanTranscription(transcribedText);
    searchQuery.value = cleanedText.trim();
    if (searchQuery.value) {
      addMessage();
    }
  } catch (error) {
    console.error('Transcription error:', error);
    alert(error.message || 'Failed to transcribe audio. Please try again.');
  }
}

function cleanTranscription(transcribedText) {
  let cleanedText = transcribedText.trim();
  const prefixes = [
    'The transcription of the audio is:',
    'The transcription is:',
  ];
  for (const prefix of prefixes) {
    if (cleanedText.startsWith(prefix)) {
      cleanedText = cleanedText.slice(prefix.length).trim();
      break;
    }
  }
  if (
    (cleanedText.startsWith("'") && cleanedText.endsWith("'")) ||
    (cleanedText.startsWith('"') && cleanedText.endsWith('"'))
  ) {
    cleanedText = cleanedText.slice(1, -1).trim();
  }
  return cleanedText;
}

async function handleFileUpload(event) {
  isUploading.value = true;
  const file = event.target.files[0];
  if (!file) return;
  try {
    const formData = new FormData();
    formData.append('file', file);
    const response = await axios.post(
      `${import.meta.env.VITE_API_URL}/upload`,
      formData,
      {
        headers: {
          Authorization: `Bearer ${await window.Clerk.session.getToken()}`,
        },
      }
    );
    // Store the uploaded document and update selection.
    const document = response.data.document || response.data.file;
    uploadedDocuments.value.unshift(document);
    selectedDocuments.value.push(document.file_id);
    if (fileInput.value) {
      fileInput.value.value = '';
    }
  } catch (error) {
    console.error('[ChatView] Upload error:', error);
    uploadStatus.value = {
      type: 'error',
      message: error.response?.data?.error || 'Failed to upload document',
    };
  } finally {
    isUploading.value = false;
  }
}

async function loadUserDocuments() {
  try {
    const response = await axios.get(
      `${import.meta.env.VITE_API_URL}/files`,
      {
        headers: {
          Authorization: `Bearer ${await window.Clerk.session.getToken()}`,
        },
      }
    );
    uploadedDocuments.value = response.data.documents;
  } catch (error) {
    console.error('[SearchSection] Error loading documents:', error);
  }
}

function toggleDocumentSelection(docId) {
  const index = selectedDocuments.value.indexOf(docId);
  if (index === -1) {
    selectedDocuments.value.push(docId);
  } else {
    selectedDocuments.value.splice(index, 1);
  }
}

function waitForSocketOpen(timeout = 5000) {
  return new Promise((resolve, reject) => {
    const interval = 50;
    let elapsed = 0;
    const checkInterval = setInterval(() => {
      if (socket.value && socket.value.readyState === WebSocket.OPEN) {
        clearInterval(checkInterval);
        resolve();
      }
      elapsed += interval;
      if (elapsed >= timeout) {
        clearInterval(checkInterval);
        errorMessage.value = 'WebSocket connection error occurred.';
        isLoading.value = false;
        reject(new Error('Socket connection timeout'));
      }
    }, interval);
  });
}

const currentMsgId = ref('');
const addMessage = async () => {
  isLoading.value = true;
  errorMessage.value = '';

  workflowData.value = [];

  // If no conversation exists, create a new chat first.
  if (!route.params.id) {
    try {
      await createNewChat();
      await nextTick();
      // After createNewChat, the router push should update the conversation id.
      currentId.value = route.params.id; // update currentId from router params
      console.log('New chat created, conversation ID:', currentId.value);
    } catch (error) {
      console.error('Failed to create new chat:', error);
      errorMessage.value = 'Failed to create new conversation. Please try again.';
      isLoading.value = false;
      return;
    }
  }

  if (messagesData.value.length === 0) {
    chatName.value = searchQuery.value;
  }

  completionMetaData.value = null;
  // plannerText.value = null
  statusText.value = 'Loading...';
  AutoScrollToBottom();
  agentThoughtsData.value = [];
  // workflowData.value = []
  emit('agentThoughtsDataChanged', agentThoughtsData.value);
  emit('metadataChanged', completionMetaData.value);
  if (!searchQuery.value.trim()) return;

  currentMsgId.value = uuidv4();
  
  // Check if the last agent_completion message is a deep_research_interrupt and user typed something
  let shouldResume = false;
  if (messagesData.value.length > 0) {
    // Find the last agent_completion message (not stream_complete)
    for (let i = messagesData.value.length - 1; i >= 0; i--) {
      const message = messagesData.value[i];
      if (message.event === 'agent_completion') {
        // Check if this agent_completion has deep_research_interrupt agent_type
        if (message.data && message.data.additional_kwargs.agent_type === 'deep_research_interrupt') {
          // If user typed something, set resume to true
          shouldResume = searchQuery.value.trim().length > 0;
        }
        break; // Found the last agent_completion, stop looking
      }
    }
  }
  
  const messagePayload = {
    event: 'user_message',
    data: searchQuery.value,
    timestamp: new Date().toISOString(),
    provider: provider.value,
    planner_model: localStorage.getItem(`selected_model_${userId.value}`) || '',
    message_id: currentMsgId.value,
    conversation_id: currentId.value,
    resume: shouldResume,
  };

  if (selectedDocuments.value && selectedDocuments.value.length > 0) {
    messagePayload.document_ids = selectedDocuments.value.map((doc) => {
      return typeof doc === 'string' ? doc : doc.file_id;
    });
  } else {
    messagePayload.document_ids = [];
  }

  if (!socket.value || socket.value.readyState !== WebSocket.OPEN) {
    try {
      console.log('Socket not connected. Connecting...');
      connectWebSocket();
      await waitForSocketOpen();

      socket.value.send(JSON.stringify(messagePayload));
      messagesData.value.push(messagePayload);
      searchQuery.value = '';
      selectedDocuments.value = [];

      console.log('Message sent after connecting:', messagePayload);
    } catch (error) {
      errorMessage.value = 'WebSocket connection error occurred.';
      isLoading.value = false;
      console.error('Failed to connect and send message:', error);
    }
  } else {
    try {
      isLoading.value = true;
      socket.value.send(JSON.stringify(messagePayload));
      messagesData.value.push(messagePayload);
      searchQuery.value = '';
      selectedDocuments.value = [];
    } catch (e) {
      console.error('ChatView error', e);
      isLoading.value = false;
    }
  }
};

function addOrUpdateModel(newData, message_id) {
  // Determine which message_id to use.
  const idToUse = message_id ? message_id : currentMsgId.value;

  // Find an existing model with matching llm_name and message_id.
  const existingModel = workflowData.value.find(
    (item) => item.llm_name === newData.llm_name && item.message_id === idToUse
  );

  if (existingModel) {
    // Update existing model and increment count.
    Object.assign(existingModel, newData);
    existingModel.count = (existingModel.count || 1) + 1;
  } else {
    // Add new model entry with initial count of 1.
    workflowData.value.push({
      ...newData,
      count: 1,
      message_id: idToUse,
    });
  }
}

async function connectWebSocket() {
  try {
    await loadKeys();

    await axios.post(
      `${import.meta.env.VITE_API_URL}/set_api_keys`,
      {
        sambanova_key: sambanovaKey.value || '',
        serper_key: serperKey.value || '',
        exa_key: exaKey.value || '',
        fireworks_key: fireworksKey.value || '',
      },
      {
        headers: {
          Authorization: `Bearer ${await window.Clerk.session.getToken()}`,
        },
      }
    );

    // Use the same base URL pattern as API calls
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const baseUrl = import.meta.env.PROD
      ? `${wsProtocol}//${window.location.host}/api` // Use the current origin in production
      : import.meta.env.VITE_WEBSOCKET_URL || 'ws://localhost:8000';

    const WEBSOCKET_URL = `${baseUrl}/chat`;
    const token = await window.Clerk.session.getToken();
    const fullUrl = `${WEBSOCKET_URL}?conversation_id=${currentId.value}`;
    socket.value = new WebSocket(fullUrl);
    socket.value.onopen = () => {
      console.log('WebSocket connection opened');
      socket.value.send(
        JSON.stringify({
          type: 'auth',
          token: `Bearer ${token}`,
        })
      );
      // Start sending pings
      pingInterval = setInterval(() => {
        if (socket.value && socket.value.readyState === WebSocket.OPEN) {
          socket.value.send(JSON.stringify({ type: 'ping' }));
        }
      }, 30000); // Send a ping every 30 seconds
    };
    socket.value.onmessage = (event) => {
      try {
        const receivedData = JSON.parse(event.data);
        
        if (receivedData.type === 'pong') {
          // Pong received, connection is alive.
          return;
        }

        // Handle streaming events
        if (receivedData.event === 'agent_completion') {
          
          // Update deep research state based on agent type
          const agentType = receivedData.additional_kwargs?.agent_type;
          if (agentType === 'react_subgraph_deep_research') {
            isInDeepResearch.value = true;
          } else if (agentType === 'deep_research_end') {
            isInDeepResearch.value = false;
          }
          
          // Update cumulative token usage if present
          if (receivedData.cumulative_usage_metadata) {
            cumulativeTokenUsage.value = {
              input_tokens: receivedData.cumulative_usage_metadata.input_tokens || 0,
              output_tokens: receivedData.cumulative_usage_metadata.output_tokens || 0,
              total_tokens: receivedData.cumulative_usage_metadata.total_tokens || 0
            };
            console.log('Updated cumulative token usage:', cumulativeTokenUsage.value);
          }
      

          
          // Check if this is a final response event
          const isFinalResponse = isFinalAgentType(receivedData.additional_kwargs?.agent_type);
          
          // Create message object and attach token usage data directly to it
          const messageData = {
            event: 'agent_completion', 
            data: receivedData || {},
            message_id: currentMsgId.value,
            conversation_id: currentId.value,
            timestamp: receivedData.timestamp || new Date().toISOString(),
            agent_type: receivedData.agent_type,
            isFinalResponse: isFinalResponse
          };
          
          // Store token usage and performance metrics together in response_metadata.usage
          if (receivedData.usage_metadata || receivedData.response_metadata) {
            if (!messageData.response_metadata) {
              messageData.response_metadata = {};
            }
            if (!messageData.response_metadata.usage) {
              messageData.response_metadata.usage = {};
            }
            
            // Store token usage data
            if (receivedData.usage_metadata) {
              messageData.response_metadata.usage.input_tokens = receivedData.usage_metadata.input_tokens || 0;
              messageData.response_metadata.usage.output_tokens = receivedData.usage_metadata.output_tokens || 0;
              messageData.response_metadata.usage.total_tokens = receivedData.usage_metadata.total_tokens || 0;
            }
            
            // Store performance metrics if they exist
            if (receivedData.response_metadata?.usage) {
              Object.assign(messageData.response_metadata.usage, receivedData.response_metadata.usage);
            }
            
            // Track metrics for run summary
            // Use currentMsgId as the run identifier to group all events from this conversation turn
            const runId = currentMsgId.value;
            trackRunMetrics(runId, receivedData.usage_metadata, receivedData.response_metadata);
          }
          
          // Still store cumulative usage separately for header display
          if (receivedData.cumulative_usage_metadata) {
            messageData.cumulative_usage_metadata = receivedData.cumulative_usage_metadata;
          }
          
          try {
            messagesData.value.push(messageData);
          } catch (error) {
            console.error('Error pushing message data:', error);
            isLoading.value = false;
            return;
          }
          
          // Set loading to false when we receive a final response
          if (isFinalResponse) {
            isLoading.value = false;
          }
        } else if (receivedData.event === 'llm_stream_chunk') {

          
          const chunkId = receivedData.id;
          
          if (chunkId) {
            // Find existing message with the same ID
            const existingIndex = messagesData.value.findIndex(
              (msg) => msg.event === 'llm_stream_chunk' && msg.data?.id === chunkId
            );
            
            if (existingIndex !== -1) {
              // Accumulate content for existing message
              try {
                const existingContent = messagesData.value[existingIndex].data?.content || '';
                const newContent = receivedData.content || '';
                messagesData.value[existingIndex].data.content = existingContent + newContent;
              } catch (error) {
                console.error('Error updating stream chunk:', error);
              }
            } else {
              // Create new message for new ID
              try {
                messagesData.value.push({
                  event: 'llm_stream_chunk',
                  data: receivedData || {},
                  message_id: currentMsgId.value,
                  conversation_id: currentId.value,
                  timestamp: new Date().toISOString()
                });
              } catch (error) {
                console.error('Error adding new stream chunk:', error);
              }
            }
          } else {
            // No ID, just add as new message
            try {
              messagesData.value.push({
                event: 'llm_stream_chunk',
                data: receivedData || {},
                message_id: currentMsgId.value,
                conversation_id: currentId.value,
                timestamp: new Date().toISOString()
              });
            } catch (error) {
              console.error('Error adding stream chunk without ID:', error);
            }

          }
        } else if (receivedData.event === 'stream_complete') {
          console.log('Stream complete:', receivedData);
          try {
            messagesData.value.push({
              event: 'stream_complete',
              data: receivedData || {},
              message_id: currentMsgId.value,
              conversation_id: currentId.value,
              timestamp: new Date().toISOString()
            });
          } catch (error) {
            console.error('Error adding stream complete message:', error);
          }
          isLoading.value = false;
        } else if (receivedData.event === 'planner_chunk') {
          addOrUpdatePlannerText({
            message_id: currentMsgId.value,
            data: receivedData.data,
          });
        } else if (receivedData.event === 'think') {
          let dataParsed = JSON.parse(receivedData.data);
          agentThoughtsData.value.push(dataParsed);

          statusText.value = dataParsed.agent_name;
          emit('agentThoughtsDataChanged', agentThoughtsData.value);
          try {
            addOrUpdateModel(dataParsed.metadata);
            
            // Add think event to messages for persistence
            try {
              messagesData.value.push({
                event: 'think',
                data: receivedData.data || {},
                message_id: receivedData.message_id || currentMsgId.value,
                conversation_id: receivedData.conversation_id || currentId.value,
                timestamp: receivedData.timestamp || new Date().toISOString()
              });
            } catch (error) {
              console.error('Error adding think message:', error);
            }

            AutoScrollToBottom();
          } catch (e) {
            console.log('model error', e);
            isLoading.value = false;
          }
        } else if (receivedData.event === 'planner') {
          let dataParsed = JSON.parse(receivedData.data);
          addOrUpdateModel(dataParsed.metadata);
          
          // Add planner event to messages for persistence
          try {
            messagesData.value.push({
              event: 'planner',
              data: receivedData.data || {},
              message_id: receivedData.message_id || currentMsgId.value,
              conversation_id: receivedData.conversation_id || currentId.value,
              timestamp: receivedData.timestamp || new Date().toISOString()
            });
          } catch (error) {
            console.error('Error adding planner message:', error);
          }

          AutoScrollToBottom();
        }
        
        // Auto scroll after any message
        AutoScrollToBottom();
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
        isLoading.value = false;
      }
    };
    socket.value.onerror = (error) => {
      console.error('WebSocket error:', error);
      if (!manualSocketClose.value)
        errorMessage.value = 'WebSocket connection error occurred.';

      isLoading.value = false;
    };
    socket.value.onclose = () => {
      console.log('WebSocket closed, attempting to reconnect...');
      isLoading.value = false;
    };
  } catch (error) {
    console.error('WebSocket connection error:', error);
    isLoading.value = false;
  }
}

function closeSocket() {
  manualSocketClose.value = true;
  if (socket.value) {
    socket.value.close();
  }
  clearInterval(pingInterval);
}
onBeforeUnmount(() => {
  closeSocket();
});
function addOrUpdatePlannerText(newEntry) {
  // Find the index of an existing entry with the same message_id
  const index = plannerTextData.value.findIndex(
    (entry) => entry.message_id === newEntry.message_id
  );

  if (index !== -1) {
    // Concatenate the new data with the existing data
    plannerTextData.value[index].data += newEntry.data;
  } else {
    // Add new entry
    plannerTextData.value.push(newEntry);
  }
}

async function removeDocument(docId) {
  try {
    await axios.delete(`${import.meta.env.VITE_API_URL}/files/${docId}`, {
      headers: {
        Authorization: `Bearer ${await window.Clerk.session.getToken()}`,
      },
    });
    const selectedIndex = selectedDocuments.value.indexOf(docId);
    if (selectedIndex !== -1) {
      selectedDocuments.value.splice(selectedIndex, 1);
    }
    uploadedDocuments.value = uploadedDocuments.value.filter(
      (doc) => doc.file_id !== docId
    );
  } catch (error) {
    console.error('[ChatView] Error removing document:', error);
    uploadStatus.value = {
      type: 'error',
      message: error.response?.data?.error || 'Failed to remove document',
    };
  }
}

function formatMessageData(msgItem) {
  try {

    switch (msgItem.event) {
      case 'agent_completion':
        // Check if this is a user message in new format
        if (msgItem.additional_kwargs?.agent_type === 'human' || msgItem.type === 'HumanMessage') {
          const formatted = {
            content: msgItem.content || '',
            data: msgItem.content || '',
            message: msgItem.content || '',
            agent_type: 'human',
            metadata: msgItem.response_metadata || null,
            additional_kwargs: msgItem.additional_kwargs || {},
            timestamp: msgItem.timestamp || new Date().toISOString(),
            type: msgItem.type || 'HumanMessage',
            id: msgItem.id
          };
          return JSON.stringify(formatted);
        }
        
        // agent_completion events from LangGraph have structured data
        if (msgItem.data && typeof msgItem.data === 'object') {
          const agentType = msgItem.data.agent_type || msgItem.data.additional_kwargs?.agent_type || 'assistant';
          
          // Special handling for financial_analysis_end - preserve structured data
          if (agentType === 'financial_analysis_end') {
            const formatted = {
              content: msgItem.data.content, // Keep the full structured content for FinancialAnalysisEndComponent
              data: msgItem.data.content,
              message: msgItem.data.content,
              agent_type: agentType,
              metadata: msgItem.data.response_metadata || null,
              additional_kwargs: msgItem.data.additional_kwargs || {},
              timestamp: msgItem.timestamp || new Date().toISOString(),
              type: msgItem.data.type || 'AIMessage',
              id: msgItem.data.id
            };
            return JSON.stringify(formatted);
          }
          
          // Default handling for other agent types
          const formatted = {
            content: msgItem.data.content || '',
            data: msgItem.data.content || '',
            message: msgItem.data.content || '',
            agent_type: agentType,
            metadata: msgItem.data.response_metadata || null,
            additional_kwargs: msgItem.data.additional_kwargs || {},
            timestamp: msgItem.timestamp || new Date().toISOString(),
            type: msgItem.data.type || 'AIMessage',
            id: msgItem.data.id
          };
          return JSON.stringify(formatted);
        }
        // Fallback for unexpected format
        return JSON.stringify({
          message: msgItem.data || msgItem.content || '',
          agent_type: 'assistant',
          timestamp: msgItem.timestamp || new Date().toISOString()
        });
      
      case 'completion':
        try {
          const parsed = typeof msgItem.data === 'string' ? JSON.parse(msgItem.data) : msgItem.data;
          return JSON.stringify({
            message: parsed.message || parsed,
            agent_type: parsed.agent_type || 'assistant',
            metadata: parsed.metadata || null,
            timestamp: msgItem.timestamp || new Date().toISOString()
          });
                  } catch (error) {
            console.error('Error parsing completion data:', error);
          return JSON.stringify({
            message: msgItem.data,
            agent_type: 'assistant',
            timestamp: msgItem.timestamp || new Date().toISOString()
          });
        }
      
      case 'llm_stream_chunk':
      case 'stream_complete':
        return JSON.stringify({
          message: msgItem.data?.content || msgItem.data,
          agent_type: 'assistant',
          timestamp: msgItem.timestamp || new Date().toISOString(),
          is_streaming: true
        });
      

      
      default:
        return JSON.stringify({
          message: msgItem.data,
          agent_type: 'assistant',
          timestamp: msgItem.timestamp || new Date().toISOString()
        });
    }
  } catch (error) {
    console.error('Error formatting message data:', error, msgItem);
    return JSON.stringify({ error: 'Failed to format message data', original: msgItem });
  }
}



// Check if we have an active streaming group for the current message
const hasActiveStreamingGroup = computed(() => {
  if (!messagesData.value || messagesData.value.length === 0 || !currentMsgId.value) {
    return false;
  }
  
  // Check if any message in the current conversation turn has streaming events
  return messagesData.value.some(msg => 
    msg.message_id === currentMsgId.value && 
    (msg.event === 'agent_completion' || msg.event === 'llm_stream_chunk')
  );
});



const filteredMessages = computed(() => {
  if (!messagesData.value || messagesData.value.length === 0) {
    return [];
  }

  try {
    const grouped = new Map();
    const streamingEvents = ['agent_completion', 'llm_stream_chunk', 'stream_complete'];
    
    // First pass: identify distinct conversation turns and streaming groups
    const messageIdCounts = {};
    const userMessages = new Set(); // Track user messages
    const aiMessages = new Set(); // Track AI messages
    
    messagesData.value.forEach(msg => {
      if (!msg) return;
      
      // Identify user messages (these should always be separate)
      if (msg.type === 'HumanMessage' || msg.agent_type === 'human' || msg.additional_kwargs?.agent_type === 'human') {
        userMessages.add(msg.message_id);
      }
      
      // Identify AI messages (these should be separate unless they're truly streaming)
      if (msg.type === 'AIMessage' || isFinalAgentType(msg.agent_type)) {
        aiMessages.add(msg.message_id);
      }
      
      if (streamingEvents.includes(msg.event) && msg.message_id) {
        // Count ALL streaming events for grouping - we want everything in one bubble
        messageIdCounts[msg.message_id] = (messageIdCounts[msg.message_id] || 0) + 1;
      }
    });
    
    // Second pass: group or separate messages
    messagesData.value.forEach((msg, index) => {
      if (!msg || msg === null || msg === undefined) {
        console.warn('Skipping null/undefined message at index:', index);
        return; // Skip null/undefined messages
      }
      
      const msgId = msg.message_id;

      // Decide whether this message should always render its own bubble
      const agentType = msg.agent_type || msg.additional_kwargs?.agent_type || msg.data?.additional_kwargs?.agent_type || msg.data?.agent_type
      

      
      // Always separate genuine user inputs
      if (agentType === 'human' || msg.type === 'HumanMessage') {
        const uniqueKey = `${msg.type || msg.agent_type}_${msgId}_${index}`;
        grouped.set(uniqueKey, msg);
        return;
      }

      if (streamingEvents.includes(msg.event) &&
          msgId &&
          !(agentType === 'human' || msg.type === 'HumanMessage')) {

        const groupKey = `streaming_${msgId}`;

        if (!grouped.has(groupKey)) {
          grouped.set(groupKey, {
            type: 'streaming_group',
            message_id: msgId,
            events: [],
            timestamp: msg.timestamp || new Date().toISOString()
          });
        }

        const group = grouped.get(groupKey);
        if (group && group.events) {
          group.events.push(msg);



          // Sort inside the group chronologically
          group.events.sort((a, b) => {
            const aTime = new Date(a.timestamp || 0).getTime();
            const bTime = new Date(b.timestamp || 0).getTime();
            return aTime - bTime;
          });
        }
        return;
      }

      // Fallback: render as individual bubble - but only if it has content
      if (msg.data?.content || msg.content) {
        const uniqueKey = `${msg.type || msg.event}_${msgId}_${index}`;

        grouped.set(uniqueKey, msg);
      }
      
    });
    
    // Convert to array and sort by timestamp
    const result = Array.from(grouped.values()).sort((a, b) => {
      const aTime = new Date(a.timestamp || 0).getTime();
      const bTime = new Date(b.timestamp || 0).getTime();
      return aTime - bTime;
    });

    return result;
  } catch (error) {
    console.error('Error in filteredMessages computed:', error);
    console.error('messagesData.value:', messagesData.value);
    // Fallback: return safe messages array filtering out null/undefined values
    const safeMessages = (messagesData.value || []).filter(msg => msg !== null && msg !== undefined);
    console.log('Returning safe messages:', safeMessages);
    return safeMessages;
  }
});

// Single Daytona sidebar state management (moved from ChatBubble)
const showDaytonaSidebar = ref(false)
const currentDaytonaEvents = ref([])
const daytonaSidebarClosed = ref(false) // Track if user manually closed it

// Artifact canvas state
const showArtifactCanvas = ref(false)
const selectedArtifact = ref(null)

// Functions for managing the single DaytonaSidebar
function closeDaytonaSidebar() {
  showDaytonaSidebar.value = false
  daytonaSidebarClosed.value = true // Mark as manually closed
}

function handleOpenDaytonaSidebar(specificEvents = null) {
  console.log('Opening Daytona sidebar...')
  showDaytonaSidebar.value = true
  daytonaSidebarClosed.value = false
  
  // Use specific events if provided, otherwise collect all events
  if (specificEvents && specificEvents.length > 0) {
    console.log('Using specific events for this message:', specificEvents.length)
    currentDaytonaEvents.value = specificEvents
  } else {
    console.log('No specific events provided, collecting all events')
    updateCurrentDaytonaEvents()
  }
  console.log('Current Daytona events:', currentDaytonaEvents.value.length)
}

function handleOpenArtifactCanvas(artifact) {
  openArtifact(artifact)
}

function openArtifact(artifact) {
  selectedArtifact.value = artifact
  showArtifactCanvas.value = true
}

function closeArtifactCanvas() {
  showArtifactCanvas.value = false
  selectedArtifact.value = null
}

// Watch for Daytona activity across all messages and manage single sidebar
const isDaytonaActiveGlobal = computed(() => {
  return filteredMessages.value.some(msg => {
    if (msg.type === 'streaming_group' && msg.events) {
      return msg.events.some(event => {
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
    }
    return false
  })
})

// Watch for Daytona activity and automatically open sidebar
watch(isDaytonaActiveGlobal, (isActive) => {
  if (isActive && !daytonaSidebarClosed.value) {
    showDaytonaSidebar.value = true
    updateCurrentDaytonaEvents()
    // Close artifact canvas if it's open since we're using sidebar now
    showArtifactCanvas.value = false
  }
})

// Also watch filteredMessages to update Daytona events when new messages arrive
watch(filteredMessages, () => {
  if (showDaytonaSidebar.value) {
    updateCurrentDaytonaEvents()
  }
}, { deep: true })

// Function to collect all Daytona-related events from all messages
function updateCurrentDaytonaEvents() {
  const allDaytonaEvents = []
  filteredMessages.value.forEach(msg => {
    if (msg.type === 'streaming_group' && msg.events) {
      const daytonaEvents = msg.events.filter(event => {
        return (event.event === 'llm_stream_chunk' && event.data?.content?.includes('DaytonaCodeSandbox')) ||
               (event.event === 'agent_completion' && event.data?.name === 'DaytonaCodeSandbox') ||
               event.isDaytonaRelated
      })
      allDaytonaEvents.push(...daytonaEvents)
    }
  })
  currentDaytonaEvents.value = allDaytonaEvents
}

// Function to check if a message is a final message that should show current token usage
function isFinalMessage(msgItem) {
  // Check for final response events in streaming groups
  if (msgItem.type === 'streaming_group' && msgItem.events) {
    return msgItem.events.some(event => {
      const agentType = event.data?.additional_kwargs?.agent_type || event.data?.agent_type || event.additional_kwargs?.agent_type
      return isFinalAgentType(agentType) || event.isFinalResponse
    })
  }
  
  // Check for direct final response messages
  const agentType = msgItem.data?.additional_kwargs?.agent_type || 
                   msgItem.data?.agent_type || 
                   msgItem.additional_kwargs?.agent_type ||
                   msgItem.agent_type
  
  return isFinalAgentType(agentType) || msgItem.isFinalResponse
}

// Function to extract token usage for a specific message
function getMessageTokenUsage(msgItem) {
  // For streaming groups, look for the final agent_completion event
  if (msgItem.type === 'streaming_group' && msgItem.events) {
    // Find the last agent_completion event with token usage in response_metadata.usage
    for (let i = msgItem.events.length - 1; i >= 0; i--) {
      const event = msgItem.events[i]
      
      // Check if token usage is stored in response_metadata.usage (same as performance metrics)
      if (event.response_metadata?.usage && event.response_metadata.usage.total_tokens > 0) {
        return {
          input_tokens: event.response_metadata.usage.input_tokens || 0,
          output_tokens: event.response_metadata.usage.output_tokens || 0,
          total_tokens: event.response_metadata.usage.total_tokens || 0
        }
      }
      
      // Fallback: check other possible locations
      if (event.data?.response_metadata?.usage && event.data.response_metadata.usage.total_tokens > 0) {
        return {
          input_tokens: event.data.response_metadata.usage.input_tokens || 0,
          output_tokens: event.data.response_metadata.usage.output_tokens || 0,
          total_tokens: event.data.response_metadata.usage.total_tokens || 0
        }
      }
    }
  }
  
  // For direct messages, check response_metadata.usage first (same as performance metrics)
  if (msgItem.response_metadata?.usage && msgItem.response_metadata.usage.total_tokens > 0) {
    return {
      input_tokens: msgItem.response_metadata.usage.input_tokens || 0,
      output_tokens: msgItem.response_metadata.usage.output_tokens || 0,
      total_tokens: msgItem.response_metadata.usage.total_tokens || 0
    }
  }
  
  // Return empty if no token data found
  return { input_tokens: 0, output_tokens: 0, total_tokens: 0 }
}



// Function to extract response metadata for a specific message
function getMessageResponseMetadata(msgItem) {
  // For streaming groups, look for the final agent_completion event
  if (msgItem.type === 'streaming_group' && msgItem.events) {
    // Find the last agent_completion event with response_metadata
    for (let i = msgItem.events.length - 1; i >= 0; i--) {
      const event = msgItem.events[i]
      
      let responseMetadata = null
      
      // Check if the event itself has response metadata (new direct attachment)
      if (event.response_metadata) {
        responseMetadata = event.response_metadata
      } else if (event.data?.response_metadata) {
        responseMetadata = event.data.response_metadata
      }
      
      if (responseMetadata) {
        return responseMetadata
      }
    }
  }
  
  // For direct messages, check the message itself (including new direct attachment)
  if (msgItem.response_metadata) {
    return msgItem.response_metadata
  } else if (msgItem.data?.response_metadata) {
    return msgItem.data.response_metadata
  }
  
  // Return null if no response metadata found
  return null
}

// Function to track metrics for a run_id
function trackRunMetrics(runId, tokenUsage, responseMetadata) {
  if (!runId) return;
  
  if (!runMetrics.value.has(runId)) {
    runMetrics.value.set(runId, {
      input_tokens: [],
      output_tokens: [],
      total_tokens: [],
      latencies: [],
      ttfts: [],
      throughputs: [],
      event_count: 0
    });
  }
  
  const runData = runMetrics.value.get(runId);
  
  // Track token usage
  if (tokenUsage) {
    if (tokenUsage.input_tokens > 0) runData.input_tokens.push(tokenUsage.input_tokens);
    if (tokenUsage.output_tokens > 0) runData.output_tokens.push(tokenUsage.output_tokens);
    if (tokenUsage.total_tokens > 0) runData.total_tokens.push(tokenUsage.total_tokens);
  }
  
  // Track performance metrics
  if (responseMetadata?.usage) {
    if (responseMetadata.usage.total_latency > 0) {
      runData.latencies.push(responseMetadata.usage.total_latency);
    }
    if (responseMetadata.usage.time_to_first_token > 0) {
      runData.ttfts.push(responseMetadata.usage.time_to_first_token);
    }
    if (responseMetadata.usage.completion_tokens_per_sec > 0) {
      runData.throughputs.push(responseMetadata.usage.completion_tokens_per_sec);
    }
  }
  
  // Only increment event count if event has both response_metadata and model_name, since we are counting llm calls
  if (responseMetadata && responseMetadata.model_name) {
    runData.event_count++;
  }
}

// Function to get run summary for display
function getRunSummary(msgItem) {
  // For final messages, we want to show the summary for the entire conversation turn
  // Find the run ID by looking backwards in messagesData to find the user message that started this turn
  let runId = null;
  
  if (msgItem.type === 'streaming_group') {
    runId = msgItem.message_id;
  } else {
    // For individual messages, find the conversation turn they belong to
    const currentMessageIndex = messagesData.value.findIndex(msg => 
      msg.message_id === msgItem.message_id || 
      (msg.type === 'streaming_group' && msg.message_id === msgItem.message_id)
    );
    
    // Look backwards to find the user message that started this conversation turn
    for (let i = currentMessageIndex; i >= 0; i--) {
      const msg = messagesData.value[i];
      const isUserMessage = msg.additional_kwargs?.agent_type === 'human' || 
                           msg.type === 'HumanMessage' ||
                           (msg.type === 'streaming_group' && msg.events?.some(e => 
                             e.additional_kwargs?.agent_type === 'human' || e.type === 'HumanMessage'
                           ));
      
      if (isUserMessage) {
        runId = msg.message_id;
        break;
      }
    }
    
    // Fallback to the message's own ID
    if (!runId) {
      runId = msgItem.message_id;
    }
  }
  

  
  if (!runId || !runMetrics.value.has(runId)) {
    return { input_tokens: 0, output_tokens: 0, total_tokens: 0, event_count: 0 };
  }
  
  const runData = runMetrics.value.get(runId);
  
  // Calculate sums and averages
  const summary = {
    input_tokens: runData.input_tokens.reduce((sum, val) => sum + val, 0),
    output_tokens: runData.output_tokens.reduce((sum, val) => sum + val, 0),
    total_tokens: runData.total_tokens.reduce((sum, val) => sum + val, 0),
    total_latency: runData.latencies.reduce((sum, val) => sum + val, 0),
    total_ttft: runData.ttfts.reduce((sum, val) => sum + val, 0),
    avg_latency: runData.latencies.length > 0 ? runData.latencies.reduce((sum, val) => sum + val, 0) / runData.latencies.length : 0,
    avg_throughput: runData.throughputs.length > 0 ? runData.throughputs.reduce((sum, val) => sum + val, 0) / runData.throughputs.length : 0,
    event_count: runData.event_count
  };
  

  return summary;
}


</script>

<style scoped>
/* New message enter/leave transitions */
.chat-enter-from,
.chat-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
.chat-enter-active,
.chat-leave-active {
  transition: all 0.3s ease;
}

/* Extra small text size */
.text-2xs {
  font-size: 0.625rem; /* 10px */
  line-height: 0.75rem; /* 12px */
}
</style>
