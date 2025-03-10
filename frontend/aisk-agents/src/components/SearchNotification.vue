<template>
  <Transition
    enter-active-class="transform ease-out duration-300 transition"
    enter-from-class="translate-y-2 opacity-0 sm:translate-y-0 sm:translate-x-2"
    enter-to-class="translate-y-0 opacity-100 sm:translate-x-0"
    leave-active-class="transition ease-in duration-100"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div v-if="show" class="fixed top-4 right-4 z-50">
      <div class="bg-white rounded-lg shadow-lg border-l-4 border-primary-500 p-4 w-[32rem]">
        <div class="flex items-start">
          <div class="flex-shrink-0">
            <svg class="h-6 w-6 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path 
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" 
              />
            </svg>
          </div>
          <div class="ml-3 w-0 flex-1 pt-0.5">
            <p class="text-sm font-bold text-gray-900">
              Search Complete! 🎉
            </p>
            <p class="mt-1 text-sm font-semibold text-gray-600">
              Your Agents have produced your content for 
              {{ resultCount }} 
              {{ resultCount === 1 ? 'result' : 'results' }} 
              in {{ time }} seconds!
            </p>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { watch } from 'vue'

const props = defineProps({
  show: {
    type: Boolean,
    required: true
  },
  time: {
    type: String,
    required: true
  },
  resultCount: {
    type: Number,
    required: true
  }
})

// Add watcher for props
watch(
  () => props.show,
  (newValue) => {
    console.log('[SearchNotification] Show status changed:', newValue)
  }
)

watch(
  () => props.resultCount,
  (newValue) => {
    console.log('[SearchNotification] Result count changed:', newValue)
  }
)
</script>
