<template>
  <div class="flex flex-col items-center justify-center space-y-4">
    <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
    <div class="text-center">
      <p class="text-gray-600">{{ message }}</p>
      <p v-if="subMessage" class="text-sm text-gray-500 mt-1">{{ subMessage }}</p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  message: {
    type: String,
    default: 'Loading...'
  },
  subMessage: {
    type: String,
    default: ''
  }
})
</script> 