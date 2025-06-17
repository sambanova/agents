<template>
  <span
    class="flex whitespace-pre text-gray-900 dark:text-gray-100"
  >
    <span
      v-for="(char, idx) in chars"
      :key="idx"
      :class="[
        'transition-opacity duration-200 ease-in-out',
        props.isLoading
          ? (isInWindow(idx) ? 'opacity-100' : 'opacity-30')
          : 'opacity-100'
      ]"
    >
      {{ char }}
    </span>
</span>
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
    default: 150
  },
  windowSize: {
    type: Number,
    default: 10
  }
})

const chars = computed(() => props.text.split(''))
const activeIndex = ref(0)
let intervalId = null

function isInWindow(idx) {
  const start = activeIndex.value
  const size = props.windowSize
  const end = (start + size) % chars.value.length

  if (start + size <= chars.value.length) {
    return idx >= start && idx < start + size
  } else {
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

watch(() => props.isLoading, val => {
  val ? startAnimation() : stopAnimation()
})

onMounted(() => {
  if (props.isLoading) startAnimation()
})

onUnmounted(() => {
  stopAnimation()
})
</script>
