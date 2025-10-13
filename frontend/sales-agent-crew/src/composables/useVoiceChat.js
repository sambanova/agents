/**
 * Voice chat composable using Hume EVI for voice interaction.
 * Flow: User speaks → Hume transcribes → Backend processes → Hume responds
 */
import { ref, computed, onUnmounted, watch } from 'vue'
import { useAuth0 } from '@auth0/auth0-vue'
import { HumeClient } from 'hume'
import { getMicrophoneStream, blobToBase64, AudioPlaybackQueue } from '../utils/audioHandler'
import { isFinalAgentType } from '../utils/globalFunctions'

export function useVoiceChat(conversationIdGetter) {
  const { getAccessTokenSilently, user } = useAuth0()

  // State
  const isVoiceMode = ref(false)
  const voiceStatus = ref('idle') // idle, connecting, listening, speaking, thinking, error
  const currentTranscript = ref('')
  const agentUpdate = ref('')
  const error = ref(null)
  const audioLevel = ref(0)
  const isMuted = ref(false) // Mute control for voice input
  const accumulatedProgress = ref([]) // Store progress updates for inclusion in final tool response

  // WebSocket and audio references
  let voiceWebSocket = null // Our backend WebSocket for agent communication
  let humeClient = null
  let humeSocket = null
  let mediaStream = null
  let mediaRecorder = null
  let audioContext = null
  let audioChunksInterval = null
  let audioPlayback = null // Audio playback queue for Hume responses

  // Track current tool call and message
  let currentToolCallId = null
  let currentMessageId = null // Backend-generated message ID for the current query

  // Store session settings from backend
  let backendSessionSettings = null
  let eviConfigId = null

  // Message deduplication
  const processedMessageIds = new Set()
  const MESSAGE_ID_CLEANUP_INTERVAL = 60000 // Clean up old IDs every minute
  let cleanupInterval = null

  // Check browser support
  const isSupported = computed(() => {
    return typeof WebSocket !== 'undefined' && typeof navigator.mediaDevices !== 'undefined'
  })

  /**
   * Get Hume access token from backend
   */
  async function getHumeToken() {
    try {
      const token = await getAccessTokenSilently()
      const response = await fetch('/api/voice/token', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error('Failed to get Hume token')
      }

      const data = await response.json()
      return data.access_token
    } catch (err) {
      console.error('Failed to get Hume token:', err)
      throw err
    }
  }

  /**
   * Connect to backend voice WebSocket for agent communication
   */
  async function connectBackendWebSocket() {
    if (voiceWebSocket?.readyState === WebSocket.OPEN) {
      return
    }

    try {
      const token = await getAccessTokenSilently()

      // Get conversation ID from getter function
      const convId = conversationIdGetter()

      if (!convId) {
        throw new Error('Conversation ID required for voice mode. Please send a message first.')
      }

      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsHost = window.location.host
      const wsUrl = `${wsProtocol}//${wsHost}/api/voice/chat?conversation_id=${convId}`

      voiceWebSocket = new WebSocket(wsUrl)

      return new Promise((resolve, reject) => {
        voiceWebSocket.onopen = async () => {
          // Send authentication
          voiceWebSocket.send(JSON.stringify({
            type: 'auth',
            token: `Bearer ${token}`
          }))

          resolve()
        }

        voiceWebSocket.onmessage = handleBackendMessage

        voiceWebSocket.onerror = (err) => {
          console.error('Backend WebSocket error:', err)
          reject(err)
        }

        voiceWebSocket.onclose = () => {
          // Gracefully end voice session
          if (isVoiceMode.value) {
            isVoiceMode.value = false
            voiceStatus.value = 'idle'
            error.value = 'Voice session ended. Press Ctrl+Space to restart'

            // Clean up resources
            stopAudioCapture()
            if (audioPlayback) {
              audioPlayback.stop()
              audioPlayback = null
            }
          }
        }
      })
    } catch (err) {
      console.error('Failed to connect backend WebSocket:', err)
      throw err
    }
  }

  /**
   * Handle messages from backend WebSocket
   */
  function handleBackendMessage(event) {
    try {
      const message = JSON.parse(event.data)

      switch (message.type) {
        case 'voice_connection_established':
          break

        case 'session_settings':
          backendSessionSettings = message.data
          eviConfigId = message.config_id

          // If Hume is already connected, send the settings now
          if (humeSocket) {
            try {
              humeSocket.sendSessionSettings(backendSessionSettings)
            } catch (e) {
              console.error('Error sending session settings:', e)
            }
          }
          break

        case 'transcription_received':
          break

        case 'agent_triggered':
          voiceStatus.value = 'thinking'

          // Store the backend-generated message ID for tracking
          if (message.message_id) {
            currentMessageId = message.message_id
          }

          // Emit event for UI to show agent workflow
          window.dispatchEvent(new CustomEvent('voice-agent-triggered', {
            detail: {
              intent: message.intent,
              text: message.text,
              message_id: message.message_id
            }
          }))
          break

        case 'agent_context':
          agentUpdate.value = message.context

          // Accumulate progress updates to include in final tool response
          if (message.context && !accumulatedProgress.value.includes(message.context)) {
            accumulatedProgress.value.push(message.context)
          }
          break

        case 'agent_response':
          agentUpdate.value = ''

          // Check for Daytona tool calls in agent responses
          if (message.text && (message.text.includes('<tool>DaytonaCodeSandbox</tool>') ||
              message.text.includes('<subgraph>DaytonaCodeSandbox'))) {
            window.dispatchEvent(new CustomEvent('voice-daytona-detected', {
              detail: {
                message_id: message.message_id || currentMessageId,
                timestamp: new Date().toISOString()
              }
            }))
          }

          // Accumulate this response - we'll send to EVI when we get the final completion
          if (message.text && currentToolCallId) {
            accumulatedProgress.value.push(message.text)
          }
          break

        case 'agent_completion_full':
          const agentType = message.data?.additional_kwargs?.agent_type || message.agent_type

          // Only send to EVI when we get the final completion
          if (isFinalAgentType(agentType) && currentToolCallId && humeSocket) {
            try {
              const finalResponse = accumulatedProgress.value[accumulatedProgress.value.length - 1] || 'Processing complete'

              humeSocket.sendToolResponseMessage({
                type: 'tool_response',
                toolCallId: currentToolCallId,
                content: finalResponse
              })

              // Clear the tool call ID and accumulated progress after successful send
              currentToolCallId = null
              accumulatedProgress.value = []
            } catch (e) {
              console.error('Error sending tool response:', e)
            }
          }
          break

        case 'llm_stream_chunk_full':
          // Check for Daytona tool calls and dispatch special detection event
          const chunkContent = message.data?.data?.content || message.data?.content || ''
          if (chunkContent.includes('<tool>DaytonaCodeSandbox</tool>') ||
              chunkContent.includes('<subgraph>DaytonaCodeSandbox</subgraph>')) {
            window.dispatchEvent(new CustomEvent('voice-daytona-detected', {
              detail: {
                message_id: message.message_id || currentMessageId,
                timestamp: new Date().toISOString()
              }
            }))
          }
          break

        case 'agent_update':
          agentUpdate.value = message.text
          break

        case 'error':
          console.error('Backend error:', message.error)
          error.value = message.error
          voiceStatus.value = 'error'
          break
      }
    } catch (err) {
      console.error('Error handling backend message:', err)
    }
  }

  /**
   * Connect to Hume EVI WebSocket
   */
  async function connectHumeEVI() {
    try {
      // Close existing Hume socket if any (prevents duplicate connections)
      if (humeSocket) {
        try {
          humeSocket.close()
        } catch (e) {
          console.error('Error closing existing Hume socket:', e)
        }
        humeSocket = null
      }

      // Get Hume access token from backend
      const accessToken = await getHumeToken()

      // Initialize Hume client
      humeClient = new HumeClient({
        apiKey: accessToken
      })

      // Connect to EVI WebSocket with config_id
      const connectOptions = {}
      if (eviConfigId) {
        connectOptions.configId = eviConfigId
      }

      humeSocket = humeClient.empathicVoice.chat.connect(connectOptions)

      // Set up event handlers
      humeSocket.on('open', () => {
        // Send backend session settings if available
        if (backendSessionSettings) {
          humeSocket.sendSessionSettings(backendSessionSettings)
        }

        voiceStatus.value = 'listening'
      })

      humeSocket.on('message', (message) => {
        handleHumeMessage(message)
      })

      humeSocket.on('error', (err) => {
        console.error('Hume EVI error:', err)
        voiceStatus.value = 'error'
        error.value = 'Hume connection error'
      })

      humeSocket.on('close', () => {
        // Gracefully end voice session
        if (isVoiceMode.value) {
          isVoiceMode.value = false
          voiceStatus.value = 'idle'
          error.value = 'Voice session ended. Press Ctrl+Space to restart'

          // Clean up resources
          stopAudioCapture()
          if (audioPlayback) {
            audioPlayback.stop()
            audioPlayback = null
          }
        }
      })

    } catch (err) {
      console.error('Failed to connect Hume EVI:', err)
      throw err
    }
  }

  /**
   * Handle messages from Hume EVI
   */
  function handleHumeMessage(message) {
    // Deduplicate messages using ID and type
    let messageKey
    if (message.type === 'audio_output') {
      messageKey = `audio_${message.id}_${message.index}`
    } else if (message.type === 'tool_call' && message.toolCallId) {
      messageKey = `tool_call_${message.toolCallId}`
    } else if (message.id) {
      messageKey = `${message.type}_${message.id}`
    } else {
      const timestamp = message.receivedAt ? message.receivedAt.getTime() : Date.now()
      messageKey = `${message.type}_${timestamp}`
    }

    // Skip if already processed
    if (processedMessageIds.has(messageKey)) {
      return
    }
    processedMessageIds.add(messageKey)

    // Handle user transcription
    if (message.type === 'user_message' || message.type === 'user_transcription') {
      const transcription = message.message?.content || message.text
      if (transcription) {
        currentTranscript.value = transcription
        voiceStatus.value = 'listening'
      }
    }

    // Handle EVI tool calls
    if (message.type === 'tool_call') {
      voiceStatus.value = 'thinking'

      if (message.name === 'query_backend_agent') {
        let query
        try {
          const params = typeof message.parameters === 'string'
            ? JSON.parse(message.parameters)
            : message.parameters
          query = params.query
        } catch (e) {
          console.error('Error parsing tool parameters:', e)
          query = message.parameters
        }

        currentToolCallId = message.toolCallId
        accumulatedProgress.value = []

        // Send query to backend
        if (voiceWebSocket?.readyState === WebSocket.OPEN) {
          voiceWebSocket.send(JSON.stringify({
            type: 'voice_transcription',
            text: query
          }))
        }
      }
    }

    // Handle assistant speaking
    if (message.type === 'assistant_message') {
      voiceStatus.value = 'speaking'
    }

    // Handle assistant finished speaking
    if (message.type === 'assistant_end') {
      voiceStatus.value = 'listening'
      currentTranscript.value = ''
    }

    // Handle audio output
    if (message.type === 'audio_output') {
      voiceStatus.value = 'speaking'

      if (message.data && audioPlayback) {
        audioPlayback.enqueue(message.data).catch(err => {
          console.error('Error playing audio chunk:', err)
        })
      }
    }

    // Handle user interruption
    if (message.type === 'user_interruption') {
      voiceStatus.value = 'listening'

      if (audioPlayback) {
        audioPlayback.stop()
      }
    }

    // Handle errors
    if (message.type === 'error') {
      console.error('Hume error:', message.error)
      error.value = message.error?.message || 'Voice error'
      voiceStatus.value = 'error'
    }
  }

  /**
   * Start audio capture and streaming to Hume
   */
  async function startAudioCapture() {
    try {
      // Get microphone stream
      mediaStream = await getMicrophoneStream()

      // Create audio context for processing
      audioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: 16000
      })

      // Create MediaRecorder for audio chunks
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'

      mediaRecorder = new MediaRecorder(mediaStream, {
        mimeType,
        audioBitsPerSecond: 16000
      })

      // Stream audio chunks to Hume every 100ms
      mediaRecorder.addEventListener('dataavailable', async (event) => {
        if (event.data.size > 0 && humeSocket) {
          // Skip sending audio if muted
          if (isMuted.value) {
            return
          }

          try {
            const base64Audio = await blobToBase64(event.data)
            humeSocket.sendAudioInput({ data: base64Audio })
          } catch (err) {
            console.error('Error sending audio chunk:', err)
          }
        }
      })

      // Start recording with 100ms chunks
      mediaRecorder.start(100)

    } catch (err) {
      console.error('Failed to start audio capture:', err)
      error.value = 'Microphone access denied'
      voiceStatus.value = 'error'
      throw err
    }
  }

  /**
   * Stop audio capture
   */
  function stopAudioCapture() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop()
      mediaRecorder = null
    }

    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop())
      mediaStream = null
    }

    if (audioContext) {
      audioContext.close()
      audioContext = null
    }

    if (audioChunksInterval) {
      clearInterval(audioChunksInterval)
      audioChunksInterval = null
    }

    audioLevel.value = 0
  }

  /**
   * Start voice mode
   */
  async function startVoiceMode() {
    try {
      // Check browser support
      if (!isSupported.value) {
        throw new Error('Your browser does not support voice mode')
      }

      // Guard: prevent starting if already in voice mode or connecting
      if (isVoiceMode.value || voiceStatus.value === 'connecting') {
        return
      }

      isVoiceMode.value = true
      error.value = null
      voiceStatus.value = 'connecting'

      // Initialize audio playback queue
      audioPlayback = new AudioPlaybackQueue()
      await audioPlayback.init()

      // Connect to backend WebSocket first
      await connectBackendWebSocket()

      // Wait for backend session settings before connecting to Hume
      let waitCount = 0
      while (!backendSessionSettings && waitCount < 50) {
        await new Promise(resolve => setTimeout(resolve, 100))
        waitCount++
      }

      // Connect to Hume EVI
      await connectHumeEVI()

      // Wait for Hume to be ready
      await new Promise(resolve => setTimeout(resolve, 1000))

      // Start capturing and streaming audio
      await startAudioCapture()

      // Set up periodic cleanup of old message IDs
      cleanupInterval = setInterval(() => {
        if (processedMessageIds.size > 1000) {
          processedMessageIds.clear()
        }
      }, MESSAGE_ID_CLEANUP_INTERVAL)

    } catch (err) {
      console.error('Failed to start voice mode:', err)
      error.value = err.message
      voiceStatus.value = 'error'
      isVoiceMode.value = false
      throw err
    }
  }

  /**
   * Stop voice mode
   */
  async function stopVoiceMode() {
    isVoiceMode.value = false
    voiceStatus.value = 'idle'

    // Stop audio capture
    stopAudioCapture()

    // Stop audio playback
    if (audioPlayback) {
      audioPlayback.stop()
      audioPlayback = null
    }

    // Clear message deduplication
    if (cleanupInterval) {
      clearInterval(cleanupInterval)
      cleanupInterval = null
    }
    processedMessageIds.clear()

    // Close Hume connection
    if (humeSocket) {
      try {
        humeSocket.close()
      } catch (e) {
        console.error('Error closing Hume socket:', e)
      }
      humeSocket = null
    }

    // Close backend WebSocket
    if (voiceWebSocket) {
      voiceWebSocket.close()
      voiceWebSocket = null
    }

    // Clear state
    currentTranscript.value = ''
    agentUpdate.value = ''
    error.value = null
    audioLevel.value = 0
  }

  /**
   * Toggle voice mode
   */
  async function toggleVoiceMode() {
    if (isVoiceMode.value) {
      await stopVoiceMode()
    } else {
      await startVoiceMode()
    }
  }

  /**
   * Toggle mute - stops sending audio to Hume but keeps session active
   */
  function toggleMute() {
    isMuted.value = !isMuted.value
  }

  // Watch for conversation ID changes - reconnect voice WebSocket to new conversation
  watch(conversationIdGetter, async (newId, oldId) => {
    if (!isVoiceMode.value) return

    if (newId !== oldId && newId) {
      // Close old Hume socket connection
      if (humeSocket) {
        try {
          humeSocket.close()
          humeSocket = null
        } catch (e) {
          console.error('Error closing old Hume socket:', e)
        }
      }

      // Close old voice WebSocket connection
      if (voiceWebSocket && voiceWebSocket.readyState === WebSocket.OPEN) {
        voiceWebSocket.close()
        voiceWebSocket = null
      }

      // Reconnect to new conversation
      try {
        await connectBackendWebSocket()
        await connectHumeEVI()
      } catch (err) {
        console.error('Failed to reconnect voice connections:', err)
        error.value = 'Failed to switch conversation in voice mode'
      }
    }
  })

  // Cleanup on unmount
  onUnmounted(() => {
    stopVoiceMode()
  })

  return {
    // State
    isVoiceMode,
    voiceStatus,
    currentTranscript,
    agentUpdate,
    error,
    audioLevel,
    isMuted,
    isSupported,

    // Methods
    startVoiceMode,
    stopVoiceMode,
    toggleVoiceMode,
    toggleMute,
  }
}
