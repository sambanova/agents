<template>
  <!-- The "group" class allows us to use group-hover on the popover -->
  <div class="relative inline-block group">
    <!-- Slot for the target element -->
    <slot></slot>
    <!-- Popover content -->
    <div
      :class="popoverPosition"
      class="absolute z-10 invisible group-hover:visible opacity-0 group-hover:opacity-100 transition-opacity duration-300"
    >
      <div class="relative inline-block">
        <!-- Arrow element -->
        <div :class="arrowClasses" :style="arrowStyle"></div>
        <!-- Popover text container -->
        <div :class="[color, 'px-2 py-1 rounded text-xs whitespace-nowrap']">
          {{ text }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  // The text that will be displayed in the popover
  text: {
    type: String,
    required: true,
  },
  // Position: 'top', 'bottom', 'left', or 'right'
  position: {
    type: String,
    default: 'top',
  },
  // Tailwind classes for background and text color (e.g., "bg-gray-700 text-white")
  color: {
    type: String,
    default: 'bg-gray-700 text-white',
  },
});

// Compute the popover container’s position based on the supplied position prop.
const popoverPosition = computed(() => {
  switch (props.position) {
    case 'top':
      return 'bottom-full mb-2 left-1/2 transform -translate-x-1/2';
    case 'bottom':
      return 'top-full mt-2 left-1/2 transform -translate-x-1/2';
    case 'left':
      return 'right-full mr-2 top-1/2 transform -translate-y-1/2';
    case 'right':
      return 'left-full ml-2 top-1/2 transform -translate-y-1/2';
    default:
      return 'bottom-full mb-2 left-1/2 transform -translate-x-1/2';
  }
});

// Compute arrow classes for a 5px arrow using Tailwind's arbitrary values.
// (We use border utilities with transparent sides.)
const arrowClasses = computed(() => {
  switch (props.position) {
    case 'top':
      // Arrow appears at the bottom of the popover, pointing down.
      return 'absolute top-full left-1/2 transform -translate-x-1/2 border-x-[5px] border-t-[5px] border-x-transparent';
    case 'bottom':
      return 'absolute bottom-full left-1/2 transform -translate-x-1/2 border-x-[5px] border-b-[5px] border-x-transparent';
    case 'left':
      return 'absolute left-full top-1/2 transform -translate-y-1/2 border-y-[5px] border-l-[5px] border-y-transparent';
    case 'right':
      return 'absolute right-full top-1/2 transform -translate-y-1/2 border-y-[5px] border-r-[5px] border-y-transparent';
    default:
      return 'absolute top-full left-1/2 transform -translate-x-1/2 border-x-[5px] border-t-[5px] border-x-transparent';
  }
});

// Compute inline styles for the arrow so its border color matches the popover background.
// (Here we use a helper function to map common bg classes to hex codes.)
const arrowStyle = computed(() => {
  switch (props.position) {
    case 'top':
      return { borderTopColor: extractBgColor(props.color) };
    case 'bottom':
      return { borderBottomColor: extractBgColor(props.color) };
    case 'left':
      return { borderLeftColor: extractBgColor(props.color) };
    case 'right':
      return { borderRightColor: extractBgColor(props.color) };
    default:
      return { borderTopColor: extractBgColor(props.color) };
  }
});

// Helper function to map background class strings to CSS color values.
// Extend this mapping as needed.
function extractBgColor(colorClass) {
  if (colorClass.includes('bg-gray-700')) return '#374151';
  if (colorClass.includes('bg-blue-600')) return '#2563eb';
  // Fallback color
  return '#374151';
}
</script>

<style scoped>
/* No additional styles needed */
</style>
