<template>
    <div class="json-renderer">
      <!-- Render objects as tables -->
      <template v-if="isObject(parsedValue)">
        <table class="w-full text-xs">
          <thead>
            <tr>
              <th class="px-2 py-1 bg-gray-200 text-left">Key</th>
              <th class="px-2 py-1 bg-gray-200 text-left">Value</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(val, key) in parsedValue" :key="key">
              <td class="px-2 py-1 bg-gray-50">{{ formatKey(key) }}</td>
              <td class="px-2 py-1 bg-gray-50">
                <!-- Recursive call -->
                <JsonRenderer :value="val" />
              </td>
            </tr>
          </tbody>
        </table>
      </template>
      <!-- Render arrays as unordered lists -->
      <template v-else-if="Array.isArray(parsedValue)">
        <ul class="list-disc ml-6 space-y-1">
          <li v-for="(item, index) in parsedValue" :key="index">
            <JsonRenderer :value="item" />
          </li>
        </ul>
      </template>
      <!-- Render primitive values -->
      <template v-else>
        <span v-html="formattedText(parsedValue)"></span>
      </template>
    </div>
  </template>
  
  <script>
  import { formattedText } from '@/utils/formatText'
  
  export default {
    name: 'JsonRenderer',
    props: {
      value: {
        type: [Object, Array, String, Number, Boolean],
        required: true
      }
    },
    computed: {
      // If the value is a string that looks like JSON, attempt to parse it.
      parsedValue() {
        if (typeof this.value === 'string') {
          const trimmed = this.value.trim();
          if ((trimmed.startsWith('{') && trimmed.endsWith('}')) ||
              (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
            try {
              // Simple conversion: replace single quotes with double quotes.
              const fixed = trimmed.replace(/'/g, '"');
              return JSON.parse(fixed);
            } catch (e) {
              // Parsing error; return original value.
              return this.value;
            }
          }
        }
        return this.value;
      }
    },
    methods: {
      isObject(val) {
        return val && typeof val === 'object' && !Array.isArray(val);
      },
      formatKey(key) {
        return String(key)
          .split('_')
          .map(word => word.charAt(0).toUpperCase() + word.slice(1))
          .join(' ');
      },
      formattedText(val) {
        return formattedText(val);
      }
    }
  }
  </script>
  
  <style scoped>
  /* Adjust styles as needed */
  table {
    width: 100%;
    border-collapse: collapse;
  }
  th, td {
    border: 1px solid #ddd;
    padding: 4px;
  }
  </style>
  