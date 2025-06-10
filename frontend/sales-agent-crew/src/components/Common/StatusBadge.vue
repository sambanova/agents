<template>
  <span 
    :class="badgeClasses"
    class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium"
  >
    <span 
      v-if="showDot" 
      :class="dotClasses"
      class="w-1.5 h-1.5 rounded-full mr-1.5"
    ></span>
    {{ text }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: {
    type: String,
    required: true,
    validator: (value) => [
      'pending', 'executing', 'completed', 'error', 
      'success', 'warning', 'info', 'default'
    ].includes(value)
  },
  text: {
    type: String,
    required: true
  },
  showDot: {
    type: Boolean,
    default: true
  },
  variant: {
    type: String,
    default: 'default',
    validator: (value) => ['default', 'subtle'].includes(value)
  }
})

const badgeClasses = computed(() => {
  const baseClasses = 'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium'
  
  const statusClasses = {
    pending: props.variant === 'subtle' 
      ? 'bg-yellow-50 text-yellow-700 border border-yellow-200' 
      : 'bg-yellow-100 text-yellow-800',
    executing: props.variant === 'subtle'
      ? 'bg-blue-50 text-blue-700 border border-blue-200'
      : 'bg-blue-100 text-blue-800',
    completed: props.variant === 'subtle'
      ? 'bg-green-50 text-green-700 border border-green-200'
      : 'bg-green-100 text-green-800',
    success: props.variant === 'subtle'
      ? 'bg-green-50 text-green-700 border border-green-200'
      : 'bg-green-100 text-green-800',
    error: props.variant === 'subtle'
      ? 'bg-red-50 text-red-700 border border-red-200'
      : 'bg-red-100 text-red-800',
    warning: props.variant === 'subtle'
      ? 'bg-yellow-50 text-yellow-700 border border-yellow-200'
      : 'bg-yellow-100 text-yellow-800',
    info: props.variant === 'subtle'
      ? 'bg-blue-50 text-blue-700 border border-blue-200'
      : 'bg-blue-100 text-blue-800',
    default: props.variant === 'subtle'
      ? 'bg-gray-50 text-gray-700 border border-gray-200'
      : 'bg-gray-100 text-gray-800'
  }
  
  return `${baseClasses} ${statusClasses[props.status] || statusClasses.default}`
})

const dotClasses = computed(() => {
  const statusDots = {
    pending: 'bg-yellow-500',
    executing: 'bg-blue-500',
    completed: 'bg-green-500',
    success: 'bg-green-500',
    error: 'bg-red-500',
    warning: 'bg-yellow-500',
    info: 'bg-blue-500',
    default: 'bg-gray-500'
  }
  
  return statusDots[props.status] || statusDots.default
})
</script>

<style scoped>
/* Pulse animation for executing status */
.bg-blue-500 {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}
</style> 