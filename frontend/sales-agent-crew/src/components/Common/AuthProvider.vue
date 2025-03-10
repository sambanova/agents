<template>
  <div v-if="!hasToken" class="fixed inset-0 flex items-center justify-center bg-gray-800 bg-opacity-50 z-50">
    <div class="bg-white p-6 rounded-lg shadow-lg w-full max-w-md">
      <h2 class="text-xl font-bold mb-4">Authentication Required</h2>
      <p class="mb-4">Please provide an access token to continue.</p>
      
      <div class="mb-4">
        <input
          v-model="tokenInput"
          type="text"
          placeholder="Enter your access token"
          class="w-full p-2 border border-gray-300 rounded"
        />
      </div>
      
      <div class="flex justify-end">
        <button
          @click="setToken"
          class="px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
        >
          Continue
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { setAccessToken, getAccessToken } from '@/utils/auth';

const tokenInput = ref('');
const hasToken = computed(() => !!getAccessToken());

function setToken() {
  if (tokenInput.value.trim()) {
    setAccessToken(tokenInput.value.trim());
    window.location.reload(); // Reload to apply the token
  }
}

onMounted(() => {
  // Check URL for token parameter
  const urlParams = new URLSearchParams(window.location.search);
  const tokenParam = urlParams.get('token');
  
  if (tokenParam && !getAccessToken()) {
    // Set token from URL parameter
    setAccessToken(tokenParam);
    // Reload the page to apply the token
    window.location.reload();
  }
});

// Expose methods for parent components
defineExpose({
  setToken: (token) => {
    setAccessToken(token);
  }
});
</script>