<template>
  <div class="chat-list overflow-x-hidden h-full">
    <div v-for="group in groupedChats" :key="group.label" class="chat-group">
      <!-- Sticky Group Header -->
      <div class="sticky-header text-xs text-primary-brandTextSecondary">
        {{ group.label }}
      </div>
      <!-- Chat Items -->
      <div>
        <ChatItem
          v-for="conversation in group.conversations"
          :key="conversation.conversation_id"
          :conversation="conversation"
          :preselectedChat="preselectedChat"
          :isMultiSelectMode="isMultiSelectMode"
          :isSelected="selectedChats.includes(conversation.conversation_id)"
          @select-conversation="handleSelectConversation"
          @delete-chat="handleDeleteChat"
          @share-chat="handleShareChat"
          @download-chat="handleDownloadChat"
          @toggle-selection="handleToggleSelection"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import ChatItem from './ChatItem.vue';

// Props passed from the parent component.
const props = defineProps({
  conversations: {
    type: Array,
    required: true,
  },
  preselectedChat: {
    type: [String, Number],
    default: null,
  },
  isMultiSelectMode: {
    type: Boolean,
    default: false,
  },
  selectedChats: {
    type: Array,
    default: () => [],
  },
});

// Emit events so that parent can listen.
const emit = defineEmits([
  'select-conversation',
  'delete-chat',
  'share-chat',
  'download-chat',
  'toggle-chat-selection',
]);

// Helper function to compute group label based on timestamp.
function getGroupLabel(timestamp) {
  const now = new Date();
  const convDate = new Date(timestamp * 1000);

  // Today
  if (
    now.getFullYear() === convDate.getFullYear() &&
    now.getMonth() === convDate.getMonth() &&
    now.getDate() === convDate.getDate()
  ) {
    return 'Today';
  }

  // Yesterday
  const yesterday = new Date();
  yesterday.setDate(now.getDate() - 1);
  if (
    yesterday.getFullYear() === convDate.getFullYear() &&
    yesterday.getMonth() === convDate.getMonth() &&
    yesterday.getDate() === convDate.getDate()
  ) {
    return 'Yesterday';
  }
  // Difference in days.
  const diffDays = (now - convDate) / (1000 * 60 * 60 * 24);
  if (diffDays <= 7) {
    return 'Last 7 Days';
  } else if (diffDays <= 30) {
    return 'Last 30 Days';
  } else if (diffDays <= 60) {
    return 'Previous 30 Days';
  } else {
    // Group by month (e.g., "January 2023")
    return convDate.toLocaleDateString(undefined, {
      month: 'long',
      year: 'numeric',
    });
  }
}

// Compute grouped conversations.
const groupedChats = computed(() => {
  const groups = {};
  props.conversations.forEach((conv) => {
    const label = getGroupLabel(conv.created_at);
    if (!groups[label]) {
      groups[label] = [];
    }
    groups[label].push(conv);
  });

  // Order for known groups.
  const order = [
    'Today',
    'Yesterday',
    'Last 7 Days',
    'Last 30 Days',
    'Previous 30 Days',
  ];
  const sortedGroups = [];
  order.forEach((label) => {
    if (groups[label]) {
      sortedGroups.push({ label, conversations: groups[label] });
      delete groups[label];
    }
  });
  // Remaining groups (by month) sorted descending.
  Object.keys(groups)
    .sort((a, b) => new Date(b) - new Date(a))
    .forEach((label) => {
      sortedGroups.push({ label, conversations: groups[label] });
    });
  return sortedGroups;
});

// Re-emit events from ChatItem.
function handleSelectConversation(conversation) {
  emit('select-conversation', conversation);
}

function handleDeleteChat(conversationId) {
  emit('delete-chat', conversationId);
}

function handleShareChat(conversationId) {
  emit('share-chat', conversationId);
}

function handleDownloadChat(conversationId) {
  emit('download-chat', conversationId);
}

function handleToggleSelection(conversationId) {
  emit('toggle-chat-selection', conversationId);
}
</script>

<style scoped>
.chat-list {
  /* max-height: 80vh; Adjust as needed */
  overflow-y: auto;
}

.chat-group {
  margin-bottom: 1rem;
}

/* Sticky header style */
.sticky-header {
  position: sticky;
  top: 0;
  background: #ffffff;
  z-index: 10;
  padding: 0.5rem 1rem;
}
</style>
