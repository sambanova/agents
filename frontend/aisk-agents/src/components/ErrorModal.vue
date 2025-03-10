<template>
  <div v-if="show" class="fixed inset-0 z-50 overflow-y-auto">
    <div class="flex items-center justify-center min-h-screen p-4">
      <!-- Backdrop -->
      <div class="fixed inset-0 bg-black opacity-30" @click="$emit('close')"></div>
      
      <div class="bg-white rounded-lg overflow-hidden shadow-xl transform transition-all sm:max-w-lg w-full z-10">
        <!-- Header -->
        <div class="bg-red-500 text-white px-4 py-2 flex items-center">
          <svg class="h-6 w-6 text-white mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
          </svg>
          <h3 class="text-lg leading-6 font-medium">Error</h3>
        </div>
        
        <!-- Content -->
        <div class="px-4 py-4">
          <p class="text-sm text-gray-700">{{ errorMessage }}</p>
          <p class="text-xs text-gray-500 mt-2">
            Please check your API keys and try again. If the problem persists, contact support.
          </p>
        </div>
        
        <!-- Actions -->
        <div class="px-4 py-3 flex justify-end bg-gray-50">
          <button 
            @click="$emit('close')"
            class="bg-red-600 hover:bg-red-700 text-white font-semibold px-4 py-2 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  show: Boolean,
  errorMessage: String
})
</script> 