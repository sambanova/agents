<template>
  <div class="h-screen flex items-stretch bg-primary-bodyBg dark:bg-gray-900">
    <div class="w-full h-full flex flex-col md:flex-row">
      <!-- Video box (2/3 on medium+, full width on small) -->
      <div class="w-full h-full md:w-[60%] flex items-center justify-center">
        <div
          class="shadow-lg rounded-lg max-h-[90vh] w-[90%] hover:w-full transition-all duration-300 border border-primary-bodyBg dark:border-gray-700 bg-white dark:bg-gray-800"
        >
          <video
            src="/Images/agent-screen-recording.webm"
            autoplay
            loop
            muted
            playsinline
            preload="auto"
            class="object-contain"
          ></video>
        </div>
      </div>

      <!-- Login box (1/3 on medium+, full width on small) -->
      <div class="w-full h-full md:w-[40%] flex flex-col justify-center items-center p-4 md:pl-12 bg-white dark:bg-gray-800">
        <div class="w-auto">
          <div class="text-center mb-2">
            <img
              src="https://sambanova.ai/hubfs/sambanova-logo-black.png"
              alt="SambaNova Logo"
              class="h-[25px] mx-auto mb-2"
            />
            <h1 class="text-4xl font-bold text-primary-brandTextPrimary dark:text-white mb-2">Agents</h1>
            <p class="text-lg text-primary-brandTextSecondary dark:text-gray-400">Agent Powered Intelligence</p>
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
              <p class="text-sm text-gray-600 dark:text-gray-400">
                Already have an account?
                <button @click="showSignUp = false" class="text-primary-600 dark:text-primary-400 font-medium hover:underline">
                  Sign in
                </button>
              </p>
            </div>
            <div class="text-center mt-4 flex flex-row justify-between w-full">
              <a class="underline text-[12px] text-gray-600 dark:text-gray-400" href="/terms-of-service">Terms Of Service</a>
              <a class="underline text-[12px] text-gray-600 dark:text-gray-400" target="_blank" href="https://sambanova.ai/privacy-policy">Privacy Policy</a>
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
              <p class="text-sm text-gray-600 dark:text-gray-400">
                Don't have an account?
                <button @click="showSignUp = true" class="text-primary-600 dark:text-primary-400 font-medium hover:underline">
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
