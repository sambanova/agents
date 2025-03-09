<template>
  <div>
    <button
      @click="showDialog = true"
      class="p-2 text-gray-600 hover:text-gray-900 transition-colors"
    >
      <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 15V17M6 9V21H18V9M6 9H18M6 9C6 5.5 8.5 3 12 3C15.5 3 18 5.5 18 9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </button>

    <!-- Token Dialog -->
    <div v-if="showDialog" class="fixed inset-0 z-50 overflow-y-auto">
      <div class="flex min-h-screen items-center justify-center p-4">
        <!-- Backdrop -->
        <div class="fixed inset-0 bg-black opacity-30" @click="showDialog = false"></div>

        <!-- Modal -->
        <div class="relative w-full max-w-md bg-white rounded-xl shadow-lg p-6">
          <div class="flex justify-between items-center mb-6">
            <h2 class="text-xl font-bold text-gray-900">Set Access Token</h2>
            <button @click="showDialog = false" class="text-gray-500 hover:text-gray-700">
              <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Access Token
            </label>
            <textarea
              v-model="tokenInput"
              placeholder="Enter your access token"
              class="w-full p-2 border border-gray-300 rounded-md h-32"
            ></textarea>
          </div>

          <div class="flex justify-end space-x-2">
            <button
              @click="showDialog = false"
              class="px-4 py-2 text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300"
            >
              Cancel
            </button>
            <button
              @click="setToken"
              class="px-4 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700"
            >
              Save Token
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { setAccessToken, getAccessToken } from '@/utils/auth';

const showDialog = ref(false);
const tokenInput = ref(getAccessToken() || '');

function setToken() {
  if (tokenInput.value.trim()) {
    setAccessToken(tokenInput.value.trim());
    showDialog.value = false;
    window.location.reload(); // Reload to apply the token
  }
}
</script>