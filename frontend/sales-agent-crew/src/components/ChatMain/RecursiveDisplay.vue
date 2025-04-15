<template>
  <div>
    <!-- If value is an object and inline mode is enabled, render key-value pairs inline -->
    <div v-if="isObject(value) && inline" class="text-ellipsis overflow-hidden">
      <span v-for="(val, key, index) in value" :key="key">
        <span v-if="isObject(val)">
          <span v-for="(valItem, keyItem, indexItem) in val" :key="keyItem">
            {{ formatKey(keyItem) }}: {{ valItem }}
          </span>
        </span>
        <span v-else> {{ formatKey(key) }}:{{ val }} </span>
        <br />
      </span>

      <span v-if="index < Object.keys(value).length - 1">, </span>
    </div>

    <!-- If value is an object (and not inline), render as a table -->
    <div v-else-if="isObject(value) && !Array.isArray(value)">
      <table class="table-auto w-full border-0">
        <tbody>
          <tr v-for="(val, key) in value" :key="key">
            <td
              class="px-4 py-2 w-[40px] text-xs text-gray-900 capitalize break-words"
            >
              {{ formatKey(key) }}
            </td>
            <td class="px-4 py-2 text-xs text-gray-900 break-words">
              <!-- Pass inline=true to render nested objects inline -->
              <RecursiveDisplay :value="val" :inline="true" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- If value is an array, render as a bullet list -->
    <div v-else-if="Array.isArray(value)">
      <ul :class="!inline ? 'list-disc' : ''" class="ml-6 space-y-1">
        <li v-for="(item, index) in value" :key="index">
          <RecursiveDisplay :value="item" :inline="true" />
        </li>
      </ul>
    </div>

    <!-- Otherwise, render as plain text -->
    <div v-else>
      <p class="text-xs break-words">{{ value }}</p>
    </div>
  </div>
</template>

<script setup>
import { defineProps } from 'vue';
import { isNumeric } from '@/utils/globalFunctions';

const props = defineProps({
  value: {
    type: null,
    required: true,
  },
  inline: {
    type: Boolean,
    default: false,
  },
});

function isObject(val) {
  return val !== null && typeof val === 'object';
}

function formatKey(key) {
  if (isNumeric(key)) {
    return key + 1;
  } else {
    key = String(key);
    return key
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }
}
</script>

<style scoped>
table {
  table-layout: auto;
}
</style>
