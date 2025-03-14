<!-- App.vue -->
<template>
  <div class="h-screen">
    <!-- Main content -->
    <main>
      <SignedIn>
        <router-view />
      </SignedIn>
      <SignedOut>
        <router-view v-if="isTermsOfServiceRoute" />
        <LoginPage v-else />
      </SignedOut>
    </main>
  </div>
</template>

<script setup>
import { SignedIn, SignedOut } from '@clerk/vue'
import LoginPage from './views/LoginPage.vue'
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const isTermsOfServiceRoute = computed(() => route.path === '/terms-of-service')
</script>
