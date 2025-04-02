<template>
  <div
    v-for="(item, index) in workflowData"
    :key="item.message_id + index || index"
    class="group flex flex-col bg-primary-brandDarkGray border border-primary-brandGray shadow-sm rounded-xl hover:shadow-md focus:outline-none focus:shadow-md transition mb-2"
  >
    <div class="px-4 py-2 md:px-5 min-w-[260px]">
      <div class="flex items-start relative justify-between">
        <!-- Left: Text Content -->
        <div class="grow">
          <h3 class="text-sm text-primary-bodyText flex items-center">
            <span class="inline-block w-[75%] truncate capitalize">
              {{ getTextAfterLastSlash(item.llm_name) }}
            </span>
            <span class="ml-1 w-[15%]"> ({{ item.count }}) </span>
          </h3>
          <p class="text-sm text-gray-500 flex justify-between">
            <span class="capitalize">{{ item.task }}</span>
            <span v-if="item.duration">
              {{ formattedDuration(item.duration) }}
            </span>
          </p>
        </div>
        <!-- Right: Icon  -->
        <div class="absolute top-[5px] right-[5px]">
          <template v-if="item.llm_name.toLowerCase().includes('meta')">
            <img class="w-4 h-4" src="/Images/icons/meta.png" alt="" />
          </template>
          <template
            v-else-if="item.llm_name.toLowerCase().includes('deepseek')"
          >
            <img class="w-4 h-4" src="/Images/icons/deepseek.png" alt="" />
          </template>
        </div>
      </div>
    </div>
    <div
      v-if="isLoading"
      class="mt-1 w-full h-1 bg-gray-300 overflow-hidden relative"
    >
      <div
        class="absolute top-0 left-0 h-full bg-primary-brandPrimaryColor animate-loader"
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
    default: () => [],
  },
  isLoading: {
    type: Boolean,
    default: false,
  },
});

// For convenience, wrap workflowData in a computed property so it remains reactive
const workflowData = computed(() => props.workflowData);

// Watch for changes to workflowData and check if new data is added
watch(
  () => props.workflowData,
  (newData, oldData) => {
    console.log('Workflow data updated:', newData);
    if (oldData && newData.length !== oldData.length) {
      console.log('New data has been added or removed.');
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
