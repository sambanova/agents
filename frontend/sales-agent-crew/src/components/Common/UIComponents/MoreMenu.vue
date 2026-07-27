<template>
    <div class="absolute top-[5px]  right-[5px] p-1 z-20 opacity-0 group-hover:opacity-100 transition-opacity inline-block text-left">
      <!-- Three-dot More Button -->
      <button
        @click="toggleMenu"
        type="button"
        class="inline-flex justify-center w-full   text-sm font-medium text-gray-700  focus:outline-none"
        :aria-expanded="menuOpen ? 'true' : 'false'"
        aria-haspopup="true"
      >
        <!-- Three dots icon -->
        <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 20 20">
          <path d="M10 6a2 2 0 110-4 2 2 0 010 4zm0 2a2 2 0 100 4 2 2 0 000-4zm0 6a2 2 0 110 4 2 2 0 010-4z" />
        </svg>
      </button>
  
      <!-- Dropdown Menu -->
      <div
        v-if="menuOpen"
        class="origin-top-right w-[100px] absolute right-0 mt-2 w-56 rounded-md shadow-lg bg-white ring-1 ring-black ring-opacity-5 focus:outline-none z-10"
        role="menu"
        aria-orientation="vertical"
        aria-labelledby="menu-button"
      >
        <div class="p-2" role="none">
          <slot>

          <!-- Option 1 -->
          <a
            href="#"
            class="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
            role="menuitem"
          >
            <svg
              class="h-5 w-5 mr-2 text-gray-500"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
            Option 1
          </a>
          <!-- Option 2 -->
          <a
            href="#"
            class="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
            role="menuitem"
          >
            <svg
              class="h-5 w-5 mr-2 text-gray-500"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3" />
            </svg>
            Option 2
          </a>
          <!-- Option 3 -->
          <a
            href="#"
            class="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
            role="menuitem"
          >
            <svg
              class="h-5 w-5 mr-2 text-gray-500"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 20l9-5-9-5-9 5 9 5z" />
            </svg>
            Option 3
          </a>
          </slot>
        </div>
      </div>
    </div>
  </template>
  
  <script setup>
  import { ref } from 'vue'
  
  // State for toggling the dropdown menu
  const menuOpen = ref(false)
  
  function toggleMenu() {
    menuOpen.value = !menuOpen.value
  }
  </script>
  
  <style scoped>
  /* You can add additional styles here if needed */
  </style>
  