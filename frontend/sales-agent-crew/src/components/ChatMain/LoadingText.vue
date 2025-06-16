<template>
  <div class="flex whitespace-pre">
    <span
      v-for="(char, idx) in chars"
      :key="idx"
      :class="[
        'transition-opacity duration-200 ease-in-out',
        isLoading
          ? (isInWindow(idx) ? 'opacity-100' : 'opacity-30')
          : 'opacity-100'
      ]"
    >
      {{ char }}
    </span>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  text: {
    type: String,
    required: true
  },
  isLoading: {
    type: Boolean,
    default: false
  },
  speed: {
    type: Number,
    default: 25
  },
  // how many chars to highlight at once
  windowSize: {
    type: Number,
    default: 10
  }
})

const chars = computed(() => props.text.split(''))
const activeIndex = ref(0)
let intervalId = null

function isInWindow(idx) {
  // build a wrapping window [activeIndex, activeIndex+windowSize)
  const start = activeIndex.value
  const end = (start + props.windowSize) % chars.value.length

  if (start + props.windowSize <= chars.value.length) {
    // non-wrapping
    return idx >= start && idx < start + props.windowSize
  } else {
    // wraps around end of array
    return idx >= start || idx < end
  }
}

function startAnimation() {
  if (intervalId) return
  intervalId = setInterval(() => {
    activeIndex.value = (activeIndex.value + 1) % chars.value.length
  }, props.speed)
}

function stopAnimation() {
  clearInterval(intervalId)
  intervalId = null
  activeIndex.value = 0
}

watch(() => props.isLoading, loading => {
  loading ? startAnimation() : stopAnimation()
})

onMounted(() => {
  if (props.isLoading) startAnimation()
})

onUnmounted(() => {
  stopAnimation()
})
</script>
