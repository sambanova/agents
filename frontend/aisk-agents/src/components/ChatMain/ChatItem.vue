<template>
    <div
      class="p-3 m-1 w-full relative cursor-pointer group"
      @click="onSelectConversation"
      :class="{ 'bg-primary-brandDarkGray rounded-md border border-primary-brandFrame': isActive }"
    >
      <!-- Menu button: visible on hover -->
      <button
        type="button"
        class="absolute right-1 top-1 z-20 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
        @click.stop="toggleMenu"
        @mousedown.stop
        aria-label="Open menu"
      >
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="#667085" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="5" r="1" />
          <circle cx="12" cy="12" r="1" />
          <circle cx="12" cy="19" r="1" />
        </svg>
      </button>
    
      <!-- Popover menu -->
      <div
        v-if="activeMenu"
        class="absolute right-1 top-8 bg-white border border-gray-200 shadow-lg rounded z-30"
        @click.stop
      >
        <button
          class="flex items-center w-full px-4 py-2 hover:bg-gray-100 text-left"
          @click="onDelete"
        >
          <svg class="w-5 h-5 mr-2" viewBox="0 0 24 24" fill="none" stroke="#667085" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6l-1 14H6L5 6" />
            <path d="M10 11v6" />
            <path d="M14 11v6" />
            <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
          </svg>
          Delete
        </button>
        <!-- <button
          class="flex items-center w-full px-4 py-2 hover:bg-gray-100 text-left"
          @click="onShare"
        >
          <svg class="w-5 h-5 mr-2" viewBox="0 0 24 24" fill="none" stroke="#667085" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 12v7a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7" />
            <polyline points="12 3 12 12" />
            <polyline points="9 6 12 3 15 6" />
          </svg>
          Share
        </button>
        <button
          class="flex items-center w-full px-4 py-2 hover:bg-gray-100 text-left"
          @click="onDownload"
        >
          <svg class="w-5 h-5 mr-2" viewBox="0 0 24 24" fill="none" stroke="#667085" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
          Download
        </button> -->
      </div>
    
      <!-- Conversation details -->
      <div class="w-full relative h-full">
        <div class="text-md capitalize color-primary-brandGray  truncate">
          {{ conversation.name ? conversation.name : "New Chat" }}
        </div>
      </div>
    </div>
  </template>
  
  <script setup>
  import { ref, computed,inject } from 'vue';
  
  // Props from parent
  const props = defineProps({
    conversation: {
      type: Object,
      required: true,
    },
    preselectedChat: {
      type: [String, Number],
      default: null,
    },
  });
  
  // Emit events for selection and menu actions.
  const emit = defineEmits(['select-conversation', 'delete-chat', 'share-chat', 'download-chat']);
  
  const activeMenu = ref(false);
  
  // Computed property for setting active background.
  const isActive = computed(() => props.preselectedChat === props.conversation.conversation_id);
  
  // Function to handle chat selection.
  function onSelectConversation() {
    emit('select-conversation', props.conversation);
    activeMenu.value = false;
  }
  
  // Toggle menu visibility.
  function toggleMenu() {
    activeMenu.value = !activeMenu.value;
  }
  
  // Emit delete event.
  function onDelete() {
    emit('delete-chat', props.conversation.conversation_id);
    activeMenu.value = false;
  }
  
  // Emit share event.
  function onShare() {
    emit('share-chat', props.conversation.conversation_id);
    activeMenu.value = false;
  }
  
  // Emit download event.
  function onDownload() {
    emit('download-chat', props.conversation.conversation_id);
    activeMenu.value = false;
  }
  </script>
  
  <style scoped>
  /* Add any additional ChatItem styles as needed */
  </style>
  