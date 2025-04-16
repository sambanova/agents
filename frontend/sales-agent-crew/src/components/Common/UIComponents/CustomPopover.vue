<template>
  <div
    v-if="isOpen"
    ref="popoverRef"
    :class="[
      'absolute right-1 bg-white border border-gray-200 shadow-lg rounded z-30',
      positionClass,
    ]"
    @click.stop
  >
    <button
      class="flex items-center w-full px-4 py-2 hover:bg-gray-100 text-left focus-visible:outline-primary-500"
      @click="onClick"
    >
      <component :is="svgIcon" />
      {{ text }}
    </button>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue';

const props = defineProps({
  text: {
    type: String,
    required: true,
  },
  svgIcon: {
    type: Object,
    required: true,
  },
  isOpen: {
    type: Boolean,
    required: true,
  },
  onClick: {
    type: Function,
    required: true,
  },
});

const popoverRef = ref(null);
const positionClass = ref('top-8');

const checkPopoverPosition = () => {
  if (!popoverRef.value) return;

  // Get the viewport height
  const viewportHeight = window.innerHeight;

  // Get the bounding rectangle of the popover
  const rect = popoverRef.value.getBoundingClientRect();

  // Define a threshold (e.g., 100 pixels from the bottom)
  const bottomThreshold = 100;

  // Check if the popover is too close to the bottom border
  if (viewportHeight - rect.bottom < bottomThreshold) {
    // Position the popover above the original position
    positionClass.value = '-top-8';
  } else {
    // Otherwise, keep the original top positioning
    positionClass.value = 'top-8';
  }
};

// Check position when menu becomes active
watch(
  () => props.isOpen,
  (newValue) => {
    if (newValue) {
      // Use nextTick to ensure the element is in the DOM
      nextTick(checkPopoverPosition);
    }
  }
);

// Add a resize listener to recheck positioning
onMounted(() => {
  window.addEventListener('resize', checkPopoverPosition);
});

onUnmounted(() => {
  window.removeEventListener('resize', checkPopoverPosition);
});
</script>
