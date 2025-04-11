<template>
  <div class="mx-2 mb-2">
    <div
      @click="isOpen = !isOpen"
      class="flex justify-between items-center cursor-pointer"
    >
      <div
        :title="getHeadingValue()"
        class="flex items-center align-items-center flex-1"
      >
        <CorrectIcon class="mr-1 flex-shrink-0" />

        <span class="line-clamp-1 text-primary-brandTextSecondary text-sm">
          {{ getHeadingValue() }}:
        </span>
      </div>
      <!-- Arrow icon toggles direction based on accordion state -->
      <div class="transition-all duration-300 flex-shrink-0">
        <svg
          v-if="!isOpen"
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
      </div>
    </div>

    <div class="m-1 p-1 border rounded-md bg-primary-brandGray" v-show="isOpen">
      <!-- If value is an object (and not an array), render all keys -->
      <div v-if="isObject(value) && !Array.isArray(value)" class="w-full">
        <div v-for="(val, key) in filterObject(value)" :key="key" class="mb-1">
          <div v-if="val !== '' || val !== null"></div>
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

      <!-- If value is an array, render as a bullet list -->
      <div v-else-if="Array.isArray(value)">
        <ul class="list-disc ml-6 space-y-1">
          <li v-for="(item, index) in value" :key="index">
            <RecursiveDisplay :value="item" />
          </li>
        </ul>
      </div>

      <!-- If heading is numeric and value has a description, display it -->
      <div v-else-if="isNumeric(heading) && value?.description">
        {{ value.description }}
      </div>

      <!-- If value is a JSON string, convert it and display it as an object -->
      <div v-else-if="isJsonString(value)" class="w-full">
        <div
          v-for="(val, key) in convertStringToJson(value)"
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

      <!-- Otherwise, render the value as plain text -->
      <div v-else>
        <div
          class="markdown-content text-[#667085] text-[12px]"
          v-html="formattedText(value)"
        ></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import CorrectIcon from '@/components/icons/CorrectIcon.vue';
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
  console.log('OBJECT', val);
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
