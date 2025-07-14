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
        <router-view v-if="isTermsOfServiceRoute" />
        <LoginPage v-else />
      </div>
    </main>
  </div>
</template>

<script setup>
import { useAuth0 } from '@auth0/auth0-vue'
import LoginPage from './views/LoginPage.vue'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const { isAuthenticated, isLoading, error } = useAuth0()
const route = useRoute()
const router = useRouter()
const isTermsOfServiceRoute = computed(() => route.path === '/terms-of-service')

const handleRetry = () => {
  // Clear any error state and redirect to login
  router.push('/login')
  window.location.reload()
}
</script>
