<!-- App.vue -->
<template>
  <div class="h-screen">
    <!-- Main content -->
    <main>
      <SignedIn>
        <router-view />
      </SignedIn>
      <SignedOut>
        <LoginPage />
      </SignedOut>
    </main>
  </div>
</template>

<script setup>
import { SignedIn, SignedOut } from '@clerk/vue'
import LoginPage from './views/LoginPage.vue'
</script>
