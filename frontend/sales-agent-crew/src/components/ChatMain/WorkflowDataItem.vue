<template>
  <div
    v-for="(item, index) in workflowData"
    :key="item.message_id + index || index"
    class="group flex flex-col bg-gray-50 border border-gray-200 rounded-lg p-3 mb-2"
  >
    <div class="flex items-start justify-between">
      <!-- Left: Text Content -->
      <div class="grow">
        <h3 class="text-xs font-semibold text-gray-800 flex items-center">
          <span class="truncate capitalize">
            {{ getTextAfterLastSlash(item.llm_name) }}
          </span>
          <span class="ml-1.5 text-gray-500 font-normal"> ({{ item.count }}) </span>
        </h3>
        <p class="text-xs text-gray-500 flex justify-between mt-1">
          <span class="capitalize">{{ item.task }}</span>
          <span v-if="item.duration">{{
            formattedDuration(item.duration)
          }}</span>
        </p>
      </div>
      <!-- Right: Icon -->
      <div class="flex-shrink-0">
        <template v-if="item.llm_name.toLowerCase().includes('meta')">
          <img class="w-4 h-4" src="/Images/icons/meta.png" alt="Meta" />
        </template>
        <template v-if="item.llm_name.toLowerCase().includes('maverick')">
          <img class="w-4 h-4" src="/Images/icons/meta.png" alt="Meta" />
        </template>
        <template v-else-if="item.llm_name.toLowerCase().includes('deepseek')">
          <img class="w-4 h-4" src="/Images/icons/deepseek.png" alt="Deepseek" />
        </template>
      </div>
    </div>
    <div
      v-if="isLoading"
      class="mt-2 w-full h-1 bg-gray-200 rounded-full overflow-hidden"
    >
      <div
        class="h-full bg-blue-500 animate-pulse"
        style="width: 100%"
      ></div>
    </div>
  </div>
</template>

<script setup>
import { defineProps, watch, computed } from 'vue';
import { formattedDuration } from '@/utils/globalFunctions';

const props = defineProps({
  workflowData: {
    type: Array,
    default: () => []
  },
  isLoading: {
    type: Boolean,
    default: false
  }
});

// For convenience, wrap workflowData in a computed property so it remains reactive
const workflowData = computed(() => props.workflowData);

// Watch for changes to workflowData and check if new data is added
watch(
  () => props.workflowData,
  (newData, oldData) => {
    if (oldData && newData.length !== oldData.length) {
      console.log("New data has been added or removed.");
      // Add any additional logic here if needed
    }
  },
  { deep: true, immediate: true }
);


function getTextAfterLastSlash(str) {
  if (!str.includes('/')) {
    // If there is no slash, return the original string
    return str;
  }
  return str.substring(str.lastIndexOf('/') + 1);
}



</script>
