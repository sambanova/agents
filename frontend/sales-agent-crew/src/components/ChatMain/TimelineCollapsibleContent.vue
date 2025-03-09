<template>
  <div class="mx-2 mb-2" >
    <div @click="isOpen = !isOpen" class="flex justify-between items-center cursor-pointer">
      <div class="flex items-center align-items-center flex-1 no-wrap">
        <CorrectIcon class="mr-1 flex-shrink-0" />
        <!-- If heading is non-numeric, display formatted key -->
        <span v-if="!isNumeric(heading)" class="line-clamp-1 text-primary-brandTextSecondary truncate text-sm">
          {{ formatKey(heading) }}:
        </span>
        <!-- If heading is numeric and value has a name property, display that -->
        <span v-else-if="isNumeric(heading) && value.name" class="line-clamp-1 text-primary-brandTextSecondary text-sm">
          {{ value.name ? value.name : value.search }}
        </span>
        <!-- Otherwise if heading is numeric, display fallback (e.g. search_query) -->
        <span v-else-if="isNumeric(heading)" class="line-clamp-1  text-primary-brandTextSecondary text-sm">
          {{ value?.search_query }}
        </span>
      </div>
      <!-- Arrow icon toggles direction based on accordion state -->
      <div class="transition-all duration-300 flex-shrink-0">
        <svg v-if="!isOpen"
             xmlns="http://www.w3.org/2000/svg"
             class="h-4 w-4 text-[#667085]"
             fill="none"
             viewBox="0 0 24 24"
             stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M19 9l-7 7-7-7" />
        </svg>
        <svg v-else
             xmlns="http://www.w3.org/2000/svg"
             class="h-4 w-4 text-[#667085] transform rotate-180"
             fill="none"
             viewBox="0 0 24 24"
             stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M19 9l-7 7-7-7" />
        </svg>
      </div>
    </div>
    <div class="m-1 p-1 border rounded-md bg-primary-brandGray" v-show="isOpen">
      <!-- If value is an object (and not an array), render all keys -->
      <div v-if="isObject(value) && !Array.isArray(value)">
        <!-- <h1>Object</h1> -->

        <div class="w-full">
    <div
      v-for="(val, key) in value"
      :key="key"
      class="mb-1"
    >
      <!-- Key Row: Dark Background -->
      <div class="px-2 py-1 text-xs text-gray-900 bg-gray-200">
        {{ formatKey(key) }}
      </div>
      <!-- Value Row: Light Background -->
      <div class="px-2 py-1 text-xs text-gray-900 bg-gray-50">
        <RecursiveDisplay :value="val" :inline="true" />
      </div>
    </div>
  </div>
</div>

      <!-- If value is an array, render as a bullet list -->
      <div v-else-if="Array.isArray(value)">
        <!-- <h1>Array</h1> -->

        <ul class="list-disc ml-6 space-y-1">
          <li v-for="(item, index) in value" :key="index">
            <RecursiveDisplay :value="item" />
          </li>
        </ul>
      </div>

      <!-- If heading is numeric and value has a description, display it -->
      <div v-else-if="isNumeric(heading) && value?.description">
        <!-- <h1>Else If Numeric</h1> -->

        {{ value.description }}
      </div>

      <!-- Otherwise, render the value as plain text -->
      <div v-else>
        <!-- <h1>Else</h1> -->

        <!-- <p class="text-sm">{{ value }}</p> -->

        <div class="markdown-content text-[#667085] text-[12px]" v-html="formattedText(value)"></div>
        <!-- <JsonRenderer :value="value" /> -->



      </div>
    </div>
  </div>
</template>

<script setup>
import { ref,defineComponent } from 'vue'
import CorrectIcon from '@/components/icons/CorrectIcon.vue'
import RecursiveDisplay from './RecursiveDisplay.vue'
import { isNumeric } from '@/utils/globalFunctions'
import { formattedText } from '@/utils/formatText'
// import JsonRenderer from './JsonRenderer.vue'

const isOpen = ref(false);

const props = defineProps({
  heading: {
    type: String,
    required: true
  },
  value: {
    type: null,
    required: true
  }
});




// Checks if a value is an object.
function isObject(val) {
  return val !== null && typeof val === 'object';
}

// Format a key: replace underscores with spaces and capitalize each word.
function formatKey(key) {
  key = String(key);
  return key
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}




</script>

<style scoped>
/*  */
</style>
