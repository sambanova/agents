<template>
  <!-- If type is 'user', show user initials inside colored circle -->
  <span v-if="props.type === 'user'" :class="avatarClass">
    <span class="text-sm font-medium text-white leading-none">
      {{ displayedInitials }}
    </span>
  </span>
  <!-- Otherwise render static company logo -->
  <span v-else>
    <img 
      src="/Images/logo-icon.png" 
      alt="Agents Icon" 
      class="h-8 w-8" 
    />
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { useAuth0 } from '@auth0/auth0-vue'

// Use the full reactive object without destructuring
const auth0 = useAuth0()

const props = defineProps({
  // When type is "user", we'll use Clerk's user data.
  // Otherwise, we'll treat props.type as a full name from which to extract initials.
  type: {
    type: String,
    default: 'user'
  },
  // A fallback initials string.
  initials: {
    type: String,
    default: ''
  },
  // Background color for user type; for other types we can use a different color.
  bgColor: {
    type: String,
    default: 'bg-[#344054]' // Used when type is "user"
  }
})

// Set background color based on type:
// if type is not "user", use #43A047 as background.
const avatarClass = computed(() => {
  const baseClasses = "shrink-0 inline-flex items-center justify-center size-[38px] rounded-full"
  const bgClass = props.type === 'user' ? props.bgColor : 'bg-[#43A047]'
  return `${baseClasses} ${bgClass}`
})

// Modified getInitials function which can handle a full name in a single argument.
function getInitials(firstName, lastName) {
  // If lastName isn't provided, assume firstName is the full name.
  if (!lastName) {
    const parts = firstName.split(' ').filter(Boolean)
    if (parts.length === 0) return ''
    if (parts.length === 1) return parts[0].charAt(0).toUpperCase()
    return parts[0].charAt(0).toUpperCase() + parts[1].charAt(0).toUpperCase()
  }
  
  let initials = ''
  if (firstName && typeof firstName === 'string' && firstName.trim().length > 0) {
    initials += firstName.trim().charAt(0).toUpperCase()
  }
  if (lastName && typeof lastName === 'string' && lastName.trim().length > 0) {
    initials += lastName.trim().charAt(0).toUpperCase()
  }
  return initials
}

// Compute the displayed initials.
// If props.type is "user", then use Auth0's user data.
// Otherwise, treat props.type as the full name.
const displayedInitials = computed(() => {
  if (props.type === 'user') {
    // Check if the Auth0 data is loaded and the user is signed in.
    if (auth0.isAuthenticated.value && auth0.user.value) {
      // Attempt to read first and last name from Auth0 user data.
      const first = auth0.user.value.given_name || auth0.user.value.name?.split(' ')[0] || ''
      const last = auth0.user.value.family_name || auth0.user.value.name?.split(' ')[1] || ''
      return getInitials(first, last)
    }
    // Fallback if Auth0 data is not available.
    return props.initials
  } else {
    return getInitials(props.type)
  }
})
</script>

<style scoped>
/* Additional styling if needed */
</style>
