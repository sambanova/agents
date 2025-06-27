<template>
  <div class="text-xs">
    <div
      @click="isOpen = !isOpen"
      class="flex justify-between items-center cursor-pointer p-2 rounded-md hover:bg-gray-50"
    >
      <div
        :title="getHeadingValue()"
        class="flex items-center align-items-center flex-1"
      >
        <span class="line-clamp-1 text-gray-500 text-xs">
          {{ getHeadingValue() }}:
        </span>
      </div>
      <!-- Arrow icon toggles direction based on accordion state -->
      <div class="transition-all duration-300 flex-shrink-0">
        <svg
          v-if="!isOpen"
          xmlns="http://www.w3.org/2000/svg"
          class="h-4 w-4 text-gray-400"
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
          class="h-4 w-4 text-gray-400 transform rotate-180"
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
      </div>
    </div>

    <div class="pl-6" v-show="isOpen">
      <!-- If value is an object (and not an array), render all keys -->
      <div v-if="isObject(value) && !Array.isArray(value)" class="w-full space-y-1 py-1">
        <div v-for="(val, key) in filterObject(value)" :key="key">
          <div v-if="val !== '' || val !== null">
            <span class="font-medium text-gray-900">{{ formatKey(key) }}: </span>
            <span class="text-gray-700">
              <RecursiveDisplay :value="val" :inline="true" />
            </span>
          </div>
        </div>
      </div>

      <!-- If value is an array, render as a bullet list -->
      <div v-else-if="Array.isArray(value)" class="py-1">
        <ul class="list-disc ml-6 space-y-1 text-gray-700">
          <li v-for="(item, index) in value" :key="index">
            <RecursiveDisplay :value="item" />
          </li>
        </ul>
      </div>

      <!-- If heading is numeric and value has a description, display it -->
      <div v-else-if="isNumeric(heading) && value?.description" class="py-1 text-gray-700">
        {{ value.description }}
      </div>

      <!-- If value is a JSON string, convert it and display it as an object -->
      <div v-else-if="isJsonString(value)" class="w-full space-y-1 py-1">
        <div
          v-for="(val, key) in convertStringToJson(value)"
          :key="key"
          class="mb-1"
        >
          <span class="font-medium text-gray-900">{{ formatKey(key) }}: </span>
          <span class="text-gray-700">
            <RecursiveDisplay :value="val" :inline="true" />
          </span>
        </div>
      </div>

      <!-- Otherwise, render the value as plain text -->
      <div v-else class="py-1">
        <div
          class="prose prose-sm max-w-none"
          v-html="formattedText(value)"
        ></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import RecursiveDisplay from './RecursiveDisplay.vue';
import { isNumeric } from '@/utils/globalFunctions';
import { formattedText } from '@/utils/formatText';

const isOpen = ref(false);

const props = defineProps({
  heading: {
    type: String,
    required: true,
  },
  value: {
    type: null,
    required: true,
  },
});

function isJsonString(val) {
  try {
    if (val[0] === '{') {
      const replacement = val.replaceAll("'", '"');
      const jsonString = JSON.parse(replacement);

      return typeof jsonString === 'object';
    }
  } catch {
    return false;
  }
}

function convertStringToJson(val) {
  const replacement = val.replaceAll("'", '"');
  const jsonString = JSON.parse(replacement);

  return filterObject(jsonString);
}

// Checks if a value is an object.
function isObject(val) {
  return val !== null && typeof val === 'object';
}

function filterObject(object) {
  // Remove empty values
  const filteredObject = { ...object };

  Object.keys(filteredObject).forEach((key) => {
    const value = filteredObject[key];

    if (
      value === null ||
      value === undefined ||
      value === '' ||
      (Array.isArray(value) && value.length === 0) ||
      (typeof value === 'object' &&
        !Array.isArray(value) &&
        Object.keys(value).length === 0)
    ) {
      delete filteredObject[key];
    }
  });

  return filteredObject;
}

// Format a key: replace underscores with spaces and capitalize each word.
function formatKey(key) {
  key = String(key);
  return key
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

// Get the correct heading text value to display.
const getHeadingValue = () => {
  // If heading is non-numeric, display formatted key.
  if (!isNumeric(props.heading)) {
    return formatKey(props.heading);
    // If heading is numeric and value has a name property, display that.
  } else if (isNumeric(props.heading) && props.value.name) {
    return props.value.name ? props.value.name : props.value.search;
    // Otherwise if heading is numeric, display fallback (e.g. search_query).
  } else {
    return props.value?.search_query;
  }
};
</script>
