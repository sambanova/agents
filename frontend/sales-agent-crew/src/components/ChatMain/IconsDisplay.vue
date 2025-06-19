<template>
  <svg
    :class="['icon', 'bounce']"
    xmlns="http://www.w3.org/2000/svg"
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="#667085"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <template v-if="!text">
      <!-- bulb -->
      <path d="M9 18h6"></path>
      <path d="M10 22h4"></path>
      <path d="M12 2a7 7 0 0 1 7 7c0 2.08-1 4-3 5v2H8v-2c-2-1-3-2.92-3-5a7 7 0 0 1 7-7z"></path>
    </template>

    <template v-else-if="lowerText.includes('tavily')">
      <!-- search -->
      <circle cx="11" cy="11" r="8"></circle>
      <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
    </template>

    <template v-else-if="lowerText.includes('code')">
      <!-- code brackets -->
      <polyline points="16 18 22 12 16 6"></polyline>
      <polyline points="8 6 2 12 8 18"></polyline>
    </template>

    <template v-else-if="lowerText.includes('arxiv')">
      <!-- book -->
      <path d="M6 2h12a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"></path>
      <line x1="6" y1="6" x2="18" y2="6"></line>
    </template>

    <template v-else>
      <!-- fallback bulb -->
      <path d="M9 18h6"></path>
      <path d="M10 22h4"></path>
      <path d="M12 2a7 7 0 0 1 7 7c0 2.08-1 4-3 5v2H8v-2c-2-1-3-2.92-3-5a7 7 0 0 1 7-7z"></path>
    </template>
  </svg>
</template>

<script setup>
import { defineProps, computed } from 'vue'

const props = defineProps({
  text: { type: String, default: '' }
})

// normalize for case-insensitive matching
const lowerText = computed(() => props.text.toLowerCase())
</script>

<style>
.icon {
  display: inline-block;
  vertical-align: middle;
}
.bounce {
  animation: bounce 1s infinite;
}
@keyframes bounce {
  0%, 100% { transform: translateY(0); opacity: 1; }
  50%      { transform: translateY(-2px); opacity: 0.7; }
}
</style>
