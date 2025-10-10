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
          // Gracefully end voice session
          if (isVoiceMode.value) {
            console.log('🛑 Voice session ended due to WebSocket close')
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
      console.log('📨 Backend message:', message.type)

      switch (message.type) {
        case 'voice_connection_established':
          console.log('✅ Backend voice connection established')
          break

        case 'session_settings':
          console.log('⚙️ Session settings received from backend')
          backendSessionSettings = message.data
          eviConfigId = message.config_id
          console.log('📥 Backend session settings:', JSON.stringify(backendSessionSettings, null, 2))
          console.log('📥 EVI Config ID:', eviConfigId)

          // If Hume is already connected, send the settings now
          if (humeSocket) {
            console.log('📤 Sending backend session settings to Hume')
            console.log('Settings object:', backendSessionSettings)
            try {
              // Send only the fields that Hume TypeScript SDK expects
              // Based on error, try sending individual fields
              if (backendSessionSettings.tools) {
                console.log('📝 Tools:', backendSessionSettings.tools)
              }
              if (backendSessionSettings.systemPrompt) {
                console.log('📝 System Prompt:', backendSessionSettings.systemPrompt.substring(0, 100))
              }

              // Try sending as-is first to see the detailed error
              humeSocket.sendSessionSettings(backendSessionSettings)
              console.log('✅ Session settings sent successfully')
            } catch (e) {
              console.error('❌ Error sending session settings:', e)
              console.error('Full error:', JSON.stringify(e, null, 2))
            }
          }
          break

        case 'transcription_received':
          console.log('✅ Backend received transcription')
          break

        case 'agent_triggered':
          // Backend agents are being triggered - show on screen
          console.log('🚀 Agents triggered:', message.intent, 'message_id:', message.message_id)
          voiceStatus.value = 'thinking'

          // Store the backend-generated message ID for tracking
          if (message.message_id) {
            currentMessageId = message.message_id
            console.log('💾 Stored message ID:', currentMessageId)
          }

          // Emit event for UI to show agent workflow
          window.dispatchEvent(new CustomEvent('voice-agent-triggered', {
            detail: {
              intent: message.intent,
              text: message.text,
              message_id: message.message_id // Include message ID for tracking
            }
          }))
          break

        case 'agent_context':
          // Agent progress update - accumulate for final response
          console.log('📊 Agent context:', message.context)
          agentUpdate.value = message.context

          // Accumulate progress updates to include in final tool response
          // This allows EVI to naturally reference what happened during processing
          if (message.context && !accumulatedProgress.value.includes(message.context)) {
            accumulatedProgress.value.push(message.context)
            console.log('📝 Accumulated progress:', accumulatedProgress.value.length, 'updates')
          }
          break

        case 'agent_response':
          // Backend agent response - accumulate until we get final completion
          console.log('🤖 Agent response received:', message.text?.substring(0, 100))
          agentUpdate.value = ''

          // Check for Daytona tool calls in agent responses
          if (message.text && (message.text.includes('<tool>DaytonaCodeSandbox</tool>') ||
              message.text.includes('<subgraph>DaytonaCodeSandbox'))) {
            console.log('🔧 Daytona tool call detected in agent_response - dispatching voice-daytona-detected event')
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
            console.log('💬 Accumulated response update:', accumulatedProgress.value.length, 'total')
          } else if (!currentToolCallId && message.text) {
            console.debug('⚠️ Received agent response but no active tool call (likely already sent)')
          }
          break

        case 'agent_completion_full':
          // Check if this is the FINAL agent completion (any final type)
          // If so, send accumulated responses to EVI as tool response
          const agentType = message.data?.additional_kwargs?.agent_type || message.agent_type

          console.log('📦 agent_completion received, agent_type:', agentType)

          // Only send to EVI when we get the final completion (handles all final types)
          if (isFinalAgentType(agentType) && currentToolCallId && humeSocket) {
            console.log('🎯 Final completion received - sending accumulated responses to EVI')

            try {
              // Get the last (final) response which should be the formatted summary
              const finalResponse = accumulatedProgress.value[accumulatedProgress.value.length - 1] || 'Processing complete'

              console.log('📤 Sending final tool response to EVI with toolCallId:', currentToolCallId)
              console.log('📊 Final response preview:', finalResponse.substring(0, 200))

              // Send the result back to EVI as a tool response
              humeSocket.sendToolResponseMessage({
                type: 'tool_response',
                toolCallId: currentToolCallId,
                content: finalResponse
              })

              console.log('✅ Tool response sent - EVI will incorporate it naturally')

              // Clear the tool call ID and accumulated progress after successful send
              currentToolCallId = null
              accumulatedProgress.value = []
            } catch (e) {
              console.error('❌ Error sending tool response:', e)
              // Don't clear currentToolCallId or progress if send failed
            }
          } else {
            console.debug('📦 Non-final agent_completion (waiting for final type), agent_type:', agentType)
          }
          break

        case 'llm_stream_chunk_full':
          // DON'T forward these to ChatView - the main chat WebSocket already receives them!
          // Forwarding creates duplicate messages with potentially different message_ids,
          // breaking the streaming group logic in filteredMessages.
          // The main WebSocket handles ALL UI updates including Daytona tool calls.
          console.log('📦 llm_stream_chunk received (main WebSocket handles UI - no forwarding needed)')

          // EXCEPTION: Check for Daytona tool calls and dispatch special detection event
          // This ensures the Daytona sidebar opens in voice mode even if main WebSocket has timing issues
          const chunkContent = message.data?.data?.content || message.data?.content || ''
          if (chunkContent.includes('<tool>DaytonaCodeSandbox</tool>') ||
              chunkContent.includes('<subgraph>DaytonaCodeSandbox</subgraph>')) {
            console.log('🔧 Daytona tool call detected in voice mode - dispatching voice-daytona-detected event')
            window.dispatchEvent(new CustomEvent('voice-daytona-detected', {
              detail: {
                message_id: message.message_id || currentMessageId,
                timestamp: new Date().toISOString()
              }
            }))
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
          // Don't forward workflow messages - the main chat WebSocket already receives them!
          // Voice WebSocket is ONLY for voice-specific messages (agent_response, agent_context)
          // Forwarding creates duplicates since both WebSockets receive the same messages
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

      // Close existing Hume socket if any (prevents duplicate connections)
      if (humeSocket) {
        console.warn('⚠️ Closing existing Hume socket before creating new one')
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

      // Connect to EVI WebSocket with config_id (has LLMs for tool support)
      const connectOptions = {}
      if (eviConfigId) {
        connectOptions.configId = eviConfigId
        console.log('🔧 Connecting with EVI config:', eviConfigId)
      } else {
        console.warn('⚠️ No EVI config_id - tools may not work')
      }

      humeSocket = humeClient.empathicVoice.chat.connect(connectOptions)

      // Set up event handlers
      humeSocket.on('open', () => {
        console.log('✅ Hume EVI WebSocket opened')

        // Send backend session settings if available (includes tools!)
        if (backendSessionSettings) {
          console.log('📤 Sending backend session settings to Hume (with tools)')
          humeSocket.sendSessionSettings(backendSessionSettings)
        } else {
          console.warn('⚠️ Backend session settings not yet available, waiting...')
          // They'll be sent when received from backend
        }

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
        // Gracefully end voice session
        if (isVoiceMode.value) {
          console.log('🛑 Voice session ended due to Hume disconnect')
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

      // Note: .connect() already opens the connection, no need to call it again
      // Calling it twice would open TWO WebSocket connections!

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
      messageKey = `audio_${message.id}_${message.index}`
    } else if (message.type === 'tool_call' && message.toolCallId) {
      // For tool calls, use toolCallId as the unique key
      messageKey = `tool_call_${message.toolCallId}`
    } else if (message.id) {
      // For other messages with IDs, use type + ID
      messageKey = `${message.type}_${message.id}`
    } else {
      // For messages without IDs, use type + received timestamp (NOT Date.now())
      const timestamp = message.receivedAt ? message.receivedAt.getTime() : Date.now()
      messageKey = `${message.type}_${timestamp}`
    }

    // Skip if already processed
    if (processedMessageIds.has(messageKey)) {
      console.log('🔄 Skipping duplicate:', message.type, messageKey)
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
        voiceStatus.value = 'listening'
        // Don't send to backend yet - let EVI decide if it needs to call the tool
      }
    }

    // Handle EVI tool calls
    if (message.type === 'tool_call') {
      console.log('🔧 EVI calling tool:', message.name, message.parameters)
      voiceStatus.value = 'thinking'

      if (message.name === 'query_backend_agent') {
        // Parameters is a JSON STRING, not an object - parse it!
        let query
        try {
          const params = typeof message.parameters === 'string'
            ? JSON.parse(message.parameters)
            : message.parameters
          query = params.query
        } catch (e) {
          console.error('❌ Error parsing tool parameters:', e)
          query = message.parameters  // Fallback
        }

        currentToolCallId = message.toolCallId  // Store for matching response
        accumulatedProgress.value = [] // Clear any previous progress from last query

        console.log('📤 Tool call - query:', query, 'toolCallId:', currentToolCallId)

        // Send query to backend (backend will generate message_id)
        if (voiceWebSocket?.readyState === WebSocket.OPEN) {
          voiceWebSocket.send(JSON.stringify({
            type: 'voice_transcription',
            text: query,
            // No message_id - backend will generate a UUID and send it back in agent_triggered
          }))
          console.log('📤 Sent tool query to backend (backend will generate message ID)')
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

      // Guard: prevent starting if already in voice mode or connecting
      if (isVoiceMode.value || voiceStatus.value === 'connecting') {
        console.warn('⚠️ Voice mode already active or connecting, ignoring duplicate start request')
        return
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

      // Wait for backend session settings (with tools) before connecting to Hume
      console.log('⏳ Waiting for session settings from backend...')
      let waitCount = 0
      while (!backendSessionSettings && waitCount < 50) {
        await new Promise(resolve => setTimeout(resolve, 100))
        waitCount++
      }

      if (!backendSessionSettings) {
        console.warn('⚠️ Timeout waiting for backend session settings, proceeding anyway')
      } else {
        console.log('✅ Got backend session settings, connecting to Hume...')
      }

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

  // Watch for conversation ID changes - reconnect voice WebSocket to new conversation
  watch(conversationIdGetter, async (newId, oldId) => {
    if (!isVoiceMode.value) return // Only care if voice mode is active

    if (newId !== oldId && newId) {
      console.log(`🔄 Conversation changed from ${oldId} to ${newId}, reconnecting...`)

      // Close old Hume socket connection
      if (humeSocket) {
        try {
          humeSocket.close()
          humeSocket = null
          console.log('✅ Closed old Hume socket')
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
        console.log('✅ Voice connections reconnected to new conversation')
      } catch (err) {
        console.error('❌ Failed to reconnect voice connections:', err)
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
    isSupported,

    // Methods
    startVoiceMode,
    stopVoiceMode,
    toggleVoiceMode,
  }
}
