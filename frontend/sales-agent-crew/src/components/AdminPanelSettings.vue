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
        <div class="flex items-center space-x-2">
          <button
            @click="viewMode = viewMode === 'simple' ? 'advanced' : 'simple'"
            class="text-sm text-blue-600 hover:text-blue-800"
          >
            {{ viewMode === 'simple' ? 'Advanced Mode' : 'Simple Mode' }}
          </button>
          <div v-if="hasUnsavedChanges" class="text-sm text-orange-600">
            <svg class="inline-block w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
            </svg>
            You have unsaved changes
          </div>
        </div>
      </div>

      <!-- Tab Navigation -->
      <div class="border-b border-gray-200 mb-6">
        <nav class="-mb-px flex space-x-8">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            @click="activeTab = tab.id"
            :class="[
              'py-2 px-1 border-b-2 font-medium text-sm',
              activeTab === tab.id
                ? 'border-primary-brandColor text-primary-brandColor'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            ]"
          >
            {{ tab.label }}
          </button>
        </nav>
      </div>

      <!-- Provider Configuration Tab -->
      <div v-if="activeTab === 'providers'" class="space-y-6">
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

        <!-- Provider Base URLs -->
        <div v-if="viewMode === 'advanced'">
          <h3 class="text-lg font-medium text-gray-900 mb-3">Provider Base URLs</h3>
          <div class="space-y-4">
            <div v-for="provider in providers" :key="provider">
              <label class="block text-sm font-medium text-gray-700 mb-1">
                {{ formatProviderName(provider) }} Base URL
                <span v-if="provider === selectedProvider" class="text-xs text-green-600 ml-2">(Active)</span>
              </label>
              <div class="flex space-x-2">
                <input
                  v-model="providerBaseUrls[provider]"
                  type="url"
                  :placeholder="getDefaultBaseUrl(provider)"
                  class="flex-1 block border border-gray-300 rounded-md shadow-sm p-2 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                />
                <button
                  @click="resetBaseUrl(provider)"
                  class="px-3 py-2 text-sm text-gray-600 hover:text-gray-800"
                  title="Reset to default"
                >
                  <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
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

        <!-- Custom Models -->
        <div v-if="viewMode === 'advanced'">
          <h3 class="text-lg font-medium text-gray-900 mb-3">Custom Models</h3>
          <div class="space-y-4">
            <div v-for="provider in providers" :key="provider" class="border rounded-lg p-4">
              <h4 class="font-medium text-sm text-gray-700 mb-2">{{ formatProviderName(provider) }}</h4>

              <!-- List existing custom models -->
              <div v-if="customModels[provider] && Object.keys(customModels[provider]).length > 0" class="mb-3 space-y-2">
                <div v-for="(model, modelId) in customModels[provider]" :key="modelId" class="flex items-center justify-between bg-gray-50 p-2 rounded">
                  <span class="text-sm">{{ model.name || modelId }}</span>
                  <button
                    @click="removeCustomModel(provider, modelId)"
                    class="text-red-600 hover:text-red-800"
                  >
                    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>

              <!-- Add new custom model -->
              <div class="flex space-x-2">
                <input
                  v-model="newCustomModels[provider].id"
                  placeholder="Model ID"
                  class="flex-1 border border-gray-300 rounded-md shadow-sm p-2 text-sm"
                />
                <input
                  v-model="newCustomModels[provider].name"
                  placeholder="Display Name"
                  class="flex-1 border border-gray-300 rounded-md shadow-sm p-2 text-sm"
                />
                <button
                  @click="addCustomModel(provider)"
                  :disabled="!newCustomModels[provider].id"
                  class="px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 text-sm"
                >
                  Add
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Task Configuration Tab -->
      <div v-if="activeTab === 'tasks'" class="space-y-6">
        <div class="mb-4">
          <p class="text-sm text-gray-600">Configure models and base URLs for specific tasks. Grouped by agent type for better organization.</p>
        </div>

        <!-- Main Agents -->
        <div class="border rounded-lg p-4">
          <h3 class="text-lg font-medium text-gray-900 mb-3 flex items-center">
            <svg class="w-5 h-5 mr-2 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Main Agents
          </h3>
          <div class="space-y-3">
            <div v-for="task in mainAgentTasks" :key="task.id" class="task-row">
              <div class="task-config">
                <label class="task-label">{{ task.name }}</label>
                <div class="task-controls">
                  <select
                    v-model="taskModels[task.id]"
                    @change="handleTaskModelChange(task.id)"
                    class="task-select"
                  >
                    <option :value="null">Use Default</option>
                    <optgroup v-for="provider in providers" :key="provider" :label="formatProviderName(provider)">
                      <option v-for="model in getProviderModels(provider)" :key="`${provider}-${model.id}`" :value="`${provider}:${model.id}`">
                        {{ model.name }}
                      </option>
                    </optgroup>
                  </select>
                  <div v-if="viewMode === 'advanced'" class="flex items-center space-x-2">
                    <input
                      v-model="taskBaseUrls[task.id]"
                      type="url"
                      placeholder="Custom Base URL (optional)"
                      class="task-url-input"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Deep Research Agents -->
        <div class="border rounded-lg p-4">
          <h3 class="text-lg font-medium text-gray-900 mb-3 flex items-center">
            <svg class="w-5 h-5 mr-2 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            Deep Research Agents
          </h3>
          <div class="space-y-3">
            <div v-for="task in deepResearchTasks" :key="task.id" class="task-row">
              <div class="task-config">
                <label class="task-label">{{ task.name }}</label>
                <div class="task-controls">
                  <select
                    v-model="taskModels[task.id]"
                    @change="handleTaskModelChange(task.id)"
                    class="task-select"
                  >
                    <option :value="null">Use Default</option>
                    <optgroup v-for="provider in providers" :key="provider" :label="formatProviderName(provider)">
                      <option v-for="model in getProviderModels(provider)" :key="`${provider}-${model.id}`" :value="`${provider}:${model.id}`">
                        {{ model.name }}
                      </option>
                    </optgroup>
                  </select>
                  <div v-if="viewMode === 'advanced'" class="flex items-center space-x-2">
                    <input
                      v-model="taskBaseUrls[task.id]"
                      type="url"
                      placeholder="Custom Base URL (optional)"
                      class="task-url-input"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Data Science Agents -->
        <div class="border rounded-lg p-4">
          <h3 class="text-lg font-medium text-gray-900 mb-3 flex items-center">
            <svg class="w-5 h-5 mr-2 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Data Science Agents
          </h3>
          <div class="space-y-3">
            <div v-for="task in dataScienceTasks" :key="task.id" class="task-row">
              <div class="task-config">
                <label class="task-label">{{ task.name }}</label>
                <div class="task-controls">
                  <select
                    v-model="taskModels[task.id]"
                    @change="handleTaskModelChange(task.id)"
                    class="task-select"
                  >
                    <option :value="null">Use Default</option>
                    <optgroup v-for="provider in providers" :key="provider" :label="formatProviderName(provider)">
                      <option v-for="model in getProviderModels(provider)" :key="`${provider}-${model.id}`" :value="`${provider}:${model.id}`">
                        {{ model.name }}
                      </option>
                    </optgroup>
                  </select>
                  <div v-if="viewMode === 'advanced'" class="flex items-center space-x-2">
                    <input
                      v-model="taskBaseUrls[task.id]"
                      type="url"
                      placeholder="Custom Base URL (optional)"
                      class="task-url-input"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Other Agents -->
        <div class="border rounded-lg p-4">
          <h3 class="text-lg font-medium text-gray-900 mb-3 flex items-center">
            <svg class="w-5 h-5 mr-2 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
            Other Agents
          </h3>
          <div class="space-y-3">
            <div v-for="task in otherTasks" :key="task.id" class="task-row">
              <div class="task-config">
                <label class="task-label">{{ task.name }}</label>
                <div class="task-controls">
                  <select
                    v-model="taskModels[task.id]"
                    @change="handleTaskModelChange(task.id)"
                    class="task-select"
                  >
                    <option :value="null">Use Default</option>
                    <optgroup v-for="provider in providers" :key="provider" :label="formatProviderName(provider)">
                      <option v-for="model in getProviderModels(provider)" :key="`${provider}-${model.id}`" :value="`${provider}:${model.id}`">
                        {{ model.name }}
                      </option>
                    </optgroup>
                  </select>
                  <div v-if="viewMode === 'advanced'" class="flex items-center space-x-2">
                    <input
                      v-model="taskBaseUrls[task.id]"
                      type="url"
                      placeholder="Custom Base URL (optional)"
                      class="task-url-input"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Legacy task configuration (hidden, kept for backward compatibility) -->
      <div v-if="false" class="mb-6">
        <!-- Old task configuration kept hidden -->
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

// View mode and tabs
const viewMode = ref('simple')
const activeTab = ref('providers')
const tabs = [
  { id: 'providers', label: 'Providers & API Keys' },
  { id: 'tasks', label: 'Task Configuration' }
]

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
const providerBaseUrls = ref({
  sambanova: '',
  fireworks: '',
  together: ''
})
const taskModels = ref({})
const taskBaseUrls = ref({})
const customModels = ref({
  sambanova: {},
  fireworks: {},
  together: {}
})
const newCustomModels = ref({
  sambanova: { id: '', name: '' },
  fireworks: { id: '', name: '' },
  together: { id: '', name: '' }
})
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

// Default base URLs
const defaultBaseUrls = {
  sambanova: 'https://api.sambanova.ai/v1',
  fireworks: 'https://api.fireworks.ai/inference/v1',
  together: 'https://api.together.xyz/v1'
}

// Computed task groups
const mainAgentTasks = computed(() =>
  tasks.value.filter(t => ['main_agent', 'code_execution_agent', 'vision_agent', 'daytona_agent'].includes(t.id))
)

const deepResearchTasks = computed(() =>
  tasks.value.filter(t => t.id.includes('deep_research'))
)

const dataScienceTasks = computed(() =>
  tasks.value.filter(t => t.id.includes('data_science'))
)

const otherTasks = computed(() =>
  tasks.value.filter(t =>
    !mainAgentTasks.value.includes(t) &&
    !deepResearchTasks.value.includes(t) &&
    !dataScienceTasks.value.includes(t)
  )
)

// Computed
const hasUnsavedChanges = computed(() => {
  if (!originalConfig.value) return false

  return (
    selectedProvider.value !== originalConfig.value.default_provider ||
    JSON.stringify(taskModels.value) !== JSON.stringify(originalConfig.value.task_models || {}) ||
    Object.keys(apiKeys.value).some(p => apiKeys.value[p] !== (originalConfig.value.api_keys?.[p] || '')) ||
    JSON.stringify(providerBaseUrls.value) !== JSON.stringify(originalConfig.value.provider_base_urls || {}) ||
    JSON.stringify(taskBaseUrls.value) !== JSON.stringify(originalConfig.value.task_base_urls || {}) ||
    JSON.stringify(customModels.value) !== JSON.stringify(originalConfig.value.custom_models || {})
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

const getDefaultBaseUrl = (provider) => {
  return defaultBaseUrls[provider] || ''
}

const resetBaseUrl = (provider) => {
  providerBaseUrls.value[provider] = ''
}

const toggleKeyVisibility = (provider) => {
  apiKeyVisibility.value[provider] = !apiKeyVisibility.value[provider]
}

const getProviderModels = (provider) => {
  const baseModels = providerModels.value[provider] || []
  const custom = customModels.value[provider] || {}

  // Combine base models with custom models
  const customModelList = Object.entries(custom).map(([id, info]) => ({
    id,
    name: info.name || id,
    isCustom: true
  }))

  return [...baseModels, ...customModelList]
}

const addCustomModel = (provider) => {
  const newModel = newCustomModels.value[provider]
  if (!newModel.id) return

  if (!customModels.value[provider]) {
    customModels.value[provider] = {}
  }

  customModels.value[provider][newModel.id] = {
    name: newModel.name || newModel.id,
    context_window: 32768,
    max_tokens: 8192
  }

  // Reset input
  newCustomModels.value[provider] = { id: '', name: '' }
}

const removeCustomModel = (provider, modelId) => {
  if (customModels.value[provider]) {
    delete customModels.value[provider][modelId]
  }
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
  console.log('loadConfiguration called - this might overwrite reset values!')
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

    // Load provider base URLs if present
    if (config.provider_base_urls) {
      providerBaseUrls.value = config.provider_base_urls
    }

    // Load task base URLs if present
    if (config.task_base_urls) {
      taskBaseUrls.value = config.task_base_urls
    }

    // Load custom models if present
    if (config.custom_models) {
      customModels.value = config.custom_models
    }

    // Load model mappings from backend if available
    if (config.model_mappings) {
      modelMappings.value = config.model_mappings
      console.log('Loaded model mappings from backend:', Object.keys(modelMappings.value))
    }

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
      api_keys: apiKeys.value,  // Now includes loaded API keys
      provider_base_urls: providerBaseUrls.value,
      task_base_urls: taskBaseUrls.value,
      custom_models: customModels.value
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

    // Filter out empty base URLs
    const filteredProviderBaseUrls = {}
    Object.entries(providerBaseUrls.value).forEach(([provider, url]) => {
      if (url) {
        filteredProviderBaseUrls[provider] = url
      }
    })

    const filteredTaskBaseUrls = {}
    Object.entries(taskBaseUrls.value).forEach(([task, url]) => {
      if (url) {
        filteredTaskBaseUrls[task] = url
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
      api_keys: apiKeys.value,
      provider_base_urls: filteredProviderBaseUrls,
      task_base_urls: filteredTaskBaseUrls,
      custom_models: customModels.value
    }, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })

    if (response.data.success) {
      originalConfig.value = JSON.parse(JSON.stringify({
        default_provider: selectedProvider.value,
        task_models: taskModels.value,
        api_keys: apiKeys.value,
        provider_base_urls: providerBaseUrls.value,
        task_base_urls: taskBaseUrls.value,
        custom_models: customModels.value
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
      // Use the config returned by the reset operation directly
      const resetConfig = response.data.config
      console.log('Reset response received:', response.data)
      console.log('Reset config:', resetConfig)

      // Update local state with the reset values
      selectedProvider.value = resetConfig.default_provider || 'sambanova'

      // Clear task models and reload from reset config
      // Use a new object to ensure reactivity
      const newTaskModels = {}
      if (resetConfig.task_models) {
        console.log('Reset config task_models:', resetConfig.task_models)
        Object.entries(resetConfig.task_models).forEach(([taskId, taskConfig]) => {
          if (taskConfig.provider && taskConfig.model) {
            const modelValue = `${taskConfig.provider}:${taskConfig.model}`
            newTaskModels[taskId] = modelValue
            console.log(`Setting task ${taskId} to ${modelValue}`)
          }
        })
      }
      // Replace the entire object to trigger reactivity
      taskModels.value = newTaskModels
      console.log('Final taskModels after reset:', taskModels.value)

      // Update model mappings if provided
      if (resetConfig.model_mappings) {
        modelMappings.value = resetConfig.model_mappings
      }

      // Update the injected selectedOption
      const selectedOption = inject('selectedOption')
      if (selectedOption) {
        const providerMapping = {
          'sambanova': { label: 'SambaNova', value: 'sambanova' },
          'fireworks': { label: 'Fireworks AI', value: 'fireworks' },
          'together': { label: 'Together AI', value: 'together' }
        }

        if (providerMapping[selectedProvider.value]) {
          selectedOption.value = providerMapping[selectedProvider.value]
          console.log('Reset selectedOption to:', selectedOption.value)
        }
      }

      // Clear all custom configurations
      providerBaseUrls.value = {
        sambanova: '',
        fireworks: '',
        together: ''
      }
      taskBaseUrls.value = {}
      customModels.value = {
        sambanova: {},
        fireworks: {},
        together: {}
      }

      // Clear API keys (they should also be reset)
      apiKeys.value = {
        sambanova: '',
        fireworks: '',
        together: ''
      }

      // Don't call loadConfiguration here - it would overwrite the reset values
      // The reset response already contains the correct default configuration

      showStatus('Configuration reset to defaults', 'success')

      // Emit configuration update to notify other components with the actual reset config
      emit('configuration-updated', resetConfig)
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
  providerBaseUrls.value = { ...originalConfig.value.provider_base_urls }
  taskBaseUrls.value = { ...originalConfig.value.task_base_urls }
  customModels.value = JSON.parse(JSON.stringify(originalConfig.value.custom_models))
}

const showStatus = (text, type) => {
  statusMessage.value = { text, type }
  setTimeout(() => {
    statusMessage.value = null
  }, 3000)
}

// Model mappings will be loaded from backend
const modelMappings = ref({})

const mapModelsToProvider = (newProvider) => {
  // Map each task's model to the equivalent in the new provider
  const updatedTaskModels = {}

  Object.entries(taskModels.value).forEach(([taskId, currentSelection]) => {
    if (currentSelection && currentSelection.includes(':')) {
      const [currentProvider, currentModel] = currentSelection.split(':')

      // Find which model key this corresponds to
      let mappedModel = null
      for (const [, mappings] of Object.entries(modelMappings.value)) {
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
  max-width: 1200px;
  margin: 0 auto;
}

.admin-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.task-row {
  padding: 0.75rem;
  background-color: #f9fafb;
  border-radius: 0.375rem;
}

.task-config {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.task-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
}

.task-controls {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.task-select {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  padding: 0.5rem;
  font-size: 0.875rem;
}

.task-url-input {
  flex: 1;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  padding: 0.5rem;
  font-size: 0.875rem;
}

@media (min-width: 768px) {
  .task-config {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }

  .task-label {
    flex: 0 0 250px;
  }

  .task-controls {
    flex: 1;
    flex-direction: row;
    align-items: center;
    gap: 0.75rem;
  }

  .task-select {
    max-width: 350px;
  }
}
</style>