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

        <!-- Custom OpenAI-Compatible Providers -->
        <div v-if="viewMode === 'advanced'">
          <h3 class="text-lg font-medium text-gray-900 mb-3">Custom OpenAI-Compatible Providers</h3>
          <div class="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-3">
            <p class="text-sm text-blue-900">
              <strong>How it works:</strong> Add any OpenAI-compatible API endpoint with its base URL and API key. When you assign a custom provider's model to a task, that provider's API key will automatically be used for authentication.
            </p>
          </div>

          <!-- List existing custom providers -->
          <div v-if="customProviders.length > 0" class="mb-4 space-y-2">
            <div v-for="(provider, index) in customProviders" :key="index" class="border rounded-lg p-3">
              <!-- View Mode -->
              <div v-if="editingProviderIndex !== index" class="flex justify-between items-start">
                <div class="flex-1">
                  <h4 class="font-medium">{{ provider.name }}
                    <span class="text-xs text-gray-500 ml-2">({{ provider.providerType === 'openai' ? 'OpenAI' : provider.providerType === 'sambanova' ? 'SambaNova' : 'Fireworks' }} Compatible)</span>
                  </h4>
                  <p class="text-sm text-gray-600">{{ provider.baseUrl }}</p>
                  <p class="text-sm text-gray-600 mt-1">Models: {{ provider.models }}</p>
                  <div v-if="provider.apiKey" class="flex items-center mt-1">
                    <span class="text-xs text-gray-500">API Key: </span>
                    <span v-if="customProviderVisibility[provider.name]" class="text-xs ml-1">{{ provider.apiKey }}</span>
                    <span v-else class="text-xs ml-1">••••••••</span>
                    <button
                      @click="customProviderVisibility[provider.name] = !customProviderVisibility[provider.name]"
                      class="ml-2 text-gray-400 hover:text-gray-600"
                    >
                      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path v-if="customProviderVisibility[provider.name]" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.519 5 12 5c4.481 0 8.268 2.943 9.542 7-1.274 4.057-5.061 7-9.542 7-4.481 0-8.268-2.943-9.542-7z" />
                        <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A9.952 9.952 0 0112 19.5c-5.247 0-9.645-4.028-9.985-9.227M9.642 9.642a3 3 0 104.715 4.715M3 3l18 18" />
                      </svg>
                    </button>
                  </div>
                </div>
                <div class="flex gap-2">
                  <button
                    @click="startEditingProvider(index)"
                    class="text-blue-600 hover:text-blue-800"
                  >
                    <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  </button>
                  <button
                    @click="removeCustomProvider(index)"
                    class="text-red-600 hover:text-red-800"
                  >
                    <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>

              <!-- Edit Mode -->
              <div v-else class="space-y-2">
                <input
                  v-model="editingProvider.name"
                  placeholder="Provider Name"
                  class="block w-full border border-gray-300 rounded-md shadow-sm p-2 text-sm"
                />
                <input
                  v-model="editingProvider.baseUrl"
                  type="url"
                  placeholder="Base URL"
                  class="block w-full border border-gray-300 rounded-md shadow-sm p-2 text-sm"
                />
                <select
                  v-model="editingProvider.providerType"
                  class="block w-full border border-gray-300 rounded-md shadow-sm p-2 text-sm"
                >
                  <option value="sambanova">SambaNova Compatible</option>
                  <option value="fireworks">Fireworks Compatible</option>
                  <option value="openai">OpenAI Compatible (Together/Custom)</option>
                </select>
                <input
                  v-model="editingProvider.apiKey"
                  type="password"
                  placeholder="API Key"
                  class="block w-full border border-gray-300 rounded-md shadow-sm p-2 text-sm"
                />
                <input
                  v-model="editingProvider.models"
                  placeholder="Model IDs (comma-separated)"
                  class="block w-full border border-gray-300 rounded-md shadow-sm p-2 text-sm"
                />
                <div class="flex gap-2">
                  <button
                    @click="saveEditedProvider(index)"
                    class="flex-1 px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
                  >
                    Save Changes
                  </button>
                  <button
                    @click="cancelEditingProvider"
                    class="flex-1 px-3 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400 text-sm"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Add new provider form -->
          <div class="border rounded-lg p-3 bg-gray-50">
            <h4 class="text-sm font-medium mb-2">Add New Provider</h4>
            <div class="space-y-2">
              <input
                v-model="newProvider.name"
                placeholder="Provider Name (e.g., My Custom API)"
                class="block w-full border border-gray-300 rounded-md shadow-sm p-2 text-sm"
              />
              <input
                v-model="newProvider.baseUrl"
                type="url"
                placeholder="Base URL (e.g., https://api.example.com/v1)"
                class="block w-full border border-gray-300 rounded-md shadow-sm p-2 text-sm"
              />
              <select
                v-model="newProvider.type"
                class="block w-full border border-gray-300 rounded-md shadow-sm p-2 text-sm"
              >
                <option value="sambanova">SambaNova Compatible</option>
                <option value="fireworks">Fireworks Compatible</option>
                <option value="openai">OpenAI Compatible (Together/Custom)</option>
              </select>
              <input
                v-model="newProvider.apiKey"
                type="password"
                placeholder="API Key (required for authentication)"
                class="block w-full border border-gray-300 rounded-md shadow-sm p-2 text-sm"
              />
              <input
                v-model="newProvider.models"
                placeholder="Model IDs (comma-separated, e.g., gpt-4, claude-3)"
                class="block w-full border border-gray-300 rounded-md shadow-sm p-2 text-sm"
              />
              <button
                @click="addCustomProvider"
                :disabled="!newProvider.name || !newProvider.baseUrl"
                class="w-full px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 text-sm"
              >
                {{ !newProvider.apiKey ? 'Add Provider (API Key Required)' : 'Add Provider' }}
              </button>
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
                v-model="apiKeys[getApiKeyName(provider)]"
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
                  v-if="apiKeys[getApiKeyName(provider)]"
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

          <!-- PayPal Invoicing Email -->
          <div class="mt-4">
            <label class="block text-sm font-medium text-gray-700 mb-1">
              PayPal Invoicing Email (Optional)
              <span class="text-xs text-gray-500 ml-2">- Required for creating shareable invoices</span>
            </label>
            <input
              v-model="apiKeys.paypal_invoicing_email"
              type="email"
              placeholder="Enter your PayPal business account email"
              class="block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
            />
            <p class="mt-1 text-xs text-gray-500">
              This is the email address you use to log in to your PayPal business account. It's required to create shareable invoice links.
            </p>
          </div>
        </div>
      </div>

        <!-- Custom Models -->
        <div v-if="viewMode === 'advanced'">
          <h3 class="text-lg font-medium text-gray-900 mb-3">Custom Models</h3>
          <p class="text-sm text-gray-600 mb-3">Add model IDs that can be used with any provider.</p>

          <!-- List existing custom models -->
          <div v-if="customModels.length > 0" class="mb-4 space-y-2">
            <div v-for="(model, index) in customModels" :key="index" class="flex items-center justify-between bg-gray-50 p-2 rounded">
              <div>
                <span class="text-sm font-medium">{{ model.name || model.id }}</span>
                <span class="text-xs text-gray-500 ml-2">({{ model.id }})</span>
                <span v-if="model.provider" class="text-xs text-gray-500 ml-2">- {{ model.provider }}</span>
              </div>
              <button
                @click="removeCustomModel(index)"
                class="text-red-600 hover:text-red-800"
              >
                <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          <!-- Add new custom model -->
          <div class="border rounded-lg p-3 bg-gray-50">
            <h4 class="text-sm font-medium mb-2">Add New Model</h4>
            <div class="space-y-2">
              <input
                v-model="newCustomModel.id"
                placeholder="Model ID (required)"
                class="block w-full border border-gray-300 rounded-md shadow-sm p-2 text-sm"
              />
              <input
                v-model="newCustomModel.name"
                placeholder="Display Name (optional)"
                class="block w-full border border-gray-300 rounded-md shadow-sm p-2 text-sm"
              />
              <select
                v-model="newCustomModel.provider"
                class="block w-full border border-gray-300 rounded-md shadow-sm p-2 text-sm"
              >
                <option value="">Available for all providers</option>
                <optgroup label="Built-in Providers">
                  <option v-for="provider in providers" :key="provider" :value="provider">
                    {{ formatProviderName(provider) }}
                  </option>
                </optgroup>
                <optgroup v-if="customProviders.length > 0" label="Custom Providers">
                  <option v-for="provider in customProviders" :key="provider.name" :value="provider.name">
                    {{ provider.name }}
                  </option>
                </optgroup>
              </select>
              <button
                @click="addCustomModel"
                :disabled="!newCustomModel.id"
                class="w-full px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 text-sm"
              >
                Add Model
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Task Configuration Tab -->
      <div v-if="activeTab === 'tasks'" class="space-y-6">
        <div class="mb-4">
          <p class="text-sm text-gray-600">Configure models and base URLs for specific tasks. Grouped by agent type for better organization.</p>

          <!-- Custom Provider Usage Summary -->
          <div v-if="customProviderUsage.length > 0" class="mt-3 bg-green-50 border border-green-200 rounded-lg p-3">
            <h4 class="text-sm font-medium text-green-900 mb-2">Custom Providers in Use:</h4>
            <ul class="text-xs text-green-800 space-y-1">
              <li v-for="usage in customProviderUsage" :key="usage.provider">
                <strong>{{ usage.provider }}:</strong> {{ usage.tasks.join(', ') }}
              </li>
            </ul>
          </div>
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
                <label class="task-label">
                  {{ task.name }}
                  <span v-if="isUsingCustomProvider(task.id)" class="text-xs text-green-600 ml-1" title="Using custom provider">🔐</span>
                </label>
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
                    <optgroup v-if="customProviders.length > 0" label="Custom Providers">
                      <template v-for="provider in customProviders" :key="`custom-${provider.name}`">
                        <!-- Models from provider definition -->
                        <option v-for="model in getProviderModels(provider)" :key="`custom:${provider.name}:${model}`" :value="`custom:${provider.name}:${model}`">
                          {{ model }} ({{ provider.name }})
                        </option>
                        <!-- Custom models added separately for this provider -->
                        <option v-for="model in customModels.filter(m => m.provider === provider.name)" :key="`custom:${provider.name}:${model.id}`" :value="`custom:${provider.name}:${model.id}`">
                          {{ model.name || model.id }} ({{ provider.name }})
                        </option>
                      </template>
                    </optgroup>
                  </select>
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
                <label class="task-label">
                  {{ task.name }}
                  <span v-if="isUsingCustomProvider(task.id)" class="text-xs text-green-600 ml-1" title="Using custom provider">🔐</span>
                </label>
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
                    <optgroup v-if="customProviders.length > 0" label="Custom Providers">
                      <template v-for="provider in customProviders" :key="`custom-${provider.name}`">
                        <!-- Models from provider definition -->
                        <option v-for="model in getProviderModels(provider)" :key="`custom:${provider.name}:${model}`" :value="`custom:${provider.name}:${model}`">
                          {{ model }} ({{ provider.name }})
                        </option>
                        <!-- Custom models added separately for this provider -->
                        <option v-for="model in customModels.filter(m => m.provider === provider.name)" :key="`custom:${provider.name}:${model.id}`" :value="`custom:${provider.name}:${model.id}`">
                          {{ model.name || model.id }} ({{ provider.name }})
                        </option>
                      </template>
                    </optgroup>
                  </select>
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
                <label class="task-label">
                  {{ task.name }}
                  <span v-if="isUsingCustomProvider(task.id)" class="text-xs text-green-600 ml-1" title="Using custom provider">🔐</span>
                </label>
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
                    <optgroup v-if="customProviders.length > 0" label="Custom Providers">
                      <template v-for="provider in customProviders" :key="`custom-${provider.name}`">
                        <!-- Models from provider definition -->
                        <option v-for="model in getProviderModels(provider)" :key="`custom:${provider.name}:${model}`" :value="`custom:${provider.name}:${model}`">
                          {{ model }} ({{ provider.name }})
                        </option>
                        <!-- Custom models added separately for this provider -->
                        <option v-for="model in customModels.filter(m => m.provider === provider.name)" :key="`custom:${provider.name}:${model.id}`" :value="`custom:${provider.name}:${model.id}`">
                          {{ model.name || model.id }} ({{ provider.name }})
                        </option>
                      </template>
                    </optgroup>
                  </select>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Financial Analysis Agents -->
        <div class="border rounded-lg p-4">
          <h3 class="text-lg font-medium text-gray-900 mb-3 flex items-center">
            <svg class="w-5 h-5 mr-2 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Financial Analysis Agents
          </h3>
          <div class="space-y-3">
            <div v-for="task in financialAnalysisTasks" :key="task.id" class="task-row">
              <div class="task-config">
                <label class="task-label">
                  {{ task.name }}
                  <span v-if="isUsingCustomProvider(task.id)" class="text-xs text-green-600 ml-1" title="Using custom provider">🔐</span>
                </label>
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
                    <optgroup v-if="customProviders.length > 0" label="Custom Providers">
                      <template v-for="provider in customProviders" :key="`custom-${provider.name}`">
                        <!-- Models from provider definition -->
                        <option v-for="model in getProviderModels(provider)" :key="`custom:${provider.name}:${model}`" :value="`custom:${provider.name}:${model}`">
                          {{ model }} ({{ provider.name }})
                        </option>
                        <!-- Custom models added separately for this provider -->
                        <option v-for="model in customModels.filter(m => m.provider === provider.name)" :key="`custom:${provider.name}:${model.id}`" :value="`custom:${provider.name}:${model.id}`">
                          {{ model.name || model.id }} ({{ provider.name }})
                        </option>
                      </template>
                    </optgroup>
                  </select>
                  <div v-if="viewMode === 'advanced'" class="flex items-center space-x-2">
                    <span class="text-xs text-gray-500">Provider-specific configuration</span>
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
                <label class="task-label">
                  {{ task.name }}
                  <span v-if="isUsingCustomProvider(task.id)" class="text-xs text-green-600 ml-1" title="Using custom provider">🔐</span>
                </label>
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
                    <optgroup v-if="customProviders.length > 0" label="Custom Providers">
                      <template v-for="provider in customProviders" :key="`custom-${provider.name}`">
                        <!-- Models from provider definition -->
                        <option v-for="model in getProviderModels(provider)" :key="`custom:${provider.name}:${model}`" :value="`custom:${provider.name}:${model}`">
                          {{ model }} ({{ provider.name }})
                        </option>
                        <!-- Custom models added separately for this provider -->
                        <option v-for="model in customModels.filter(m => m.provider === provider.name)" :key="`custom:${provider.name}:${model.id}`" :value="`custom:${provider.name}:${model.id}`">
                          {{ model.name || model.id }} ({{ provider.name }})
                        </option>
                      </template>
                    </optgroup>
                  </select>
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
  together: '',
  paypal_invoicing_email: ''
})
const apiKeyVisibility = ref({
  sambanova: false,
  fireworks: false,
  together: false
})
// Custom OpenAI-compatible providers
const customProviders = ref([])
const newProvider = ref({ name: '', baseUrl: '', apiKey: '', type: 'openai', models: '' })
const customProviderVisibility = ref({})
const showNewProviderApiKey = ref(false)
// Edit mode state
const editingProviderIndex = ref(null)
const editingProvider = ref({})
// Task models and custom models
const taskModels = ref({})
const customModels = ref([])
const newCustomModel = ref({ id: '', name: '', provider: '' })
const tasks = ref([])

// Helper to check if a task is using a custom provider
const isUsingCustomProvider = (taskId) => {
  const modelValue = taskModels.value[taskId]
  return modelValue && modelValue.startsWith('custom:')
}

// Computed property to show custom provider usage
const customProviderUsage = computed(() => {
  const usage = {}

  Object.entries(taskModels.value).forEach(([taskId, modelValue]) => {
    if (modelValue && modelValue.startsWith('custom:')) {
      const parts = modelValue.split(':')
      const providerName = parts[1]
      const task = tasks.value.find(t => t.id === taskId)

      if (!usage[providerName]) {
        usage[providerName] = []
      }
      usage[providerName].push(task ? task.name : taskId)
    }
  })

  return Object.entries(usage).map(([provider, taskList]) => ({
    provider,
    tasks: taskList
  }))
})
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

// Helper function to get models array from a provider
// Handles both custom provider objects and built-in provider strings
const getProviderModels = (provider) => {
  // If provider is an object (custom provider), parse its models field
  if (typeof provider === 'object' && provider !== null) {
    if (!provider.models) return []

    // If it's already an array, return it
    if (Array.isArray(provider.models)) {
      return provider.models
    }

    // If it's a string, split by comma and trim
    if (typeof provider.models === 'string') {
      return provider.models
        .split(',')
        .map(m => m.trim())
        .filter(m => m.length > 0)
    }

    return []
  }

  // If provider is a string (built-in provider), look up in providerModels
  const baseModels = providerModels.value[provider] || []

  // Add custom models for this provider
  const customModelsList = customModels.value
    .filter(m => m.provider === provider || !m.provider)
    .map(m => ({
      id: m.id,
      name: m.name || m.id,
      isCustom: true
    }))

  return [...baseModels, ...customModelsList]
}

// Base URLs now handled by backend configuration

// Computed task groups
const mainAgentTasks = computed(() =>
  tasks.value.filter(t => ['main_agent', 'code_execution_agent', 'daytona_agent', 'vision_agent'].includes(t.id))
)

const deepResearchTasks = computed(() =>
  tasks.value.filter(t => t.id.includes('deep_research'))
)

const dataScienceTasks = computed(() =>
  tasks.value.filter(t => t.id.includes('data_science'))
)

const financialAnalysisTasks = computed(() =>
  tasks.value.filter(t => t.id.includes('financial') || t.id.includes('crewai'))
)

const otherTasks = computed(() =>
  tasks.value.filter(t =>
    !mainAgentTasks.value.includes(t) &&
    !deepResearchTasks.value.includes(t) &&
    !dataScienceTasks.value.includes(t) &&
    !financialAnalysisTasks.value.includes(t)
  )
)

// Computed
const hasUnsavedChanges = computed(() => {
  if (!originalConfig.value) return false

  return (
    selectedProvider.value !== originalConfig.value.default_provider ||
    JSON.stringify(taskModels.value) !== JSON.stringify(originalConfig.value.task_models || {}) ||
    Object.keys(apiKeys.value).some(p => apiKeys.value[p] !== (originalConfig.value.api_keys?.[p] || '')) ||
    JSON.stringify(customProviders.value) !== JSON.stringify(originalConfig.value.custom_providers || []) ||
    JSON.stringify(customModels.value) !== JSON.stringify(originalConfig.value.custom_models || [])
  )
})

// Methods
const getApiKeyName = (provider) => {
  // Check if this is a custom provider
  const isCustomProvider = customProviders.value.some(cp => cp.name === provider)

  // Custom providers use 'custom_' prefix
  if (isCustomProvider) {
    return `custom_${provider}`
  }

  // Built-in providers use their name directly
  return provider
}

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

// getAllModels function removed - not used

const addCustomProvider = () => {
  if (!newProvider.value.name) {
    showStatus('Please enter a provider name', 'error')
    return
  }
  if (!newProvider.value.baseUrl) {
    showStatus('Please enter a base URL', 'error')
    return
  }
  if (!newProvider.value.apiKey) {
    showStatus('API key is required for authentication', 'error')
    return
  }

  // Parse models - can be comma-separated string or leave as string for backend to parse
  const modelsValue = newProvider.value.models ? newProvider.value.models.trim() : ''

  customProviders.value.push({
    name: newProvider.value.name,
    baseUrl: newProvider.value.baseUrl,
    apiKey: newProvider.value.apiKey,
    providerType: newProvider.value.type || 'openai',  // Use providerType instead of type
    models: modelsValue  // Include models field
  })

  // Store visibility state
  customProviderVisibility.value[newProvider.value.name] = false

  // Reset form
  newProvider.value = { name: '', baseUrl: '', apiKey: '', type: 'openai', models: '' }
  showNewProviderApiKey.value = false
  showStatus('Custom provider added with API key', 'success')
}

const removeCustomProvider = (index) => {
  const provider = customProviders.value[index]
  // Remove associated models
  customModels.value = customModels.value.filter(m => m.provider !== provider.name)
  // Remove provider
  customProviders.value.splice(index, 1)
  delete customProviderVisibility.value[provider.name]
}

const startEditingProvider = (index) => {
  // Copy provider data to editingProvider
  editingProviderIndex.value = index
  editingProvider.value = {
    name: customProviders.value[index].name,
    baseUrl: customProviders.value[index].baseUrl,
    apiKey: customProviders.value[index].apiKey,
    providerType: customProviders.value[index].providerType,
    models: customProviders.value[index].models
  }
}

const saveEditedProvider = (index) => {
  // Validate inputs
  if (!editingProvider.value.name || !editingProvider.value.baseUrl || !editingProvider.value.apiKey) {
    showStatus('Please fill in all required fields', 'error')
    return
  }

  // Update the provider in the array
  customProviders.value[index] = {
    name: editingProvider.value.name,
    baseUrl: editingProvider.value.baseUrl,
    apiKey: editingProvider.value.apiKey,
    providerType: editingProvider.value.providerType,
    models: editingProvider.value.models
  }

  // Exit edit mode
  editingProviderIndex.value = null
  editingProvider.value = {}

  showStatus('Custom provider updated', 'success')
}

const cancelEditingProvider = () => {
  // Reset edit mode
  editingProviderIndex.value = null
  editingProvider.value = {}
}

const addCustomModel = () => {
  if (!newCustomModel.value.id) return

  customModels.value.push({
    id: newCustomModel.value.id,
    name: newCustomModel.value.name || newCustomModel.value.id,
    provider: newCustomModel.value.provider || ''
  })

  // Reset form
  newCustomModel.value = { id: '', name: '', provider: '' }
}

const removeCustomModel = (index) => {
  customModels.value.splice(index, 1)
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

    // Load custom providers if present
    if (config.custom_providers) {
      customProviders.value = config.custom_providers
      // Initialize visibility states
      config.custom_providers.forEach(provider => {
        customProviderVisibility.value[provider.name] = false
      })

      // Populate custom provider API keys from apiKeys.value after keys are loaded
      // This will happen in the next section when API keys are loaded
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
          together: keysResponse.data.together_key || '',
          paypal_invoicing_email: keysResponse.data.paypal_invoicing_email || ''
        }

        // Load custom provider API keys (they come with "custom_" prefix)
        Object.keys(keysResponse.data).forEach(key => {
          if (key.startsWith('custom_')) {
            apiKeys.value[key] = keysResponse.data[key]
          }
        })

        console.log('Loaded API keys:', {
          sambanova: apiKeys.value.sambanova ? 'present' : 'empty',
          fireworks: apiKeys.value.fireworks ? 'present' : 'empty',
          together: apiKeys.value.together ? 'present' : 'empty',
          customProviders: Object.keys(apiKeys.value).filter(k => k.startsWith('custom_')).length
        })

        // Populate custom provider API keys into their objects
        customProviders.value.forEach(provider => {
          const customKeyName = `custom_${provider.name}`
          if (apiKeys.value[customKeyName]) {
            provider.apiKey = apiKeys.value[customKeyName]
            console.log(`Loaded API key for custom provider ${provider.name}`)
          }
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
      console.log('Loading task models, custom providers:', customProviders.value.map(cp => cp.name))
      Object.entries(config.task_models).forEach(([taskId, taskConfig]) => {
        if (taskConfig.provider && taskConfig.model) {
          // Check if this provider is a custom provider
          const isCustomProvider = customProviders.value.some(cp => cp.name === taskConfig.provider)

          console.log(`Task ${taskId}: provider=${taskConfig.provider}, isCustom=${isCustomProvider}`)

          if (isCustomProvider) {
            // Handle custom provider format
            taskModels.value[taskId] = `custom:${taskConfig.provider}:${taskConfig.model}`
          } else {
            // Handle regular provider format
            taskModels.value[taskId] = `${taskConfig.provider}:${taskConfig.model}`
          }
        }
      })
      console.log('Final taskModels after load:', JSON.parse(JSON.stringify(taskModels.value)))
    }

    // Store original config for change detection (after loading API keys)
    originalConfig.value = JSON.parse(JSON.stringify({
      default_provider: selectedProvider.value,
      task_models: taskModels.value,
      api_keys: apiKeys.value,  // Now includes loaded API keys
      custom_providers: customProviders.value,
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

const handleTaskModelChange = (taskId) => {
  // Task model change handled by v-model
  console.log(`[handleTaskModelChange] ${taskId} changed to:`, taskModels.value[taskId])
}

const testProvider = async (provider) => {
  const apiKeyName = getApiKeyName(provider)

  if (!apiKeys.value[apiKeyName]) {
    showStatus(`Please enter an API key for ${formatProviderName(provider)}`, 'error')
    return
  }

  testingProvider.value = provider
  testResults.value[provider] = null

  try {
    const token = await getAccessTokenSilently()
    const response = await axios.post(`${apiBaseUrl.value}/admin/test-connection`, {
      provider: provider,
      api_key: apiKeys.value[apiKeyName]
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
  // Prevent multiple simultaneous saves
  if (isSaving.value) {
    console.log('Save already in progress, skipping...')
    return
  }

  isSaving.value = true

  try {
    // Prepare task models in the correct format
    const formattedTaskModels = {}
    console.log('[SAVE] Raw taskModels before formatting:', taskModels.value.main_agent)
    Object.entries(taskModels.value).forEach(([taskId, value]) => {
      if (value && value.includes(':')) {
        // Handle custom provider format: custom:providerName:modelId
        if (value.startsWith('custom:')) {
          const parts = value.split(':')
          const customProviderName = parts[1]

          if (taskId === 'main_agent') {
            console.log(`[SAVE] main_agent is custom: provider=${customProviderName}, model=${parts[2]}`)
          }
          formattedTaskModels[taskId] = {
            provider: customProviderName,  // Use the custom provider name as provider
            model: parts[2]
          }
        } else {
          const [provider, model] = value.split(':')
          if (taskId === 'main_agent') {
            console.log(`[SAVE] main_agent is built-in: provider=${provider}, model=${model}`)
          }
          formattedTaskModels[taskId] = { provider, model }
        }
      }
    })
    console.log('[SAVE] Formatted main_agent:', formattedTaskModels.main_agent)

    const token = await getAccessTokenSilently()

    // Prepare all API keys including custom providers
    const allApiKeys = { ...apiKeys.value }

    // Add custom provider API keys to the main API keys object
    customProviders.value.forEach(provider => {
      if (provider.apiKey) {
        // Store custom provider API keys with a special prefix
        allApiKeys[`custom_${provider.name}`] = provider.apiKey
      }
    })

    // Debug log what we're sending
    console.log('Saving configuration with API keys:', {
      sambanova: apiKeys.value.sambanova ? 'present' : 'empty',
      fireworks: apiKeys.value.fireworks ? 'present' : 'empty',
      together: apiKeys.value.together ? 'present' : 'empty',
      customProviders: customProviders.value.map(p => ({ name: p.name, hasKey: !!p.apiKey }))
    })

    const response = await axios.post(`${apiBaseUrl.value}/admin/config`, {
      default_provider: selectedProvider.value,
      task_models: formattedTaskModels,
      api_keys: allApiKeys,  // Use the combined API keys
      custom_providers: customProviders.value,
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
        custom_providers: customProviders.value,
        custom_models: customModels.value
      }))

      showStatus('Configuration saved successfully', 'success')
      // Don't emit to close the modal, just show the success message
      // emit('configuration-updated', response.data.config)
      // emit('api-keys-updated', apiKeys.value)
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
      customProviders.value = []
      customModels.value = []

      // Clear API keys (they should also be reset)
      apiKeys.value = {
        sambanova: '',
        fireworks: '',
        together: '',
        paypal_invoicing_email: ''
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
  customProviders.value = JSON.parse(JSON.stringify(originalConfig.value.custom_providers || []))
  customModels.value = JSON.parse(JSON.stringify(originalConfig.value.custom_models || []))
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