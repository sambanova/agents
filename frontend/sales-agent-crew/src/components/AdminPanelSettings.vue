<template>
  <div>
    <!-- Check VITE env variable first, then backend status -->
    <div v-if="!isViteEnabled" class="text-center py-8">
      <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
      </svg>
      <h3 class="mt-2 text-sm font-medium text-gray-900">Admin Panel Not Available</h3>
      <p class="mt-1 text-sm text-gray-500">
        The admin panel feature is not enabled in this environment.
      </p>
    </div>

    <div v-else-if="!isBackendEnabled" class="text-center py-8">
      <svg class="mx-auto h-12 w-12 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
      <h3 class="mt-2 text-sm font-medium text-gray-900">Backend Configuration Required</h3>
      <p class="mt-1 text-sm text-gray-500">
        The admin panel requires backend configuration. Please set SHOW_ADMIN_PANEL=true in the backend environment.
      </p>
    </div>

    <div v-else class="admin-panel">
      <div class="admin-header">
        <h2 class="text-2xl font-bold mb-4">
          <svg class="inline-block w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          LLM Provider Configuration
        </h2>
        <div v-if="hasUnsavedChanges" class="text-sm text-orange-600">
          <svg class="inline-block w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
          </svg>
          You have unsaved changes
        </div>
      </div>

      <!-- Provider Selection -->
      <div class="mb-6">
        <label class="block text-sm font-medium text-gray-700 mb-2">Default Provider</label>
        <select
          v-model="selectedProvider"
          @change="handleProviderChange"
          class="block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
        >
          <option v-for="provider in providers" :key="provider" :value="provider">
            {{ formatProviderName(provider) }}
          </option>
        </select>
      </div>

      <!-- API Keys Management -->
      <div class="mb-6">
        <h3 class="text-lg font-medium text-gray-900 mb-3">API Keys</h3>
        <div class="space-y-4">
          <div v-for="provider in providers" :key="provider">
            <label class="block text-sm font-medium text-gray-700 mb-1">
              {{ formatProviderName(provider) }} API Key
              <span v-if="provider === selectedProvider" class="text-xs text-green-600 ml-2">(Active)</span>
            </label>
            <div class="relative">
              <input
                v-model="apiKeys[provider]"
                :type="apiKeyVisibility[provider] ? 'text' : 'password'"
                :placeholder="`Enter ${formatProviderName(provider)} API key`"
                class="block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:outline-none focus:ring-primary-500 focus:border-primary-500 pr-20"
              />
              <div class="absolute inset-y-0 right-0 flex items-center">
                <button
                  @click="toggleKeyVisibility(provider)"
                  class="px-3 text-gray-400 hover:text-gray-600"
                >
                  <svg v-if="apiKeyVisibility[provider]" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.519 5 12 5c4.481 0 8.268 2.943 9.542 7-1.274 4.057-5.061 7-9.542 7-4.481 0-8.268-2.943-9.542-7z" />
                  </svg>
                  <svg v-else class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A9.952 9.952 0 0112 19.5c-5.247 0-9.645-4.028-9.985-9.227M9.642 9.642a3 3 0 104.715 4.715M3 3l18 18" />
                  </svg>
                </button>
                <button
                  v-if="apiKeys[provider]"
                  @click="testProvider(provider)"
                  :disabled="testingProvider === provider"
                  class="px-3 text-blue-600 hover:text-blue-800 disabled:opacity-50"
                >
                  <svg v-if="testingProvider === provider" class="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                  </svg>
                  <span v-else>Test</span>
                </button>
              </div>
            </div>
            <div v-if="testResults[provider]" class="mt-2 text-sm" :class="testResults[provider].success ? 'text-green-600' : 'text-red-600'">
              {{ testResults[provider].message }}
            </div>
          </div>
        </div>
      </div>

      <!-- Model Configuration for Tasks -->
      <div class="mb-6">
        <h3 class="text-lg font-medium text-gray-900 mb-3">Task-Specific Models</h3>
        <div class="space-y-3">
          <div v-for="task in tasks" :key="task.id" class="flex items-center space-x-3">
            <div class="flex-1">
              <label class="block text-sm font-medium text-gray-700">{{ task.name }}</label>
            </div>
            <div class="flex-1">
              <select
                v-model="taskModels[task.id]"
                @change="handleTaskModelChange(task.id)"
                class="block w-full border border-gray-300 rounded-md shadow-sm p-1 text-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
              >
                <option :value="null">Use Default</option>
                <optgroup v-for="provider in providers" :key="provider" :label="formatProviderName(provider)">
                  <option v-for="model in providerModels[provider]" :key="`${provider}-${model.id}`" :value="`${provider}:${model.id}`">
                    {{ model.name }}
                  </option>
                </optgroup>
              </select>
            </div>
          </div>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="flex justify-between">
        <button
          @click="resetConfiguration"
          class="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50"
        >
          Reset to Defaults
        </button>
        <div class="space-x-2">
          <button
            @click="cancelChanges"
            v-if="hasUnsavedChanges"
            class="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            @click="saveConfiguration"
            :disabled="!hasUnsavedChanges || isSaving"
            class="px-4 py-2 bg-primary-brandColor text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
          >
            <span v-if="isSaving">Saving...</span>
            <span v-else>Save Changes</span>
          </button>
        </div>
      </div>

      <!-- Status Messages -->
      <div v-if="statusMessage" class="mt-4 p-3 rounded-md" :class="statusMessage.type === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'">
        {{ statusMessage.text }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, inject } from 'vue'
import axios from 'axios'
import { useAuth0 } from '@auth0/auth0-vue'

const emit = defineEmits(['configuration-updated', 'api-keys-updated'])

const { getAccessTokenSilently } = useAuth0()

// Check VITE environment variable first
const isViteEnabled = ref(import.meta.env.VITE_SHOW_ADMIN_PANEL === 'true')
const isBackendEnabled = ref(false)

// API Base URL
const apiBaseUrl = computed(() => import.meta.env.VITE_API_URL || '/api')

// State
const providers = ref(['sambanova', 'fireworks', 'together'])
const selectedProvider = ref('sambanova')
const apiKeys = ref({
  sambanova: '',
  fireworks: '',
  together: ''
})
const apiKeyVisibility = ref({
  sambanova: false,
  fireworks: false,
  together: false
})
const taskModels = ref({})
const tasks = ref([])
const providerModels = ref({
  sambanova: [],
  fireworks: [],
  together: []
})
const originalConfig = ref(null)
const testingProvider = ref(null)
const testResults = ref({})
const isSaving = ref(false)
const statusMessage = ref(null)

// Computed
const hasUnsavedChanges = computed(() => {
  if (!originalConfig.value) return false

  return (
    selectedProvider.value !== originalConfig.value.default_provider ||
    JSON.stringify(taskModels.value) !== JSON.stringify(originalConfig.value.task_models || {}) ||
    Object.keys(apiKeys.value).some(p => apiKeys.value[p] !== (originalConfig.value.api_keys?.[p] || ''))
  )
})

// Methods
const formatProviderName = (provider) => {
  const names = {
    sambanova: 'SambaNova',
    fireworks: 'Fireworks AI',
    together: 'Together AI'
  }
  return names[provider] || provider
}

const toggleKeyVisibility = (provider) => {
  apiKeyVisibility.value[provider] = !apiKeyVisibility.value[provider]
}

const checkAdminStatus = async () => {
  if (!isViteEnabled.value) {
    return
  }

  try {
    const token = await getAccessTokenSilently()
    const response = await axios.get(`${apiBaseUrl.value}/admin/status`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    isBackendEnabled.value = response.data.enabled
  } catch (error) {
    console.error('Failed to check admin status:', error)
    isBackendEnabled.value = false
  }
}

const loadConfiguration = async () => {
  try {
    const token = await getAccessTokenSilently()

    // Load configuration
    const response = await axios.get(`${apiBaseUrl.value}/admin/config`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })

    const config = response.data
    selectedProvider.value = config.default_provider || 'sambanova'

    // Also update the injected selectedOption from MainLayout
    const selectedOption = inject('selectedOption')
    if (selectedOption) {
      const providerMapping = {
        'sambanova': { label: 'SambaNova', value: 'sambanova' },
        'fireworks': { label: 'Fireworks AI', value: 'fireworks' },
        'together': { label: 'Together AI', value: 'together' }
      }

      if (providerMapping[selectedProvider.value]) {
        selectedOption.value = providerMapping[selectedProvider.value]
        console.log('Updated selectedOption from loaded config:', selectedOption.value)
      }
    }

    // Also load API keys
    try {
      const keysResponse = await axios.get(`${apiBaseUrl.value}/get_api_keys`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (keysResponse.data) {
        apiKeys.value = {
          sambanova: keysResponse.data.sambanova_key || '',
          fireworks: keysResponse.data.fireworks_key || '',
          together: keysResponse.data.together_key || ''
        }
        console.log('Loaded API keys:', {
          sambanova: apiKeys.value.sambanova ? 'present' : 'empty',
          fireworks: apiKeys.value.fireworks ? 'present' : 'empty',
          together: apiKeys.value.together ? 'present' : 'empty'
        })
      }
    } catch (keyError) {
      console.log('Could not load API keys:', keyError.message)
    }

    // Initialize task models with defaults from tasks list first
    tasks.value.forEach(task => {
      if (task.provider && task.model) {
        taskModels.value[task.id] = `${task.provider}:${task.model}`
      }
    })

    // Then override with any user-specific configurations
    if (config.task_models) {
      Object.entries(config.task_models).forEach(([taskId, taskConfig]) => {
        if (taskConfig.provider && taskConfig.model) {
          taskModels.value[taskId] = `${taskConfig.provider}:${taskConfig.model}`
        }
      })
    }

    // Store original config for change detection (after loading API keys)
    originalConfig.value = JSON.parse(JSON.stringify({
      default_provider: selectedProvider.value,
      task_models: taskModels.value,
      api_keys: apiKeys.value  // Now includes loaded API keys
    }))

  } catch (error) {
    console.error('Failed to load configuration:', error)
    showStatus('Failed to load configuration', 'error')
  }
}

const loadProviders = async () => {
  try {
    const token = await getAccessTokenSilently()
    const response = await axios.get(`${apiBaseUrl.value}/admin/providers`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    providers.value = response.data
  } catch (error) {
    console.error('Failed to load providers:', error)
  }
}

const loadModels = async () => {
  for (const provider of providers.value) {
    try {
      const token = await getAccessTokenSilently()
      const response = await axios.get(`${apiBaseUrl.value}/admin/models/${provider}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })
      providerModels.value[provider] = response.data.models
    } catch (error) {
      console.error(`Failed to load models for ${provider}:`, error)
      providerModels.value[provider] = []
    }
  }
}

const loadTasks = async () => {
  try {
    const token = await getAccessTokenSilently()
    const response = await axios.get(`${apiBaseUrl.value}/admin/tasks`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })
    tasks.value = response.data
  } catch (error) {
    console.error('Failed to load tasks:', error)
  }
}

const handleProviderChange = () => {
  // When provider changes, automatically map models to equivalent ones
  mapModelsToProvider(selectedProvider.value)
}

const handleTaskModelChange = () => {
  // Task model change handled by v-model
}

const testProvider = async (provider) => {
  if (!apiKeys.value[provider]) {
    showStatus(`Please enter an API key for ${formatProviderName(provider)}`, 'error')
    return
  }

  testingProvider.value = provider
  testResults.value[provider] = null

  try {
    const token = await getAccessTokenSilently()
    const response = await axios.post(`${apiBaseUrl.value}/admin/test-connection`, {
      provider: provider,
      api_key: apiKeys.value[provider]
    }, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })

    testResults.value[provider] = response.data
  } catch (error) {
    testResults.value[provider] = {
      success: false,
      message: error.response?.data?.error || 'Connection test failed'
    }
  } finally {
    testingProvider.value = null
  }
}

const saveConfiguration = async () => {
  isSaving.value = true

  try {
    // Prepare task models in the correct format
    const formattedTaskModels = {}
    Object.entries(taskModels.value).forEach(([taskId, value]) => {
      if (value && value.includes(':')) {
        const [provider, model] = value.split(':')
        formattedTaskModels[taskId] = { provider, model }
      }
    })

    const token = await getAccessTokenSilently()

    // Debug log what we're sending
    console.log('Saving configuration with API keys:', {
      sambanova: apiKeys.value.sambanova ? 'present' : 'empty',
      fireworks: apiKeys.value.fireworks ? 'present' : 'empty',
      together: apiKeys.value.together ? 'present' : 'empty'
    })

    const response = await axios.post(`${apiBaseUrl.value}/admin/config`, {
      default_provider: selectedProvider.value,
      task_models: formattedTaskModels,
      api_keys: apiKeys.value
    }, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })

    if (response.data.success) {
      originalConfig.value = JSON.parse(JSON.stringify({
        default_provider: selectedProvider.value,
        task_models: taskModels.value,
        api_keys: apiKeys.value
      }))

      showStatus('Configuration saved successfully', 'success')
      emit('configuration-updated', response.data.config)
      emit('api-keys-updated', apiKeys.value)
    }
  } catch (error) {
    console.error('Failed to save configuration:', error)
    showStatus(error.response?.data?.error || 'Failed to save configuration', 'error')
  } finally {
    isSaving.value = false
  }
}

const resetConfiguration = async () => {
  if (!confirm('Reset all settings to defaults? This will clear your custom configuration.')) {
    return
  }

  try {
    const token = await getAccessTokenSilently()
    const response = await axios.delete(`${apiBaseUrl.value}/admin/config`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })

    if (response.data.success) {
      await loadConfiguration()

      // Update the injected selectedOption to reflect the default provider
      const selectedOption = inject('selectedOption')
      if (selectedOption) {
        const providerMapping = {
          'sambanova': { label: 'SambaNova', value: 'sambanova' },
          'fireworks': { label: 'Fireworks AI', value: 'fireworks' },
          'together': { label: 'Together AI', value: 'together' }
        }

        // After reset, it should be back to sambanova (default)
        selectedOption.value = providerMapping['sambanova']
        console.log('Reset selectedOption to default:', selectedOption.value)
      }

      showStatus('Configuration reset to defaults', 'success')

      // Emit configuration update to notify other components
      emit('configuration-updated', response.data.config)
    }
  } catch (error) {
    console.error('Failed to reset configuration:', error)
    showStatus('Failed to reset configuration', 'error')
  }
}

const cancelChanges = () => {
  if (!originalConfig.value) return

  selectedProvider.value = originalConfig.value.default_provider
  taskModels.value = { ...originalConfig.value.task_models }
  apiKeys.value = { ...originalConfig.value.api_keys }
}

const showStatus = (text, type) => {
  statusMessage.value = { text, type }
  setTimeout(() => {
    statusMessage.value = null
  }, 3000)
}

// Model mapping for cross-provider switching
// Based on actual models used in production
const modelMappings = {
  'deepseek-v3': {
    'sambanova': 'DeepSeek-V3-0324',
    'fireworks': 'accounts/fireworks/models/deepseek-v3-0324',
    'together': 'deepseek-ai/DeepSeek-V3'
  },
  'deepseek-r1-distill-70b': {
    'sambanova': 'DeepSeek-R1-Distill-Llama-70B',
    'fireworks': 'accounts/fireworks/models/deepseek-r1',
    'together': 'deepseek-ai/DeepSeek-R1-Distill-Llama-70B'
  },
  'deepseek-r1': {
    'sambanova': 'DeepSeek-R1-0528',
    'fireworks': 'accounts/fireworks/models/deepseek-r1',
    'together': 'deepseek-ai/DeepSeek-R1'
  },
  'llama-3.3-70b': {
    'sambanova': 'Meta-Llama-3.3-70B-Instruct',
    'fireworks': 'accounts/fireworks/models/llama-v3p3-70b-instruct',
    'together': 'meta-llama/Llama-3.3-70B-Instruct-Turbo'
  },
  'llama-4-maverick': {
    'sambanova': 'Llama-4-Maverick-17B-128E-Instruct',
    'fireworks': 'accounts/fireworks/models/llama-v4-maverick',
    'together': 'meta-llama/Llama-4-Maverick'
  },
  'llama-3.1-8b': {
    'sambanova': 'Meta-Llama-3.1-8B-Instruct',
    'fireworks': 'accounts/fireworks/models/llama-v3p1-8b-instruct',
    'together': 'meta-llama/Llama-3.1-8B-Instruct-Turbo'
  },
  'qwen3-32b': {
    'sambanova': 'Qwen3-32B',
    'fireworks': 'accounts/fireworks/models/qwen2.5-32b-instruct',
    'together': 'Qwen/Qwen2.5-32B-Instruct'
  }
}

const mapModelsToProvider = (newProvider) => {
  // Map each task's model to the equivalent in the new provider
  const updatedTaskModels = {}

  Object.entries(taskModels.value).forEach(([taskId, currentSelection]) => {
    if (currentSelection && currentSelection.includes(':')) {
      const [currentProvider, currentModel] = currentSelection.split(':')

      // Find which model key this corresponds to
      let mappedModel = null
      for (const [, mappings] of Object.entries(modelMappings)) {
        if (mappings[currentProvider] === currentModel) {
          // Found the model key, now get the equivalent for new provider
          mappedModel = mappings[newProvider]
          break
        }
      }

      // If we found a mapping, use it; otherwise keep the same model ID
      if (mappedModel) {
        updatedTaskModels[taskId] = `${newProvider}:${mappedModel}`
      } else {
        // Try to keep the same model if it exists in the new provider
        const newProviderModels = providerModels.value[newProvider] || []
        const modelExists = newProviderModels.some(m => m.id === currentModel)
        if (modelExists) {
          updatedTaskModels[taskId] = `${newProvider}:${currentModel}`
        } else {
          // Clear the selection if model doesn't exist in new provider
          updatedTaskModels[taskId] = null
        }
      }
    }
  })

  // Update all task models at once
  Object.assign(taskModels.value, updatedTaskModels)
}

const loadStoredApiKeys = () => {
  // Load API keys from localStorage if available
  const storedKeys = localStorage.getItem('llm_api_keys')
  if (storedKeys) {
    try {
      const parsed = JSON.parse(storedKeys)
      Object.assign(apiKeys.value, parsed)
    } catch (error) {
      console.error('Failed to parse stored API keys:', error)
    }
  }
}

// Watch for API key changes and store them
watch(apiKeys, (newKeys) => {
  localStorage.setItem('llm_api_keys', JSON.stringify(newKeys))
}, { deep: true })

// Initialize
onMounted(async () => {
  if (isViteEnabled.value) {
    await checkAdminStatus()
    if (isBackendEnabled.value) {
      loadStoredApiKeys()
      // Load providers and models first, then configuration
      await Promise.all([
        loadProviders(),
        loadModels(),
        loadTasks()
      ])
      // Load configuration after models are available
      await loadConfiguration()
    }
  }
})
</script>

<style scoped>
.admin-panel {
  max-width: 800px;
  margin: 0 auto;
}

.admin-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}
</style>