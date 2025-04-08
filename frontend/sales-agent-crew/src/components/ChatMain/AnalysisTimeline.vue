<template>
  <div class="vertical-timeline mb-4">
    <!-- Timeline Header -->
    <div class="flex items-center justify-start">
      <h2 v-if="!isLoading" class="text-md text-primary-brandTextSecondary">
        Analysis Concluded (<span class="text-sm"
          >{{ formattedDuration(parsedData?.metadata?.duration) }}s</span
        >)
      </h2>
      <h2 v-if="isLoading" class="text-md text-primary-brandTextSecondary">
        <StatusText :text="statusText" />
      </h2>
      <button
        @click="toggleCollapse"
        class="toggle-btn flex items-center text-blue-500 hover:text-blue-600 focus:outline-none"
      >
        <svg
          v-if="collapsed"
          xmlns="http://www.w3.org/2000/svg"
          class="h-4 w-4 text-[#667085]"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M19 9l-7 7-7-7"
          />
        </svg>
        <svg
          v-else
          xmlns="http://www.w3.org/2000/svg"
          class="h-4 w-4 text-[#667085] transform rotate-180"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>
    </div>
    <!-- Timeline Body -->
    <div
      v-show="!collapsed"
      ref="timelineBodyRef"
      class="relative pl-[18px] pt-4 pb-4"
    >
      <!-- Animated Vertical Line -->
      <div
        class="timeline-line absolute top-0 left-0 w-[2px] bg-primary-timeLine"
        :style="{ height: containerHeight + 'px' }"
      />

      <!-- Card Section -->
      <div
        v-if="workflowData && workflowData.length > 0"
        class="w-100 p-2 mx-auto"
      >
        <component
          :is="workflowData.length > 1 ? HorizontalScroll : 'div'"
          :class="workflowData.length !== 1 ?? 'flex my-2'"
        >
          <div class="flex space-x-4">
            <WorkflowDataItem :workflowData="workflowData" />
          </div>
        </component>
      </div>
      <!-- Inline metadata items -->
      <MetaData v-if="presentMetadata" :presentMetadata="presentMetadata" />
      <!-- Planner text -->
      <div
        class="ml-2 markdown-content text-[#667085]"
        v-html="renderedContent"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue';
import WorkflowDataItem from '@/components/ChatMain/WorkflowDataItem.vue';
import MetaData from '@/components/ChatMain/MetaData.vue';
import StatusText from '@/components/Common/StatusText.vue';
import HorizontalScroll from '@/components/Common/UIComponents/HorizontalScroll.vue';
import { renderMarkdownWithJSON } from '@/utils/formatText';

const props = defineProps({
  isLoading: { type: Boolean, default: false },
  parsedData: { type: Object, default: () => ({}) },
  workflowData: { type: Array, default: () => [] },
  presentMetadata: { type: [Object, Array], default: null },
  plannerText: { type: String, default: '' },
  statusText: { type: String, default: '' },
  defaultCollapsed: { type: Boolean, default: true },
});

const renderedContent = computed(() =>
  renderMarkdownWithJSON(props.plannerText)
);
const collapsed = ref(props.defaultCollapsed || false);

function toggleCollapse() {
  collapsed.value = !collapsed.value;
  // If opening the timeline, update the height after the next tick
  if (!collapsed.value) {
    nextTick(() => {
      updateHeight();
    });
  }
}

function formattedDuration(duration) {
  if (typeof duration !== 'number' || isNaN(duration)) return duration;
  return duration.toFixed(2);
}

// Reference to the timeline body element
const timelineBodyRef = ref(null);
// Reactive variable to hold the measured height of the container
const containerHeight = ref(0);

// Function to update containerHeight based on the timeline body's scrollHeight
function updateHeight() {
  nextTick(() => {
    if (timelineBodyRef.value) {
      containerHeight.value = timelineBodyRef.value.scrollHeight;
    }
  });
}

// Update height whenever the rendered content changes
watch(renderedContent, () => {
  updateHeight();
});

// Also update height when the timeline is opened (in case v-show affected layout)
watch(collapsed, (newVal) => {
  if (!newVal) {
    nextTick(() => {
      updateHeight();
    });
  }
});

// On mount, update height if the timeline is visible
onMounted(() => {
  if (!collapsed.value) {
    updateHeight();
  }
});
</script>

<style scoped>
.vertical-timeline {
  border-radius: 0.5rem;
  overflow: hidden;
}
.toggle-btn {
  transition: color 0.3s ease;
}
/* The timeline-line now smoothly transitions its height */
.timeline-line {
  transition: height 0.3s ease;
}
</style>
