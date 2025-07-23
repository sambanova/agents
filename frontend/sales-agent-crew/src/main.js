// main.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import { createAuth0 } from '@auth0/auth0-vue'

// Import your router
import router from './router/index.js'
// import './test-auth0-config.js' // Temporary - for debugging

const AUTH0_DOMAIN = import.meta.env.VITE_AUTH0_DOMAIN
const AUTH0_CLIENT_ID = import.meta.env.VITE_AUTH0_CLIENT_ID
const AUTH0_SCOPES = import.meta.env.VITE_AUTH0_SCOPES || 'openid profile email'

if (!AUTH0_DOMAIN || !AUTH0_CLIENT_ID) {
  throw new Error('Missing Auth0 configuration')
}

// Create and mount the app
const app = createApp(App)

// Create a Pinia instance
const pinia = createPinia()

app.use(createAuth0({
  domain: AUTH0_DOMAIN,
  clientId: AUTH0_CLIENT_ID,
  authorizationParams: {
    redirect_uri: window.location.hostname === 'localhost' ? window.location.origin : window.location.origin + '/callback',
    scope: AUTH0_SCOPES
  },
  cacheLocation: 'localstorage',
  useRefreshTokens: true,
  useRefreshTokensFallback: true
}))
app.use(pinia) // Register Pinia
app.use(router)
app.mount('#app')
