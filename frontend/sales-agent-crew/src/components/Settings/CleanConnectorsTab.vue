<template>
  <div class="space-y-4">
    <div class="mb-4">
      <p class="text-sm text-gray-600">
        Allow Claude to reference other apps and services for more context.
      </p>
    </div>

    <!-- Loading State -->
    <div v-if="loadingConnectors" class="flex justify-center py-8">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-brandColor"></div>
    </div>

    <!-- Empty State -->
    <div v-else-if="!connectors || connectors.length === 0" class="text-center py-8">
      <p class="text-gray-500">No apps available to connect</p>
      <p class="text-sm text-gray-400 mt-2">Check back later for new integrations</p>
    </div>

    <!-- Connectors List -->
    <div v-else class="space-y-3">
      <div
        v-for="connector in connectors"
        :key="connector.provider_id"
        class="flex items-center justify-between p-4 bg-white border border-gray-200 rounded-lg hover:border-gray-300 transition-colors"
      >
        <!-- Left side: Icon and info -->
        <div class="flex items-center space-x-3">
          <img
            v-if="getConnectorIcon(connector.provider_id)"
            :src="getConnectorIcon(connector.provider_id)"
            :alt="connector.name"
            class="w-8 h-8 rounded"
          >
          <div v-else class="w-8 h-8 rounded bg-gray-200 flex items-center justify-center text-sm font-bold">
            {{ connector.name ? connector.name.charAt(0) : '?' }}
          </div>

          <div>
            <h4 class="font-medium text-gray-900">{{ connector.name }}</h4>
            <p v-if="connector.status === 'connected'" class="text-xs text-gray-500">
              Connected
            </p>
            <p v-else class="text-xs text-gray-500">
              Disconnected
            </p>
          </div>
        </div>

        <!-- Right side: Actions -->
        <div class="flex items-center space-x-2">
          <!-- Connected Status Badge -->
          <span
            v-if="connector.status === 'connected'"
            class="text-sm text-blue-600 font-medium"
          >
            Connected
          </span>

          <!-- Connect/Disconnect Button -->
          <button
            v-if="connector.status === 'not_configured'"
            @click="connectApp(connector.provider_id)"
            class="px-4 py-1.5 text-sm bg-white border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 font-medium transition-colors flex items-center space-x-1"
          >
            <span>Connect</span>
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </button>

          <!-- Three dots menu for connected apps -->
          <div v-if="connector.status === 'connected'" class="relative">
            <button
              @click.stop="toggleMenu(connector.provider_id)"
              data-menu-button
              class="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
            >
              <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
              </svg>
            </button>

            <!-- Dropdown Menu -->
            <div
              v-if="openMenuId === connector.provider_id"
              data-menu-dropdown
              class="absolute right-0 mt-2 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-10"
            >
              <button
                @click.stop="openToolSelection(connector)"
                class="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center space-x-2"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                </svg>
                <span>Select tools</span>
              </button>
              <button
                @click.stop="disconnectApp(connector.provider_id)"
                class="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center space-x-2 border-t"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                <span>Disconnect</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Tool Selection Modal -->
    <div
      v-if="showToolModal"
      class="fixed inset-0 z-50 overflow-y-auto"
      @click.self="closeToolModal"
    >
      <div class="flex min-h-screen items-center justify-center p-4">
        <!-- Backdrop -->
        <div class="fixed inset-0 bg-black opacity-30" @click="closeToolModal"></div>

        <!-- Modal -->
        <div class="relative bg-white rounded-xl shadow-lg p-6 max-w-md w-full max-h-[80vh] overflow-hidden flex flex-col">
          <!-- Header -->
          <div class="flex justify-between items-center mb-4">
            <div>
              <h3 class="text-lg font-semibold text-gray-900">
                {{ selectedConnector?.name }} Tools
              </h3>
              <p class="text-sm text-gray-500 mt-1">
                Select which tools to enable for this connection
              </p>
            </div>
            <button @click="closeToolModal" class="text-gray-400 hover:text-gray-600">
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Search -->
          <div class="relative mb-4">
            <input
              v-model="toolSearchQuery"
              type="text"
              placeholder="Search tools..."
              class="w-full px-3 py-2 pl-10 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-primary-brandColor focus:border-primary-brandColor"
            >
            <svg class="absolute left-3 top-2.5 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>

          <!-- Tools List -->
          <div class="flex-1 overflow-y-auto space-y-1 pr-2">
            <label
              v-for="tool in filteredTools"
              :key="tool.id"
              class="flex items-start space-x-3 p-3 hover:bg-gray-50 rounded-lg cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                :checked="tool.enabled"
                @change="toggleTool(selectedConnector.provider_id, tool.id, $event.target.checked)"
                class="mt-0.5 h-4 w-4 text-primary-brandColor rounded border-gray-300 focus:ring-primary-brandColor"
              >
              <div class="flex-1">
                <div class="font-medium text-sm text-gray-900">{{ tool.name }}</div>
                <div class="text-xs text-gray-500 mt-0.5">{{ tool.description }}</div>
              </div>
            </label>

            <div v-if="filteredTools.length === 0" class="text-center py-4 text-sm text-gray-500">
              No tools found matching "{{ toolSearchQuery }}"
            </div>
          </div>

          <!-- Footer -->
          <div class="mt-4 pt-4 border-t flex justify-between items-center">
            <div class="text-sm text-gray-500">
              {{ enabledToolsCount }} of {{ selectedConnector?.available_tools?.length || 0 }} tools enabled
            </div>
            <div class="flex space-x-2">
              <button
                @click="selectAllTools"
                class="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800"
              >
                Select all
              </button>
              <button
                @click="deselectAllTools"
                class="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800"
              >
                Deselect all
              </button>
              <button
                @click="closeToolModal"
                class="px-4 py-1.5 text-sm bg-primary-brandColor text-white rounded-md hover:bg-primary-700"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- OAuth Progress Modal -->
    <div v-if="oauthInProgress" class="fixed inset-0 z-50 bg-black bg-opacity-50 flex items-center justify-center">
      <div class="bg-white rounded-lg p-6 max-w-sm w-full">
        <h3 class="text-lg font-medium mb-2">Connecting to {{ oauthProviderName }}...</h3>
        <p class="text-sm text-gray-600 mb-4">
          Please complete the authorization in the popup window.
        </p>
        <button @click="cancelOAuth" class="px-4 py-2 bg-gray-300 text-gray-700 rounded hover:bg-gray-400">
          Cancel
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAuth0 } from '@auth0/auth0-vue'

const emit = defineEmits(['connector-updated'])

const { getAccessTokenSilently } = useAuth0()

const connectors = ref([])
const loadingConnectors = ref(false)
const openMenuId = ref(null)
const showToolModal = ref(false)
const selectedConnector = ref(null)
const toolSearchQuery = ref('')
const oauthInProgress = ref(false)
const oauthProviderName = ref('')
const oauthWindow = ref(null)

const connectorIcons = {
  'google': '/icons/google.svg',
  'gmail': 'https://upload.wikimedia.org/wikipedia/commons/7/7e/Gmail_icon_%282020%29.svg',
  'google_drive': 'https://upload.wikimedia.org/wikipedia/commons/1/12/Google_Drive_icon_%282020%29.svg',
  'google_calendar': 'https://upload.wikimedia.org/wikipedia/commons/a/a5/Google_Calendar_icon_%282020%29.svg',
  'atlassian': 'https://wac-cdn.atlassian.com/assets/img/favicons/atlassian/favicon-32x32.png',
  'paypal': 'https://www.paypalobjects.com/webstatic/icon/pp258.png'
}

const getConnectorIcon = (providerId) => {
  return connectorIcons[providerId] || null
}

const filteredTools = computed(() => {
  if (!selectedConnector.value?.available_tools) return []

  if (!toolSearchQuery.value) {
    return selectedConnector.value.available_tools
  }

  const query = toolSearchQuery.value.toLowerCase()
  return selectedConnector.value.available_tools.filter(tool =>
    tool.name.toLowerCase().includes(query) ||
    tool.description.toLowerCase().includes(query)
  )
})

const enabledToolsCount = computed(() => {
  if (!selectedConnector.value?.available_tools) return 0
  return selectedConnector.value.available_tools.filter(t => t.enabled).length
})

const toggleMenu = (providerId) => {
  openMenuId.value = openMenuId.value === providerId ? null : providerId
}

const openToolSelection = (connector) => {
  selectedConnector.value = connector
  showToolModal.value = true
  openMenuId.value = null
  toolSearchQuery.value = ''
}

const closeToolModal = () => {
  showToolModal.value = false
  selectedConnector.value = null
  toolSearchQuery.value = ''
}

const selectAllTools = () => {
  if (selectedConnector.value?.available_tools) {
    selectedConnector.value.available_tools.forEach(tool => {
      tool.enabled = true
      toggleTool(selectedConnector.value.provider_id, tool.id, true)
    })
  }
}

const deselectAllTools = () => {
  if (selectedConnector.value?.available_tools) {
    selectedConnector.value.available_tools.forEach(tool => {
      tool.enabled = false
      toggleTool(selectedConnector.value.provider_id, tool.id, false)
    })
  }
}

const fetchConnectors = async () => {
  loadingConnectors.value = true
  try {
    const token = await getAccessTokenSilently()
    const response = await fetch(`${import.meta.env.VITE_API_URL}/connectors/user`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })

    if (response.ok) {
      const data = await response.json()
      // The response is already an array of connectors
      connectors.value = Array.isArray(data) ? data : data.connectors || []
    }
  } catch (error) {
    console.error('Error fetching connectors:', error)
  } finally {
    loadingConnectors.value = false
  }
}

const connectApp = async (providerId) => {
  const connector = connectors.value.find(c => c.provider_id === providerId)
  oauthProviderName.value = connector?.name || providerId
  oauthInProgress.value = true

  try {
    const token = await getAccessTokenSilently()
    const response = await fetch(`${import.meta.env.VITE_API_URL}/connectors/${providerId}/auth/init`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      throw new Error('Failed to initialize OAuth')
    }

    const { authorization_url } = await response.json()

    // Open OAuth window
    const width = 500
    const height = 600
    const left = (window.innerWidth - width) / 2
    const top = (window.innerHeight - height) / 2

    oauthWindow.value = window.open(
      authorization_url,
      `${providerId}_oauth`,
      `width=${width},height=${height},left=${left},top=${top}`
    )

    // Poll for window closure
    const pollTimer = setInterval(() => {
      if (oauthWindow.value && oauthWindow.value.closed) {
        clearInterval(pollTimer)
        oauthInProgress.value = false
        // Refresh connectors after OAuth completes
        setTimeout(() => {
          fetchConnectors()
        }, 1000)
      }
    }, 500)

  } catch (error) {
    console.error('Error connecting app:', error)
    oauthInProgress.value = false
  }
}

const disconnectApp = async (providerId) => {
  openMenuId.value = null

  if (!confirm('Are you sure you want to disconnect this app?')) {
    return
  }

  try {
    const token = await getAccessTokenSilently()
    const response = await fetch(`${import.meta.env.VITE_API_URL}/connectors/${providerId}/disconnect`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })

    if (response.ok) {
      await fetchConnectors()
      emit('connector-updated')
    }
  } catch (error) {
    console.error('Error disconnecting app:', error)
  }
}

const toggleTool = async (providerId, toolId, enabled) => {
  try {
    const token = await getAccessTokenSilently()
    await fetch(`${import.meta.env.VITE_API_URL}/connectors/${providerId}/tools/${toolId}`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ enabled })
    })
  } catch (error) {
    console.error('Error toggling tool:', error)
  }
}

const cancelOAuth = () => {
  if (oauthWindow.value && !oauthWindow.value.closed) {
    oauthWindow.value.close()
  }
  oauthInProgress.value = false
}

// Click outside handler for menu
const handleClickOutside = (event) => {
  if (!event.target.closest('[data-menu-button]') && !event.target.closest('[data-menu-dropdown]')) {
    openMenuId.value = null
  }
}

onMounted(() => {
  fetchConnectors()
  document.addEventListener('click', handleClickOutside)

  // Listen for OAuth completion
  window.addEventListener('message', (event) => {
    if (event.data.type === 'oauth-complete') {
      if (oauthWindow.value) {
        oauthWindow.value.close()
      }
      oauthInProgress.value = false
      fetchConnectors()
    }
  })
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
/* Custom scrollbar for tools list */
.overflow-y-auto::-webkit-scrollbar {
  width: 6px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: #f3f4f6;
  border-radius: 3px;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 3px;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}
</style>