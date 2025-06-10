<template>
  <button
    @click="toggle()"
    :aria-label="isDark ? 'Switch to light mode' : 'Switch to dark mode'"
    class="p-2 rounded-full transition-colors duration-300
           flex items-center justify-center"
    :class="isDark
      ? 'border border-white text-white'
      : 'border border-lg  border-primary-brandBorder text-black'"
  >
    <component
      :is="isDark ? SunIcon : MoonIcon"
      class="w-4 h-4"
      aria-hidden="true"
    />
  </button>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { SunIcon, MoonIcon } from '@heroicons/vue/24/outline'

const isDark = ref(false)

onMounted(() => {
  // 1) load saved preference, or fall back to browser default
  const saved = localStorage.getItem('dark-mode')
  if (saved !== null) {
    isDark.value = saved === '1'
  } else {
    isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches
  }
  applyTheme()
})

function applyTheme() {
  document.documentElement.classList.toggle('dark', isDark.value)
}

function toggle() {
  isDark.value = !isDark.value
  localStorage.setItem('dark-mode', isDark.value ? '1' : '0')
  applyTheme()
}
</script>

<style scoped>
button {
  background: transparent;
}
</style>
