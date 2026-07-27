<template>
  <label class="inline-flex items-center cursor-pointer">
    <input type="checkbox" v-model="checked" class="sr-only peer" />
    <div
      class="relative w-11 h-6 bg-gray-200 rounded-full transition-colors duration-300
             dark:bg-gray-700
             peer-checked:bg-primary-brandBorder
             after:content-[''] after:absolute after:top-[2px] after:left-[2px]
             after:bg-white after:border after:border-gray-300 after:rounded-full
             after:h-5 after:w-5 after:transition-all dark:after:border-gray-600
             peer-checked:after:translate-x-full peer-checked:after:border-white"
    ></div>
    <span v-if="label" class="ml-3 text-sm font-medium text-gray-900">
      {{ label }}
    </span>
  </label>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  chatMode: { type: Boolean, default: true },
  label: { type: String, default: '' }
})
const emit = defineEmits(['update:chatMode'])
const checked = computed({
  get: () => props.chatMode,
  set: (val) => emit('update:chatMode', val)
})
</script>
