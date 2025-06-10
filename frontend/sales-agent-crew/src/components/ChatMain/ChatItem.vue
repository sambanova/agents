<template>
  <div
    class="p-3 m-1 w-full relative cursor-pointer group bg-white dark:bg-gray-900"
    @click="onSelectConversation"
    :class="{
      'bg-primary-brandDarkGray dark:bg-gray-700 rounded-md border border-primary-brandFrame dark:border-gray-600': isActive,
    }"
  >
    <!-- Menu button: visible on hover -->
    <button
      type="button"
      class="absolute right-1 top-1 z-20 opacity-0 group-hover:opacity-100 transition-opacity duration-200 text-gray-600 dark:text-gray-400"
      @click.stop="toggleMenu"
      @mousedown.stop
      aria-label="Open menu"
    >
      <svg
        class="w-5 h-5"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <circle cx="12" cy="5" r="1" />
        <circle cx="12" cy="12" r="1" />
        <circle cx="12" cy="19" r="1" />
      </svg>
    </button>

    <CustomPopover
      text="Delete"
      :svgIcon="TrashCanIcon"
      :isOpen="activeMenu"
      :onClick="onDelete"
    />

    <!-- Conversation details -->
    <div class="w-full relative h-full">
      <div class="text-md capitalize text-brandTextSecondary dark:text-gray-200 truncate">
        {{ conversation.name || 'New Chat' }}
      </div>
    </div>
  </div>
</template>


<script setup>
import { ref, computed } from 'vue';
import CustomPopover from '../Common/UIComponents/CustomPopover.vue';
import TrashCanIcon from '../icons/TrashCanIcon.vue';

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
const emit = defineEmits([
  'select-conversation',
  'delete-chat',
  'share-chat',
  'download-chat',
]);

const activeMenu = ref(false);

// Computed property for setting active background.
const isActive = computed(
  () => props.preselectedChat === props.conversation.conversation_id
);

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
