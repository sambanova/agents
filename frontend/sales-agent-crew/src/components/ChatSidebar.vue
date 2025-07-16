<template>
  <div
    class="w-64 h-full border border-primary-brandFrame bg-white rounded-l flex flex-col"
  >
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
        @select-conversation="onSelectConversation"
        @delete-chat="onDeleteChat"
        @share-chat="onShareChat"
        @download-chat="onDownloadChat"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, computed } from 'vue';

import { useAuth } from '@clerk/vue';
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
const emit = defineEmits(['selectConversation']);
const preselectedChat = ref('');
/** Clerk user */
const { userId } = useAuth();

const sambanovaKey = ref(null);
const serperKey = ref(null);
const exaKey = ref(null);
const missingKeysList = ref({});
const conversations = ref([]);
const chatsLoaded = ref(false); // Track if chats have been loaded

// Event handler functions for events emitted from ChatList/ChatItem.
function onSelectConversation(conversation) {
  console.log('Parent: Selected conversation', conversation);
  preselectedChat.value = conversation.conversation_id;
  router.push(`/${conversation.conversation_id}`);
}

/**
 * On mounted => load local conversation list + decrypt keys
 */
onMounted(() => {
  console.log('ChatSidebar mounted, authentication check');
  
  // Check if user is authenticated before loading data
  if (!window.Clerk || !window.Clerk.session) {
    console.log('Skipping user data loading - user not authenticated');
    return;
  }

  loadChats();
  loadKeys();

  emitterMitt.on('keys-updated', loadKeys);

  let cId = route.params.id;
  if (cId) preselectedChat.value = cId;
});

async function deleteChat(conversationId) {
  // Check if user is authenticated
  if (!window.Clerk || !window.Clerk.session) {
    console.log('Skipping deleteChat - user not authenticated');
    return;
  }

  const url = `${import.meta.env.VITE_API_URL}/chat/${conversationId}`;
  try {
    const response = await axios.delete(url, {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${await window.Clerk.session.getToken()}`,
      },
    });

    chatsLoaded.value = false; // Reset flag to force reload
    loadChats();
    return response.data;
  } catch (error) {
    console.error('Error deleting chat:', error);

    throw error;
  }
}

async function loadKeys(missingKeysListData) {
  // Check if user is authenticated
  if (!window.Clerk || !window.Clerk.session) {
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
  if (!window.Clerk || !window.Clerk.session) {
    console.log('Skipping loadChats - user not authenticated');
    return;
  }

  try {
    const uid = userId.value || 'anonymous';
    const resp = await axios.get(`${import.meta.env.VITE_API_URL}/chat/list`, {
      headers: {
        Authorization: `Bearer ${await window.Clerk.session.getToken()}`,
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
  if (!window.Clerk || !window.Clerk.session) {
    console.log('Skipping createNewChat - user not authenticated');
    return;
  }

  console.log('CREATE1');
  emitterMitt.emit('new-chat', { message: 'The new chat button was clicked!' });
}

// Updated delete handler calls deleteChat().
async function onDeleteChat(conversationId) {
  console.log('Parent: Delete conversation', conversationId);
  try {
    await deleteChat(conversationId);
  } catch (error) {
    console.error('Delete action failed:', error);
  }
}

function onShareChat(conversationId) {
  console.log('Parent: Share conversation', conversationId);
}

function onDownloadChat(conversationId) {
  console.log('Parent: Download conversation', conversationId);
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
    if (window.Clerk && window.Clerk.session && !chatsLoaded.value) {
      loadChats();
    }
  }
);

async function refreshChats() {
  chatsLoaded.value = false;
  await loadChats();
}
</script>
