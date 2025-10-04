<template>
  <div class="voice-settings">
    <div class="settings-header">
      <h3 class="settings-title">Voice Settings</h3>
      <p class="settings-description">Customize your voice interaction experience</p>
    </div>

    <div class="settings-content">
      <!-- Voice Selection -->
      <div class="setting-group">
        <label class="setting-label">Voice</label>
        <select
          v-model="localConfig.voice_name"
          @change="handleConfigChange"
          class="setting-select"
        >
          <option value="ITO">ITO (Default - Conversational)</option>
          <option value="KORA">KORA (Warm & Friendly)</option>
          <option value="DACHER">DACHER (Professional)</option>
          <option value="AURA">AURA (Calm & Clear)</option>
          <option value="FINN">FINN (Energetic)</option>
        </select>
        <p class="setting-hint">Choose the voice personality for your assistant</p>
      </div>

      <!-- Narration Toggle -->
      <div class="setting-group">
        <div class="setting-toggle">
          <div>
            <label class="setting-label">Enable Narration</label>
            <p class="setting-hint">Hear agent thoughts and reasoning process</p>
          </div>
          <button
            @click="toggleNarration"
            :class="[
              'toggle-button',
              { 'toggle-active': localConfig.narration_enabled }
            ]"
          >
            <span
              :class="[
                'toggle-slider',
                { 'toggle-slider-active': localConfig.narration_enabled }
              ]"
            ></span>
          </button>
        </div>
      </div>

      <!-- Speech Speed -->
      <div class="setting-group">
        <label class="setting-label">Speech Speed</label>
        <div class="speed-options">
          <button
            v-for="speed in speechSpeeds"
            :key="speed.value"
            @click="setSpeechSpeed(speed.value)"
            :class="[
              'speed-option',
              { 'speed-option-active': localConfig.speech_speed === speed.value }
            ]"
          >
            {{ speed.label }}
          </button>
        </div>
      </div>

      <!-- Save Button -->
      <div class="setting-actions">
        <button
          @click="saveSettings"
          :disabled="isSaving"
          class="save-button"
        >
          <svg v-if="!isSaving" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>
          <svg v-else class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <span>{{ isSaving ? 'Saving...' : 'Save Settings' }}</span>
        </button>

        <p v-if="saveMessage" :class="['save-message', saveMessage.type]">
          {{ saveMessage.text }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { useAuth0 } from '@auth0/auth0-vue'
import axios from 'axios'

const { getAccessTokenSilently } = useAuth0()

const emit = defineEmits(['settings-updated'])

// State
const localConfig = reactive({
  voice_name: 'ITO',
  narration_enabled: true,
  speech_speed: 'normal'
})

const isSaving = ref(false)
const saveMessage = ref(null)

const speechSpeeds = [
  { value: 'slow', label: 'Slow' },
  { value: 'normal', label: 'Normal' },
  { value: 'fast', label: 'Fast' }
]

// Methods
async function loadSettings() {
  try {
    const token = await getAccessTokenSilently()
    const response = await axios.get('/api/voice/config', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    })

    if (response.data) {
      Object.assign(localConfig, response.data)
    }
  } catch (err) {
    console.error('Failed to load voice settings:', err)
  }
}

function toggleNarration() {
  localConfig.narration_enabled = !localConfig.narration_enabled
  handleConfigChange()
}

function setSpeechSpeed(speed) {
  localConfig.speech_speed = speed
  handleConfigChange()
}

function handleConfigChange() {
  // Clear save message on change
  saveMessage.value = null
}

async function saveSettings() {
  try {
    isSaving.value = true
    saveMessage.value = null

    const token = await getAccessTokenSilently()
    await axios.post('/api/voice/config', localConfig, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })

    saveMessage.value = {
      type: 'success',
      text: 'Settings saved successfully!'
    }

    emit('settings-updated', localConfig)

    // Clear success message after 3 seconds
    setTimeout(() => {
      saveMessage.value = null
    }, 3000)
  } catch (err) {
    console.error('Failed to save voice settings:', err)
    saveMessage.value = {
      type: 'error',
      text: 'Failed to save settings. Please try again.'
    }
  } finally {
    isSaving.value = false
  }
}

// Load settings on mount
onMounted(() => {
  loadSettings()
})
</script>

<style scoped>
.voice-settings {
  background: white;
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.settings-header {
  padding: 1.5rem;
  border-bottom: 1px solid #e5e7eb;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.settings-title {
  font-size: 1.25rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
}

.settings-description {
  font-size: 0.875rem;
  opacity: 0.9;
}

.settings-content {
  padding: 1.5rem;
}

.setting-group {
  margin-bottom: 1.5rem;
}

.setting-group:last-child {
  margin-bottom: 0;
}

.setting-label {
  display: block;
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
  margin-bottom: 0.5rem;
}

.setting-hint {
  font-size: 0.75rem;
  color: #6b7280;
  margin-top: 0.25rem;
}

.setting-select {
  width: 100%;
  padding: 0.625rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  color: #374151;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
}

.setting-select:hover {
  border-color: #9ca3af;
}

.setting-select:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.setting-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.toggle-button {
  position: relative;
  width: 3rem;
  height: 1.75rem;
  border-radius: 9999px;
  background: #d1d5db;
  border: none;
  cursor: pointer;
  transition: background 0.2s;
}

.toggle-button.toggle-active {
  background: #667eea;
}

.toggle-slider {
  position: absolute;
  top: 0.25rem;
  left: 0.25rem;
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 50%;
  background: white;
  transition: transform 0.2s;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.toggle-slider.toggle-slider-active {
  transform: translateX(1.25rem);
}

.speed-options {
  display: flex;
  gap: 0.5rem;
}

.speed-option {
  flex: 1;
  padding: 0.625rem 1rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  color: #6b7280;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
}

.speed-option:hover {
  border-color: #9ca3af;
  background: #f9fafb;
}

.speed-option.speed-option-active {
  border-color: #667eea;
  background: #ede9fe;
  color: #667eea;
}

.setting-actions {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid #e5e7eb;
}

.save-button {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.save-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.save-button:active:not(:disabled) {
  transform: translateY(0);
}

.save-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.save-message {
  margin-top: 0.75rem;
  padding: 0.75rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  text-align: center;
}

.save-message.success {
  background: #d1fae5;
  color: #065f46;
}

.save-message.error {
  background: #fee2e2;
  color: #991b1b;
}
</style>
