<template>
  <div v-if="isOpen" class="fixed inset-0 z-50 overflow-y-auto">
    <div class="flex min-h-screen items-center justify-center p-4">
      <!-- Backdrop -->
      <div class="fixed inset-0 bg-black opacity-30" @click="close"></div>

      <!-- Modal -->
      <div class="relative w-full max-w-4xl bg-white rounded-xl shadow-lg p-6">
        <div class="flex justify-between items-center mb-6">
          <h2 class="text-2xl font-semibold text-primary-brandTextPrimary">Settings</h2>
          <button @click="close" class="text-primary-brandTextSecondary hover:text-gray-700">
            <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Tabs -->
        <div class="mb-6">
          <div class="border-b border-gray-200">
            <nav class="-mb-px flex space-x-8">
              <button
                @click="activeTab = 'api-keys'"
                :class="[
                  'py-2 px-1 border-b-2 font-medium text-sm',
                  activeTab === 'api-keys'
                    ? 'border-primary-brandColor text-primary-brandColor'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                ]"
              >
                API Keys
              </button>
              
              <button
                @click="activeTab = 'export'"
                :class="[
                  'py-2 px-1 border-b-2 font-medium text-sm',
                  activeTab === 'export'
                    ? 'border-primary-brandColor text-primary-brandColor'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                ]"
              >
                Export Data
              </button>
              
              <button
                @click="activeTab = 'connectors'"
                :class="[
                  'py-2 px-1 border-b-2 font-medium text-sm',
                  activeTab === 'connectors'
                    ? 'border-primary-brandColor text-primary-brandColor'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                ]"
              >
                Connected Apps
              </button>

              <!-- Admin Panel Tab (only show if enabled) -->
              <button
                v-if="isAdminPanelEnabled"
                @click="activeTab = 'admin'"
                :class="[
                  'py-2 px-1 border-b-2 font-medium text-sm',
                  activeTab === 'admin'
                    ? 'border-primary-brandColor text-primary-brandColor'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                ]"
              >
                LLM Configuration
              </button>

            </nav>
          </div>
        </div>

        <!-- Error Message -->
        <div v-if="errorMessage" class="mb-4 p-3 bg-red-100 text-red-700 rounded">
          {{ errorMessage }}
        </div>

        <!-- Success Message -->
        <div v-if="successMessage" class="mb-4 p-3 bg-green-100 text-green-700 rounded">
          {{ successMessage }}
        </div>

        <!-- Tab Content -->
        <div class="tab-content">

          <!-- API Keys Tab -->
          <div v-if="activeTab === 'api-keys'" class="space-y-6">
            <!-- Show different UI based on admin panel status -->
            <div v-if="isAdminPanelEnabled" class="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h3 class="text-lg font-semibold text-blue-800 mb-2">API Key Management has Moved</h3>
              <p class="text-sm text-blue-700 mb-3">
                When the Admin Panel is enabled, all API keys are managed through the Admin Panel tab.
              </p>
              <ul class="list-disc list-inside text-sm text-blue-700 space-y-1 ml-4">
                <li>Configure your LLM provider (SambaNova, Fireworks, Together)</li>
                <li>Set API keys for each provider</li>
                <li>Customize model selection for different tasks</li>
              </ul>
              <button
                @click="activeTab = 'admin'"
                class="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                Go to Admin Panel →
              </button>
            </div>

            <!-- Original API Keys UI - only shown when admin panel is disabled -->
            <template v-else>
          <!-- SambaNova API Key -->
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              SambaNova API Key <span v-if="missingKeys.sambanova" class="text-red-500 text-sm mt-1">(*Required Key)</span>
              <a 
                href="https://cloud.sambanova.ai/"
                target="_blank"
                class="text-primary-link hover:text-primary-800 ml-2 text-sm"
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
                class="px-3 py-1 text-sm border  border-primary-brandBorder text-primary-brandColor text-sm  rounded focus:outline-none"
              >
                Clear Key
              </button>
              <button 
                @click="saveSambanovaKey"
                class="px-3 py-1 text-sm bg-primary-brandColor text-white rounded focus:outline-none"
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
                class="text-primary-link hover:text-primary-800 ml-2 text-sm"
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
                class="px-3 py-1 text-sm border  border-primary-brandBorder text-primary-brandColor text-sm  rounded focus:outline-none"
              >
                Clear Key
              </button>
              <button 
                @click="saveExaKey"
                class="px-3 py-1 text-sm bg-primary-brandColor text-white rounded focus:outline-none"
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
                class="text-primary-link hover:text-primary-800 ml-2 text-sm"
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
                class="px-3 py-1 text-sm border  border-primary-brandBorder text-primary-brandColor text-sm  rounded focus:outline-none"
              >
                Clear Key
              </button>
              <button 
                @click="saveSerperKey"
                class="px-3 py-1 text-sm bg-primary-brandColor text-white rounded focus:outline-none"
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
                class="text-primary-link hover:text-primary-800 ml-2 text-sm"
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
                class="px-3 py-1 text-sm border  border-primary-brandBorder text-primary-brandColor text-sm  rounded focus:outline-none"
              >
                Clear Key
              </button>
              <button 
                @click="saveFireworksKey"
                class="px-3 py-1 text-sm bg-primary-brandColor text-white rounded focus:outline-none"
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
            </label>
            <select
              v-model="selectedModel"
              @change="handleModelSelection"
              class="block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
            >
              <option value="DeepSeek V3">DeepSeek V3 - 32K</option>
            </select>
          </div>

          <div class="mt-6 border-t flex flex-row justify-between pt-4">
            <div class="flex flex-col items-center">
            <label class="block text-sm   font-medium text-gray-700 mb-2">
              Select provider
            </label>
            <SelectProvider  v-model:selectedOption="selectedOption" />
          </div>
          <div class="mt-6 flex flex-row items-center pt-4 text-primary-link">
            <a class="text-sm underline" href="https://community.sambanova.ai/c/agents/87" target="_blank">FAQ (SN Community)</a>
            </div>
          </div>
          
          <!-- Delete Account Section -->
          <div class="mt-8 pt-6 border-t border-gray-200">
            <div class="relative">
              <!-- Empty div to match the structure of other sections -->
            </div>
            <div class="flex justify-start space-x-2 mt-2">
              <button 
                @click="confirmDeleteAccount" 
                class="text-red-600 underline text-sm hover:text-red-700 focus:outline-none"
              >
                Delete Account
              </button>
            </div>
          </div>
          </template>
          </div>

          <!-- Export Data Tab -->
          <div v-if="activeTab === 'export'" class="space-y-6">
            <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h3 class="text-lg font-medium text-blue-900 mb-2">Export Your Data</h3>
              <p class="text-sm text-blue-700 mb-4">
                Download all your conversations, uploaded files, and generated artifacts in a convenient ZIP archive. 
                This includes your complete chat history and all associated files.
              </p>
              
              <!-- Export Status -->
              <div v-if="exportStatus && exportStatus.status !== 'no_export'" class="mb-4 p-3 rounded-md" 
                   :class="exportStatus.status === 'ready' ? 'bg-green-100 border border-green-200' : 'bg-yellow-100 border border-yellow-200'">
                <div class="flex items-center">
                  <svg v-if="exportStatus.status === 'ready'" class="w-5 h-5 text-green-600 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                  </svg>
                  <svg v-else class="w-5 h-5 text-yellow-600 mr-2 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <div>
                    <p class="font-medium" :class="exportStatus.status === 'ready' ? 'text-green-800' : 'text-yellow-800'">
                      {{ exportStatus.status === 'ready' ? 'Export Ready!' : 'Export Processing...' }}
                    </p>
                    <p class="text-sm" :class="exportStatus.status === 'ready' ? 'text-green-600' : 'text-yellow-600'">
                      {{ exportStatus.status === 'ready' 
                          ? `File: ${exportStatus.filename} (${formatFileSize(exportStatus.size)})` 
                          : 'This may take a few minutes depending on your data size.' }}
                    </p>
                  </div>
                </div>
                
                <!-- Download button when ready -->
                <div v-if="exportStatus.status === 'ready'" class="mt-3 flex space-x-2">
                  <button 
                    @click="downloadExport"
                    class="inline-flex items-center px-3 py-2 text-sm bg-green-600 text-white rounded-md hover:bg-green-700 focus:outline-none"
                    :disabled="isDownloading"
                  >
                    <svg v-if="isDownloading" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <svg v-else class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                    </svg>
                    {{ isDownloading ? 'Downloading...' : 'Download Export' }}
                  </button>
                  <button 
                    @click="clearExport"
                    class="px-3 py-2 text-sm border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 focus:outline-none"
                  >
                    Clear
                  </button>
                </div>
              </div>
              
              <!-- Request Export Button -->
              <div class="flex justify-between items-center">
                <div>
                  <button 
                    @click="confirmExport"
                    class="inline-flex items-center px-4 py-2 bg-primary-brandColor text-white text-sm font-medium rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
                    :disabled="isExporting || (exportStatus && exportStatus.status === 'processing')"
                  >
                    <svg v-if="isExporting" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <svg v-else class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"/>
                    </svg>
                    {{ isExporting ? 'Requesting Export...' : 'Request Export' }}
                  </button>
                </div>
                
                <div class="text-sm text-gray-600">
                  <button 
                    @click="checkExportStatus" 
                    class="text-primary-brandColor hover:text-primary-700 underline"
                    :disabled="isCheckingStatus"
                  >
                    {{ isCheckingStatus ? 'Checking...' : 'Check Status' }}
                  </button>
                </div>
              </div>
              
              <!-- Export Info -->
              <div class="mt-4 text-xs text-gray-600">
                <p>• Your export will include all conversations, messages, uploaded files, and generated artifacts</p>
                <p>• Files are organized by type and include metadata</p>
                <p>• Exports are available for download for 24 hours</p>
                <p>• Large exports may take several minutes to process</p>
              </div>
            </div>
          </div>

          <!-- Connected Apps Tab -->
          <div v-if="activeTab === 'connectors'" class="space-y-4">
            <CleanConnectorsTab @connector-updated="handleConnectorUpdate" />
          </div>

          <!-- Admin Panel Tab -->
          <div v-if="activeTab === 'admin' && isAdminPanelEnabled" class="space-y-4">
            <AdminPanelSettings
              @configuration-updated="handleConfigurationUpdate"
              @api-keys-updated="handleApiKeysUpdate"
            />
          </div>

        </div>

        <!-- Export Confirmation Modal -->
        <div v-if="showExportConfirmation" class="fixed inset-0 z-50 overflow-y-auto" style="background-color: rgba(0, 0, 0, 0.5);">
          <div class="flex min-h-screen items-center justify-center p-4">
            <div class="relative w-full max-w-md bg-white rounded-lg shadow-lg p-6">
              <div class="text-center">
                <svg class="mx-auto h-12 w-12 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"/>
                </svg>
                <h3 class="mt-4 text-lg font-medium text-primary-brandTextPrimary">Confirm Data Export</h3>
                <p class="mt-2 text-sm text-gray-500 text-left text-primary-brandTextSecondary">
                  This will create a ZIP archive containing all your conversations, messages, uploaded files, and generated artifacts. 
                  The export may take several minutes to process depending on the amount of data.
                </p>
                <p class="mt-2 text-sm text-blue-600 text-left">
                  Your export will be available for download for 24 hours and will include:
                </p>
                <ul class="mt-1 text-sm text-gray-500 text-left list-disc list-inside">
                  <li>All conversation history and metadata</li>
                  <li>Uploaded files and generated artifacts</li>
                  <li>Organized folder structure with README</li>
                </ul>
                <div class="mt-6 flex justify-center space-x-4">
                  <button 
                    @click="cancelExport" 
                    class="px-3 py-1 text-sm border border-primary-brandBorder text-primary-brandColor text-sm rounded focus:outline-none"
                  >
                    Cancel
                  </button>
                  <button 
                    @click="executeExport" 
                    class="inline-flex items-center px-3 py-1 text-sm bg-primary-brandColor text-white rounded focus:outline-none focus:outline-none"
                    :disabled="isExporting"
                  >
                    <svg v-if="isExporting" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    {{ isExporting ? 'Requesting...' : 'Start Export' }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Delete Account Confirmation Modal -->
        <div v-if="showDeleteConfirmation" class="fixed inset-0 z-50 overflow-y-auto" style="background-color: rgba(0, 0, 0, 0.5);">
          <div class="flex min-h-screen items-center justify-center p-4">
            <div class="relative w-full max-w-md bg-white rounded-lg shadow-lg p-6">
              <div class="text-center">
                <h3 class="mt-4 text-lg font-medium text-primary-brandTextPrimary ">Confirm Data Deletion</h3>
                <p class="mt-2 text-sm text-gray-500 text-left  text-primary-brandTextSecondary">
                  Are you sure you want to delete all your data? This will permanently delete all your conversations, documents, and API keys. This action cannot be undone and will log you out.
                </p>
                <div class="mt-6 flex justify-center space-x-4">
                  <button 
                    @click="cancelDeleteAccount" 
                    class="px-3 py-1 text-sm border  border-primary-brandBorder text-primary-brandColor text-sm  rounded focus:outline-none"
                  >
                    Cancel
                  </button>
                  <button 
                    @click="executeDeleteAccount" 
                    class="inline-flex items-center px-3 py-1 text-sm bg-primary-brandColor text-white rounded focus:outline-none focus:outline-none "
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
import { ref, watch, defineProps, defineExpose, defineEmits, onMounted, computed, inject, nextTick } from 'vue'
import { useAuth0 } from '@auth0/auth0-vue'
import { encryptKey, decryptKey } from '../utils/encryption'
import axios from 'axios'
import emitterMitt from '@/utils/eventBus.js';
import SelectProvider from '@/components/ChatMain/SelectProvider.vue'
import AdminPanelSettings from '@/components/AdminPanelSettings.vue'
import CleanConnectorsTab from '@/components/Settings/CleanConnectorsTab.vue'


const selectedOption = inject('selectedOption')

const isUserKeysEnabled = computed(() => {
  return import.meta.env.VITE_ENABLE_USER_KEYS === 'true'
})

const isAdminPanelEnabled = computed(() => {
  return import.meta.env.VITE_SHOW_ADMIN_PANEL === 'true'
})




const props = defineProps({
  provider: String, // Current provider name passed from parent
})

const emit = defineEmits(['keysUpdated'])

const { user, getAccessTokenSilently, logout } = useAuth0()
const userId = computed(() => user.value?.sub)

const isOpen = ref(false)
const activeTab = ref('api-keys')  // Default to api-keys tab
const sambanovaKey = ref('')
const exaKey = ref('')
const serperKey = ref('')
const fireworksKey = ref('')
const errorMessage = ref('')
const successMessage = ref('')
// Available model options - update both here and in the template when adding new models
const AVAILABLE_MODELS = ['DeepSeek V3']
const selectedModel = ref(null)
const keysLoaded = ref(false)
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


const loadKeys = async () => {
  if (!userId.value) return;

  try {
    // Get all saved keys from localStorage
    const savedSambanovaKey = localStorage.getItem(`sambanova_key_${userId.value}`);
    const savedExaKey = localStorage.getItem(`exa_key_${userId.value}`);
    const savedSerperKey = localStorage.getItem(`serper_key_${userId.value}`);
    const savedFireworksKey = localStorage.getItem(`fireworks_key_${userId.value}`);
    const savedModel = localStorage.getItem(`selected_model_${userId.value}`);

    // Decrypt and set sambanova key (always available)
    sambanovaKey.value = savedSambanovaKey ? await decryptKey(savedSambanovaKey) : '';
    
    // Decrypt and set other keys only if user keys are enabled
    if (isUserKeysEnabled.value) {
      exaKey.value = savedExaKey ? await decryptKey(savedExaKey) : '';
      serperKey.value = savedSerperKey ? await decryptKey(savedSerperKey) : '';
      fireworksKey.value = savedFireworksKey ? await decryptKey(savedFireworksKey) : '';
    } else {
      exaKey.value = '';
      serperKey.value = '';
      fireworksKey.value = '';
    }

    // Handle model selection
    if (!savedModel || savedModel === 'null' || savedModel === 'undefined' || savedModel.trim() === '' || !AVAILABLE_MODELS.includes(savedModel)) {
      selectedModel.value = 'DeepSeek V3';
      localStorage.setItem(`selected_model_${userId.value}`, 'DeepSeek V3');
    } else {
      selectedModel.value = savedModel;
    }
    
  } catch (error) {
    console.error('Failed to load keys:', error);
    errorMessage.value = 'Failed to load saved keys';
  }
}

// Load keys on mount and check if modal should be open
watch(userId, async (newId) => {
  if (newId) {
    await loadKeys()
    keysLoaded.value = true
    checkRequiredKeys() // Ensure modal opens if needed
    emitterMitt.emit('keys-updated', missingKeys.value)
  }
}, { immediate: true })

onMounted(() => {
  emitterMitt.on('check-keys', checkRequiredKeys);
});


// Watch for provider changes and check required keys dynamically
watch(() => props.provider, async () => {
  await checkRequiredKeys()
  updateAndCallEvents()
})
watch([exaKey, serperKey, sambanovaKey, fireworksKey], () => {
  // checkRequiredKeys()
})

// ✅ Function to check if required keys are missing
const checkRequiredKeys = () => {

  if (!keysLoaded.value) return;

  missingKeys.value = {
    exa: !exaKey.value&&isUserKeysEnabled.value,
    serper: !serperKey.value&&isUserKeysEnabled.value,
    sambanova: props.provider === 'sambanova' && !sambanovaKey.value,
    fireworks: props.provider === 'fireworks' && !fireworksKey.value&&isUserKeysEnabled.value
  }

  isOpen.value = Object.values(missingKeys.value).some((missing) => missing)
  emitterMitt.emit('keys-updated',  missingKeys.value );

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

// ✅ Function to manually open modal
const openModal = (tabName = null) => {
  // Ensure tabName is a string or null, not an event object
  if (tabName && typeof tabName === 'string') {
    activeTab.value = tabName
  } else {
    // Ensure we always have a default tab
    activeTab.value = 'api-keys'
  }

  isOpen.value = true
}

// ✅ Function to manually close modal
const close = () => {
  isOpen.value = false
  // Don't reset activeTab here - keep the last selected tab
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
  // Skip updating keys via /set_api_keys if admin panel is enabled
  // Admin panel manages all keys through /admin/config endpoint
  if (isAdminPanelEnabled.value) {
    console.log('Admin panel is enabled, skipping /set_api_keys call')
    return
  }

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
        'Authorization': `Bearer ${await getAccessTokenSilently()}`

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

const updateAndCallEvents=()=>{

  checkRequiredKeys()

  emit('keysUpdated')
  emitterMitt.emit('keys-updated',  missingKeys.value );

}

// Admin Panel handlers
const handleConfigurationUpdate = (config) => {
  console.log('Configuration updated:', config)
  // Update the selectedOption with the new provider from the admin config
  if (config && config.default_provider && selectedOption && selectedOption.value) {
    const providerMapping = {
      'sambanova': { label: 'SambaNova', value: 'sambanova' },
      'fireworks': { label: 'Fireworks AI', value: 'fireworks' },
      'together': { label: 'Together AI', value: 'together' }
    }

    if (providerMapping[config.default_provider]) {
      selectedOption.value = providerMapping[config.default_provider]
      console.log('Updated selectedOption to:', selectedOption.value)
    }
  }
}

const handleApiKeysUpdate = (apiKeys) => {
  console.log('API keys updated:', apiKeys)
  // Update the missing keys and emit events
  updateAndCallEvents()
}

// Connector update handler
const handleConnectorUpdate = () => {
  console.log('Connector updated')
  // Any additional logic if needed
}

// ✅ Expose methods for parent component
defineExpose({
  openModal,
  checkRequiredKeys,
  activeTab,  // Expose activeTab so parent can set it
  exaKey: exaKey.value,
    serperKey: serperKey.value,
    fireworksKey: fireworksKey.value,
    selectedModel: selectedModel.value
})

// Export functionality
const showExportConfirmation = ref(false)
const isExporting = ref(false)
const isDownloading = ref(false)
const isCheckingStatus = ref(false)
const exportStatus = ref(null)

// Format file size for display
const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// Check export status on mount if export tab is active
const checkExportStatus = async () => {
  if (isCheckingStatus.value) return
  
  try {
    isCheckingStatus.value = true
    const response = await axios.get(`${import.meta.env.VITE_API_URL}/export/status`, {
      headers: {
        'Authorization': `Bearer ${await getAccessTokenSilently()}`
      }
    })
    
    if (response.status === 200) {
      exportStatus.value = response.data
    } else if (response.status === 404) {
      exportStatus.value = { status: 'no_export' }
    }
  } catch (error) {
    if (error.response?.status === 404) {
      exportStatus.value = { status: 'no_export' }
    } else {
      console.error('Error checking export status:', error)
      errorMessage.value = 'Failed to check export status'
    }
  } finally {
    isCheckingStatus.value = false
  }
}

const confirmExport = () => {
  showExportConfirmation.value = true
}

const cancelExport = () => {
  showExportConfirmation.value = false
}

const executeExport = async () => {
  try {
    isExporting.value = true
    showExportConfirmation.value = false
    
    const response = await axios.post(`${import.meta.env.VITE_API_URL}/export/request`, {}, {
      headers: {
        'Authorization': `Bearer ${await getAccessTokenSilently()}`
      }
    })
    
    if (response.status === 202) {
      successMessage.value = 'Export request submitted! You will be notified when your export is ready.'
      exportStatus.value = { status: 'processing' }
      
      // Start polling for status updates
      setTimeout(() => {
        pollExportStatus()
      }, 5000) // Start checking after 5 seconds
      
    } else {
      errorMessage.value = 'Failed to request export. Please try again.'
    }
  } catch (error) {
    console.error('Error requesting export:', error)
    errorMessage.value = error.response?.data?.error || 'Failed to request export. Please try again.'
  } finally {
    isExporting.value = false
    clearMessagesAfterDelay()
  }
}

const pollExportStatus = async () => {
  try {
    await checkExportStatus()
    
    // Continue polling if still processing
    if (exportStatus.value?.status === 'processing') {
      setTimeout(() => {
        pollExportStatus()
      }, 10000) // Check every 10 seconds
    }
  } catch (error) {
    console.error('Error polling export status:', error)
  }
}

const downloadExport = async () => {
  if (isDownloading.value) return
  
  try {
    isDownloading.value = true
    
    const response = await axios.get(`${import.meta.env.VITE_API_URL}/export/download`, {
      headers: {
        'Authorization': `Bearer ${await getAccessTokenSilently()}`
      },
      responseType: 'blob'
    })
    
    if (response.status === 200) {
      // Create download link
      const blob = new Blob([response.data], { type: 'application/zip' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = exportStatus.value?.filename || 'samba_copilot_export.zip'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
      
      successMessage.value = 'Export downloaded successfully!'
    } else {
      errorMessage.value = 'Failed to download export'
    }
  } catch (error) {
    console.error('Error downloading export:', error)
    errorMessage.value = error.response?.data?.error || 'Failed to download export'
  } finally {
    isDownloading.value = false
    clearMessagesAfterDelay()
  }
}

const clearExport = async () => {
  try {
    const response = await axios.delete(`${import.meta.env.VITE_API_URL}/export/clear`, {
      headers: {
        'Authorization': `Bearer ${await getAccessTokenSilently()}`
      }
    })
    
    if (response.status === 200) {
      exportStatus.value = { status: 'no_export' }
      successMessage.value = 'Export data cleared successfully'
    } else {
      errorMessage.value = 'Failed to clear export data'
    }
  } catch (error) {
    console.error('Error clearing export:', error)
    errorMessage.value = 'Failed to clear export data'
  } finally {
    clearMessagesAfterDelay()
  }
}

// Check export status when the export tab becomes active
watch(activeTab, (newTab) => {
  if (newTab === 'export') {
    checkExportStatus()
  }
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
        'Authorization': `Bearer ${await getAccessTokenSilently()}`
      }
    })
    
    if (response.status === 200) {
      // Clear local storage
      // const keysToRemove = [
      //   `sambanova_key_${userId.value}`,
      //   `exa_key_${userId.value}`,
      //   `serper_key_${userId.value}`,
      //   `fireworks_key_${userId.value}`
      // ]
      
      // keysToRemove.forEach(key => localStorage.removeItem(key))

      localStorage.clear();

      
      // Show success message briefly
      successMessage.value = 'Account data deleted successfully. Logging out...'
      
      // Log out the user after a short delay
      setTimeout(async () => {
        logout({ logoutParams: { returnTo: window.location.origin } })
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
