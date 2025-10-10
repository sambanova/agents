<!-- App.vue -->
<template>
  <div class="h-screen">
    <!-- Loading state -->
    <div v-if="isLoading" class="h-full flex items-center justify-center">
      <div class="text-center">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-950 mx-auto mb-4"></div>
        <p class="text-gray-600">Loading...</p>
      </div>
    </div>
    
    <!-- Error state -->
    <div v-else-if="error" class="h-full flex items-center justify-center">
      <div class="text-center bg-red-50 p-6 rounded-lg max-w-md mx-4">
        <h2 class="text-red-800 text-xl font-semibold mb-2">Authentication Error</h2>
        <p class="text-red-600 mb-4">{{ error.message }}</p>
        <button 
          @click="handleRetry"
          class="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
        >
          Retry Login
        </button>
      </div>
    </div>
    
    <!-- Main content -->
    <main v-else>
      <div v-if="isAuthenticated">
        <router-view />
      </div>
      <div v-else>
        <router-view v-if="isTermsOfServiceRoute || isSharedConversationRoute" />
        <LoginPage v-else />
      </div>
    </main>
  </div>
</template>

<script setup>
import { useAuth0 } from '@auth0/auth0-vue'
import LoginPage from './views/LoginPage.vue'
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const { isAuthenticated, isLoading, error, getAccessTokenSilently } = useAuth0()
const route = useRoute()
const router = useRouter()
const isTermsOfServiceRoute = computed(() => route.path === '/terms-of-service')
const isSharedConversationRoute = computed(() => route.path.startsWith('/share/'))

const handleRetry = () => {
  // Clear any error state and redirect to login
  router.push('/login')
  window.location.reload()
}

// Sync localStorage keys and config to Redis if Redis is empty (e.g., after restart)
const syncLocalStorageToRedis = async () => {
  console.log('[SYNC] Checking if localStorage needs to be synced to Redis...')

  const token = await getAccessTokenSilently()
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api'

  try {
    // Check if Redis has config
    let needsSync = false
    try {
      const configResponse = await axios.get(`${apiBaseUrl}/admin/config`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      console.log('[SYNC] Redis config found')
    } catch (configError) {
      if (configError.response?.status === 404) {
        console.log('[SYNC] Redis config is empty (404), needs sync')
        needsSync = true
      }
    }

    // Also check API keys
    try {
      const keysResponse = await axios.get(`${apiBaseUrl}/get_api_keys`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      console.log('[SYNC] Redis keys found')
      if (!keysResponse.data || !keysResponse.data.sambanova_key) {
        needsSync = true
      }
    } catch (keysError) {
      if (keysError.response?.status === 404) {
        console.log('[SYNC] Redis keys are empty (404), needs sync')
        needsSync = true
      }
    }

    if (!needsSync) {
      console.log('[SYNC] Redis already has config and keys, no sync needed')
      return
    }

    // Sync API keys
    const storedKeys = localStorage.getItem('llm_api_keys')
    if (storedKeys) {
      const parsedKeys = JSON.parse(storedKeys)
      console.log('[SYNC] Syncing API keys from localStorage')

      const apiKeysPayload = {
        sambanova_key: parsedKeys.sambanova || '',
        fireworks_key: parsedKeys.fireworks || '',
        together_key: parsedKeys.together || '',
        serper_key: parsedKeys.serper_key || '',
        exa_key: parsedKeys.exa_key || '',
        paypal_invoicing_email: parsedKeys.paypal_invoicing_email || ''
      }

      await axios.post(`${apiBaseUrl}/set_api_keys`, apiKeysPayload, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })
      console.log('[SYNC] Successfully synced API keys to Redis')
    }

    // Sync LLM config
    const storedConfig = localStorage.getItem('llm_config')
    if (storedConfig) {
      const parsedConfig = JSON.parse(storedConfig)
      console.log('[SYNC] Found config in localStorage, syncing...')

      await axios.post(`${apiBaseUrl}/admin/config`, parsedConfig, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })
      console.log('[SYNC] Successfully synced LLM config to Redis')
    }

    console.log('[SYNC] Sync completed successfully')
  } catch (error) {
    console.error('[SYNC] Failed to sync:', error)
  }
}

// Watch for authentication and loading to complete, then sync
watch([isAuthenticated, isLoading], async ([authenticated, loading]) => {
  console.log('[SYNC] Watch triggered - authenticated:', authenticated, 'loading:', loading)
  if (authenticated && !loading) {
    console.log('[SYNC] User authenticated and not loading, starting sync check...')
    await syncLocalStorageToRedis()
  }
}, { immediate: true })
</script>
