<!-- src/components/Header.vue -->
<template>
  <header class=" bg-primary-bodyBg sticky top-0 z-50  ">
    <div class="h-[56px] mx-auto px-4 sm:px-6 flex items-center justify-between">
      <!-- Left: Brand -->
      <div class="flex items-center space-x-2 sm:space-x-4">
        <div class="flex-shrink-0">
          <img
            src="/logo.svg" 
            alt="Samba Sales Agents Logo" 
            class="h-6 md:hidden size-[30px]"
            
          />
          <img 
            src="/logo-icon.svg" 
            alt="Samba Sales Agents Logo" 
            class="hidden md:h-8 md:block size-[30px]"
          />
        </div>
        <h1 class="text-[16px]  font-bold text-primary-brandTextPrimary tracking-tight text-center">
          Agents
        </h1>
      </div>

      <!-- Right: Chat mode toggle, date/time, settings, user -->
      <div class="flex items-center space-x-4">
        
        <span class="invisible">
        <SelectProvider   v-model:selectedOption="selectedOption" />
      </span>
        <!-- NEW: Chat Mode Toggle -->
        <div v-if="isWorkflowEnabled" class="flex items-center space-x-2">
          <ToggleSwitch v-model:chatMode="chatMode" label="" />

          <!-- <label for="modeToggle" class="text-sm text-right text-gray-600">Chat Mode</label>
          <input
            
            id="modeToggle"
            type="checkbox"
            v-model="chatMode"
            class="h-4 w-4 text-primary-600 border-gray-300 focus:ring-primary-500"
          /> -->
        </div>

        <!-- <ToggleSwitch 
           id="modeToggle"
            type="checkbox"
            v-model="chatMode"  
            :chatMode="chatMode"
            /> -->
<!-- 
        <div class="hidden sm:block lg:hidden text-sm text-right text-gray-600">
          {{ shortCurrentDateTime }}
        </div>

        <div class="hidden lg:block text-sm text-right text-gray-600 w-1/2">
          {{ currentDateTime }}
        </div> -->

        <button
          @click="openSettings"
          class="p-2 text-gray-600 hover:text-primary-brandTextPrimary transition-colors"
        >
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" 
                  stroke-linejoin="round" 
                  stroke-width="2" 
                  d="M10.325 4.317c.426-1.756 2.722-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 001.066-2.572c-.94-1.543.826-3.31 2.37-2.37.765-1.36 2.722-1.36 3.486 0z" />
            <path stroke-linecap="round" 
                  stroke-linejoin="round" 
                  stroke-width="2" 
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>

        <SignedIn>
          <UserButton 

            afterSignOutUrl="/login"
            :appearance="{ elements: { avatarBox: 'bg-primary-brandAvatarGray h-8 w-8 sm:h-10 sm:w-10' } }"
          />
        </SignedIn>
      </div>
    </div>
    
    <SettingsModal :provider="selectedOption.value" ref="settingsModalRef" @keysUpdated="onKeysUpdated" />
  </header>
</template>

<script setup>
import { ref, computed, watch ,inject, onMounted} from 'vue'
import { SignedIn, UserButton } from '@clerk/vue'
import SettingsModal from './SettingsModal.vue'
import ToggleSwitch from '@/components/Common/UIComponents/ToggleSwitch.vue'
import SelectProvider from '@/components/ChatMain/SelectProvider.vue'
// import Dropdown from './Dropdown.vue'


const isWorkflowEnabled = computed(() => {
  return import.meta.env.VITE_ENABLE_WORKFLOW_TOGGLE === 'true'
})

// Inject the shared state provided in MainLayout.vue.
const selectedOption = inject('selectedOption')

const chatMode = ref(true)
// We'll emit 'modeToggled' to the parent
const emit = defineEmits(['keysUpdated','modeToggled'])

watch(chatMode, (val) => {
  emit('modeToggled', val)
})

onMounted(async () => {
  emit('modeToggled', true)
  settingsModalRef.value?.checkRequiredKeys()

})

const settingsModalRef = ref(null)
function openSettings() {
  // settingsModalRef.value.isOpen = true
  settingsModalRef.value?.openModal()

}

function onKeysUpdated() {
  
  emit('keysUpdated')
}

const currentDateTime = computed(() => {
  const now = new Date()
  return new Intl.DateTimeFormat('en-US', {
    dateStyle: 'full',
    timeStyle: 'short'
  }).format(now)
})

const shortCurrentDateTime = computed(() => {
  const now = new Date()
  return new Intl.DateTimeFormat('en-US', {
    dateStyle: 'short',
    timeStyle: 'short'
  }).format(now).replace(', ', '\n')
})

// Add defineExpose to make openSettings accessible to parent
defineExpose({
  openSettings
})
</script>
