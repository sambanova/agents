<template>
  <div class="flex items-center bg-red-50 rounded-md p-3 shadow-sm">
    <!-- Material-like Error Icon -->
    <div class="flex-shrink-0">
      <svg class="h-6 w-6 text-red-700" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    </div>
    <!-- Alert Content -->
    <div class="ml-3">
      <h3 class="text-sm  text-red-700">  <span class="mt-1 text-sm ">
        {{ parsed.data?.error || "An unknown error occurred" }}
      </span></h3>
    
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  parsed: {
    type: Object,
    required: true
  }
});
</script>
