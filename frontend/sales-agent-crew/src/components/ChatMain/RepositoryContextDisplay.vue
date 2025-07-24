<template>
  <div v-if="repositoryContext" class="repository-context-display">
    <!-- Repository Context Banner -->
    <div class="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <div class="flex-shrink-0">
            <svg class="w-6 h-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2-2z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5a2 2 0 012-2h4a2 2 0 012 2v1H8V5z" />
            </svg>
          </div>
          <div>
            <h4 class="text-sm font-medium text-blue-900">
              🔧 SWE Agent Repository Context
            </h4>
            <div class="flex items-center space-x-4 text-xs text-blue-700">
              <span class="flex items-center">
                <svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" />
                </svg>
                {{ repositoryContext.repo_full_name }}
              </span>
              <span class="flex items-center">
                <svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M2 3a1 1 0 011-1h2.153a1 1 0 01.986.836l.74 4.435a1 1 0 01-.54 1.06l-1.548.773a11.037 11.037 0 006.105 6.105l.774-1.548a1 1 0 011.059-.54l4.435.74a1 1 0 01.836.986V17a1 1 0 01-1 1h-2C7.82 18 2 12.18 2 5V3z" />
                </svg>
                {{ repositoryContext.branch || 'default' }}
              </span>
            </div>
          </div>
        </div>
        <div class="flex items-center space-x-2">
          <!-- Quick Actions -->
          <button 
            @click="showSWEPrompts = !showSWEPrompts"
            class="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors"
          >
            {{ showSWEPrompts ? 'Hide' : 'Show' }} SWE Templates
          </button>
          <button 
            @click="clearRepositoryContext"
            class="p-1 text-blue-600 hover:text-blue-800 transition-colors"
            title="Clear repository context"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- SWE Prompt Templates (collapsible) -->
    <div v-if="showSWEPrompts" class="mb-4 p-4 bg-gray-50 border border-gray-200 rounded-lg">
      <h5 class="text-sm font-medium text-gray-900 mb-3">🚀 SWE Agent Quick Templates</h5>
      
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <!-- Feature Implementation -->
        <button 
          @click="useSWETemplate('feature')"
          class="p-3 text-left bg-white border border-gray-200 rounded hover:border-blue-300 hover:bg-blue-50 transition-all group"
        >
          <div class="flex items-center space-x-2 mb-1">
            <span class="text-lg">✨</span>
            <span class="text-sm font-medium text-gray-900 group-hover:text-blue-900">Feature Implementation</span>
          </div>
          <p class="text-xs text-gray-600 group-hover:text-blue-700">
            Add new functionality with proper testing and documentation
          </p>
        </button>

        <!-- Bug Fix -->
        <button 
          @click="useSWETemplate('bug_fix')"
          class="p-3 text-left bg-white border border-gray-200 rounded hover:border-red-300 hover:bg-red-50 transition-all group"
        >
          <div class="flex items-center space-x-2 mb-1">
            <span class="text-lg">🐛</span>
            <span class="text-sm font-medium text-gray-900 group-hover:text-red-900">Bug Fix</span>
          </div>
          <p class="text-xs text-gray-600 group-hover:text-red-700">
            Investigate and fix issues with proper error handling
          </p>
        </button>

        <!-- Code Refactoring -->
        <button 
          @click="useSWETemplate('refactor')"
          class="p-3 text-left bg-white border border-gray-200 rounded hover:border-green-300 hover:bg-green-50 transition-all group"
        >
          <div class="flex items-center space-x-2 mb-1">
            <span class="text-lg">🔄</span>
            <span class="text-sm font-medium text-gray-900 group-hover:text-green-900">Refactoring</span>
          </div>
          <p class="text-xs text-gray-600 group-hover:text-green-700">
            Improve code quality, performance, and maintainability
          </p>
        </button>

        <!-- GitHub Issue -->
        <button 
          @click="useSWETemplate('github_issue')"
          class="p-3 text-left bg-white border border-gray-200 rounded hover:border-purple-300 hover:bg-purple-50 transition-all group"
        >
          <div class="flex items-center space-x-2 mb-1">
            <span class="text-lg">📋</span>
            <span class="text-sm font-medium text-gray-900 group-hover:text-purple-900">GitHub Issue</span>
          </div>
          <p class="text-xs text-gray-600 group-hover:text-purple-700">
            Implement solutions for specific GitHub issues
          </p>
        </button>
      </div>

      <!-- Custom Template -->
      <div class="mt-3 p-3 bg-white border border-gray-200 rounded">
        <div class="flex items-center space-x-2 mb-2">
          <span class="text-lg">💡</span>
          <span class="text-sm font-medium text-gray-900">Custom Request</span>
        </div>
        <div class="flex space-x-2">
          <input 
            v-model="customPrompt"
            type="text" 
            placeholder="Describe what you want the SWE agent to do..."
            class="flex-1 px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            @keydown.enter="useSWETemplate('custom')"
          />
          <button 
            @click="useSWETemplate('custom')"
            :disabled="!customPrompt.trim()"
            class="px-3 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const emit = defineEmits(['send-message', 'clear-context'])

// Reactive data
const repositoryContext = ref(null)
const showSWEPrompts = ref(false)
const customPrompt = ref('')

// SWE prompt templates
const sweTemplates = {
  feature: `Add [FEATURE_NAME] to the repository with the following requirements:
- [Requirement 1]
- [Requirement 2]
- [Requirement 3]

Please analyze the existing codebase structure, identify the best approach, and implement this feature with proper testing and documentation.`,

  bug_fix: `Fix the following issue in the repository:

**Issue Description:** [Describe the bug]
**Steps to Reproduce:** 
1. [Step 1]
2. [Step 2]
3. [Step 3]

**Expected Behavior:** [What should happen]
**Actual Behavior:** [What actually happens]

Please investigate the root cause, implement a fix, and add tests to prevent regression.`,

  refactor: `Refactor [COMPONENT/MODULE] in the repository to improve:
- Code readability and maintainability
- Performance and efficiency
- Adherence to best practices
- [Additional improvements]

Please analyze the current implementation, identify areas for improvement, and implement the refactoring while maintaining existing functionality.`,

  github_issue: `GitHub Issue #[NUMBER]: [TITLE]

**Description:** [Issue description from GitHub]

**Acceptance Criteria:**
- [Criteria 1]
- [Criteria 2]
- [Criteria 3]

**Additional Context:** [Any additional information]

Please analyze the issue, create an implementation plan, and develop a solution that meets all the acceptance criteria.`
}

// Use SWE template
const useSWETemplate = (templateType) => {
  if (!repositoryContext.value) return

  let promptContent = ''
  
  if (templateType === 'custom') {
    promptContent = customPrompt.value.trim()
    customPrompt.value = ''
  } else if (sweTemplates[templateType]) {
    promptContent = sweTemplates[templateType]
  } else {
    return
  }

  // Create the SWE agent message with repository context
  const sweMessage = createSWEMessage(promptContent)
  
  // Emit to parent component to send the message
  emit('send-message', sweMessage)
  
  // Collapse templates after use
  showSWEPrompts.value = false
}

// Create SWE agent message with repository context
const createSWEMessage = (content) => {
  const repoContext = `REPO: ${repositoryContext.value.repo_full_name}
BRANCH: ${repositoryContext.value.branch || 'main'}

${content}`

  return `<subgraph>swe_agent</subgraph>
<subgraph_input>
${repoContext}
</subgraph_input>`
}

// Clear repository context
const clearRepositoryContext = () => {
  repositoryContext.value = null
  localStorage.removeItem('swe_repository_context')
  
  // Emit to parent
  emit('clear-context')
  
  // Dispatch event for other components
  window.dispatchEvent(new CustomEvent('repository-context-cleared'))
}

// Load repository context
const loadRepositoryContext = () => {
  try {
    const saved = localStorage.getItem('swe_repository_context')
    if (saved) {
      repositoryContext.value = JSON.parse(saved)
    }
  } catch (error) {
    console.error('Error loading repository context:', error)
  }
}

// Event listeners for repository context changes
const handleRepositoryContextSet = (event) => {
  repositoryContext.value = event.detail
}

const handleRepositoryContextCleared = () => {
  repositoryContext.value = null
}

// Initialize on mount
onMounted(() => {
  loadRepositoryContext()
  
  // Listen for repository context events
  window.addEventListener('repository-context-set', handleRepositoryContextSet)
  window.addEventListener('repository-context-cleared', handleRepositoryContextCleared)
})

// Cleanup on unmount
onUnmounted(() => {
  window.removeEventListener('repository-context-set', handleRepositoryContextSet)
  window.removeEventListener('repository-context-cleared', handleRepositoryContextCleared)
})

// Expose repository context for parent components
defineExpose({
  repositoryContext,
  createSWEMessage
})
</script>

<style scoped>
.repository-context-display {
  /* Add any custom styles here */
}
</style> 