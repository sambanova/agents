/**
 * Voice chat composable using Hume EVI for voice interaction.
 * Flow: User speaks → Hume transcribes → Backend processes → Hume responds
 */
import { ref, computed, onUnmounted } from 'vue'
import { useAuth0 } from '@auth0/auth0-vue'
import { HumeClient } from 'hume'
import { getMicrophoneStream, blobToBase64, AudioPlaybackQueue } from '../utils/audioHandler'

export function useVoiceChat(conversationId) {
  const { getAccessTokenSilently, user } = useAuth0()

  // State
  const isVoiceMode = ref(false)
  const voiceStatus = ref('idle') // idle, connecting, listening, speaking, thinking, error
  const currentTranscript = ref('')
  const agentUpdate = ref('')
  const error = ref(null)
  const audioLevel = ref(0)

  // WebSocket and audio references
  let voiceWebSocket = null // Our backend WebSocket for agent communication
  let humeClient = null
  let humeSocket = null
  let mediaStream = null
  let mediaRecorder = null
  let audioContext = null
  let audioChunksInterval = null
  let audioPlayback = null // Audio playback queue for Hume responses

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

      // Get conversation ID value
      const convId = typeof conversationId === 'object' && 'value' in conversationId
        ? conversationId.value
        : conversationId

      if (!convId) {
        throw new Error('Conversation ID required for voice mode. Please send a message first.')
      }

      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsHost = window.location.host
      const wsUrl = `${wsProtocol}//${wsHost}/api/voice/chat?conversation_id=${convId}`

      console.log('🔌 Connecting to backend voice WebSocket:', wsUrl)
      voiceWebSocket = new WebSocket(wsUrl)

      return new Promise((resolve, reject) => {
        voiceWebSocket.onopen = async () => {
          console.log('✅ Backend voice WebSocket connected')

          // Send authentication
          voiceWebSocket.send(JSON.stringify({
            type: 'auth',
            token: `Bearer ${token}`
          }))

          resolve()
        }

        voiceWebSocket.onmessage = handleBackendMessage

        voiceWebSocket.onerror = (err) => {
          console.error('❌ Backend WebSocket error:', err)
          reject(err)
        }

        voiceWebSocket.onclose = () => {
          console.log('🔌 Backend WebSocket closed')
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
      console.log('📨 Backend message:', message.type)

      switch (message.type) {
        case 'voice_connection_established':
          console.log('✅ Backend voice connection established')
          break

        case 'session_settings':
          console.log('⚙️ Session settings received')
          break

        case 'transcription_received':
          console.log('✅ Backend received transcription')
          break

        case 'agent_triggered':
          // Backend agents are being triggered - show on screen
          console.log('🚀 Agents triggered:', message.intent)
          voiceStatus.value = 'thinking'

          // Emit event for UI to show agent workflow
          window.dispatchEvent(new CustomEvent('voice-agent-triggered', {
            detail: { intent: message.intent, text: message.text }
          }))
          break

        case 'agent_context':
          // Agent progress update - inject as temporary context for EVI narration
          console.log('📊 Agent context:', message.context)
          agentUpdate.value = message.context

          // Inject as temporary context for EVI to naturally narrate
          if (humeSocket && message.context) {
            // Send as session settings with temporary context
            humeSocket.sendSessionSettings({
              context: {
                text: message.context,
                type: "temporary"  // Only applies to next response
              }
            })
          }
          break

        case 'agent_response':
          // Agent finished processing - have Hume speak the response
          console.log('🤖 Agent response:', message.text)
          agentUpdate.value = ''

          // Clean and send response to Hume to speak
          if (humeSocket && message.text) {
            // Strip HTML tags and limit length
            let cleanText = message.text.replace(/<[^>]*>/g, '').trim()

            // If too long, create a brief summary for Hume
            if (cleanText.length > 500) {
              cleanText = "I've completed the analysis. The results are displayed on your screen."
            }

            sendAssistantMessage(cleanText)
          }
          break

        case 'agent_update':
          // Real-time agent activity updates
          agentUpdate.value = message.text
          break

        case 'error':
          console.error('❌ Backend error:', message.error)
          error.value = message.error
          voiceStatus.value = 'error'
          break

        default:
          console.log('Unknown backend message type:', message.type)
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
      console.log('🎤 Connecting to Hume EVI...')

      // Get Hume access token from backend
      const accessToken = await getHumeToken()

      // Initialize Hume client
      humeClient = new HumeClient({
        apiKey: accessToken
      })

      // Connect to EVI WebSocket
      humeSocket = humeClient.empathicVoice.chat.connect()

      // Set up event handlers
      humeSocket.on('open', () => {
        console.log('✅ Hume EVI WebSocket opened')

        // Send session settings
        const convId = typeof conversationId === 'object' && 'value' in conversationId
          ? conversationId.value
          : conversationId

        humeSocket.sendSessionSettings({
          context: {
            text: `Conversation ID: ${convId}. You are a helpful voice assistant.`
          }
        })

        console.log('📤 Sent session settings to Hume')
        voiceStatus.value = 'listening'
      })

      humeSocket.on('message', (message) => {
        handleHumeMessage(message)
      })

      humeSocket.on('error', (err) => {
        console.error('❌ Hume EVI error:', err)
        voiceStatus.value = 'error'
        error.value = 'Hume connection error'
      })

      humeSocket.on('close', () => {
        console.log('🔌 Hume EVI disconnected')
      })

      // Actually connect the socket
      humeSocket.connect()

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
      // For audio chunks, use ID + index as key
      messageKey = `${message.id}_${message.index}`
    } else if (message.id) {
      // For other messages with IDs
      messageKey = `${message.type}_${message.id}`
    } else {
      // For messages without IDs (like assistant_end), use type + timestamp
      messageKey = `${message.type}_${Date.now()}`
    }

    // Skip if already processed
    if (processedMessageIds.has(messageKey)) {
      return
    }
    processedMessageIds.add(messageKey)

    console.log('🎵 Hume message:', message)

    // Handle user transcription
    if (message.type === 'user_message' || message.type === 'user_transcription') {
      const transcription = message.message?.content || message.text
      if (transcription) {
        console.log('🎤 User said:', transcription)
        currentTranscript.value = transcription
        voiceStatus.value = 'thinking'

        // Send transcription to backend for agent processing
        if (voiceWebSocket?.readyState === WebSocket.OPEN) {
          voiceWebSocket.send(JSON.stringify({
            type: 'voice_transcription',
            text: transcription,
            message_id: `voice_${Date.now()}`
          }))
          console.log('📤 Sent transcription to backend')
        }
      }
    }

    // Handle assistant speaking
    if (message.type === 'assistant_message') {
      console.log('🔊 Hume speaking')
      voiceStatus.value = 'speaking'
    }

    // Handle assistant finished speaking
    if (message.type === 'assistant_end') {
      console.log('✅ Hume finished speaking')
      voiceStatus.value = 'listening'
      currentTranscript.value = ''
    }

    // Handle audio output
    if (message.type === 'audio_output') {
      voiceStatus.value = 'speaking'

      // Play the audio chunk
      if (message.data && audioPlayback) {
        console.log('🔊 Playing audio chunk', message.index, 'final:', message.is_final_chunk)
        audioPlayback.enqueue(message.data).catch(err => {
          console.error('Error playing audio chunk:', err)
        })
      }
    }

    // Handle user interruption
    if (message.type === 'user_interruption') {
      console.log('⚠️ User interrupted')
      voiceStatus.value = 'listening'

      // Stop any ongoing audio playback
      if (audioPlayback) {
        audioPlayback.stop()
        console.log('🔇 Stopped audio playback due to interruption')
      }
    }

    // Handle errors
    if (message.type === 'error') {
      console.error('❌ Hume error:', message.error)
      error.value = message.error?.message || 'Voice error'
      voiceStatus.value = 'error'
    }
  }

  /**
   * Send assistant message to Hume to speak
   */
  function sendAssistantMessage(text) {
    if (!humeSocket) {
      console.warn('⚠️ Hume socket not connected')
      return
    }

    console.log('📢 Sending to Hume to speak:', text)
    humeSocket.sendAssistantInput({ text })
    voiceStatus.value = 'speaking'
  }

  /**
   * Start audio capture and streaming to Hume
   */
  async function startAudioCapture() {
    try {
      console.log('🎙️ Starting microphone capture...')

      // Get microphone stream
      mediaStream = await getMicrophoneStream()

      // Create audio context for processing
      audioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: 16000 // Hume recommends 16kHz
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
          try {
            const base64Audio = await blobToBase64(event.data)
            humeSocket.sendAudioInput({ data: base64Audio })
          } catch (err) {
            console.error('Error sending audio chunk:', err)
          }
        }
      })

      // Start recording with 100ms chunks (Hume recommendation for web apps)
      mediaRecorder.start(100)
      console.log('✅ Audio capture started, streaming to Hume')

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
    console.log('🛑 Audio capture stopped')
  }

  /**
   * Start voice mode
   */
  async function startVoiceMode() {
    try {
      console.log('🎙️ Starting voice mode...')

      // Check browser support
      if (!isSupported.value) {
        throw new Error('Your browser does not support voice mode')
      }

      isVoiceMode.value = true
      error.value = null
      voiceStatus.value = 'connecting'

      // Initialize audio playback queue
      audioPlayback = new AudioPlaybackQueue()
      await audioPlayback.init()
      console.log('🔊 Audio playback initialized')

      // Connect to backend WebSocket first
      await connectBackendWebSocket()

      // Then connect to Hume EVI
      await connectHumeEVI()

      // Wait a bit for Hume to be ready
      await new Promise(resolve => setTimeout(resolve, 1000))

      // Start capturing and streaming audio
      await startAudioCapture()

      // Set up periodic cleanup of old message IDs
      cleanupInterval = setInterval(() => {
        // Clear the set periodically to prevent memory buildup
        // Keep only recent IDs (this is a simple approach)
        if (processedMessageIds.size > 1000) {
          processedMessageIds.clear()
        }
      }, MESSAGE_ID_CLEANUP_INTERVAL)

      console.log('✅ Voice mode started')
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
    console.log('🛑 Stopping voice mode...')

    isVoiceMode.value = false
    voiceStatus.value = 'idle'

    // Stop audio capture
    stopAudioCapture()

    // Stop audio playback
    if (audioPlayback) {
      audioPlayback.stop()
      audioPlayback = null
      console.log('🔊 Audio playback stopped')
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

    console.log('✅ Voice mode stopped')
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
    isSupported,

    // Methods
    startVoiceMode,
    stopVoiceMode,
    toggleVoiceMode,
  }
}
