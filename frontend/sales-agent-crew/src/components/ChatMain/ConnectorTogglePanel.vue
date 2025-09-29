<template>
  <div class="connector-toggle-panel">
    <!-- Connector List (Connected and Available) -->
    <div v-if="connectors && connectors.length > 0" class="space-y-2">
      <div
        v-for="connector in connectors"
        :key="connector.provider_id"
        class="flex items-center justify-between py-1.5"
      >
        <div class="flex items-center space-x-2.5">
          <img
            v-if="getConnectorIcon(connector.provider_id)"
            :src="getConnectorIcon(connector.provider_id)"
            :alt="connector.name"
            class="w-5 h-5"
          >
          <div v-else class="w-5 h-5 rounded bg-gray-200 flex items-center justify-center text-xs font-semibold">
            {{ connector.name ? connector.name.charAt(0) : '?' }}
          </div>
          <span class="text-sm text-gray-700">{{ connector.name }}</span>
        </div>

        <!-- Connected: Show Toggle -->
        <label v-if="connector.status === 'connected'" @click.stop class="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            :checked="connector.enabled_in_chat !== false"
            @change="toggleConnector(connector.provider_id, $event.target.checked)"
            class="sr-only peer"
          >
          <div class="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary-brandColor"></div>
        </label>

        <!-- Not Connected: Show Connect Button -->
        <button
          v-else-if="connector.status === 'not_configured'"
          @click.stop="connectApp(connector.provider_id)"
          class="text-sm text-primary-brandColor hover:text-primary-700 font-medium flex items-center space-x-1"
        >
          <span>Connect</span>
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </button>

        <!-- Expired: Show Reconnect Button -->
        <button
          v-else-if="connector.status === 'expired'"
          @click.stop="connectApp(connector.provider_id)"
          class="text-sm text-yellow-600 hover:text-yellow-700 font-medium flex items-center space-x-1"
        >
          <span>Reconnect</span>
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Divider if there are connectors -->
    <div v-if="connectors && connectors.length > 0" class="border-t border-gray-100 my-3"></div>

    <!-- Manage connectors button -->
    <button
      @click.stop="() => { console.log('Manage button clicked'); $emit('manage-connectors') }"
      class="flex items-center space-x-2 w-full py-2 px-2 text-sm text-gray-600 hover:bg-gray-50 rounded-md transition-colors"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
      <span>Manage connectors</span>
      <svg class="w-3 h-3 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
      </svg>
    </button>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuth0 } from '@auth0/auth0-vue'

const emit = defineEmits(['manage-connectors', 'refresh'])

const connectors = ref([])
const loading = ref(false)
const oauthWindow = ref(null)

const { getAccessTokenSilently } = useAuth0()

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

const fetchConnectors = async () => {
  loading.value = true
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
      connectors.value = data.map(c => ({
        ...c,
        enabled_in_chat: c.enabled_in_chat !== undefined ? c.enabled_in_chat : true
      }))
    }
  } catch (error) {
    console.error('Error fetching connectors:', error)
  } finally {
    loading.value = false
  }
}

const toggleConnector = async (providerId, enabled) => {
  console.log('toggleConnector called:', providerId, enabled)
  // Update local state immediately for responsive UI
  const connector = connectors.value.find(c => c.provider_id === providerId)
  if (connector) {
    connector.enabled_in_chat = enabled
    console.log('Updated connector state:', connector)
  }

  // Send update to backend
  try {
    const token = await getAccessTokenSilently()
    const response = await fetch(`${import.meta.env.VITE_API_URL}/connectors/${providerId}/toggle-chat`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ enabled })
    })
    console.log('Toggle response:', response.status)
  } catch (error) {
    console.error('Error toggling connector:', error)
    // Revert on error
    if (connector) {
      connector.enabled_in_chat = !enabled
    }
  }
}

const connectApp = async (providerId) => {
  try {
    // Get OAuth URL from backend
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
        // Refresh connectors after OAuth completes
        setTimeout(() => {
          fetchConnectors()
          emit('refresh')
        }, 1000)
      }
    }, 500)

  } catch (error) {
    console.error('Error connecting app:', error)
  }
}

onMounted(() => {
  console.log('ConnectorTogglePanel mounted')
  console.log('Initial connectors:', connectors.value)
  fetchConnectors()

  // Listen for OAuth completion messages
  window.addEventListener('message', (event) => {
    if (event.data.type === 'oauth-complete') {
      if (oauthWindow.value) {
        oauthWindow.value.close()
      }
      fetchConnectors()
      emit('refresh')
    }
  })
})

// Expose refresh method for parent component
defineExpose({
  refresh: fetchConnectors
})
</script>

<style scoped>
.connector-toggle-panel {
  padding: 0.5rem;
}
</style>