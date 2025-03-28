<template>
  <header class="bg-primary-bodyBg sticky top-0 z-50">
    <div class="h-[56px] mx-auto px-6 flex items-center justify-between">
      <!-- Left: Brand -->
      <div class="flex items-center space-x-2">
        <div class="flex-shrink-0 h-[28px]">
          <button>
            <svg
              width="28"
              height="28"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M22 4V20H2V4H22ZM4 8.67H6.5V6H4V8.67ZM6.5 10.67H4V13.34H6.5V10.67ZM20 6H8.5V18H20V6ZM6.5 18V15.33H4V18H6.5Z"
                fill="#667085"
              />
            </svg>
          </button>
        </div>

        <h1
          class="text-xl font-bold text-primary-brandTextPrimary tracking-tight text-center"
        >
          Agentic
        </h1>
      </div>

      <!-- Right: Chat mode toggle, settings, user -->
      <div class="flex items-center space-x-4">
        <div class="flex items-center space-x-0">
          <button
            @click="toggleTheme"
            class="p-2 text-gray-600 hover:text-primary-brandTextPrimary transition-colors"
          >
            <!-- Dark mode icon -->
            <span v-if="themeMode === 'dark'">
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M9.37 5.51C9.19 6.15 9.1 6.82 9.1 7.5C9.1 11.58 12.42 14.9 16.5 14.9C17.18 14.9 17.85 14.81 18.49 14.63C17.45 17.19 14.93 19 12 19C8.14 19 5 15.86 5 12C5 9.07 6.81 6.55 9.37 5.51ZM12 3C7.03 3 3 7.03 3 12C3 16.97 7.03 21 12 21C16.97 21 21 16.97 21 12C21 11.54 20.96 11.08 20.9 10.64C19.92 12.01 18.32 12.9 16.5 12.9C13.52 12.9 11.1 10.48 11.1 7.5C11.1 5.69 11.99 4.08 13.36 3.1C12.92 3.04 12.46 3 12 3Z"
                  fill="#667085"
                />
              </svg>
            </span>

            <!-- Light mode icon -->
            <span v-else>
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M12 9C13.65 9 15 10.35 15 12C15 13.65 13.65 15 12 15C10.35 15 9 13.65 9 12C9 10.35 10.35 9 12 9ZM12 7C9.24 7 7 9.24 7 12C7 14.76 9.24 17 12 17C14.76 17 17 14.76 17 12C17 9.24 14.76 7 12 7ZM2 13H4C4.55 13 5 12.55 5 12C5 11.45 4.55 11 4 11H2C1.45 11 1 11.45 1 12C1 12.55 1.45 13 2 13ZM20 13H22C22.55 13 23 12.55 23 12C23 11.45 22.55 11 22 11H20C19.45 11 19 11.45 19 12C19 12.55 19.45 13 20 13ZM11 2V4C11 4.55 11.45 5 12 5C12.55 5 13 4.55 13 4V2C13 1.45 12.55 1 12 1C11.45 1 11 1.45 11 2ZM11 20V22C11 22.55 11.45 23 12 23C12.55 23 13 22.55 13 22V20C13 19.45 12.55 19 12 19C11.45 19 11 19.45 11 20ZM5.99 4.58C5.6 4.19 4.96 4.19 4.58 4.58C4.19 4.97 4.19 5.61 4.58 5.99L5.64 7.05C6.03 7.44 6.67 7.44 7.05 7.05C7.43 6.66 7.44 6.02 7.05 5.64L5.99 4.58ZM18.36 16.95C17.97 16.56 17.33 16.56 16.95 16.95C16.56 17.34 16.56 17.98 16.95 18.36L18.01 19.42C18.4 19.81 19.04 19.81 19.42 19.42C19.81 19.03 19.81 18.39 19.42 18.01L18.36 16.95ZM19.42 5.99C19.81 5.6 19.81 4.96 19.42 4.58C19.03 4.19 18.39 4.19 18.01 4.58L16.95 5.64C16.56 6.03 16.56 6.67 16.95 7.05C17.34 7.43 17.98 7.44 18.36 7.05L19.42 5.99ZM7.05 18.36C7.44 17.97 7.44 17.33 7.05 16.95C6.66 16.56 6.02 16.56 5.64 16.95L4.58 18.01C4.19 18.4 4.19 19.04 4.58 19.42C4.97 19.8 5.61 19.81 5.99 19.42L7.05 18.36Z"
                  fill="#667085"
                />
              </svg>
            </span>
          </button>

          <button
            @click="openSettings"
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

          <SignedIn>
            <UserButton
              afterSignOutUrl="/login"
              :appearance="{
                elements: {
                  avatarBox: 'bg-primary-brandAvatarGray h-10 w-10',
                },
              }"
            />
          </SignedIn>
        </div>

        <button
          class="py-2 px-4 w-full border border-primary-brandBorder bg-primary-brandColor hover:bg-primary-brandColor/90 text-white text-sm rounded"
          @click="console.log('New chat clicked')"
          :disabled="false"
        >
          + New Chat
        </button>
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
import { ref, computed, watch, inject, onMounted } from 'vue';
import { SignedIn, UserButton } from '@clerk/vue';
import SettingsModal from './SettingsModal.vue';

const themeMode = ref('light'); // Default theme mode

const toggleTheme = () => {
  console.log('toggleTheme', themeMode.value);
  themeMode.value = themeMode.value === 'light' ? 'dark' : 'light';
};

// Inject the shared state provided in MainLayout.vue.
const selectedOption = inject('selectedOption');

const chatMode = ref(true);
// We'll emit 'modeToggled' to the parent
const emit = defineEmits(['keysUpdated', 'modeToggled']);

watch(chatMode, (val) => {
  emit('modeToggled', val);
});

onMounted(async () => {
  emit('modeToggled', true);
  settingsModalRef.value?.checkRequiredKeys();
});

const settingsModalRef = ref(null);
function openSettings() {
  // settingsModalRef.value.isOpen = true
  settingsModalRef.value?.openModal();
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
