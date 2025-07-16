<template>
  <div
    class="p-3 m-1 w-full relative cursor-pointer group"
    @click="onSelectConversation"
    :class="{
      'bg-primary-brandDarkGray rounded-md border border-primary-brandFrame':
        isActive,
      'bg-blue-50 border-blue-200': isMultiSelectMode && isSelected,
    }"
  >
    <!-- Checkbox for multi-select mode -->
    <div v-if="isMultiSelectMode" class="absolute left-2 top-1/2 transform -translate-y-1/2 z-30">
      <input
        type="checkbox"
        :checked="isSelected"
        @click.stop="onToggleSelection"
        class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
      />
    </div>

    <!-- Menu button: visible on hover (only in normal mode) -->
    <button
      v-if="!isMultiSelectMode"
      type="button"
      class="absolute right-1 top-1 z-20 opacity-0 group-hover:opacity-100 transition-opacity duration-200"
      @click.stop="toggleMenu"
      @mousedown.stop
      aria-label="Open menu"
    >
      <svg
        class="w-5 h-5"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#667085"
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
    <div class="w-full relative h-full" :class="{ 'ml-6': isMultiSelectMode }">
      <div class="text-sm capitalize color-primary-brandGray truncate">
        {{ conversation.name ? conversation.name : 'New Chat' }}
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
  isMultiSelectMode: {
    type: Boolean,
    default: false,
  },
  isSelected: {
    type: Boolean,
    default: false,
  },
});

// Emit events for selection and menu actions.
const emit = defineEmits([
  'select-conversation',
  'delete-chat',
  'share-chat',
  'download-chat',
  'toggle-selection',
]);

const activeMenu = ref(false);

// Computed property for setting active background.
const isActive = computed(
  () => props.preselectedChat === props.conversation.conversation_id
);

// Function to handle chat selection.
function onSelectConversation() {
  if (props.isMultiSelectMode) {
    // In multi-select mode, toggle selection
    onToggleSelection();
  } else {
    // Normal mode - emit selection event
    emit('select-conversation', props.conversation);
    activeMenu.value = false;
  }
}

// Function to handle selection toggle in multi-select mode
function onToggleSelection() {
  emit('toggle-selection', props.conversation.conversation_id);
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
