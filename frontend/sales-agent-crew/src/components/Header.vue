<template>
  <header class="bg-primary-bodyBg sticky top-0 z-50">
    <div class="h-[56px] mx-auto px-6 flex items-center justify-between">
      <!-- Left: Brand -->
      <div class="flex items-center gap-3">
        <img
          src="/Images/logo-nsai.svg"
          alt="SambaNova Sales Agents Logo"
          class="h-8"
        />
        <div class="flex items-center gap-2">
          <span class="text-base sm:text-lg font-semibold text-gray-500">
            Agents
          </span>
          <span
            class="px-2 py-[2px] text-[10px] font-semibold rounded-full bg-yellow-100 text-yellow-800 border border-yellow-300"
          >
            Preview
          </span>
        </div>
      </div>

      <!-- Right: Chat mode toggle, settings, user -->
      <div class="flex items-center space-x-4">
        <span class="invisible">
          <SelectProvider v-model:selectedOption="selectedOption" />
        </span>

        <!-- Chat Mode Toggle -->
        <div v-if="isWorkflowEnabled" class="flex items-center space-x-2">
          <ToggleSwitch v-model:chatMode="chatMode" label="" />
        </div>

        <button
          @click="openSettings()"
          class="p-2 text-gray-600 hover:text-primary-brandTextPrimary transition-colors"
        >
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M19.4323 12.98C19.4723 12.66 19.5023 12.34 19.5023 12C19.5023 11.66 19.4723 11.34 19.4323 11.02L21.5423 9.37C21.7323 9.22 21.7823 8.95 21.6623 8.73L19.6623 5.27C19.5723 5.11 19.4023 5.02 19.2223 5.02C19.1623 5.02 19.1023 5.03 19.0523 5.05L16.5623 6.05C16.0423 5.65 15.4823 5.32 14.8723 5.07L14.4923 2.42C14.4623 2.18 14.2523 2 14.0023 2H10.0023C9.75228 2 9.54228 2.18 9.51228 2.42L9.13228 5.07C8.52228 5.32 7.96228 5.66 7.44228 6.05L4.95228 5.05C4.89228 5.03 4.83228 5.02 4.77228 5.02C4.60228 5.02 4.43228 5.11 4.34228 5.27L2.34228 8.73C2.21228 8.95 2.27228 9.22 2.46228 9.37L4.57228 11.02C4.53228 11.34 4.50228 11.67 4.50228 12C4.50228 12.33 4.53228 12.66 4.57228 12.98L2.46228 14.63C2.27228 14.78 2.22228 15.05 2.34228 15.27L4.34228 18.73C4.43228 18.89 4.60228 18.98 4.78228 18.98C4.84228 18.98 4.90228 18.97 4.95228 18.95L7.44228 17.95C7.96228 18.35 8.52228 18.68 9.13228 18.93L9.51228 21.58C9.54228 21.82 9.75228 22 10.0023 22H14.0023C14.2523 22 14.4623 21.82 14.4923 21.58L14.8723 18.93C15.4823 18.68 16.0423 18.34 16.5623 17.95L19.0523 18.95C19.1123 18.97 19.1723 18.98 19.2323 18.98C19.4023 18.98 19.5723 18.89 19.6623 18.73L21.6623 15.27C21.7823 15.05 21.7323 14.78 21.5423 14.63L19.4323 12.98ZM17.4523 11.27C17.4923 11.58 17.5023 11.79 17.5023 12C17.5023 12.21 17.4823 12.43 17.4523 12.73L17.3123 13.86L18.2023 14.56L19.2823 15.4L18.5823 16.61L17.3123 16.1L16.2723 15.68L15.3723 16.36C14.9423 16.68 14.5323 16.92 14.1223 17.09L13.0623 17.52L12.9023 18.65L12.7023 20H11.3023L10.9523 17.52L9.89228 17.09C9.46228 16.91 9.06228 16.68 8.66228 16.38L7.75228 15.68L6.69228 16.11L5.42228 16.62L4.72228 15.41L5.80228 14.57L6.69228 13.87L6.55228 12.74C6.52228 12.43 6.50228 12.2 6.50228 12C6.50228 11.8 6.52228 11.57 6.55228 11.27L6.69228 10.14L5.80228 9.44L4.72228 8.6L5.42228 7.39L6.69228 7.9L7.73228 8.32L8.63228 7.64C9.06228 7.32 9.47228 7.08 9.88228 6.91L10.9423 6.48L11.1023 5.35L11.3023 4H12.6923L13.0423 6.48L14.1023 6.91C14.5323 7.09 14.9323 7.32 15.3323 7.62L16.2423 8.32L17.3023 7.89L18.5723 7.38L19.2723 8.59L18.2023 9.44L17.3123 10.14L17.4523 11.27ZM12.0023 8C9.79228 8 8.00228 9.79 8.00228 12C8.00228 14.21 9.79228 16 12.0023 16C14.2123 16 16.0023 14.21 16.0023 12C16.0023 9.79 14.2123 8 12.0023 8ZM12.0023 14C10.9023 14 10.0023 13.1 10.0023 12C10.0023 10.9 10.9023 10 12.0023 10C13.1023 10 14.0023 10.9 14.0023 12C14.0023 13.1 13.1023 14 12.0023 14Z"
              fill="#667085"
            />
          </svg>
        </button>

        <div v-if="isAuthenticated" class="relative">
          <button
            @click="toggleUserMenu"
            class="bg-gray-100 hover:bg-gray-200 h-10 w-10 rounded-full flex items-center justify-center text-gray-700 font-semibold transition-all duration-200 ring-2 ring-transparent hover:ring-indigo-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {{ userInitials }}
          </button>
          
          <!-- User Menu Dropdown -->
          <div 
            v-if="showUserMenu"
            @click.stop
            class="absolute right-0 mt-3 w-72 bg-white rounded-xl shadow-xl border border-gray-100 z-50 overflow-hidden"
          >
            <!-- User Info Section -->
            <div class="px-6 py-4 bg-gray-50 border-b border-gray-100">
              <div class="flex items-center space-x-3">
                <div class="bg-indigo-100 h-12 w-12 rounded-full flex items-center justify-center">
                  <span class="text-indigo-600 font-semibold text-lg">{{ userInitials }}</span>
                </div>
                <div class="flex-1 min-w-0">
                  <div class="font-semibold text-gray-900 truncate">
                    {{ user?.name || user?.email?.split('@')[0] || 'User' }}
                  </div>
                  <div class="text-sm text-gray-500 truncate">{{ user?.email }}</div>
                </div>
              </div>
            </div>

            <!-- Menu Items -->
            <div class="py-2">
              <!-- Sign Out -->
              <button
                @click="logout"
                class="w-full px-6 py-3 text-left flex items-center space-x-3 text-gray-700 hover:bg-gray-50 transition-colors duration-150"
              >
                <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path>
                </svg>
                <div>
                  <div class="font-medium">Sign out</div>
                  <div class="text-xs text-gray-500">Log out of your account</div>
                </div>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <SettingsModal
      :provider="selectedOption.value"
      ref="settingsModalRef"
      @keysUpdated="onKeysUpdated"
    />
  </header>
</template>

<script setup>
import { ref, computed, watch, inject, onMounted, nextTick } from 'vue';
import { useAuth0 } from '@auth0/auth0-vue';
import SettingsModal from './SettingsModal.vue';
import ToggleSwitch from '@/components/Common/UIComponents/ToggleSwitch.vue';
import SelectProvider from '@/components/ChatMain/SelectProvider.vue';
// import Dropdown from './Dropdown.vue'

const isWorkflowEnabled = computed(() => {
  return import.meta.env.VITE_ENABLE_WORKFLOW_TOGGLE === 'true';
});

// Inject the shared state provided in MainLayout.vue.
const selectedOption = inject('selectedOption');

// Auth0 composable
const { isAuthenticated, user, logout: auth0Logout } = useAuth0();

// User menu state
const showUserMenu = ref(false);

// Computed user initials
const userInitials = computed(() => {
  if (!user.value) return '';
  const name = user.value.name || user.value.email || '';
  const nameParts = name.split(' ');
  if (nameParts.length >= 2) {
    return (nameParts[0][0] + nameParts[1][0]).toUpperCase();
  }
  return name[0]?.toUpperCase() || '';
});

// User menu functions
const toggleUserMenu = () => {
  showUserMenu.value = !showUserMenu.value;
};

const logout = () => {
  showUserMenu.value = false;
  auth0Logout({ 
    logoutParams: { 
      returnTo: window.location.origin 
    } 
  });
};

const chatMode = ref(true);
// We'll emit 'modeToggled' to the parent
const emit = defineEmits(['keysUpdated', 'modeToggled']);

watch(chatMode, (val) => {
  emit('modeToggled', val);
});

onMounted(async () => {
  emit('modeToggled', true);
  settingsModalRef.value?.checkRequiredKeys();
  
  // Close user menu when clicking outside
  document.addEventListener('click', (event) => {
    if (showUserMenu.value && !event.target.closest('.relative')) {
      showUserMenu.value = false;
    }
  });
});

const settingsModalRef = ref(null);
function openSettings(tabOrEvent = null) {
  showUserMenu.value = false; // Close user menu

  // Check if it's an event object (from direct @click) or a tab name string
  let tab = null;
  if (typeof tabOrEvent === 'string') {
    tab = tabOrEvent;
  } else if (tabOrEvent && typeof tabOrEvent === 'object' && tabOrEvent.type) {
    // It's an event object, ignore it
    tab = null;
  }

  // Pass the tab directly to openModal
  settingsModalRef.value?.openModal(tab);
}

function onKeysUpdated() {
  emit('keysUpdated');
}

const currentDateTime = computed(() => {
  const now = new Date();
  return new Intl.DateTimeFormat('en-US', {
    dateStyle: 'full',
    timeStyle: 'short',
  }).format(now);
});

const shortCurrentDateTime = computed(() => {
  const now = new Date();
  return new Intl.DateTimeFormat('en-US', {
    dateStyle: 'short',
    timeStyle: 'short',
  })
    .format(now)
    .replace(', ', '\n');
});

// Add defineExpose to make openSettings accessible to parent
defineExpose({
  openSettings,
});
</script>
