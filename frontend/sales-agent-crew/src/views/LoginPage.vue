<template>
  <div class="h-screen flex items-stretch bg-gray-50">
    <div class="w-full h-full flex flex-col md:flex-row">
      <!-- Video box (2/3 on medium+, full width on small) -->
      <div class="w-full h-full md:w-[60%] flex items-center justify-center">
        <div class="shadow-lg rounded-lg max-h-[90vh] w-[90%] hover:w-full transition-all duration-300 border border-primary-bodyBg">
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
      <div class="w-full h-full md:w-[40%] flex flex-col justify-center items-center p-4 md:pl-12">
        <div class="w-full max-w-md">
          <!-- Logo and Branding -->
          <div class="text-center mb-8">
            <img 
              src="/Images/logo-nsai.svg" 
              alt="SambaNova Logo" 
              class="h-[32px] mx-auto mb-4"
            />
            <h1 class="text-3xl font-bold text-gray-900 mb-2">Agents</h1>
            <p class="text-lg text-gray-600">Agent Powered Intelligence</p>
          </div>
          
          <!-- Professional Auth Form -->
          <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
            <div class="mb-6">
              <h2 class="text-xl font-semibold text-gray-900 text-center mb-2">
                {{ isSignUp ? 'Create your account' : 'Welcome back' }}
              </h2>
              <p class="text-sm text-gray-600 text-center">
                {{ isSignUp ? 'Please fill in the details to get started.' : 'Please sign in to your account.' }}
              </p>
            </div>

            <!-- Social Login Buttons -->
            <div class="space-y-3 mb-6">
              <button 
                @click="loginWithGoogle"
                :disabled="isLoading"
                class="w-full flex items-center justify-center py-3 px-4 border border-gray-300 rounded-lg shadow-sm bg-white text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 font-medium"
              >
                <svg class="w-5 h-5 mr-3" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Continue with Google
              </button>
            </div>
            
            <!-- Divider -->
            <div class="relative mb-6">
              <div class="absolute inset-0 flex items-center">
                <div class="w-full border-t border-gray-300"></div>
              </div>
              <div class="relative flex justify-center text-sm">
                <span class="px-3 bg-white text-gray-500">or</span>
              </div>
            </div>
            
            <!-- Email Only Form -->
            <form @submit.prevent="handleEmailAuth" class="space-y-4">
              <div>
                <label for="email" class="block text-sm font-medium text-gray-700 mb-2">
                  Email address
                </label>
                <input 
                  id="email"
                  v-model="email"
                  type="email" 
                  required
                  class="w-full px-4 py-3 border border-gray-300 rounded-lg shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all duration-200"
                  placeholder="Enter your email address"
                />
              </div>
              
              <!-- Error Message -->
              <div v-if="errorMessage" class="text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg p-3">
                {{ errorMessage }}
              </div>
              
              <!-- Continue Button -->
              <button 
                type="submit"
                :disabled="isLoading || !email"
                class="w-full flex justify-center py-3 px-4 border border-transparent rounded-lg shadow-sm text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
              >
                <svg v-if="isLoading" class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span v-if="isLoading">Opening login...</span>
                <span v-else>Continue</span>
              </button>
            </form>
            
            <!-- Toggle between Login/Signup -->
            <div class="mt-6 text-center">
              <p class="text-sm text-gray-600">
                {{ isSignUp ? 'Already have an account?' : "Don't have an account?" }}
                <button 
                  @click="toggleSignUp" 
                  class="text-indigo-600 hover:text-indigo-500 font-medium ml-1"
                >
                  {{ isSignUp ? 'Sign in' : 'Sign up' }}
                </button>
              </p>
            </div>
          </div>
          
          <!-- Footer Links -->
          <div class="text-center mt-6 space-y-3">
            <div class="flex justify-center items-center space-x-4 text-sm">
              <a class="text-gray-500 hover:text-gray-700 underline" href="/terms-of-service">
                Terms Of Service
              </a>
              <span class="text-gray-300">|</span>
              <a class="text-gray-500 hover:text-gray-700 underline" target="_blank" href="https://sambanova.ai/privacy-policy">
                Privacy Policy
              </a>
            </div>
            
            <div class="space-y-1">
              <div class="text-xs text-gray-400">Vendors</div>
              <a class="text-xs text-gray-500 hover:text-gray-700 underline" target="_blank" href="https://www.daytona.io/company/terms-of-service">
                Daytona Terms of Service
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAuth0 } from '@auth0/auth0-vue'

const { loginWithPopup, isLoading } = useAuth0()

// Form state
const email = ref('')
const isSignUp = ref(false)
const errorMessage = ref('')

// Toggle between login and signup
const toggleSignUp = () => {
  isSignUp.value = !isSignUp.value
  errorMessage.value = ''
}

// Social login methods using popup
const loginWithGoogle = async () => {
  try {
    errorMessage.value = ''
    await loginWithPopup({
      authorizationParams: {
        connection: 'google-oauth2'
      }
    })
  } catch (error) {
    console.error('Google login error:', error)
    errorMessage.value = 'Failed to sign in with Google. Please try again.'
  }
}

// Email authentication - opens Auth0 popup with pre-filled email
const handleEmailAuth = async () => {
  errorMessage.value = ''
  
  try {
    await loginWithPopup({
      authorizationParams: {
        connection: 'Username-Password-Authentication',
        screen_hint: isSignUp.value ? 'signup' : 'login',
        login_hint: email.value
      }
    })
  } catch (error) {
    console.error('Email authentication error:', error)
    errorMessage.value = 'Authentication was cancelled or failed. Please try again.'
  }
}
</script>

<style scoped>
/* Additional custom styles for professional appearance */
.transition-all {
  transition: all 0.2s ease-in-out;
}

/* Focus ring styling */
input:focus {
  outline: none;
}

/* Button hover effects */
button:not(:disabled):hover {
  transform: translateY(-1px);
}

button:not(:disabled):active {
  transform: translateY(0);
}
</style>
