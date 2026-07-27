<template>
  <div class="oauth-callback">
    <div class="container" :class="containerClass">
      <h1>{{ title }}</h1>
      <p>{{ message }}</p>
      <div v-if="loading" class="spinner"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const loading = ref(true)
const title = ref('Connecting...')
const message = ref('Please wait while we complete the connection.')

const success = computed(() => route.query.success === 'true')
const error = computed(() => route.query.error)
const provider = computed(() => route.query.provider)

const containerClass = computed(() => {
  if (success.value) return 'success'
  if (error.value) return 'error'
  return ''
})

onMounted(() => {
  // Handle the OAuth callback
  if (success.value) {
    // Success case
    title.value = '✅ Connected Successfully!'
    message.value = `${provider.value ? provider.value.charAt(0).toUpperCase() + provider.value.slice(1) : 'Service'} has been connected to your account.`
    loading.value = false
    
    // Try to notify parent window if in popup
    if (window.opener && !window.opener.closed) {
      try {
        window.opener.postMessage({ 
          type: 'oauth-complete', 
          success: true,
          provider: provider.value
        }, window.location.origin)
      } catch (e) {
        console.error('Could not post message to parent:', e)
      }
    }
    
    // Close window after short delay
    setTimeout(() => {
      message.value = 'This window will close automatically...'
      setTimeout(() => {
        // Try to close if we're a popup
        if (window.opener) {
          window.close()
        } else {
          // If not a popup, redirect to home
          window.location.href = '/'
        }
      }, 1000)
    }, 1500)
  } else if (error.value) {
    // Error case
    title.value = '❌ Connection Failed'
    
    // Provide user-friendly error messages
    let errorMessage = 'An error occurred during connection.'
    if (error.value === 'access_denied') {
      errorMessage = 'Access was denied. Please try again and grant the necessary permissions.'
    } else if (error.value === 'callback_failed') {
      errorMessage = 'Failed to complete the connection. Please try again.'
    }
    
    message.value = errorMessage
    loading.value = false
    
    // Auto-close after longer delay for errors
    setTimeout(() => {
      if (window.opener) {
        window.close()
      } else {
        window.location.href = '/'
      }
    }, 5000)
  } else {
    // Unexpected state
    title.value = 'Processing...'
    message.value = 'Completing OAuth flow...'
    
    // Auto-close as fallback
    setTimeout(() => {
      if (window.opener) {
        window.close()
      } else {
        window.location.href = '/'
      }
    }, 3000)
  }
})
</script>

<style scoped>
.oauth-callback {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

.container {
  text-align: center;
  padding: 2rem;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  min-width: 300px;
}

.container.success {
  background: rgba(16, 185, 129, 0.2);
}

.container.error {
  background: rgba(239, 68, 68, 0.2);
}

h1 {
  margin: 0 0 1rem 0;
  font-size: 1.5rem;
}

p {
  margin: 0 0 1rem 0;
  opacity: 0.9;
}

.spinner {
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top: 3px solid white;
  width: 30px;
  height: 30px;
  animation: spin 1s linear infinite;
  margin: 1rem auto;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>