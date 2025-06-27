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
            src="/Images/SambaNova-dark-logo.png" 
            alt="SambaNova Logo" 
            class="h-[25px] mx-auto mb-2"
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
                formButtonPrimary: 'bg-primary-950 hover:bg-primary-800',
                footerActionLink: 'text-primary-600 hover:text-primary-700'
              }
            }"
          />
          <div class="text-center mt-4 flex flex-col justify-between w-full">
          <p class="text-sm text-gray-600">
            By signing up you agree to our
          </p>
          <p class="text-sm text-gray-600">
            <a class="underline text-primary-link text-[12px]" href="/terms-of-service">Terms Of Service</a>
            and
            <a class="underline text-primary-link text-[12px]" target="_blank" href="https://sambanova.ai/privacy-policy">Privacy Policy</a>
          </p>
          </div>
          <div class="text-center mt-4">
            <p class="text-sm text-gray-600">
              Already have an account? 
              <button @click="showSignUp = false" class="text-primary-link font-medium hover:underline">
                Sign in
              </button>
            </p>
          </div>
        </div>
        
        <!-- Sign In component -->
        <div v-else>
          <SignIn 
            afterSignInUrl="/"
            :appearance="{ 
              elements: {
                formButtonPrimary: 'bg-primary-950 hover:bg-primary-800',
                footerActionLink: 'text-primary-600 hover:text-primary-700'
              }
            }"
          />
          <div class="text-center mt-4 flex flex-col justify-between w-full">
          <p class="text-sm text-gray-600">
            By signing in you agree to our
          </p>
          <p class="text-sm text-gray-600">
            <a class="underline text-primary-link text-[12px]" href="/terms-of-service">Terms Of Service</a>
            and
            <a class="underline text-primary-link text-[12px]" target="_blank" href="https://sambanova.ai/privacy-policy">Privacy Policy</a>
          </p>
          </div>
          <div class="text-center mt-4">
            <p class="text-sm text-gray-600">
              Don't have an account? 
              <button @click="showSignUp = true" class="text-primary-link font-medium hover:underline">
                Sign up
              </button>
            </p>
          </div>
        </div>
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
.cl-footer {
  display: none;
}
</style>
