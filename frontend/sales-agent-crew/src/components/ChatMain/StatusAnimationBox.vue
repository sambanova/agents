<template>
  <div
    class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700
           p-2 rounded-lg max-h-[200px] w-full flex flex-col overflow-hidden"
  >
    <!-- Top: sliding two-letter window over the title -->
    <div class="py-4 h-10 flex items-center overflow-hidden dark:text-white">
      <span
        v-for="(char, idx) in textChars"
        :key="idx"
        :class="[
          'transition-opacity duration-500',
          // if not loading, force full opacity; otherwise highlight only the active pair
          !props.isLoading
            ? 'opacity-100'
            : isActive(idx)
              ? 'opacity-100'
              : 'opacity-40'
        ]"
      >
        {{ char }}
      </span>
    </div>

    <!-- Log area: shows the evolving content -->
    <div
      ref="logRef"
      class="flex-1 text-gray-400 dark:text-gray-300 py-2 overflow-y-auto
             space-y-1 text-sm"
    >
      <div v-for="(line, i) in logLines" :key="i">
        {{ line }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted, nextTick } from 'vue'
import { isFinalAgentType } from '@/utils/globalFunctions.js'

const props = defineProps({
  title: {
    type: String,
    default: ''
  },
  content: {
    type: String,
    default: ''
  },
  isLoading: {
    type: Boolean,
    default: false
  }
})

// Split title into characters
const textChars = computed(() => props.title.split(''))

// Index for the two-letter window
const pairIndex = ref(0)
let pairInterval = null

function startAnimation() {
  if (pairInterval !== null) return
  pairInterval = setInterval(() => {
    pairIndex.value = (pairIndex.value + 2) % textChars.value.length
  }, 150)
}

function stopAnimation() {
  clearInterval(pairInterval)
  pairInterval = null
}

// Watch isLoading: start when true, stop when false
watch(
  () => props.isLoading,
  (loading) => {
    if (loading) startAnimation()
    else stopAnimation()
  },
  { immediate: true }
)

onUnmounted(stopAnimation)

function isActive(idx) {
  return (
    idx === pairIndex.value ||
    idx === (pairIndex.value + 1) % textChars.value.length
  )
}

const logLines = computed(() =>
  props.content.split('\n').filter(line => line !== '')
)

const logRef = ref(null)
watch(
  () => props.content,
  async () => {
    await nextTick()
    if (logRef.value) {
      logRef.value.scrollTo({
        top: logRef.value.scrollHeight,
        behavior: 'smooth'
      })
    }
  }
)

</script>