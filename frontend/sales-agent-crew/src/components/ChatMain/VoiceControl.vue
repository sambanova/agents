<template>
  <div class="voice-control-container">
    <!-- Voice Controls Group -->
    <div class="voice-controls-group">
      <!-- Unified Voice Button (Start/Stop Only) -->
      <button
        @click="handleButtonClick"
        :disabled="!isSupported || voiceStatus === 'connecting' || !conversationId"
        :class="[
          'voice-button',
          voiceStatusClass,
          {
            'voice-button-active': isVoiceMode,
            'voice-button-muted': isVoiceMode && isMuted
          }
        ]"
        :title="buttonTitle"
      >
      <!-- Microphone Icon (Always show mic icon unless speaking) -->
      <svg
        v-if="voiceStatus !== 'speaking'"
        class="w-5 h-5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
        />
      </svg>

      <!-- Speaking Animation (Agent responding) -->
      <div v-else-if="voiceStatus === 'speaking'" class="speaking-animation">
        <span></span>
        <span></span>
        <span></span>
      </div>

      <!-- Audio Level Indicator (Pulsing Ring) -->
      <div
        v-if="isVoiceMode && audioLevel > 0 && !isMuted"
        class="audio-level-ring"
        :style="{ transform: `scale(${1 + audioLevel / 100})` }"
      ></div>
    </button>

    <!-- Mute Button (only show when voice mode is active) -->
    <button
      v-if="isVoiceMode"
      @click="toggleMute"
      class="mute-button"
      :class="{ 'mute-button-muted': isMuted }"
      :title="isMuted ? 'Unmute microphone (Ctrl+M)' : 'Mute microphone (Ctrl+M)'"
    >
      <!-- Microphone Icon -->
      <svg
        class="w-4 h-4"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
        />
      </svg>
      <!-- Red slash ALWAYS visible to indicate it's the mute button -->
      <div class="mute-slash"></div>
    </button>
  </div>

    <!-- Error/Info Message -->
    <div v-if="error" :class="['voice-message', isSessionEnded ? 'voice-info' : 'voice-error']">
      <svg v-if="!isSessionEnded" class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
        <path
          fill-rule="evenodd"
          d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
          clip-rule="evenodd"
        />
      </svg>
      <svg v-else class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
        <path
          fill-rule="evenodd"
          d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
          clip-rule="evenodd"
        />
      </svg>
      <span>{{ error }}</span>
    </div>

    <!-- Keyboard Shortcut Hint - Hidden for cleaner UI (status shown in VoiceStatusBadge) -->
    <div v-if="false" class="voice-hint">
      Click or <kbd>Ctrl</kbd>+<kbd>Space</kbd> to start
    </div>
    <div v-else-if="false" class="voice-hint">
      <span v-if="voiceStatus === 'speaking'" class="text-green-600">Agent speaking</span>
      <span v-else-if="isMuted" class="text-red-500">Muted</span>
      <span v-else class="text-blue-600">Listening</span>
      · Click to stop
    </div>
    <div v-else-if="false" class="voice-hint">
      <kbd>Ctrl</kbd>+<kbd>Space</kbd> to restart
    </div>
    <div v-else-if="false" class="voice-hint text-gray-400">
      Send a message first
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { useVoiceChat } from '@/composables/useVoiceChat'

const props = defineProps({
  conversationId: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['voice-status-changed', 'voice-mode-starting'])

// Use voice chat composable - pass getter function for reactive tracking
const {
  isVoiceMode,
  voiceStatus,
  error,
  audioLevel,
  isMuted,
  isSupported,
  toggleVoiceMode,
  toggleMute
} = useVoiceChat(() => props.conversationId)

// Computed
const voiceStatusClass = computed(() => {
  const statusMap = {
    idle: 'status-idle',
    connecting: 'status-connecting',
    listening: 'status-listening',
    speaking: 'status-speaking',
    thinking: 'status-thinking',
    error: 'status-error'
  }
  return statusMap[voiceStatus.value] || 'status-idle'
})

const isSessionEnded = computed(() => {
  return error.value && error.value.toLowerCase().includes('session ended')
})

const buttonTitle = computed(() => {
  if (!isSupported.value) {
    return 'Voice mode not supported in your browser'
  }

  if (!props.conversationId) {
    return 'Send a message first to start voice mode'
  }

  // Simple: Start or Stop
  if (!isVoiceMode.value) {
    return 'Start voice mode (Click or Ctrl+Space)'
  }

  return 'Stop voice mode (Click or Ctrl+Space)'
})

// Methods
async function handleButtonClick() {
  try {
    // Simple: Always toggle voice mode on/off
    if (!isVoiceMode.value) {
      // Starting voice mode
      emit('voice-mode-starting')
      // Small delay to let parent connect main WebSocket
      await new Promise(resolve => setTimeout(resolve, 500))
    }

    // Toggle voice mode (start or stop)
    await toggleVoiceMode()
    emit('voice-status-changed', {
      isActive: isVoiceMode.value,
      status: voiceStatus.value
    })
  } catch (err) {
    console.error('Voice button click error:', err)
  }
}

// Keyboard shortcut
async function handleKeyboardShortcut(event) {
  // Ctrl+Space or Cmd+Space - toggle voice mode on/off
  if ((event.ctrlKey || event.metaKey) && event.code === 'Space') {
    event.preventDefault()
    try {
      if (!isVoiceMode.value) {
        // Start voice mode
        emit('voice-mode-starting')
        await new Promise(resolve => setTimeout(resolve, 500))
      }
      await toggleVoiceMode()
      emit('voice-status-changed', {
        isActive: isVoiceMode.value,
        status: voiceStatus.value
      })
    } catch (err) {
      console.error('Voice toggle error:', err)
    }
  }

  // Ctrl+M or Cmd+M - toggle mute (only when voice mode is active)
  if ((event.ctrlKey || event.metaKey) && event.code === 'KeyM' && isVoiceMode.value) {
    event.preventDefault()
    toggleMute()
  }

  // Escape to stop voice mode
  if (event.code === 'Escape' && isVoiceMode.value) {
    try {
      await toggleVoiceMode()
      emit('voice-status-changed', {
        isActive: isVoiceMode.value,
        status: voiceStatus.value
      })
    } catch (err) {
      console.error('Voice toggle error:', err)
    }
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyboardShortcut)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyboardShortcut)
})
</script>

<style scoped>
.voice-control-container {
  position: relative;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}

.voice-controls-group {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.voice-button {
  position: relative;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: #6b7280;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: none;
  pointer-events: auto;
}

.voice-button:hover:not(:disabled) {
  background: #f3f4f6;
  border-radius: 0.5rem;
}

.voice-button:active:not(:disabled) {
  transform: scale(0.95);
}

.voice-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Status Colors */
.status-idle {
  color: #6b7280;
}

.status-connecting {
  color: #f59e0b;
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

.status-listening {
  color: #3b82f6;
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

.status-speaking {
  color: #10b981;
}

.status-thinking {
  color: #f59e0b;
  animation: pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

.status-error {
  color: #ef4444;
}

.voice-button-active {
  background: #667eea;
  color: white;
  border-radius: 0.5rem;
}

/* Show red color when muted */
.voice-button-muted {
  color: #ef4444 !important;
}

/* Mute Button */
.mute-button {
  position: relative;
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: #6b7280;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: none;
  pointer-events: auto;
}

.mute-button:hover {
  background: #f3f4f6;
  border-radius: 0.5rem;
}

.mute-button:active {
  transform: scale(0.95);
}

.mute-button-muted {
  color: #ef4444;
}

.mute-button-muted:hover {
  background: #fef2f2;
  border-radius: 0.5rem;
}

/* Red slash overlay for muted state */
.mute-slash {
  position: absolute;
  width: 1.75rem;
  height: 0.15rem;
  background: #ef4444;
  transform: rotate(-45deg);
  border-radius: 999px;
  pointer-events: none;
}

/* Audio Level Ring */
.audio-level-ring {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border-radius: 0.5rem;
  background: rgba(59, 130, 246, 0.1);
  opacity: 0.8;
  transition: transform 0.1s ease;
  pointer-events: none;
}

/* Speaking Animation */
.speaking-animation {
  display: flex;
  gap: 0.25rem;
  align-items: flex-end;
  height: 1.5rem;
}

.speaking-animation span {
  width: 0.25rem;
  background: currentColor;
  border-radius: 999px;
  animation: speaking-bar 1s ease-in-out infinite;
}

.speaking-animation span:nth-child(1) {
  animation-delay: 0s;
}

.speaking-animation span:nth-child(2) {
  animation-delay: 0.2s;
}

.speaking-animation span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes speaking-bar {
  0%, 100% {
    height: 0.5rem;
  }
  50% {
    height: 1.25rem;
  }
}

/* Message Styles */
.voice-message {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  max-width: 300px;
  text-align: center;
  white-space: nowrap;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  z-index: 50;
}

.voice-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
}

.voice-info {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #2563eb;
}

/* Keyboard Hint */
.voice-hint {
  font-size: 0.75rem;
  color: #9ca3af;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.voice-hint kbd {
  padding: 0.125rem 0.375rem;
  background: #f3f4f6;
  border: 1px solid #d1d5db;
  border-radius: 0.25rem;
  font-size: 0.75rem;
  font-family: monospace;
}

/* Pulse Animation */
@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}
</style>
