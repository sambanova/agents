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

// Global code copy functionality
function addCopyButtonsToCodeBlocks() {
  const codeBlocks = document.querySelectorAll('.prose pre:not([data-copy-added])')
  
  codeBlocks.forEach(codeBlock => {
    // Mark this code block as processed
    codeBlock.setAttribute('data-copy-added', 'true')
    
    // Create copy button
    const copyBtn = document.createElement('button')
    copyBtn.className = 'code-copy-btn'
    copyBtn.innerHTML = `
      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
      </svg>
      <span>Copy</span>
    `
    
    // Add click handler
    copyBtn.addEventListener('click', async () => {
      const code = codeBlock.querySelector('code')
      if (code) {
        try {
          await navigator.clipboard.writeText(code.textContent)
          copyBtn.innerHTML = `
            <svg class="w-3 h-3 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
            </svg>
            <span>Copied!</span>
          `
          copyBtn.classList.add('bg-green-600')
          copyBtn.classList.remove('bg-gray-600')
          
          setTimeout(() => {
            copyBtn.innerHTML = `
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
              </svg>
              <span>Copy</span>
            `
            copyBtn.classList.remove('bg-green-600')
            copyBtn.classList.add('bg-gray-600')
          }, 2000)
        } catch (err) {
          console.error('Failed to copy code:', err)
        }
      }
    })
    
    codeBlock.appendChild(copyBtn)
  })
}

// Run on initial load
document.addEventListener('DOMContentLoaded', addCopyButtonsToCodeBlocks)

// Also run when new content is added (for dynamic content)
const observer = new MutationObserver(() => {
  addCopyButtonsToCodeBlocks()
})

observer.observe(document.body, {
  childList: true,
  subtree: true
})
