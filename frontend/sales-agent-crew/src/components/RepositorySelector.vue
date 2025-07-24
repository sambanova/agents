<template>
  <div class="repository-selector">
    <!-- Repository Selection Header -->
    <div class="mb-4">
      <h3 class="text-lg font-medium text-primary-brandTextPrimary mb-2">
        🔧 SWE Agent Repository
      </h3>
      <p class="text-sm text-primary-brandTextSecondary">
        Select a repository for the SWE Agent to work with
      </p>
    </div>

    <!-- GitHub Token Required Message -->
    <div v-if="!hasGitHubToken" class="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
      <div class="flex items-center">
        <svg class="w-5 h-5 text-yellow-600 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.5 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
        <div>
          <p class="text-sm text-yellow-800">
            <strong>GitHub token required:</strong> Please add your GitHub Personal Access Token in Settings to use the SWE Agent.
          </p>
        </div>
      </div>
    </div>

    <!-- Repository Selection (only show if token exists) -->
    <div v-if="hasGitHubToken" class="space-y-4">
      <!-- Selection Type -->
      <div class="flex space-x-4">
        <label class="flex items-center">
          <input 
            type="radio" 
            v-model="selectionType" 
            value="user_repo" 
            class="mr-2 text-primary-brandColor focus:ring-primary-brandColor"
          />
          <span class="text-sm text-primary-brandTextPrimary">Your Repositories</span>
        </label>
        <label class="flex items-center">
          <input 
            type="radio" 
            v-model="selectionType" 
            value="public_repo" 
            class="mr-2 text-primary-brandColor focus:ring-primary-brandColor"
          />
          <span class="text-sm text-primary-brandTextPrimary">Public Repository</span>
        </label>
      </div>

      <!-- User Repositories Dropdown -->
      <div v-if="selectionType === 'user_repo'">
        <label class="block text-sm font-medium text-primary-brandTextPrimary mb-1">
          Select Repository
        </label>
        
        <!-- Loading State -->
        <div v-if="loadingRepos" class="flex items-center text-sm text-primary-brandTextSecondary">
          <svg class="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          Loading your repositories...
        </div>

        <!-- Repository Dropdown -->
        <select 
          v-else
          v-model="selectedRepo" 
          @change="onRepoSelect"
          class="block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
        >
          <option value="">Select a repository...</option>
          <option 
            v-for="repo in userRepos" 
            :key="repo.full_name" 
            :value="repo.full_name"
          >
            {{ repo.full_name }} {{ repo.language ? `(${repo.language})` : '' }}
          </option>
        </select>

        <!-- Error loading repos -->
        <div v-if="repoError" class="mt-2 text-sm text-red-600">
          {{ repoError }}
        </div>
      </div>

      <!-- Public Repository Input -->
      <div v-if="selectionType === 'public_repo'">
        <label class="block text-sm font-medium text-primary-brandTextPrimary mb-1">
          Repository Name
        </label>
        <input 
          type="text" 
          v-model="publicRepoName"
          placeholder="owner/repository-name"
          @blur="validateRepository"
          @input="onPublicRepoInput"
          class="block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
        />
        
        <!-- Validation feedback -->
        <div v-if="validating" class="mt-2 flex items-center text-sm text-primary-brandTextSecondary">
          <svg class="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          Validating repository...
        </div>
        
        <div v-if="repoValidation.error" class="mt-2 text-sm text-red-600">
          {{ repoValidation.error }}
        </div>
        
        <div v-if="repoValidation.valid" class="mt-2 text-sm text-green-600">
          ✓ Repository found: {{ repoValidation.repo_info?.description || 'No description' }}
        </div>
      </div>

      <!-- Branch Selection -->
      <div v-if="selectedRepo || (repoValidation.valid && publicRepoName)">
        <label class="block text-sm font-medium text-primary-brandTextPrimary mb-1">
          Branch (optional)
        </label>
        <input 
          type="text" 
          v-model="selectedBranch" 
          placeholder="main"
          class="block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:outline-none focus:ring-primary-500 focus:border-primary-500"
        />
        <p class="text-xs text-primary-brandTextSecondary mt-1">
          Leave empty to use the default branch
        </p>
      </div>

      <!-- Current Context Display -->
      <div v-if="repositoryContext" class="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg">
        <div class="flex items-center justify-between">
          <div class="flex items-center">
            <svg class="w-5 h-5 text-green-600 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p class="text-sm font-medium text-green-800">
                Active Repository: {{ repositoryContext.repo_full_name }}
              </p>
              <p class="text-xs text-green-600">
                Branch: {{ repositoryContext.branch || 'default' }}
              </p>
            </div>
          </div>
          <button 
            @click="clearRepositoryContext"
            class="text-green-600 hover:text-green-800"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Action Buttons -->
      <div v-if="(selectedRepo || (repoValidation.valid && publicRepoName)) && !repositoryContext" class="flex justify-end space-x-2">
        <button 
          @click="setRepositoryContext"
          :disabled="settingContext"
          class="px-4 py-2 bg-primary-brandColor text-white rounded hover:bg-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50"
        >
          <span v-if="settingContext" class="flex items-center">
            <svg class="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Setting Context...
          </span>
          <span v-else>Set Repository Context</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useAuth0 } from '@auth0/auth0-vue'
import axios from 'axios'

const { getAccessTokenSilently } = useAuth0()

const emit = defineEmits(['repository-selected'])

// Reactive data
const selectionType = ref('user_repo')
const selectedRepo = ref('')
const publicRepoName = ref('')
const selectedBranch = ref('')
const userRepos = ref([])
const loadingRepos = ref(false)
const repoError = ref('')
const validating = ref(false)
const settingContext = ref(false)
const repositoryContext = ref(null)
const repoValidation = ref({ valid: false, error: null, repo_info: null })
const hasGitHubToken = ref(false)

// Check if GitHub token exists
const checkGitHubToken = async () => {
  try {
    const response = await axios.get(`${import.meta.env.VITE_API_URL}/get_api_keys`, {
      headers: {
        'Authorization': `Bearer ${await getAccessTokenSilently()}`
      }
    })
    hasGitHubToken.value = !!(response.data.github_token && response.data.github_token.trim())
  } catch (error) {
    console.error('Error checking GitHub token:', error)
    hasGitHubToken.value = false
  }
}

// Load user repositories
const loadUserRepos = async () => {
  if (!hasGitHubToken.value) return
  
  loadingRepos.value = true
  repoError.value = ''
  
  try {
    const response = await axios.get(`${import.meta.env.VITE_API_URL}/swe/repositories/user`, {
      headers: {
        'Authorization': `Bearer ${await getAccessTokenSilently()}`
      }
    })
    userRepos.value = response.data
  } catch (error) {
    console.error('Error loading repositories:', error)
    repoError.value = error.response?.data?.error || 'Failed to load repositories'
  } finally {
    loadingRepos.value = false
  }
}

// Validate public repository
const validateRepository = async () => {
  if (!publicRepoName.value.trim() || !publicRepoName.value.includes('/')) {
    repoValidation.value = { valid: false, error: null, repo_info: null }
    return
  }

  validating.value = true
  
  try {
    const response = await axios.post(`${import.meta.env.VITE_API_URL}/swe/repositories/validate`, {
      repo_full_name: publicRepoName.value.trim()
    }, {
      headers: {
        'Authorization': `Bearer ${await getAccessTokenSilently()}`,
        'Content-Type': 'application/json'
      }
    })
    repoValidation.value = response.data
  } catch (error) {
    console.error('Error validating repository:', error)
    repoValidation.value = {
      valid: false,
      error: error.response?.data?.error || 'Failed to validate repository',
      repo_info: null
    }
  } finally {
    validating.value = false
  }
}

// Handle repository selection
const onRepoSelect = () => {
  if (selectedRepo.value) {
    // Auto-set branch to empty for user repos (will use default)
    selectedBranch.value = ''
  }
}

// Handle public repo input
const onPublicRepoInput = () => {
  repoValidation.value = { valid: false, error: null, repo_info: null }
}

// Set repository context
const setRepositoryContext = async () => {
  const repoName = selectionType.value === 'user_repo' ? selectedRepo.value : publicRepoName.value
  
  if (!repoName) return

  settingContext.value = true
  
  try {
    // For now, we'll just store the context locally
    // In a full implementation, you might want to send this to the backend
    repositoryContext.value = {
      repo_full_name: repoName,
      branch: selectedBranch.value || 'main',
      selection_type: selectionType.value
    }
    
    // Store in localStorage for persistence
    localStorage.setItem('swe_repository_context', JSON.stringify(repositoryContext.value))
    
    // Emit event for other components
    window.dispatchEvent(new CustomEvent('repository-context-set', { 
      detail: repositoryContext.value 
    }))
    
    // Emit to parent component (SettingsModal)
    emit('repository-selected', repositoryContext.value)
    
  } catch (error) {
    console.error('Error setting repository context:', error)
  } finally {
    settingContext.value = false
  }
}

// Clear repository context
const clearRepositoryContext = () => {
  repositoryContext.value = null
  localStorage.removeItem('swe_repository_context')
  
  // Emit event for other components
  window.dispatchEvent(new CustomEvent('repository-context-cleared'))
}

// Load existing context on mount
const loadExistingContext = () => {
  try {
    const saved = localStorage.getItem('swe_repository_context')
    if (saved) {
      repositoryContext.value = JSON.parse(saved)
    }
  } catch (error) {
    console.error('Error loading repository context:', error)
  }
}

// Watch for selection type changes
watch(selectionType, () => {
  selectedRepo.value = ''
  publicRepoName.value = ''
  selectedBranch.value = ''
  repoValidation.value = { valid: false, error: null, repo_info: null }
})

// Watch for GitHub token changes
watch(hasGitHubToken, (newValue) => {
  if (newValue) {
    loadUserRepos()
  } else {
    userRepos.value = []
    repositoryContext.value = null
  }
})

// Initialize on mount
onMounted(async () => {
  await checkGitHubToken()
  loadExistingContext()
  
  if (hasGitHubToken.value) {
    await loadUserRepos()
  }
})

// Expose methods for parent components
defineExpose({
  repositoryContext: computed(() => repositoryContext.value),
  clearRepositoryContext,
  checkGitHubToken
})
</script>

<style scoped>
/* Add any custom styles here */
</style> 