<template>
  <div class="voice-control-container">
    <!-- Microphone Button -->
    <button
      @click="handleToggleVoice"
      :disabled="!isSupported || voiceStatus === 'connecting' || !conversationId"
      :class="[
        'voice-button',
        voiceStatusClass,
        { 'voice-button-active': isVoiceMode }
      ]"
      :title="buttonTitle"
    >
      <!-- Microphone Icon -->
      <svg
        v-if="!isVoiceMode"
        class="w-6 h-6"
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

      <!-- Stop Icon -->
      <svg
        v-else-if="isVoiceMode && voiceStatus !== 'speaking'"
        class="w-6 h-6"
        fill="currentColor"
        viewBox="0 0 24 24"
      >
        <rect x="6" y="6" width="12" height="12" rx="2" />
      </svg>

      <!-- Speaking Animation -->
      <div v-else class="speaking-animation">
        <span></span>
        <span></span>
        <span></span>
      </div>

      <!-- Audio Level Indicator (Pulsing Ring) -->
      <div
        v-if="isVoiceMode && audioLevel > 0"
        class="audio-level-ring"
        :style="{ transform: `scale(${1 + audioLevel / 100})` }"
      ></div>
    </button>

    <!-- Error Message -->
    <div v-if="error" class="voice-error">
      <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
        <path
          fill-rule="evenodd"
          d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
          clip-rule="evenodd"
        />
      </svg>
      <span>{{ error }}</span>
    </div>

    <!-- Keyboard Shortcut Hint -->
    <div v-if="!isVoiceMode && !error && conversationId" class="voice-hint">
      <kbd>Ctrl</kbd>+<kbd>Space</kbd> for voice
    </div>
    <div v-else-if="!isVoiceMode && !error && !conversationId" class="voice-hint text-gray-400">
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

// Use voice chat composable
const {
  isVoiceMode,
  voiceStatus,
  error,
  audioLevel,
  isSupported,
  toggleVoiceMode
} = useVoiceChat(props.conversationId)

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

const buttonTitle = computed(() => {
  if (!isSupported.value) {
    return 'Voice mode not supported in your browser'
  }

  if (!props.conversationId) {
    return 'Send a message first to start voice mode'
  }

  const statusTitles = {
    idle: 'Start voice mode (Ctrl+Space)',
    connecting: 'Connecting...',
    listening: 'Listening... Click to stop',
    speaking: 'Speaking... Click to stop',
    thinking: 'Processing... Click to stop',
    error: 'Voice error - Click to retry'
  }

  return statusTitles[voiceStatus.value] || 'Toggle voice mode'
})

// Methods
async function handleToggleVoice() {
  try {
    // If activating voice mode, emit event first to let parent prepare
    if (!isVoiceMode.value) {
      emit('voice-mode-starting')
      // Small delay to let parent connect main WebSocket
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

// Keyboard shortcut
function handleKeyboardShortcut(event) {
  // Ctrl+Space or Cmd+Space
  if ((event.ctrlKey || event.metaKey) && event.code === 'Space') {
    event.preventDefault()
    handleToggleVoice()
  }

  // Escape to stop voice mode
  if (event.code === 'Escape' && isVoiceMode.value) {
    handleToggleVoice()
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
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.voice-button {
  position: relative;
  width: 3rem;
  height: 3rem;
  border-radius: 50%;
  border: 2px solid #e5e7eb;
  background: white;
  color: #6b7280;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.voice-button:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
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
  border-color: #d1d5db;
  color: #6b7280;
}

.status-connecting {
  border-color: #fbbf24;
  color: #f59e0b;
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

.status-listening {
  border-color: #3b82f6;
  color: #3b82f6;
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

.status-speaking {
  border-color: #10b981;
  color: #10b981;
}

.status-thinking {
  border-color: #f59e0b;
  color: #f59e0b;
  animation: pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

.status-error {
  border-color: #ef4444;
  color: #ef4444;
}

.voice-button-active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-color: #667eea;
}

/* Audio Level Ring */
.audio-level-ring {
  position: absolute;
  top: -4px;
  left: -4px;
  right: -4px;
  bottom: -4px;
  border-radius: 50%;
  border: 2px solid #3b82f6;
  opacity: 0.5;
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

/* Error Message */
.voice-error {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 0.5rem;
  color: #dc2626;
  font-size: 0.875rem;
  max-width: 300px;
  text-align: center;
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
