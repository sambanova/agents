<template>
  <div class="h-screen flex items-stretch  ">
    <div class="w-full h-full flex flex-col md:flex-row">
      <!-- Login box (1/3 on medium+, full width on small) -->
    
      <!-- Video box (2/3 on medium+, full width on small) -->
      <div class="w-full h-full  md:w-[60%] flex items-center justify-center  ">
        <div class="shadow-lg  rounded-lg  max-h-[90vh] w-[90%] hover:w-full transition-all duration-300 border border-primary-bodyBg">
  <video 
    src="/Images/agent-screen-recording.webm" 
    autoplay
    loop
    muted
    playsinline
    preload="auto"
    class="  object-contain "
  ></video>
</div>

      </div>
      <div class="w-full h-full md:w-[40%] flex flex-col justify-center items-center p-4 md:pl-12">
        <div class="w-auto">
        <div class="text-center mb-2">
          <img 
            src="/Images/logo-nsai.svg" 
            alt="SambaNova Logo" 
            class="h-[25px] mx-auto mb-2"
          />
          <h1 class="text-4xl font-bold text-primary-brandTextPrimary mb-2">Agents</h1>
          <p class="text-lg text-primary-brandTextSecondary">Agent Powered Intelligence</p>
        </div>
        
        <!-- Auth0 Login component -->
        <div class="w-full max-w-sm">
          <div class="bg-white p-6 rounded-lg shadow-md border">
            <h2 class="text-xl font-semibold text-center mb-4">Sign In</h2>
            <button 
              @click="login"
              :disabled="isLoading"
              class="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-primary-950 hover:bg-primary-800 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <svg v-if="isLoading" class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span v-if="isLoading">Signing in...</span>
              <span v-else>Sign in with Email</span>
            </button>
          </div>
          
          <div class="text-center mt-4">
            <div class="mb-2">
              <a class="underline text-[12px]" href="/terms-of-service">Terms Of Service</a>
              <span class="mx-2 text-[12px]">|</span>
              <a class="underline text-[12px]" target="_blank" href="https://sambanova.ai/privacy-policy">Privacy Policy</a>
            </div>
            <div class="text-[10px] text-gray-500 mb-1">Vendors</div>
            <div>
              <a class="underline text-[12px]" target="_blank" href="https://www.daytona.io/company/terms-of-service">Daytona Terms of Service</a>
            </div>
          </div>
        </div>
      </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { useAuth0 } from '@auth0/auth0-vue'

const { loginWithRedirect, isLoading } = useAuth0()

const login = () => {
  loginWithRedirect({
    appState: {
      target: '/'
    }
  })
}
</script>

<style>
/* Remove any Auth0 specific styles if needed */
</style>
