<template>
  <transition name="slide-down">
    <div v-if="isVisible" class="voice-status-badge">
      <!-- Status Icon -->
      <div class="status-icon" :class="`status-${voiceStatus}`">
        <!-- Listening Icon -->
        <svg
          v-if="voiceStatus === 'listening'"
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

        <!-- Thinking/Processing Icon -->
        <svg
          v-else-if="voiceStatus === 'thinking'"
          class="w-5 h-5 animate-spin"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            class="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            stroke-width="4"
          ></circle>
          <path
            class="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          ></path>
        </svg>

        <!-- Speaking Icon -->
        <svg
          v-else-if="voiceStatus === 'speaking'"
          class="w-5 h-5"
          fill="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"
          />
        </svg>

        <!-- Connecting Icon -->
        <svg
          v-else-if="voiceStatus === 'connecting'"
          class="w-5 h-5 animate-pulse"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M13 10V3L4 14h7v7l9-11h-7z"
          />
        </svg>
      </div>

      <!-- Status Text -->
      <div class="status-content">
        <div class="status-label">{{ statusLabel }}</div>

        <!-- Current Transcript -->
        <div v-if="currentTranscript" class="transcript-text">
          "{{ currentTranscript }}"
        </div>

        <!-- Agent Update -->
        <div v-if="agentUpdate" class="agent-update-text">
          {{ agentUpdate }}
        </div>
      </div>

      <!-- Close Button -->
      <button
        @click="$emit('close')"
        class="close-button"
        title="Minimize"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>
    </div>
  </transition>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  voiceStatus: {
    type: String,
    required: true,
    validator: (value) => ['idle', 'connecting', 'listening', 'speaking', 'thinking'].includes(value)
  },
  currentTranscript: {
    type: String,
    default: ''
  },
  agentUpdate: {
    type: String,
    default: ''
  },
  isVisible: {
    type: Boolean,
    default: true
  }
})

defineEmits(['close'])

const statusLabel = computed(() => {
  const labels = {
    idle: 'Voice Mode',
    connecting: 'Connecting to voice service...',
    listening: 'Listening...',
    speaking: 'Agent speaking',
    thinking: 'Agent thinking...'
  }
  return labels[props.voiceStatus] || 'Voice Mode'
})
</script>

<style scoped>
.voice-status-badge {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 0.75rem;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
  max-width: 500px;
  min-width: 250px;
  animation: slideDown 0.3s ease;
}

.status-icon {
  flex-shrink: 0;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(10px);
}

.status-icon.status-listening {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

.status-icon.status-thinking {
  animation: pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

.status-content {
  flex: 1;
  min-width: 0;
}

.status-label {
  font-weight: 600;
  font-size: 0.875rem;
  margin-bottom: 0.25rem;
}

.transcript-text {
  font-size: 0.875rem;
  font-style: italic;
  opacity: 0.9;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-update-text {
  font-size: 0.8125rem;
  opacity: 0.85;
  margin-top: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.agent-update-text::before {
  content: '';
  width: 0.375rem;
  height: 0.375rem;
  background: white;
  border-radius: 50%;
  animation: blink 1.5s ease-in-out infinite;
}

.close-button {
  flex-shrink: 0;
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}

.close-button:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: scale(1.1);
}

.close-button:active {
  transform: scale(0.9);
}

/* Animations */
@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-1rem);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.7;
    transform: scale(1.05);
  }
}

@keyframes blink {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}

/* Transitions */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease;
}

.slide-down-enter-from {
  opacity: 0;
  transform: translateY(-1rem);
}

.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-1rem);
}
</style>
