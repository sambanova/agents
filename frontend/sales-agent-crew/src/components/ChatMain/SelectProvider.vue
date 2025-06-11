<template>
  <div class="relative inline-block text-left" ref="dropdownRef">
    <!-- Dropdown Button -->
    <button
      @click="toggleDropdown"
      :disabled="!showOtherProviders"
      type="button"
      class="inline-flex justify-between items-center w-full rounded-md border border-gray-300 dark:border-gray-600 shadow-sm px-4 py-2 bg-white dark:bg-gray-800 text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none"
    >
      {{ localSelected.label }}
      <!-- Chevron Icon -->
      <svg
        class="-mr-1 ml-2 h-5 w-5 text-gray-500 dark:text-gray-400"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
      >
        <path
          fill-rule="evenodd"
          d="M5.23 7.21a.75.75 0 011.06.02L10 10.94l3.71-3.71a.75.75 0 111.06 1.06l-4.24 4.24a.75.75 0 01-1.06 0L5.25 8.29a.75.75 0 01-.02-1.08z"
          clip-rule="evenodd"
        />
      </svg>
    </button>

    <!-- Dropdown Menu -->
    <transition name="dropdown">
      <div
        v-if="open && showOtherProviders"
        class="origin-top-right absolute right-0 mt-2 w-56 rounded-md shadow-lg bg-white dark:bg-gray-800 ring-1 ring-black ring-opacity-5 dark:ring-gray-700 dark:ring-opacity-50"
        role="menu"
        aria-orientation="vertical"
      >
        <div class="py-1">
          <template v-for="option in options" :key="option.value">
            <a
              href="#"
              @click.prevent="selectOption(option)"
              class="block px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-orange-600 dark:hover:bg-orange-500 hover:text-white transition-colors focus:outline-none active:outline-none"
              role="menuitem"
            >
              {{ option.label }}
            </a>
          </template>
        </div>
      </div>
    </transition>
  </div>
</template>


<script setup>
import { ref, watch } from 'vue'

// Accept the shared value as a prop for v-model binding.
const props = defineProps({
  selectedOption: {
    type: Object,
    default: () => ({ label: 'SambaNova', value: 'sambanova' })
  }
})
const emit = defineEmits(['update:selectedOption'])

// Create a local copy that reflects the prop.
const localSelected = ref(props.selectedOption)
const open = ref(false)

// Check the env variable: Only show other providers if true.
const showOtherProviders = import.meta.env.VITE_SHOW_OTHER_PROVIDERS === 'true'

// Updated options: Both providers.
const options = ref([
  { label: 'SambaNova', value: 'sambanova' },
  { label: 'Fireworks', value: 'fireworks' }
])
// If not showing other providers, filter options to just the first one.
if (!showOtherProviders) {
  options.value = options.value.filter(option => option.value === 'sambanova')
}

const dropdownRef = ref(null)

function toggleDropdown() {
  // If other providers are disabled, do nothing.
  if (!showOtherProviders) return
  open.value = !open.value
}

function selectOption(option) {
  localSelected.value = option
  // Emit the update so that the parent gets updated.
  emit('update:selectedOption', option)
  open.value = false
}

// Close dropdown if click is outside.
function handleClickOutside(event) {
  if (dropdownRef.value && !dropdownRef.value.contains(event.target)) {
    open.value = false
  }
}

document.addEventListener('click', handleClickOutside)

// Keep localSelected in sync if the prop changes.
watch(
  () => props.selectedOption,
  (newVal) => {
    localSelected.value = newVal
  }
)
</script>

<style scoped>
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 150ms ease-in-out;
}
.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: scale(95%);
}
.dropdown-enter-to,
.dropdown-leave-from {
  opacity: 1;
  transform: scale(100%);
}
</style>
