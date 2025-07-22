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
      <div v-if="isObject(value) && !Array.isArray(value)" class="w-full space-y-1 py-1 text-xs">
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
      <div v-else-if="Array.isArray(value)" class="py-1 text-xs">
        <ul class="list-disc ml-6 space-y-1 text-gray-700">
          <li v-for="(item, index) in value" :key="index">
            <RecursiveDisplay :value="item" />
          </li>
        </ul>
      </div>

      <!-- If heading is numeric and value has a description, display it -->
      <div v-else-if="isNumeric(heading) && value?.description" class="py-1 text-gray-700 text-xs">
        {{ value.description }}
      </div>

      <!-- If value is a JSON string, convert it and display it as an object -->
      <div v-else-if="isJsonString(value)" class="w-full space-y-1 py-1 text-xs">
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

      <!-- Code (for data science tool calls) -->
      <div v-else-if="typeof value === 'object' && value.code" class="py-1 text-xs">
        <pre class="text-xs text-gray-700 whitespace-pre-wrap overflow-x-auto">{{ value.code }}</pre>
      </div>

      <!-- Data Science Tool Calls -->
      <div v-else-if="isDataScienceToolCall" class="py-1 text-xs">
        <!-- Show explanation text at the top like other messages -->
        <div v-if="explanationText" class="mb-3 text-gray-700 leading-relaxed">
          <div v-html="renderMarkdown(explanationText)"></div>
        </div>
        
        <!-- Show code button -->
        <button
          v-if="extractedCode"
          @click="isModalOpen = true"
          class="inline-flex items-center space-x-2 px-3 py-2 text-sm font-medium text-gray-600 bg-gray-50 border border-gray-200 rounded-md hover:bg-gray-100 hover:border-gray-300 transition-colors"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
          </svg>
          <span>View Code</span>
        </button>
        <div v-else class="bg-gray-100 p-3 rounded border text-xs">
          <div class="text-gray-600 mb-2">Raw content (no code extracted):</div>
          <pre class="text-xs overflow-x-auto">{{ value }}</pre>
        </div>
      </div>

      <!-- Otherwise, render the value as markdown -->
      <div v-else class="py-1 text-xs text-gray-700 leading-relaxed">
        <div
          v-html="renderMarkdown(value)"
        ></div>
      </div>
    </div>
  </div>
  
  <!-- Code Modal (outside the conditional rendering) -->
  <CodeModal
    :is-open="isModalOpen"
    :code="extractedCode"
    :language="'Python'"
    :title="`Data Science Tool Call - ${toolCallName}`"
    @close="isModalOpen = false"
  />
</template>

<script setup>
import { ref, computed } from 'vue';
import RecursiveDisplay from './RecursiveDisplay.vue';
import CodeModal from './CodeModal.vue';
import { isNumeric } from '@/utils/globalFunctions';
import { renderMarkdown } from '@/utils/markdownRenderer';

const isOpen = ref(false);
const isModalOpen = ref(false);

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

// Detect and parse data science tool calls
const isDataScienceToolCall = computed(() => {
  // Check if value is a code object
  if (typeof props.value === 'object' && props.value.code) {
    const content = props.value.code
    const isToolCall = content.includes('<tool>user_daytona_execute_code</tool>') ||
                       content.includes('user_daytona_execute_code')
    
    // Debug logging
    if (isToolCall) {
      console.log('Data science tool call detected in TimelineCollapsibleContent (code):', {
        heading: props.heading,
        contentPreview: content.substring(0, 200) + '...'
      })
    }
    
    return isToolCall
  }
  
  // Check if value is a string
  if (typeof props.value !== 'string') return false
  
  const content = props.value
  const isToolCall = content.includes('<tool>user_daytona_execute_code</tool>') ||
                     content.includes('user_daytona_execute_code')
  
  // Debug logging
  if (isToolCall) {
    console.log('Data science tool call detected in TimelineCollapsibleContent:', {
      heading: props.heading,
      contentPreview: content.substring(0, 200) + '...'
    })
  }
  
  return isToolCall
})

const toolCallName = computed(() => {
  if (!isDataScienceToolCall.value) return ''
  
  let content
  if (typeof props.value === 'object' && props.value.code) {
    content = props.value.code
  } else {
    content = props.value
  }
  
  const toolMatch = content.match(/<tool>([^<]+)<\/tool>/)
  return toolMatch ? toolMatch[1].replace(/_/g, ' ') : 'user_daytona_execute_code'
})

const extractedCode = computed(() => {
  if (!isDataScienceToolCall.value) return ''

  // Get the content from either code object or string
  let content
  if (typeof props.value === 'object' && props.value.code) {
    content = props.value.code
  } else {
    content = props.value
  }

  console.log('RAW CONTENT DEBUG:', {
    heading: props.heading,
    valueType: typeof props.value,
    hasRawText: typeof props.value === 'object' && props.value.raw_text,
    contentLength: content.length,
    contentPreview: content.substring(0, 500) + '...'
  })

  // Extract only the code part from the tool call
  const toolStart = content.indexOf('<tool>user_daytona_execute_code</tool>')
  if (toolStart === -1) return content

  const toolInputStart = content.indexOf('<tool_input>', toolStart)
  if (toolInputStart === -1) return content

  const codeStart = content.indexOf('<code>', toolInputStart)
  if (codeStart === -1) return content

  const codeEnd = content.indexOf('</code>', codeStart)
  if (codeEnd === -1) return content

  // Extract the code between <code> and </code> tags
  const code = content.substring(codeStart + 6, codeEnd).trim()
  return code
})

const explanationText = computed(() => {
  if (!isDataScienceToolCall.value) return ''

  // Get the content from either code object or string
  let content
  if (typeof props.value === 'object' && props.value.code) {
    content = props.value.code
  } else {
    content = props.value
  }

  // Extract the explanation text (everything before the tool call)
  const toolStart = content.indexOf('<tool>user_daytona_execute_code</tool>')
  if (toolStart === -1) return ''

  // Get everything before the tool call
  const explanation = content.substring(0, toolStart).trim()
  return explanation
})

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
