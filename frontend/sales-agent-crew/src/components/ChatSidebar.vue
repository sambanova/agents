<template>
  <div
    class="relative h-full border border-primary-brandFrame bg-white rounded-l flex flex-col transition-all duration-300"
    :class="isCollapsed ? 'w-0' : 'w-64'"
  >
    <!-- Collapse Button -->
    <button
      v-if="localIsMobile || props.isMobile || isCollapsed"
      @click="toggleCollapse"
      class="absolute top-1/2 -right-4 z-10 p-1 bg-white border border-primary-brandFrame rounded-full"
    >
      <svg
        class="w-5 h-5 text-gray-500"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          v-if="!isCollapsed"
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M15 19l-7-7 7-7"
        ></path>
        <path
          v-else
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M9 5l7 7-7 7"
        ></path>
      </svg>
    </button>

    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Header -->
      <div class="px-4 py-2 flex items-center justify-between">
        <button
          class="p-2 w-full border border-primary-brandBorder text-primary-brandColor text-sm rounded"
          @click="createNewChat"
          :disabled="missingKeysArray.length > 0"
        >
          + New Chat
        </button>
      </div>

      <!-- If missing any key, show a small alert -->
      <div
        v-if="missingKeysArray.length > 0"
        class="bg-yellow-50 text-yellow-700 text-sm p-2"
      >
        <span class="capitalize" v-for="(keyItem, index) in missingKeysArray">
          {{ index > 0 ? ',' : '' }}{{ keyItem ? keyItem : '' }}
        </span>
        key(s) are missing. Please set them in settings.
      </div>

      <!-- Conversation list -->
      <div class="flex-1 overflow-x-hidden">
        <ChatList
          :conversations="conversations"
          :preselectedChat="preselectedChat"
          :isMultiSelectMode="isMultiSelectMode"
          :selectedChats="selectedChats"
          @select-conversation="onSelectConversation"
          @delete-chat="onDeleteChat"
          @share-chat="onShareChat"
          @download-chat="onDownloadChat"
          @toggle-chat-selection="onToggleChatSelection"
        />
      </div>

      <!-- Bottom controls -->
      <div class="px-4 py-2 border-t border-gray-200">
        <!-- Multi-select controls -->
        <div v-if="isMultiSelectMode" class="space-y-2">
          <div class="flex items-center justify-between">
            <button
              @click="selectAllChats"
              class="text-xs text-primary-brandColor hover:text-primary-brandTextPrimary underline"
            >
              {{ allChatsSelected ? 'Deselect All' : 'Select All' }}
            </button>
            <span class="text-xs text-primary-brandTextSecondary">
              {{ selectedChats.length }} selected
            </span>
          </div>
          <div class="flex space-x-2">
            <button
              @click="exitMultiSelectMode"
              class="px-3 py-2 text-xs bg-white text-primary-brandColor border border-primary-brandBorder rounded hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              @click="bulkDeleteChats"
              :disabled="selectedChats.length === 0"
              class="flex-1 px-3 py-2 text-xs bg-primary-brandColor text-white rounded hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Delete Selected
            </button>
          </div>
        </div>

        <!-- Delete Chats button -->
        <div v-else>
          <button
            @click="enterMultiSelectMode"
            class="w-full px-3 py-2 text-xs bg-purple-50 text-purple-700 rounded hover:bg-purple-100 flex items-center justify-center space-x-2"
          >
            <svg
              class="w-4 h-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path d="M3 6h18" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
              <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
            <span>Delete Chats</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation Dialog -->
    <div v-if="showDeleteConfirmation" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div class="bg-white rounded-lg p-6 max-w-sm mx-4">
        <div class="text-center">
          <h3 class="text-lg font-semibold text-primary-brandTextPrimary mb-4">
            Confirm Data Deletion
          </h3>
          <p class="text-sm text-primary-brandTextSecondary mb-6">
            Are you sure you want to delete {{ selectedChats.length }} chat(s)? This will permanently delete the selected conversations. This action cannot be undone.
          </p>
          <div class="flex space-x-3">
            <button
              @click="cancelBulkDelete"
              class="flex-1 px-4 py-2 text-sm bg-white text-primary-brandColor border border-primary-brandBorder rounded hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              @click="confirmBulkDelete"
              class="flex-1 px-4 py-2 text-sm bg-primary-brandColor text-white rounded hover:opacity-90"
            >
              Delete Data
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, computed } from 'vue';

import { useAuth0 } from '@auth0/auth0-vue';
import { decryptKey } from '@/utils/encryption'; // adapt path if needed
import { useRoute, useRouter } from 'vue-router';
import emitterMitt from '@/utils/eventBus.js';
import ChatList from '@/components/ChatMain/ChatList.vue';
import axios from 'axios';
const router = useRouter();
const route = useRoute();
/**
 * We'll store in localStorage under key "my_conversations_<userId>"
 * an array of { conversation_id, title, created_at }
 */
const emit = defineEmits([
  'selectConversation',
  'reload-user-documents',
  'toggle-collapse',
]);
const preselectedChat = ref('');

const props = defineProps({
  isCollapsed: {
    type: Boolean,
    default: false,
  },
  isMobile: {
    type: Boolean,
    default: false,
  },
});

// Local mobile detection to ensure button is always visible when needed
const localIsMobile = ref(false);

// Check mobile state on mount and resize
const checkMobile = () => {
  localIsMobile.value = window.innerWidth < 768;
};

onMounted(() => {
  checkMobile();
  window.addEventListener('resize', checkMobile);
});

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile);
});

function toggleCollapse() {
  emit('toggle-collapse');
}

/** Auth0 user */
const { user, getAccessTokenSilently, isAuthenticated } = useAuth0();
const userId = computed(() => user.value?.sub);

const sambanovaKey = ref(null);
const serperKey = ref(null);
const exaKey = ref(null);
const missingKeysList = ref({});
const conversations = ref([]);
const chatsLoaded = ref(false); // Track if chats have been loaded

// Multi-select state
const isMultiSelectMode = ref(false);
const selectedChats = ref([]);
const showDeleteConfirmation = ref(false);

// Computed properties for multi-select
const allChatsSelected = computed(() => {
  return conversations.value.length > 0 && selectedChats.value.length === conversations.value.length;
});

// Event handler functions for events emitted from ChatList/ChatItem.
function onSelectConversation(conversation) {
  if (isMultiSelectMode.value) {
    // In multi-select mode, toggle selection instead of navigating
    onToggleChatSelection(conversation.conversation_id);
  } else {
    // Normal mode - navigate to chat
    console.log('Parent: Selected conversation');
    preselectedChat.value = conversation.conversation_id;
    router.push(`/${conversation.conversation_id}`);
  }
}

// Multi-select mode functions
function enterMultiSelectMode() {
  isMultiSelectMode.value = true;
  selectedChats.value = [];
}

function exitMultiSelectMode() {
  isMultiSelectMode.value = false;
  selectedChats.value = [];
}

function onToggleChatSelection(conversationId) {
  const index = selectedChats.value.indexOf(conversationId);
  if (index > -1) {
    selectedChats.value.splice(index, 1);
  } else {
    selectedChats.value.push(conversationId);
  }
}

function selectAllChats() {
  if (allChatsSelected.value) {
    selectedChats.value = [];
  } else {
    selectedChats.value = conversations.value.map(chat => chat.conversation_id);
  }
}

async function bulkDeleteChats() {
  if (selectedChats.value.length === 0) return;
  
  showDeleteConfirmation.value = true;
}

async function confirmBulkDelete() {
  try {
    // Delete chats one by one
    for (const conversationId of selectedChats.value) {
      await deleteChat(conversationId);
    }
    
    // Exit multi-select mode after successful deletion
    exitMultiSelectMode();
    showDeleteConfirmation.value = false;
  } catch (error) {
    console.error('Bulk delete failed:', error);
    alert('Some chats could not be deleted. Please try again.');
  }
}

function cancelBulkDelete() {
  showDeleteConfirmation.value = false;
}

/**
 * On mounted => load local conversation list + decrypt keys
 */
onMounted(() => {
  console.log('ChatSidebar mounted, authentication check');
  
  // Check if user is authenticated before loading data
  if (!isAuthenticated.value) {
    console.log('Skipping user data loading - user not authenticated');
    return;
  }

  loadChats();
  loadKeys();

  emitterMitt.on('keys-updated', loadKeys);
  emitterMitt.on('refresh-chat-list', loadChats);

  let cId = route.params.id;
  if (cId) preselectedChat.value = cId;
});

onUnmounted(() => {
  // Clean up event listeners
  emitterMitt.off('keys-updated', loadKeys);
  emitterMitt.off('refresh-chat-list', loadChats);
});

async function deleteChat(conversationId) {
  // Check if user is authenticated
  if (!isAuthenticated.value) {
    console.log('Skipping deleteChat - user not authenticated');
    return;
  }

  const url = `${import.meta.env.VITE_API_URL}/chat/${conversationId}`;
  try {
    const response = await axios.delete(url, {
              headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${await getAccessTokenSilently()}`,
        },
    });

    chatsLoaded.value = false; // Reset flag to force reload
    loadChats();
    
    // Emit event to parent to reload user documents (artifacts)
    console.log('Emitting reload-user-documents event after chat deletion');
    emit('reload-user-documents');
    
    return response.data;
  } catch (error) {
    console.error('Error deleting chat:', error);

    throw error;
  }
}

async function loadKeys(missingKeysListData) {
  // Check if user is authenticated
  if (!isAuthenticated.value) {
    console.log('Skipping loadKeys - user not authenticated');
    return;
  }

  if (missingKeysListData) {
    console.log('missingKeysList', missingKeysListData);

    missingKeysList.value = missingKeysListData;
  }

  try {
    const uid = userId.value || 'anonymous';
    const encryptedSamba = localStorage.getItem(`sambanova_key_${uid}`);
    const encryptedSerp = localStorage.getItem(`serper_key_${uid}`);
    const encryptedExa = localStorage.getItem(`exa_key_${uid}`);

    sambanovaKey.value = encryptedSamba
      ? await decryptKey(encryptedSamba)
      : null;
    serperKey.value = encryptedSerp ? await decryptKey(encryptedSerp) : null;
    exaKey.value = encryptedExa ? await decryptKey(encryptedExa) : null;
  } catch (err) {
    console.error('[ChatSidebar] Error decrypting keys:', err);
  }
}

defineExpose({ loadChats, refreshChats });
const missingKeysArray = computed(() => {
  if (!missingKeysList.value || typeof missingKeysList.value !== 'object')
    return [];
  return Object.keys(missingKeysList.value).filter(
    (key) => missingKeysList.value[key]
  );
});
async function loadChats() {
  // Check if user is authenticated
  if (!isAuthenticated.value) {
    console.log('Skipping loadChats - user not authenticated');
    return;
  }

  try {
    const uid = userId.value || 'anonymous';
    const resp = await axios.get(`${import.meta.env.VITE_API_URL}/chat/list`, {
      headers: {
        Authorization: `Bearer ${await getAccessTokenSilently()}`,
      },
    });
    conversations.value = resp.data?.chats;
    chatsLoaded.value = true; // Mark as loaded
  } catch (err) {
    console.error('Error loading chats:', err);
    // Don't show alert for shared conversations
    if (!route.path.startsWith('/share/')) {
      alert('Failed to load conversations. Check keys or console.');
    }
  }
}

/** Start a new conversation => calls /chat/init with decrypted keys */
async function createNewChat() {
  // Check if user is authenticated
  if (!isAuthenticated.value) {
    console.log('Skipping createNewChat - user not authenticated');
    return;
  }

  console.log('CREATE1');
  emitterMitt.emit('new-chat', { message: 'The new chat button was clicked!' });
}

// Updated delete handler calls deleteChat().
async function onDeleteChat(conversationId) {
  console.log('Parent: Delete conversation');
  try {
    await deleteChat(conversationId);
  } catch (error) {
    console.error('Delete action failed:', error);
  }
}

function onShareChat(conversationId) {
  console.log('Parent: Share conversation');
}

function onDownloadChat(conversationId) {
  console.log('Parent: Download conversation');
}

watch(
  () => route.params.id,
  (newId, oldId) => {
    if (newId) {
      preselectedChat.value = newId;
    } else {
      preselectedChat.value = null;
    }
    
    // Only load chats if user is authenticated and chats haven't been loaded yet
    if (isAuthenticated.value && !chatsLoaded.value) {
      loadChats();
    }
  }
);

async function refreshChats() {
  chatsLoaded.value = false;
  await loadChats();
}
</script>
