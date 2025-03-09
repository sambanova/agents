<template>
  <span :class="avatarClass">
    <span class="text-sm font-medium text-white leading-none">
      {{ displayedInitials }}
    </span>
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  // When type is "user", we'll use default initials
  // Otherwise, we'll treat props.type as a full name from which to extract initials
  type: {
    type: String,
    default: 'user'
  },
  // A fallback initials string
  initials: {
    type: String,
    default: 'US'
  },
  // Background color for user type; for other types we can use a different color
  bgColor: {
    type: String,
    default: 'bg-[#344054]' // Used when type is "user"
  }
})

// Set background color based on type:
// if type is not "user", use #43A047 as background
const avatarClass = computed(() => {
  const baseClasses = "shrink-0 inline-flex items-center justify-center size-[38px] rounded-full"
  const bgClass = props.type === 'user' ? props.bgColor : 'bg-[#43A047]'
  return `${baseClasses} ${bgClass}`
})

// Modified getInitials function which can handle a full name in a single argument
function getInitials(fullName) {
  const parts = fullName.split(' ').filter(Boolean)
  if (parts.length === 0) return ''
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase()
  return parts[0].charAt(0).toUpperCase() + parts[1].charAt(0).toUpperCase()
}

// Compute the displayed initials
// If props.type is "user", then use default initials
// Otherwise, treat props.type as the full name
const displayedInitials = computed(() => {
  if (props.type === 'user') {
    return props.initials
  } else {
    return getInitials(props.type)
  }
})
</script>

<style scoped>
/* Additional styling if needed */
</style>