<template>
  <div class="min-h-screen bg-gradient-to-br from-primary-50 to-blue-50 flex items-center justify-center p-4">
    <div class="w-full flex flex-col xl:flex-row justify-between items-center">
      <!-- Left side (login form) - always full width on screens < 1180px -->
      <div class="w-full xl:w-[30%] flex flex-col justify-center items-center xl:pl-12">
        <div class="text-center mb-8">
          <img 
            src="https://sambanova.ai/hubfs/sambanova-logo-black.png" 
            alt="SambaNova Logo" 
            class="h-12 mx-auto mb-6"
          />
          <h1 class="text-4xl font-bold text-primary-brandTextPrimary mb-2">Agents</h1>
          <p class="text-lg text-primary-brandTextSecondary">Agent Powered Intelligence</p>
        </div>
        
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
      </div>

      <!-- Video - below login on screens < 1180px, on right side for larger screens -->
      <div class="w-full xl:w-[70%] flex items-center justify-center mt-8 xl:mt-0 xl:pr-12">
        <div class="p-2 rounded-xl bg-gradient-to-br from-[#EE7624] to-[#f59e67] shadow-xl max-w-full">
          <video 
            src="/Images/agent-screen-recording.webm" 
            autoplay
            loop
            muted
            playsinline
            preload="auto"
            class="rounded-lg max-h-[80vh] w-auto object-contain border-4 border-white"
          ></video>
        </div>
      </div>
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