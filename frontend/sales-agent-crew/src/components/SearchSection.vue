<template>
  <div class="right-4 z-1 bg-white pt-2 pb-3 sm:pt-4 sm:pb-6">
    <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-0">
      <div class="flex justify-between items-center mb-3">
        <button
          type="button"
          class="inline-flex hidden justify-center items-center gap-x-2 rounded-lg font-medium text-gray-800 hover:text-blue-600 focus:outline-none focus:text-blue-600 text-xs sm:text-sm"
        >
          <input
            type="file"
            ref="fileInput"
            @change="handleFileUpload"
            class="hidden"
            accept=".pdf,.doc,.docx,.csv,.xlsx,.xls"
          />
          <svg
            class="shrink-0 size-4"
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M5 12h14" />
            <path d="M12 5v14" />
          </svg>
          New chat
        </button>

        <!-- Custom components must be registered in your Vue component -->
        <!-- <StatusText />
      <AudioRecorder /> -->

        <button
          type="button"
          class="py-1.5 hidden px-2 inline-flex items-center gap-x-2 text-xs font-medium rounded-lg border border-gray-200 bg-white text-gray-800 shadow-sm hover:bg-gray-50 focus:outline-none focus:bg-gray-50 disabled:opacity-50 disabled:pointer-events-none"
        >
          <svg
            class="size-3"
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            fill="currentColor"
            viewBox="0 0 16 16"
          >
            <path
              d="M5 3.5h6A1.5 1.5 0 0 1 12.5 5v6a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 11V5A1.5 1.5 0 0 1 5 3.5z"
            />
          </svg>
          Stop generating
        </button>
      </div>

      <!-- Input -->
      <div class="relative">
        <textarea
          v-model="searchQuery"
          type="search"
          placeholder="Ask me about...companies to target, research topics, or company stocks and financials"
          :disabled="isLoading"
          class="p-2 pb-12 block w-full bg-gray-100 border-gray-200 rounded-lg text-sm focus:outline-none active:outline-none border focus:border-orange-500"
        ></textarea>
        <!-- Toolbar -->
        <div class="absolute bottom-px inset-x-px p-2 rounded-b-lg bg-gray-100">
          <div class="flex justify-between items-center">
            <!-- Button Group -->
            <div class="flex items-center">
              <!-- Mic Button -->
              <button
                class="inline-flex hidden shrink-0 justify-center items-center size-8 rounded-lg text-gray-500 hover:bg-gray-100 focus:z-1 focus:outline-none focus:bg-gray-100"
              >
                <svg
                  class="shrink-0 size-4"
                  xmlns="http://www.w3.org/2000/svg"
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <rect width="18" height="18" x="3" y="3" rx="2" />
                  <line x1="9" x2="15" y1="15" y2="9" />
                </svg>
              </button>

              <!-- End Mic Button -->
              <!-- Attach Button -->
              <button
                @click="$refs.fileInput.click()"
                :disabled="isLoading"
                type="button"
                class="inline-flex shrink-0 justify-center items-center size-8 rounded-lg text-gray-500 hover:bg-gray-100 focus:z-1 focus:outline-none focus:bg-gray-100"
              >
                <svg
                  class="shrink-0 size-4"
                  xmlns="http://www.w3.org/2000/svg"
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path
                    d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"
                  />
                </svg>
              </button>
              <!-- End Attach Button -->
            </div>
            <!-- End Button Group -->
            <!-- Button Group -->
            <div class="flex items-center gap-x-1">
              <!-- Mic Button -->
              <Popover
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
                    'text-orange-500 ': isRecording,
                  }"
                  class="inline-flex shrink-0 justify-center items-center size-8 rounded-lg text-gray-500 hover:bg-gray-100 focus:z-1 focus:outline-none focus:bg-gray-100"
                >
                  <svg
                    v-if="!isRecording"
                    className="w-6 h-6 text-gray-800 dark:text-white"
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
                    className="w-6 h-6 text-gray-800 dark:text-white"
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
              </Popover>
              <!-- End Mic Button -->
              <!-- Send Button -->
              <button
                type="button"
                @click="performSearch"
                :disabled="isLoading || !searchQuery.trim()"
                class="inline-flex shrink-0 justify-center items-center size-8 rounded-lg text-white bg-orange-600 hover:bg-orange-500 focus:z-1 disabled:opacity-50 focus:outline-none focus:bg-orange-500"
              >
                <svg
                  class="shrink-0 size-3.5"
                  xmlns="http://www.w3.org/2000/svg"
                  width="16"
                  height="16"
                  fill="currentColor"
                  viewBox="0 0 16 16"
                >
                  <path
                    d="M15.964.686a.5.5 0 0 0-.65-.65L.767 5.855H.766l-.452.18a.5.5 0 0 0-.082.887l.41.26.001.002 4.995 3.178 3.178 4.995.002.002.26.41a.5.5 0 0 0 .886-.083l6-15Zm-1.833 1.89L6.637 10.07l-.215-.338a.5.5 0 0 0-.154-.154l-.338-.215 7.494-7.494 1.178-.471-.47 1.178Z"
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
    <!-- Warning Message for missing keys -->
    <div
      v-if="missingKeys.length > 0"
      class="mb-4 p-4 rounded-lg bg-yellow-50 border border-yellow-200"
    >
      <div class="flex">
        <svg
          class="h-6 w-6 text-yellow-600 flex-shrink-0 mr-3"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            fill-rule="evenodd"
            d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
            clip-rule="evenodd"
          />
        </svg>
        <div>
          <p class="text-yellow-700">
            Please set up your {{ missingKeys.join(', ') }} API key{{
              missingKeys.length > 1 ? 's' : ''
            }}
            in the
            <button
              @click="$emit('openSettings')"
              class="text-yellow-800 underline hover:text-yellow-900 font-medium"
            >
              settings
            </button>
          </p>
        </div>
      </div>
    </div>

    <!-- Search Input Area -->
    <div class="flex hidden items-center space-x-4">
      <div class="relative flex-1">
        <input
          v-model="searchQuery"
          type="search"
          placeholder="Ask me about...companies to target, research topics, or company stocks and financials"
          class="w-full p-3 pr-12 rounded-lg border border-gray-300 focus:border-orange-500 focus:outline-none"
          :disabled="isLoading"
        />

        <!-- Voice Input Button -->
        <button
          @click="toggleRecording"
          :disabled="isLoading"
          :class="{
            'text-orange-500': !isRecording,
            'text-red-500 animate-pulse': isRecording,
          }"
          class="absolute right-2 top-1/2 transform -translate-y-1/2 p-2 hover:bg-gray-100 rounded-full transition-colors"
          title="Voice Search"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-6 w-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
            />
          </svg>
        </button>
      </div>

      <!-- Upload Button -->
      <div class="relative">
        <input
          type="file"
          ref="fileInput"
          @change="handleFileUpload"
          class="hidden"
          accept=".pdf,.doc,.docx,.csv,.xlsx,.xls"
        />
        <Popover
          text="Upload Documents"
          position="top"
          color="bg-black text-white"
        >
          <button
            @click="$refs.fileInput.click()"
            :disabled="isLoading"
            class="px-4 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50 flex items-center"
            title="Upload Document"
          >
            <DocumentArrowUpIcon class="w-5 h-5" />
          </button>
        </Popover>
      </div>

      <button
        @click="performSearch"
        :disabled="isLoading || !searchQuery.trim()"
        class="px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
      >
        <span v-if="!isLoading">Search</span>
        <span v-else>Searching...</span>
      </button>
    </div>

    <!-- Upload Status -->
    <div
      v-if="uploadStatus"
      class="mt-2 text-sm"
      :class="{
        'text-red-600': uploadStatus.type === 'error',
        'text-green-600': uploadStatus.type !== 'error',
      }"
    >
      {{ uploadStatus.message }}
    </div>

    <!-- Recording Status -->
    <div
      v-if="isRecording"
      class="mt-2 text-sm text-gray-600 flex items-center space-x-2"
    >
      <span
        class="inline-block w-2 h-2 bg-red-500 rounded-full animate-pulse"
      ></span>
      <span>Recording... Click microphone to stop</span>
    </div>

    <!-- Uploaded Documents Section -->
    <div v-if="uploadedDocuments.length > 0" class="mt-4">
      <h3 class="text-sm font-medium text-gray-700 mb-2">Uploaded Documents</h3>
      <div class="space-y-2">
        <div
          v-for="doc in uploadedDocuments"
          :key="doc.id"
          class="flex items-center justify-between p-2 bg-gray-50 rounded-lg border border-gray-200 hover:bg-gray-100"
        >
          <div class="flex items-center space-x-3">
            <input
              type="checkbox"
              :checked="selectedDocuments.includes(doc.id)"
              @change="toggleDocumentSelection(doc.id)"
              class="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
            />
            <div>
              <p class="text-sm font-medium text-gray-900">
                {{ doc.filename }}
              </p>
              <p class="text-xs text-gray-500">
                Uploaded
                {{ new Date(doc.upload_timestamp * 1000).toLocaleString() }} •
                {{ doc.num_chunks }} chunks
              </p>
            </div>
          </div>
          <button
            @click="removeDocument(doc.id)"
            class="p-1 text-gray-400 hover:text-red-500 rounded-full hover:bg-gray-200 transition-colors"
            title="Remove document"
          >
            <XMarkIcon class="w-5 h-5" />
          </button>
        </div>
      </div>
      <p class="mt-2 text-xs text-gray-500">
        Select documents to include in your search
      </p>
    </div>

    <!-- Error Modal -->
    <ErrorModal
      :show="showErrorModal"
      :errorMessage="errorMessage"
      @close="showErrorModal = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue';
import { useAuth } from '@clerk/vue';
import { decryptKey } from '../utils/encryption';
import ErrorModal from './ErrorModal.vue';
import axios from 'axios';
import { uploadDocument } from '../services/api';
import Popover from '@/components/Common/UIComponents/CustomTooltip.vue';
import { DocumentArrowUpIcon, XMarkIcon } from '@heroicons/vue/24/outline';

const props = defineProps({
  keysUpdated: {
    type: Number,
    default: 0,
  },
  isLoading: {
    type: Boolean,
    default: false,
  },
  // The runId from MainLayout
  runId: {
    type: String,
    default: '',
  },
  sessionId: {
    type: String,
    default: '',
  },
});

const emit = defineEmits([
  'searchStart',
  'searchComplete',
  'searchError',
  'openSettings',
]);

// Reactive state
const searchQuery = ref('');
const isRecording = ref(false);
const mediaRecorder = ref(null);
const audioChunks = ref([]);
const sambanovaKey = ref(null);
const exaKey = ref(null);
const serperKey = ref(null);
const errorMessage = ref('');
const showErrorModal = ref(false);
const fileInput = ref(null);
const uploadStatus = ref(null);

// Add new reactive state for documents
const uploadedDocuments = ref([]);
const selectedDocuments = ref([]);

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
  } catch (error) {
    console.error('Error loading keys:', error);
    errorMessage.value = 'Error loading API keys';
    showErrorModal.value = true;
  }
}

onMounted(async () => {
  await loadKeys();
  await loadUserDocuments();
});

watch(
  () => props.keysUpdated,
  async () => {
    await loadKeys();
  },
  { immediate: true }
);

const missingKeys = computed(() => {
  const missing = [];
  if (!sambanovaKey.value) missing.push('SambaNova');
  if (!exaKey.value) missing.push('Exa');
  if (!serperKey.value) missing.push('Serper');
  return missing;
});

async function performSearch() {
  try {
    // 1) Indicate we are about to do "routing_query"
    emit('searchStart', 'routing_query');

    // 2) Determine route
    const routeResp = await axios.post(
      `${import.meta.env.VITE_API_URL}/route`,
      { query: searchQuery.value },
      {
        headers: {
          'Content-Type': 'application/json',
          'x-sambanova-key': sambanovaKey.value || '',
          'x-user-id': userId.value || '',
          'x-run-id': props.runId || '',
        },
      }
    );

    const detectedType = routeResp.data.type;

    // 3) Tell parent "searchStart" with final type
    emit('searchStart', detectedType || 'unknown');

    // 4) Execute the final query with selected documents
    const parameters = {
      ...routeResp.data.parameters,
      document_ids: selectedDocuments.value,
    };

    const executeResp = await axios.post(
      `${import.meta.env.VITE_API_URL}/execute/${detectedType}`,
      parameters,
      {
        headers: {
          'Content-Type': 'application/json',
          'x-sambanova-key': sambanovaKey.value || '',
          'x-serper-key': serperKey.value || '',
          'x-exa-key': exaKey.value || '',
          'x-user-id': userId.value || '',
          'x-run-id': props.runId || '',
          'x-session-id': props.sessionId || '',
        },
      }
    );

    // 5) searchComplete
    emit('searchComplete', {
      type: detectedType,
      query: searchQuery.value,
      results: executeResp.data,
    });

    // 6) Clear search query
    searchQuery.value = '';
  } catch (error) {
    console.error('[SearchSection] performSearch error:', error);
    emit('searchError', error);
  }
}

/**
 * Voice recording / transcription (unchanged)
 */
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
      model: 'Qwen2-Audio-7B-Instruct',
      messages: [
        {
          role: 'system',
          content: 'You are an Automatic Speech Recognition tool.',
        },
        {
          role: 'user',
          content: [
            {
              type: 'audio_content',
              audio_content: {
                content: `data:audio/webm;base64,${audioBase64}`,
              },
            },
          ],
        },
        {
          role: 'user',
          content:
            'Please transcribe the previous audio and only return the transcription.',
        },
      ],
      response_format: 'streaming',
      stream: true,
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

    // streaming response
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
      performSearch();
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
  // Remove surrounding quotes if present
  if (
    (cleanedText.startsWith("'") && cleanedText.endsWith("'")) ||
    (cleanedText.startsWith('"') && cleanedText.endsWith('"'))
  ) {
    cleanedText = cleanedText.slice(1, -1).trim();
  }
  return cleanedText;
}

async function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;
  try {
    uploadStatus.value = { type: 'info', message: 'Uploading document...' };
    const formData = new FormData();
    formData.append('file', file);
    const response = await axios.post(
      `${import.meta.env.VITE_API_URL}/upload`,
      formData,
      {
        headers: {
          'x-user-id': userId.value || '',
        },
      }
    );
    // Store the uploaded document
    const document = response.data.document;
    uploadedDocuments.value.push(document);
    selectedDocuments.value.push(document.id);
    uploadStatus.value = {
      type: 'success',
      message: 'Document uploaded successfully!',
    };

    // Clear the file input
    if (fileInput.value) {
      fileInput.value.value = '';
    }
  } catch (error) {
    console.error('[SearchSection] Upload error:', error);
    uploadStatus.value = {
      type: 'error',
      message: error.response?.data?.error || 'Failed to upload document',
    };
  }
}
// Load user's documents on mount
async function loadUserDocuments() {
  try {
    const response = await axios.get(
      `${import.meta.env.VITE_API_URL}/documents`,
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
async function removeDocument(docId) {
  try {
    // Remove from backend
    await axios.delete(
      `${import.meta.env.VITE_API_URL}/documents/${userId.value}/${docId}`
    );
    // Remove from selected documents if it was selected
    const selectedIndex = selectedDocuments.value.indexOf(docId);
    if (selectedIndex !== -1) {
      selectedDocuments.value.splice(selectedIndex, 1);
    }
    // Remove from uploaded documents list
    uploadedDocuments.value = uploadedDocuments.value.filter(
      (doc) => doc.id !== docId
    );
    // Show success message
    uploadStatus.value = {
      type: 'success',
      message: 'Document removed successfully!',
    };
    setTimeout(() => {
      uploadStatus.value = null;
    }, 3000);
  } catch (error) {
    console.error('[SearchSection] Error removing document:', error);
    uploadStatus.value = {
      type: 'error',
      message: error.response?.data?.error || 'Failed to remove document',
    };
  }
}
</script>

<style scoped>
/* Basic styling for demonstration. */
</style>
