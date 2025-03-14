<template>
  <div v-if="isOpen" class="fixed inset-0 z-50 overflow-y-auto">
    <div class="flex min-h-screen items-center justify-center p-4">
      <!-- Backdrop -->
      <div class="fixed inset-0 bg-black opacity-30" @click="close"></div>

      <!-- Modal -->
      <div class="relative w-full max-w-lg bg-white rounded-xl shadow-lg p-6">
        <div class="flex justify-between items-center mb-6">
          <h2 class="text-2xl font-semibold text-primary-brandTextPrimary">API Settings</h2>
          <button @click="close" class="text-primary-brandTextSecondary hover:text-gray-700">
            <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Error Message -->
        <div v-if="errorMessage" class="mb-4 p-3 bg-red-100 text-red-700 rounded">
          {{ errorMessage }}
        </div>

        <!-- Success Message -->
        <div v-if="successMessage" class="mb-4 p-3 bg-green-100 text-green-700 rounded">
          {{ successMessage }}
        </div>

        <div class="space-y-6">
          <!-- SambaNova API Key -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              SambaNova API Key <span v-if="missingKeys.sambanova" class="text-red-500 text-sm mt-1">(*Required Key)</span>
              <a 
                href="https://cloud.sambanova.ai/"
                target="_blank"
                class="text-primary-600 hover:text-primary-700 ml-2 text-sm"
              >
                Get Key →
              </a>
            </label>
            <div class="relative">
              <input
                v-model="sambanovaKey"
                :type="sambanovaKeyVisible ? 'text' : 'password'"
                placeholder="Enter your SambaNova API Key"
                class="block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:outline-none focus:ring-primary-500 focus:border-primary-500 pr-10"
              />
              <button 
                @click="toggleSambanovaKeyVisibility"
                class="absolute inset-y-0 right-0 px-3 flex items-center text-primary-brandTextSecondary hover:text-gray-700"
              >
                <svg v-if="sambanovaKeyVisible" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none"
                     viewBox="0 0 24 24" stroke="currentColor">
                  <!-- Eye Open Icon -->
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                        d="M2.458 12C3.732 7.943 7.519 5 12 5c4.481 0 8.268 2.943 9.542 7" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                        d="M2.458 12c1.508 4.057 5.294 7 9.542 7s8.034-2.943 9.542-7" />
                </svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none"
                     viewBox="0 0 24 24" stroke="currentColor">
                  <!-- Eye Closed Icon -->
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M13.875 18.825A9.952 9.952 0 0112 19.5c-5.247 0-9.645-4.028-9.985-9.227M9.642 9.642a3 3 0 104.715 4.715" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M3 3l18 18" />
                </svg>
              </button>
            </div>
            <!-- Save and Clear Buttons -->
            <div class="flex justify-end space-x-2 mt-2">
              <button 
                @click="clearSambanovaKey"
                class="px-3 py-1 text-sm bg-red-500 text-white rounded-md hover:bg-red-600 focus:outline-none"
              >
                Clear Key
              </button>
              <button 
                @click="saveSambanovaKey"
                class="px-3 py-1 text-sm bg-primary-600 text-white rounded-md hover:bg-primary-700 focus:outline-none"
              >
                Save Key
              </button>
            </div>
          </div>

          <!-- Exa API Key -->
          <div v-if="isUserKeysEnabled">
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Exa API Key <span v-if="missingKeys.exa" class="text-red-500 text-sm mt-1">(*Required Key)</span>

              <a 
                href="https://exa.ai/"
                target="_blank"
                class="text-primary-600 hover:text-primary-700 ml-2 text-sm"
              >
                Get Key →
              </a>
            </label>
            <div class="relative">
              <input
                v-model="exaKey"
                :type="exaKeyVisible ? 'text' : 'password'"
                placeholder="Enter your Exa API Key"
                class="block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:outline-none focus:ring-primary-500 focus:border-primary-500 pr-10"
              />
              <button 
                @click="toggleExaKeyVisibility"
                class="absolute inset-y-0 right-0 px-3 flex items-center text-primary-brandTextSecondary hover:text-gray-700"
              >
                <svg v-if="exaKeyVisible" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none"
                     viewBox="0 0 24 24" stroke="currentColor">
                  <!-- Eye Open Icon -->
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                        d="M2.458 12C3.732 7.943 7.519 5 12 5c4.481 0 8.268 2.943 9.542 7" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                        d="M2.458 12c1.508 4.057 5.294 7 9.542 7s8.034-2.943 9.542-7" />
                </svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none"
                     viewBox="0 0 24 24" stroke="currentColor">
                  <!-- Eye Closed Icon -->
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M13.875 18.825A9.952 9.952 0 0112 19.5c-5.247 0-9.645-4.028-9.985-9.227M9.642 9.642a3 3 0 104.715 4.715" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M3 3l18 18" />
                </svg>
              </button>
            </div>
            <!-- Save and Clear Buttons -->
            <div class="flex justify-end space-x-2 mt-2">
              <button 
                @click="clearExaKey"
                class="px-3 py-1 text-sm bg-red-500 text-white rounded-md hover:bg-red-600 focus:outline-none"
              >
                Clear Key
              </button>
              <button 
                @click="saveExaKey"
                class="px-3 py-1 text-sm bg-primary-600 text-white rounded-md hover:bg-primary-700 focus:outline-none"
              >
                Save Key
              </button>
            </div>
          </div>

          <!-- Serper API Key -->
          <div v-if="isUserKeysEnabled">
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Serper API Key <span v-if="missingKeys.serper" class="text-red-500 text-sm mt-1">(*Required Key)</span>
              <a 
                href="https://serper.dev/"
                target="_blank"
                class="text-primary-600 hover:text-primary-700 ml-2 text-sm"
              >
                Get Key →
              </a>
            </label>
            <div class="relative">
              <input
                v-model="serperKey"
                :type="serperKeyVisible ? 'text' : 'password'"
                placeholder="Enter your Serper API Key"
                class="block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:outline-none focus:ring-primary-500 focus:border-primary-500 pr-10"
              />
              <button 
                @click="toggleSerperKeyVisibility"
                class="absolute inset-y-0 right-0 px-3 flex items-center text-primary-brandTextSecondary hover:text-gray-700"
              >
                <!-- Eye icon -->
              </button>
            </div>
            <!-- Add Save and Clear Buttons for Serper -->
            <div class="flex justify-end space-x-2 mt-2">
              <button 
                @click="clearSerperKey"
                class="px-3 py-1 text-sm bg-red-500 text-white rounded-md hover:bg-red-600 focus:outline-none"
              >
                Clear Key
              </button>
              <button 
                @click="saveSerperKey"
                class="px-3 py-1 text-sm bg-primary-600 text-white rounded-md hover:bg-primary-700 focus:outline-none"
              >
                Save Key
              </button>
            </div>
          </div>

          <!-- Fireworks API Key -->
          <div v-if="isUserKeysEnabled" >
            <label class="block text-sm font-medium text-gray-700 mb-1">
              Fireworks API Key <span v-if="missingKeys.fireworks" class="text-red-500 text-sm mt-1">(*Required Key)</span>
              <a 
                href="https://fireworks.ai/"
                target="_blank"
                class="text-primary-600 hover:text-primary-700 ml-2 text-sm"
              >
                Get Key →
              </a>
            </label>
            <div class="relative">
              <input
                v-model="fireworksKey"
                :type="fireworksKeyVisible ? 'text' : 'password'"
                placeholder="Enter your Fireworks API Key"
                class="block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:outline-none focus:ring-primary-500 focus:border-primary-500 pr-10"
              />
              <button 
                @click="toggleFireworksKeyVisibility"
                class="absolute inset-y-0 right-0 px-3 flex items-center text-primary-brandTextSecondary hover:text-gray-700"
              >
                <!-- Eye icon -->
              </button>
            </div>
            <!-- Add Save and Clear Buttons for Serper -->
            <div class="flex justify-end space-x-2 mt-2">
              <button 
                @click="clearFireworksKey"
                class="px-3 py-1 text-sm bg-red-500 text-white rounded-md hover:bg-red-600 focus:outline-none"
              >
                Clear Key
              </button>
              <button 
                @click="saveFireworksKey"
                class="px-3 py-1 text-sm bg-primary-600 text-white rounded-md hover:bg-primary-700 focus:outline-none"
              >
                Save Key
              </button>
            </div>
          </div>

          <!-- Model Selection -->
          <div class="mt-6 border-t pt-4 flex flex-col">
            <label class="block text-sm font-medium text-gray-700 mb-2">
              Planner Model Selection
              <br>
              <span class="text-red-500 text-sm">
                (DeepSeek R1 8K Requires early access to API)
              </span>
            </label>
            <select
              v-model="selectedModel"
              @change="handleModelSelection"
              class="block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
            >
              <option value="llama-3.3-70b">Meta-Llama-3.3-70B-Instruct - 128K</option>
              <option value="deepseek-r1">DeepSeek-R1 - 8K</option>
              <option value="llama-3.1-tulu-3-405b">Llama-3.1-Tulu-3-405B - 16K</option>
            </select>
          </div>

          <div class="mt-6 border-t flex flex-row justify-between pt-4">
            <div class="flex flex-col items-center">
            <label class="block text-sm   font-medium text-gray-700 mb-2">
              Select provider
            </label>
            <SelectProvider  v-model:selectedOption="selectedOption" />
          </div>
          <div class="mt-6 flex flex-row items-center pt-4">
            <a class="text-sm underline" href="https://community.sambanova.ai/c/agents/87" target="_blank">FAQ (SN Community)</a>
            </div>
          </div>
          
          <!-- Delete Account Section -->
          <div class="mt-8 pt-6 border-t border-gray-200">
            <div class="relative">
              <!-- Empty div to match the structure of other sections -->
            </div>
            <div class="flex justify-end space-x-2 mt-2">
              <button 
                @click="confirmDeleteAccount" 
                class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
              >
                Delete Account
              </button>
            </div>
          </div>
        </div>

        <!-- Delete Account Confirmation Modal -->
        <div v-if="showDeleteConfirmation" class="fixed inset-0 z-50 overflow-y-auto" style="background-color: rgba(0, 0, 0, 0.5);">
          <div class="flex min-h-screen items-center justify-center p-4">
            <div class="relative w-full max-w-md bg-white rounded-lg shadow-lg p-6">
              <div class="text-center">
                <h3 class="mt-4 text-lg font-medium text-gray-900">Confirm Data Deletion</h3>
                <p class="mt-2 text-sm text-gray-500">
                  Are you sure you want to delete all your data? This will permanently delete all your conversations, documents, and API keys. This action cannot be undone and will log you out.
                </p>
                <div class="mt-6 flex justify-center space-x-4">
                  <button 
                    @click="cancelDeleteAccount" 
                    class="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md shadow-sm text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                  >
                    Cancel
                  </button>
                  <button 
                    @click="executeDeleteAccount" 
                    class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                    :disabled="isDeleting"
                  >
                    <svg v-if="isDeleting" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    {{ isDeleting ? 'Deleting...' : 'Delete Data' }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { ref, watch, defineProps, defineExpose, defineEmits, onMounted, computed,inject } from 'vue'
import { useAuth } from '@clerk/vue'
import { encryptKey, decryptKey } from '../utils/encryption'
import axios from 'axios'
import emitterMitt from '@/utils/eventBus.js';
import SelectProvider from '@/components/ChatMain/SelectProvider.vue'

const selectedOption = inject('selectedOption')

const isUserKeysEnabled = computed(() => {
  return import.meta.env.VITE_ENABLE_USER_KEYS === 'true'
})




const props = defineProps({
  provider: String, // Current provider name passed from parent
})

const emit = defineEmits(['keysUpdated'])

const { userId } = useAuth()

const isOpen = ref(false)
const sambanovaKey = ref('')
const exaKey = ref('')
const serperKey = ref('')
const fireworksKey = ref('')
const errorMessage = ref('')
const successMessage = ref('')
const selectedModel = ref('llama-3.3-70b')
// Key visibility controls
const sambanovaKeyVisible = ref(false)
const exaKeyVisible = ref(false)
const serperKeyVisible = ref(false)
const fireworksKeyVisible = ref(false)

// Missing keys state for validation messages
const missingKeys = ref({
  exaKey: false,
  serperKey: false,
  sambanovaKey: false,
  fireworksKey: false
})


// Load keys on mount and check if modal should be open
onMounted(async () => {
  await loadKeys()
 await checkRequiredKeys() // Ensure modal opens if needed
  emitterMitt.on('check-keys', checkRequiredKeys);
  emitterMitt.emit('keys-updated',  missingKeys.value );

})


// Watch for provider changes and check required keys dynamically
watch(() => props.provider, async () => {
  await checkRequiredKeys()
  updateAndCallEvents()
})
watch([exaKey, serperKey, sambanovaKey, fireworksKey], () => {
  // checkRequiredKeys()
})

// ✅ Function to load saved keys
const loadKeys = async () => {
  let savedExaKey = '';
  let savedSerperKey = '';
  let savedFireworksKey = '';

  console.log(isUserKeysEnabled.value,isUserKeysEnabled.value)
  if (!isUserKeysEnabled.value) {

    

  } else {
    savedExaKey = localStorage.getItem(`exa_key_${userId.value}`);
    savedSerperKey = localStorage.getItem(`serper_key_${userId.value}`);
    savedFireworksKey = localStorage.getItem(`fireworks_key_${userId.value}`);
  }

  try {
    const savedModel = localStorage.getItem(`selected_model_${userId.value}`);
    const savedSambanovaKey = localStorage.getItem(`sambanova_key_${userId.value}`);
    console.log("Try savedExaKey,savedSerperKey,savedFireworksKey",savedExaKey,savedSerperKey,savedFireworksKey)

    sambanovaKey.value = savedSambanovaKey ? await decryptKey(savedSambanovaKey) : '';
    exaKey.value = savedExaKey 
      ? (!isUserKeysEnabled.value ? savedExaKey : await decryptKey(savedExaKey))
      : '';
    serperKey.value = savedSerperKey 
      ? (!isUserKeysEnabled.value ? savedSerperKey : await decryptKey(savedSerperKey))
      : '';
    fireworksKey.value = savedFireworksKey 
      ? (!isUserKeysEnabled.value ? savedFireworksKey : await decryptKey(savedFireworksKey))
      : '';


    // If no model was saved, save the default
    if (!savedModel) {
      localStorage.setItem(`selected_model_${userId.value}`, selectedModel.value);
    } else {
      selectedModel.value = savedModel;
    }
  } catch (error) {
    console.error('Failed to load keys:', error);
    errorMessage.value = 'Failed to load saved keys';
  }
}

// Toggle key visibility
const toggleSambanovaKeyVisibility = () => {
  sambanovaKeyVisible.value = !sambanovaKeyVisible.value
}

const toggleExaKeyVisibility = () => {
  exaKeyVisible.value = !exaKeyVisible.value
}

const toggleSerperKeyVisibility = () => {
  serperKeyVisible.value = !serperKeyVisible.value
}

const toggleFireworksKeyVisibility = () => {
  fireworksKeyVisible.value = !fireworksKeyVisible.value
}

const handleModelSelection = () => {
  localStorage.setItem(`selected_model_${userId.value}`, selectedModel.value)
  emit('keysUpdated')
}
// ✅ Function to check if required keys are missing
const checkRequiredKeys = () => {


  missingKeys.value = {
    exa: !exaKey.value&&isUserKeysEnabled.value,
    serper: !serperKey.value&&isUserKeysEnabled.value,
    sambanova: props.provider === 'sambanova' && !sambanovaKey.value,
    fireworks: props.provider === 'fireworks' && !fireworksKey.value&&isUserKeysEnabled.value
  }

  isOpen.value = Object.values(missingKeys.value).some((missing) => missing)
  emitterMitt.emit('keys-updated',  missingKeys.value );

}

// ✅ Function to manually open modal
const openModal = () => {
  isOpen.value = true
}

// ✅ Function to manually close modal
const close = () => {
  isOpen.value = false
  errorMessage.value = ''
  successMessage.value = ''
}

// Save functions for individual keys
const saveSambanovaKey = async () => {
  try {
    if (!sambanovaKey.value) {
      errorMessage.value = 'SambaNova API key cannot be empty!'
      return
    }
    const encryptedKey = await encryptKey(sambanovaKey.value)
    localStorage.setItem(`sambanova_key_${userId.value}`, encryptedKey)
    successMessage.value = 'SambaNova API key saved successfully!'
    await updateBackendKeys()
    updateAndCallEvents()


  } catch (error) {
    console.error('Failed to save SambaNova key:', error)
    errorMessage.value = 'Failed to save SambaNova API key'
  } finally {
    clearMessagesAfterDelay()
  }
}

const clearSambanovaKey =async () => {

  try{

 
  localStorage.removeItem(`sambanova_key_${userId.value}`)
}catch(e){
  console.log("samabanova clear ",e)
}
  sambanovaKey.value = ''
  successMessage.value = 'SambaNova API key cleared successfully!'
  await updateBackendKeys()
  updateAndCallEvents()
  clearMessagesAfterDelay()
  emitterMitt.emit('keys-updated',  missingKeys.value );

}

const saveExaKey = async () => {
  try {
    if (!exaKey.value) {
      errorMessage.value = 'Exa API key cannot be empty!'
      return
    }
    const encryptedKey = await encryptKey(exaKey.value)
    localStorage.setItem(`exa_key_${userId.value}`, encryptedKey)
    successMessage.value = 'Exa API key saved successfully!'
    await updateBackendKeys()
    updateAndCallEvents()
  } catch (error) {
    console.error('Failed to save Exa key:', error)
    errorMessage.value = 'Failed to save Exa API key'
  } finally {
    clearMessagesAfterDelay()
  }
}

const clearExaKey =async () => {
  localStorage.removeItem(`exa_key_${userId.value}`)
  exaKey.value = ''
  successMessage.value = 'Exa API key cleared successfully!'
 await  updateBackendKeys()
 
  clearMessagesAfterDelay()
  updateAndCallEvents()

}

const saveSerperKey = async () => {
  try {
    if (!serperKey.value) {
      errorMessage.value = 'Serper API key cannot be empty!'
      return
    }
    const encryptedKey = await encryptKey(serperKey.value)
    localStorage.setItem(`serper_key_${userId.value}`, encryptedKey)
    successMessage.value = 'Serper API key saved successfully!'
    await updateBackendKeys()
   
    updateAndCallEvents()

  } catch (error) {
    console.error('Failed to save Serper key:', error)
    errorMessage.value = 'Failed to save Serper API key'
  } finally {
    clearMessagesAfterDelay()
  }
}

// Add the updateBackendKeys function
const updateBackendKeys = async () => {
  try {
    const url = `${import.meta.env.VITE_API_URL}/set_api_keys`
    const postParams = {
      sambanova_key: sambanovaKey.value || '',
      serper_key: serperKey.value || '',
      exa_key: exaKey.value || '',
      fireworks_key: fireworksKey.value || ''
    }

    const response = await axios.post(url, postParams, {
      headers: {
        'Authorization': `Bearer ${await window.Clerk.session.getToken()}`

      }
    })
    if (response.status === 200) {
      console.log('API keys updated in backend successfully')
    }



  } catch (error) {
    console.error('Error updating API keys in backend:', error)
    errorMessage.value = 'Failed to update API keys in backend'
  }
}

const saveFireworksKey = async () => {
  try {
    if (!fireworksKey.value) {
      errorMessage.value = 'Fireworks API key cannot be empty!'
      return
    }
    const encryptedKey = await encryptKey(fireworksKey.value)
    localStorage.setItem(`fireworks_key_${userId.value}`, encryptedKey)
    successMessage.value = 'Fireworks API key saved successfully!'
    await updateBackendKeys()
    updateAndCallEvents()

  } catch (error) {
    console.error('Failed to save Fireworks key:', error)
    errorMessage.value = 'Failed to save Fireworks API key'
  } finally {
    clearMessagesAfterDelay()
  }
}

const clearMessagesAfterDelay = () => {
  setTimeout(() => {
    errorMessage.value = ''
    successMessage.value = ''
  }, 3000)

  
}
const clearFireworksKey = async() => {
  localStorage.removeItem(`fireworks_key_${userId.value}`)
  fireworksKey.value = ''
  successMessage.value = 'Fireworks API key cleared successfully!'
  await updateBackendKeys()
  
  clearMessagesAfterDelay()
  updateAndCallEvents()

}

const clearSerperKey = async () => {
  localStorage.removeItem(`serper_key_${userId.value}`)
  serperKey.value = ''
  successMessage.value = 'Serper API key cleared successfully!'
  await updateBackendKeys()
  updateAndCallEvents()
  clearMessagesAfterDelay()

}

const updateAndCallEvents=async()=>{

  await checkRequiredKeys()

  emit('keysUpdated')
  emitterMitt.emit('keys-updated',  missingKeys.value );

}

// ✅ Expose methods for parent component
defineExpose({
  openModal,
  checkRequiredKeys,
  exaKey: exaKey.value,
    serperKey: serperKey.value,
    fireworksKey: fireworksKey.value,
    selectedModel: selectedModel.value
})

// Delete account functionality
const showDeleteConfirmation = ref(false)
const isDeleting = ref(false)

const confirmDeleteAccount = () => {
  showDeleteConfirmation.value = true
}

const cancelDeleteAccount = () => {
  showDeleteConfirmation.value = false
}

const executeDeleteAccount = async () => {
  try {
    isDeleting.value = true
    
    // Call the delete user data endpoint
    const response = await axios.delete(`${import.meta.env.VITE_API_URL}/user/data`, {
      headers: {
        'Authorization': `Bearer ${await window.Clerk.session.getToken()}`
      }
    })
    
    if (response.status === 200) {
      // Clear local storage
      const keysToRemove = [
        `sambanova_key_${userId.value}`,
        `exa_key_${userId.value}`,
        `serper_key_${userId.value}`,
        `fireworks_key_${userId.value}`
      ]
      
      keysToRemove.forEach(key => localStorage.removeItem(key))
      
      // Show success message briefly
      successMessage.value = 'Account data deleted successfully. Logging out...'
      
      // Log out the user after a short delay
      setTimeout(async () => {
        await window.Clerk.signOut()
        // Redirect to login page
        window.location.href = '/login'
      }, 2000)
    }
  } catch (error) {
    console.error('Error deleting account data:', error)
    errorMessage.value = 'Failed to delete account data. Please try again.'
    showDeleteConfirmation.value = false
  } finally {
    isDeleting.value = false
  }
}
</script>
