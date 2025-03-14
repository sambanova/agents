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
        
        <!-- Sign Up component (default) -->
        <div v-if="showSignUp">
          <SignUp 
            afterSignUpUrl="/"
            :appearance="{ 
              elements: {
                formButtonPrimary: 'bg-primary-600 hover:bg-primary-700',
                footerActionLink: 'text-primary-600 hover:text-primary-700'
              }
            }"
          />
          <div class="text-center mt-4">
            <p class="text-sm text-gray-600">
              Already have an account? 
              <button @click="showSignUp = false" class="text-primary-600 font-medium hover:underline">
                Sign in
              </button>
            </p>
          </div>
          <div class="text-center mt-4 flex flex-row justify-between">
            <a class="underline text-[12px]" href="/terms-of-service">Terms Of Service</a>
            <a class=" underline text-[12px] mt-1" target="_blank" href="https://sambanova.ai/privacy-policy">Privacy Policy</a>
          </div>
        </div>
        
        <!-- Sign In component -->
        <div v-else>
          <SignIn 
            afterSignInUrl="/"
            :appearance="{ 
              elements: {
                formButtonPrimary: 'bg-primary-600 hover:bg-primary-700',
                footerActionLink: 'text-primary-600 hover:text-primary-700'
              }
            }"
          />
          <div class="text-center mt-4">
            <p class="text-sm text-gray-600">
              Don't have an account? 
              <button @click="showSignUp = true" class="text-primary-600 font-medium hover:underline">
                Sign up
              </button>
            </p>
          </div>
        </div>
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
import { SignIn, SignUp } from '@clerk/vue'
import { ref } from 'vue'

// State to toggle between sign-in and sign-up, defaulting to sign-up
const showSignUp = ref(true)
</script>

<style>
.cl-footer{
  display: none;
}
</style>