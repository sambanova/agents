<template>
  <div class="min-h-screen bg-gradient-to-br from-primary-50 to-blue-50 flex items-center justify-center p-4">
    <div class="max-w-md w-full flex flex-col justify-center items-center ">
      <div class="text-center mb-8">
        <img 
          src="https://sambanova.ai/hubfs/sambanova-logo-black.png" 
          alt="SambaNova Logo" 
          class="h-12 mx-auto mb-6"
        />
        <h1 class="text-4xl font-bold text-primary-brandTextPrimary mb-2">Agents</h1>
        <p class="text-lg text-primary-brandTextSecondary">Agent Powered Intelligence</p>
      </div>
      
      <!-- <div class=" rounded-xl flex items-center flex-row "> -->
        <SignIn 
        afterSignInUrl="/"

          :appearance="{ 
            elements: {
              // headerTitle: 'hidden',
              // headerSubtitle: 'hidden',
              // footerAction: 'hidden'
            }
          }"
        />
      <!-- </div> -->
    </div>
  </div>
</template>

<script setup>
import { SignIn } from '@clerk/vue'
</script>
<style>
.cl-footer{
  display: none;
}
</style>