<script setup>
import { onMounted, ref } from 'vue';
import AuthProvider from './components/Common/AuthProvider.vue';
import { setAccessToken, hasToken } from './utils/auth';

const authProviderRef = ref(null);

onMounted(() => {
  // Get token from URL query parameter
  const urlParams = new URLSearchParams(window.location.search);
  const token = urlParams.get('token');
  
  if (token) {
    // Store token in localStorage for use across the app
    setAccessToken(token);
    
    // Remove token from URL to keep it clean (optional)
    const url = new URL(window.location);
    url.searchParams.delete('token');
    window.history.replaceState({}, '', url);
  }
});

// Expose method to set token programmatically
// This can be called from anywhere using $root.$setAuthToken(newToken)
const setAuthToken = (token) => {
  setAccessToken(token);
  if (authProviderRef.value) {
    authProviderRef.value.setToken(token);
  }
  window.location.reload(); // Reload to apply token
};

// Expose the method
defineExpose({
  setAuthToken
});
</script>

<template>
  <div>
    <router-view />
    <AuthProvider ref="authProviderRef" />
  </div>
</template>