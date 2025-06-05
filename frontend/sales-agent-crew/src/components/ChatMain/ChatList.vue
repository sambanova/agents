<template>
  <div class="chat-list overflow-x-hidden h-full bg-white dark:bg-gray-900">
    <div
      v-for="group in groupedChats"
      :key="group.label"
      class="chat-group"
    >
      <!-- Sticky Group Header -->
      <div
        class="sticky top-0 z-10 px-4 py-2 text-xs font-medium text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-800"
      >
        {{ group.label }}
      </div>

      <!-- Chat Items -->
      <div>
        <ChatItem
          v-for="conversation in group.conversations"
          :key="conversation.conversation_id"
          :conversation="conversation"
          :preselectedChat="preselectedChat"
          @select-conversation="handleSelectConversation"
          @delete-chat="handleDeleteChat"
          @share-chat="handleShareChat"
          @download-chat="handleDownloadChat"
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
});

// Emit events so that parent can listen.
const emit = defineEmits([
  'select-conversation',
  'delete-chat',
  'share-chat',
  'download-chat',
]);

// Helper: determine grouping label based on timestamp.
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

  // Difference in days
  const diffDays = (now - convDate) / (1000 * 60 * 60 * 24);
  if (diffDays <= 7) {
    return 'Last 7 Days';
  } else if (diffDays <= 30) {
    return 'Last 30 Days';
  } else if (diffDays <= 60) {
    return 'Previous 30 Days';
  } else {
    // Fallback: Month Year format (e.g., "January 2023")
    return convDate.toLocaleDateString(undefined, {
      month: 'long',
      year: 'numeric',
    });
  }
}

// Compute grouped conversations array for rendering.
const groupedChats = computed(() => {
  const groups = {};
  props.conversations.forEach((conv) => {
    const label = getGroupLabel(conv.created_at);
    if (!groups[label]) {
      groups[label] = [];
    }
    groups[label].push(conv);
  });

  // Define a desired order for known groups:
  const order = ['Today', 'Yesterday', 'Last 7 Days', 'Last 30 Days', 'Previous 30 Days'];
  const sortedGroups = [];

  // Push in-order if they exist
  order.forEach((label) => {
    if (groups[label]) {
      sortedGroups.push({ label, conversations: groups[label] });
      delete groups[label];
    }
  });

  // For any remaining labels (e.g. "May 2024", "April 2025"), sort descending by date
  Object.keys(groups)
    .sort((a, b) => new Date(b) - new Date(a))
    .forEach((label) => {
      sortedGroups.push({ label, conversations: groups[label] });
    });

  return sortedGroups;
});

// Re-emit events from ChatItem
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
</script>

<style scoped>
.chat-list {
  /* If you still want vertical scrolling, keep this;
     background color is handled via Tailwind classes now. */
  overflow-y: auto;
}

.chat-group {
  margin-bottom: 1rem;
}

/*
  We removed the CSS for .sticky-header (background: #ffffff) 
  because now we rely on Tailwind’s bg-white dark:bg-gray-800.
*/
</style>
