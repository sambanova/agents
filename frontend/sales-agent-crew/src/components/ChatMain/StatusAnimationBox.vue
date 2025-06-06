<template>
  <div
    class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 p-2 rounded-lg max-h-[200px] w-full flex flex-col overflow-hidden"
  >
    <!-- Top static text with two-letter fade window -->
    <div class="py-4 h-10 flex items-center justify-start overflow-hidden  dark:text-white">
      <span
        v-for="(char, idx) in textChars"
        :key="idx"
        :class="[
          'transition-opacity duration-500',
          isActive(idx) ? 'opacity-100' : 'opacity-40'
        ]"
      >
        {{ char }}
      </span>
    </div>

    <!-- Continuous log area -->
    <div
      ref="logRef"
      class="flex-1 text-gray-400 dark:text-gray-300 py-2 overflow-y-auto space-y-1 text-sm"
    >
      <div v-for="(line, i) in log" :key="i">
        {{ line }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'

const text = 'Analysing..'
const textChars = computed(() => text.split(''))

const pairIndex = ref(0)
let pairInterval = null

const log = ref([])
const logRef = ref(null)
let logInterval = null

// Advance the two-letter window every 150ms
onMounted(() => {
  pairInterval = setInterval(() => {
    pairIndex.value = (pairIndex.value + 2) % text.length
  }, 150)

  // Append a new log line every 1000ms
  logInterval = setInterval(() => {
    log.value.push(
      `This is dummy text This is dummy text This is dummy text This is dummy text  #${log.value.length + 1}`
    )
  }, 1000)
})

onUnmounted(() => {
  clearInterval(pairInterval)
  clearInterval(logInterval)
})

// Scroll to bottom whenever log changes
watch(
  log,
  async () => {
    await nextTick()
    if (logRef.value) {
      logRef.value.scrollTo({
        top: logRef.value.scrollHeight,
        behavior: 'smooth',
      })
    }
  },
  { deep: true }
)

// Helper to determine if a character index is active
function isActive(idx) {
  return (
    idx === pairIndex.value ||
    idx === (pairIndex.value + 2) % text.length
  )
}
</script>
