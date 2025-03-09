// main.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'

// Import your router
import router from './router/index.js'

// Create and mount the app
const app = createApp(App)

// Create a Pinia instance
const pinia = createPinia()

app.use(pinia) // Register Pinia
app.use(router)
app.mount('#app')