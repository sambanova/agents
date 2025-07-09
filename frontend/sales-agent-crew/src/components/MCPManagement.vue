<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex justify-between items-center">
      <div>
        <h3 class="text-lg font-semibold text-primary-brandTextPrimary">MCP Tools & Integrations</h3>
        <p class="text-sm text-primary-brandTextSecondary mt-1">
          Manage your Model Context Protocol (MCP) servers to connect external tools and data sources
        </p>
      </div>
      <div class="flex items-center space-x-3">
        <button 
          @click="refreshAllServerStatus"
          :disabled="refreshing"
          class="px-3 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-500 disabled:opacity-50"
        >
          {{ refreshing ? 'Refreshing...' : 'Refresh Status' }}
        </button>
        <button 
          @click="showAddServer = true"
          class="px-4 py-2 bg-primary-brandColor text-white rounded-md hover:bg-primary-brandColorHover focus:outline-none focus:ring-2 focus:ring-primary-brandColor"
        >
          Add Server
        </button>
      </div>
    </div>

    <!-- Server List -->
    <div class="space-y-3">
      <div v-if="loading" class="text-center py-8">
        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-brandColor mx-auto"></div>
        <p class="mt-2 text-sm text-primary-brandTextSecondary">Loading MCP servers...</p>
      </div>
      
      <div v-else-if="servers.length === 0" class="text-center py-8">
        <div class="text-gray-400 mb-4">
          <svg class="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
          </svg>
        </div>
        <p class="text-primary-brandTextSecondary">No MCP servers configured</p>
        <p class="text-sm text-primary-brandTextSecondary mt-1">Add your first server to get started</p>
      </div>

      <div v-else class="space-y-3">
        <div 
          v-for="server in servers" 
          :key="server.server_id"
          class="border border-gray-200 rounded-lg p-4 hover:border-primary-brandColor transition-colors"
        >
          <div class="flex justify-between items-start">
            <div class="flex-1">
              <div class="flex items-center space-x-3">
                <h4 class="font-medium text-primary-brandTextPrimary">{{ server.name }}</h4>
                <span 
                  :class="[
                    'px-2 py-1 rounded-full text-xs font-medium',
                    server.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                  ]"
                >
                  {{ server.enabled ? 'Enabled' : 'Disabled' }}
                </span>
                <span 
                  v-if="server.health_status"
                  :class="[
                    'px-2 py-1 rounded-full text-xs font-medium',
                    getHealthStatusColor(server.health_status)
                  ]"
                >
                  {{ formatHealthStatus(server.health_status) }}
                </span>
                <button
                  v-if="server.health_status_loading"
                  class="inline-flex items-center px-2 py-1 text-xs text-gray-500"
                  disabled
                >
                  <div class="animate-spin rounded-full h-3 w-3 border-b border-gray-400 mr-1"></div>
                  Checking...
                </button>
              </div>
              <p class="text-sm text-primary-brandTextSecondary mt-1">{{ server.description }}</p>
              <div class="flex items-center space-x-4 mt-2 text-xs text-primary-brandTextSecondary">
                <span>{{ server.transport.toUpperCase() }}</span>
                <span>{{ server.url || server.command }}</span>
                <span v-if="server.tools && server.tools.length > 0">
                  {{ server.tools.length }} tool{{ server.tools.length > 1 ? 's' : '' }}
                </span>
              </div>
            </div>
            <div class="flex items-center space-x-2 ml-4">
              <!-- Start/Stop removed: orchestrator auto-manages lifecycle -->
              <button 
                @click="toggleServer(server)"
                :class="[
                  'px-3 py-1 rounded text-sm font-medium transition-colors',
                  server.enabled 
                    ? 'bg-orange-100 text-orange-800 hover:bg-orange-200' 
                    : 'bg-green-100 text-green-800 hover:bg-green-200'
                ]"
              >
                {{ server.enabled ? 'Disable' : 'Enable' }}
              </button>
              <button 
                @click="refreshServerHealth(server)"
                :disabled="server.health_status_loading"
                class="p-2 text-primary-brandTextSecondary hover:text-primary-brandTextPrimary transition-colors disabled:opacity-50"
                title="Refresh server status"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
                </svg>
              </button>
              <button 
                @click="editServer(server)"
                class="p-2 text-primary-brandTextSecondary hover:text-primary-brandTextPrimary transition-colors"
                title="Edit server"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                </svg>
              </button>
              <button 
                @click="deleteServer(server)"
                class="p-2 text-red-600 hover:text-red-800 transition-colors"
                title="Delete server"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                </svg>
              </button>
            </div>
          </div>
          
          <!-- Tool List -->
          <div v-if="server.tools && server.tools.length > 0" class="mt-3 pt-3 border-t border-gray-100">
            <div class="flex flex-wrap gap-2">
              <span 
                v-for="tool in server.tools" 
                :key="tool.name"
                class="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs"
                :title="tool.description"
              >
                {{ tool.name }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Add/Edit Server Modal -->
    <div v-if="showAddServer || editingServer" class="fixed inset-0 z-50 overflow-y-auto">
      <div class="flex min-h-screen items-center justify-center p-4">
        <div class="fixed inset-0 bg-black opacity-30" @click="closeModal"></div>
        
        <div class="relative w-full max-w-2xl bg-white rounded-xl shadow-lg p-6">
          <div class="flex justify-between items-center mb-6">
            <h3 class="text-lg font-semibold text-primary-brandTextPrimary">
              {{ editingServer ? 'Edit MCP Server' : 'Add MCP Server' }}
            </h3>
            <button @click="closeModal" class="text-primary-brandTextSecondary hover:text-gray-700">
              <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <form @submit.prevent="saveServer" class="space-y-4">
            <!-- Basic Information -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                <input 
                  v-model="serverForm.name"
                  type="text"
                  required
                  class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-brandColor"
                  placeholder="e.g., Jira"
                />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Transport *</label>
                <select 
                  v-model="serverForm.transport"
                  required
                  class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-brandColor"
                >
                  <option value="stdio">stdio</option>
                </select>
              </div>
            </div>

            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <textarea 
                v-model="serverForm.description"
                rows="2"
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-brandColor"
                placeholder="Brief description of what this server provides"
              />
            </div>

            <!-- Transport-specific fields -->
            <div v-if="serverForm.transport === 'http' || serverForm.transport === 'sse'">
              <label class="block text-sm font-medium text-gray-700 mb-1">URL *</label>
              <input 
                v-model="serverForm.url"
                type="url"
                required
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-brandColor"
                placeholder="https://example.com/mcp"
              />
            </div>

            <div v-if="serverForm.transport === 'stdio'">
              <label class="block text-sm font-medium text-gray-700 mb-1">Command *</label>
              <input 
                v-model="serverForm.command"
                type="text"
                required
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-brandColor"
                placeholder="e.g., mcp-server-name"
              />
            </div>

            <!-- Command Arguments -->
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Arguments</label>
              <div class="space-y-2">
                <div v-for="(arg, index) in serverForm.args" :key="index" class="flex space-x-2">
                  <input 
                    v-model="serverForm.args[index]"
                    type="text"
                    class="flex-1 border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-brandColor"
                    placeholder="--argument-name"
                  />
                  <button 
                    type="button"
                    @click="removeArg(index)"
                    class="px-3 py-2 text-red-600 hover:text-red-800"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                    </svg>
                  </button>
                </div>
                <button 
                  type="button"
                  @click="addArg"
                  class="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                >
                  + Add Argument
                </button>
              </div>
            </div>

            <!-- Environment Variables -->
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Environment Variables</label>
              <div class="space-y-2">
                <div v-for="(envVar, index) in serverForm.envVars" :key="index" class="flex space-x-2">
                  <input 
                    v-model="envVar.key"
                    type="text"
                    class="flex-1 border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-brandColor"
                    placeholder="VARIABLE_NAME"
                  />
                  <input 
                    v-model="envVar.value"
                    type="text"
                    class="flex-1 border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-brandColor"
                    placeholder="variable_value"
                  />
                  <button 
                    type="button"
                    @click="removeEnvVar(index)"
                    class="px-3 py-2 text-red-600 hover:text-red-800"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                    </svg>
                  </button>
                </div>
                <button 
                  type="button"
                  @click="addEnvVar"
                  class="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                >
                  + Add Environment Variable
                </button>
              </div>
            </div>

            <!-- Enable/Disable -->
            <div class="flex items-center">
              <input 
                v-model="serverForm.enabled"
                type="checkbox"
                class="h-4 w-4 text-primary-brandColor focus:ring-primary-brandColor border-gray-300 rounded"
              />
              <label class="ml-2 block text-sm text-gray-700">
                Enable this server immediately
              </label>
            </div>

            <!-- Form Actions -->
            <div class="flex justify-end space-x-3 pt-4">
              <button 
                type="button"
                @click="closeModal"
                class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button 
                type="submit"
                :disabled="saving"
                class="px-4 py-2 bg-primary-brandColor text-white rounded-md hover:bg-primary-brandColorHover disabled:opacity-50"
              >
                {{ saving ? 'Saving...' : (editingServer ? 'Update Server' : 'Add Server') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Error Messages -->
    <div v-if="error" class="mt-4 p-3 bg-red-100 text-red-700 rounded-md">
      {{ error }}
    </div>

    <!-- Success Messages -->
    <div v-if="success" class="mt-4 p-3 bg-green-100 text-green-700 rounded-md">
      {{ success }}
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuth } from '@clerk/vue'
import axios from 'axios'

const { userId } = useAuth()

// State
const servers = ref([])
const loading = ref(false)
const refreshing = ref(false)
const error = ref('')
const success = ref('')
const showAddServer = ref(false)
const editingServer = ref(null)
const saving = ref(false)

// Form state
const serverForm = ref({
  name: '',
  description: '',
  transport: 'stdio',
  url: '',
  command: '',
  args: [],
  envVars: [],
  enabled: false
})

// Load servers on mount
onMounted(async () => {
  await loadServers()
})

// Load servers from API - OPTIMIZED: Don't auto-load health status
async function loadServers() {
  loading.value = true
  error.value = ''
  try {
    const response = await axios.get(`${import.meta.env.VITE_API_URL}/mcp/servers`, {
      headers: {
        'Authorization': `Bearer ${await window.Clerk.session.getToken()}`
      }
    })
    servers.value = response.data.servers
    
    // Initialize additional properties for UI state
    servers.value.forEach(server => {
      server.health_status_loading = false
    })
    
    // Only load health status for enabled servers on initial load
    const enabledServers = servers.value.filter(s => s.enabled)
    if (enabledServers.length > 0) {
      await loadServerDetailsForServers(enabledServers)
    }
  } catch (err) {
    error.value = 'Failed to load MCP servers'
    console.error('Error loading servers:', err)
  } finally {
    loading.value = false
  }
}

// Load health status for specific servers - OPTIMIZED: Batch requests
async function loadServerDetailsForServers(serverList) {
  const promises = serverList.map(async (server) => {
    server.health_status_loading = true
    try {
      const healthResponse = await axios.get(`${import.meta.env.VITE_API_URL}/mcp/servers/${server.server_id}/health`, {
        headers: {
          'Authorization': `Bearer ${await window.Clerk.session.getToken()}`
        }
      })
      server.health_status = healthResponse.data.status
      server.tools = healthResponse.data.available_tools || []
    } catch (err) {
      console.warn(`Failed to get health status for server ${server.server_id}:`, err)
      server.health_status = 'unknown'
      server.tools = []
    } finally {
      server.health_status_loading = false
    }
  })
  
  await Promise.allSettled(promises)
}

// Refresh all server status
async function refreshAllServerStatus() {
  refreshing.value = true
  try {
    await loadServerDetailsForServers(servers.value)
    success.value = 'Server status refreshed'
    clearMessages()
  } catch (err) {
    error.value = 'Failed to refresh server status'
    console.error('Error refreshing status:', err)
  } finally {
    refreshing.value = false
  }
}

// Refresh single server health
async function refreshServerHealth(server) {
  await loadServerDetailsForServers([server])
}

// Start/stop functions removed – orchestrator handles lifecycle automatically

// Toggle server enabled/disabled
async function toggleServer(server) {
  try {
    await axios.post(`${import.meta.env.VITE_API_URL}/mcp/servers/${server.server_id}/toggle`, {}, {
      headers: {
        'Authorization': `Bearer ${await window.Clerk.session.getToken()}`
      }
    })
    server.enabled = !server.enabled
    success.value = `Server ${server.enabled ? 'enabled' : 'disabled'} successfully`
    
    // Refresh health status after enabling
    if (server.enabled) {
      setTimeout(async () => {
        await refreshServerHealth(server)
      }, 1000)
    }
    
    clearMessages()
  } catch (err) {
    error.value = `Failed to ${server.enabled ? 'disable' : 'enable'} server`
    clearMessages()
  }
}

// Helper functions for UI
function getHealthStatusColor(status) {
  switch (status) {
    case 'healthy':
    case 'running':
      return 'bg-green-100 text-green-800'
    case 'error':
    case 'unhealthy':
      return 'bg-red-100 text-red-800'
    case 'stopped':
      return 'bg-gray-100 text-gray-600'
    case 'starting':
      return 'bg-blue-100 text-blue-800'
    default:
      return 'bg-yellow-100 text-yellow-800'
  }
}

function formatHealthStatus(status) {
  switch (status) {
    case 'healthy':
      return 'Healthy'
    case 'running':
      return 'Running'
    case 'error':
      return 'Error'
    case 'unhealthy':
      return 'Unhealthy'
    case 'stopped':
      return 'Stopped'
    case 'starting':
      return 'Starting'
    default:
      return 'Unknown'
  }
}

// Edit server
function editServer(server) {
  editingServer.value = server
  serverForm.value = {
    name: server.name,
    description: server.description,
    transport: server.transport,
    url: server.url || '',
    command: server.command || '',
    args: [...(server.args || [])],
    envVars: Object.entries(server.env_vars || {}).map(([key, value]) => ({ key, value })),
    enabled: server.enabled
  }
  showAddServer.value = true
}

// Delete server
async function deleteServer(server) {
  if (!confirm(`Are you sure you want to delete "${server.name}"?`)) {
    return
  }
  
  try {
    await axios.delete(`${import.meta.env.VITE_API_URL}/mcp/servers/${server.server_id}`, {
      headers: {
        'Authorization': `Bearer ${await window.Clerk.session.getToken()}`
      }
    })
    servers.value = servers.value.filter(s => s.server_id !== server.server_id)
    success.value = 'Server deleted successfully'
    clearMessages()
  } catch (err) {
    error.value = 'Failed to delete server'
    clearMessages()
  }
}

// Save server (add or update)
async function saveServer() {
  saving.value = true
  error.value = ''
  
  try {
    const serverData = {
      name: serverForm.value.name,
      description: serverForm.value.description,
      transport: serverForm.value.transport,
      url: serverForm.value.url,
      command: serverForm.value.command,
      args: serverForm.value.args.filter(arg => arg.trim() !== ''),
      env_vars: serverForm.value.envVars.reduce((acc, envVar) => {
        if (envVar.key && envVar.value) {
          acc[envVar.key] = envVar.value
        }
        return acc
      }, {}),
      enabled: serverForm.value.enabled
    }
    
    if (editingServer.value) {
      // Update existing server
      await axios.put(`${import.meta.env.VITE_API_URL}/mcp/servers/${editingServer.value.server_id}`, serverData, {
        headers: {
          'Authorization': `Bearer ${await window.Clerk.session.getToken()}`
        }
      })
      success.value = 'Server updated successfully'
    } else {
      // Add new server
      await axios.post(`${import.meta.env.VITE_API_URL}/mcp/servers`, serverData, {
        headers: {
          'Authorization': `Bearer ${await window.Clerk.session.getToken()}`
        }
      })
      success.value = 'Server added successfully'
    }
    
    await loadServers()
    closeModal()
    clearMessages()
  } catch (err) {
    error.value = editingServer.value ? 'Failed to update server' : 'Failed to add server'
    console.error('Error saving server:', err)
  } finally {
    saving.value = false
  }
}

// Close modal
function closeModal() {
  showAddServer.value = false
  editingServer.value = null
  serverForm.value = {
    name: '',
    description: '',
    transport: 'stdio',
    url: '',
    command: '',
    args: [],
    envVars: [],
    enabled: false
  }
}

// Add/remove arguments
function addArg() {
  serverForm.value.args.push('')
}

function removeArg(index) {
  serverForm.value.args.splice(index, 1)
}

// Add/remove environment variables
function addEnvVar() {
  serverForm.value.envVars.push({ key: '', value: '' })
}

function removeEnvVar(index) {
  serverForm.value.envVars.splice(index, 1)
}

// Clear messages after delay
function clearMessages() {
  setTimeout(() => {
    error.value = ''
    success.value = ''
  }, 5000)
}
</script> 