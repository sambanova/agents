// main.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import { clerkPlugin } from '@clerk/vue'

// Import your router
import router from './router/index.js'

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY


if (!PUBLISHABLE_KEY) {
  throw new Error('Missing Publishable Key')
}

// Create and mount the app
const app = createApp(App)

// Create a Pinia instance
const pinia = createPinia()

app.use(clerkPlugin, { 
  publishableKey: PUBLISHABLE_KEY,  
  signInUrl: '/login',
  signUpUrl: '/login'
})
app.use(pinia) // Register Pinia
app.use(router)
app.mount('#app')
