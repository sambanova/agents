<template>
  <div v-if="isOpen" class="fixed inset-y-0 right-0 flex flex-col bg-white border-l border-gray-200 shadow-2xl z-50 overflow-hidden transition-all duration-300" 
       :class="{ 'w-1/2': !isCollapsed, 'w-16': isCollapsed }">
    
    <!-- Header -->
    <div class="flex items-center justify-between p-4 border-b bg-gradient-to-r from-blue-50 to-purple-50">
      <div v-if="!isCollapsed" class="flex items-center space-x-3">
        <div class="w-8 h-8 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
          <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
          </svg>
        </div>
        <div>
          <h3 class="text-lg font-semibold text-gray-900">Canvas</h3>
          <p class="text-sm text-gray-600">Data Analysis & Artefact Generation</p>
        </div>
      </div>
      
      <!-- Collapsed header -->
      <div v-else class="flex flex-col items-center space-y-2 w-full">
        <div class="w-8 h-8 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
          <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
          </svg>
        </div>
      </div>
      
      <div class="flex items-center space-x-2">
        <!-- Collapse/Expand Button -->
        <button 
          @click="toggleCollapse"
          class="p-2 hover:bg-gray-100 rounded-full transition-colors"
          :aria-label="isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
        >
          <svg v-if="isCollapsed" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
          </svg>
          <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path>
          </svg>
        </button>
        
        <!-- Close Button -->
        <button 
          @click="handleClose"
          class="p-2 hover:bg-gray-100 rounded-full transition-colors"
          aria-label="Close sidebar"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
          </svg>
        </button>
      </div>
    </div>

    <!-- Content Area -->
    <div v-if="!isCollapsed" class="flex-1 overflow-y-auto h-full">
      <!-- Status Section -->
      <div class="p-4 border-b bg-gray-50">
        <div class="flex items-center space-x-3">
          <div :class="statusDotClass" class="w-3 h-3 rounded-full flex-shrink-0"></div>
          <div class="flex-1">
            <div class="flex items-center space-x-2">
              <span class="text-sm font-medium text-gray-900">{{ currentStatus }}</span>
              <div v-if="isProcessing" class="animate-spin">
                <svg class="w-4 h-4 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                </svg>
              </div>
            </div>
            <div v-if="statusDetails" class="text-xs text-gray-600 mt-1">{{ statusDetails }}</div>
          </div>
        </div>

      </div>

      <!-- Code Section -->
      <div v-if="codeContent" class="border-b">
        <div class="p-4">
          <div class="flex items-center justify-between mb-3">
            <button
              @click="toggleCodeSection"
              class="flex items-center space-x-2 text-left hover:text-blue-600 transition-colors"
            >
              <svg :class="{ 'rotate-90': codeExpanded }" class="w-4 h-4 transform transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
              </svg>
              <h4 class="font-medium text-gray-900">Python Code</h4>
              <span class="text-xs text-gray-500">({{ codeLines }} lines)</span>
            </button>
            
            <button
              v-if="codeExpanded"
              @click="copyCode"
              class="text-xs text-gray-500 hover:text-gray-700 flex items-center space-x-1 px-2 py-1 rounded hover:bg-gray-100"
            >
              <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
              </svg>
              <span>Copy</span>
            </button>
          </div>
          
          <!-- Expandable Code Display -->
          <div v-if="codeExpanded" class="bg-gray-900 rounded-lg overflow-hidden border">
            <div class="bg-gray-800 px-4 py-2 text-xs text-gray-300 border-b border-gray-700 flex justify-between items-center">
              <span>Python Analysis Script</span>
              <span>{{ codeLines }} lines</span>
            </div>
            <div 
              ref="codeContainer"
              class="p-4 overflow-auto max-h-96"
              style="scrollbar-width: thin; scrollbar-color: #6b7280 #374151;"
            >
              <pre class="text-sm font-mono leading-relaxed"><code v-text="codeContent" style="color: #e5e7eb; white-space: pre-wrap; word-wrap: break-word;"></code></pre>
            </div>
          </div>
          
          <!-- Collapsed Code Preview -->
          <div v-else class="bg-gray-100 rounded-lg p-3 text-sm text-gray-600">
            <div class="font-mono">{{ codePreview }}</div>
          </div>
        </div>
      </div>

      <!-- Artifacts Section -->
      <div v-if="artifacts.length > 0" class="border-b">
        <div class="p-4">
          <div class="flex items-center justify-between mb-3">
            <button
              @click="toggleArtifactsSection"
              class="flex items-center space-x-2 text-left hover:text-blue-600 transition-colors"
            >
              <svg :class="{ 'rotate-90': artifactsExpanded }" class="w-4 h-4 transform transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
              </svg>
              <h4 class="font-medium text-gray-900">Generated Artifacts</h4>
              <span class="text-xs text-gray-500">({{ artifacts.length }} file{{ artifacts.length > 1 ? 's' : '' }})</span>
            </button>
          </div>
          
          <div v-if="artifactsExpanded" class="space-y-4">
            <div 
              v-for="(artifact, index) in artifacts" 
              :key="artifact.id"
              class="bg-gray-50 rounded-lg overflow-hidden border hover:shadow-md transition-shadow cursor-pointer"
              @click="expandArtifact(artifact)"
            >
              <div class="p-3 border-b bg-white">
                <div class="flex items-center justify-between">
                  <div class="flex items-center space-x-2">
                    <!-- File Type Icon -->
                    <div class="w-6 h-6 flex items-center justify-center">
                      <svg v-if="artifact.type === 'image'" class="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                      </svg>
                      <svg v-else-if="artifact.type === 'pdf'" class="w-4 h-4 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                      </svg>
                      <svg v-else-if="artifact.type === 'markdown'" class="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
                      </svg>
                      <svg v-else-if="artifact.type === 'html'" class="w-4 h-4 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
                      </svg>
                      <svg v-else-if="artifact.type === 'powerpoint'" class="w-4 h-4 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 8h8M8 12h8M8 16h4"></path>
                      </svg>
                      <svg v-else-if="artifact.type === 'csv'" class="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 9h6M9 12h6M9 15h6"></path>
                      </svg>
                      <svg v-else class="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                      </svg>
                    </div>
                    <h5 class="font-medium text-sm text-gray-900">{{ artifact.title }}</h5>
                    <span class="text-xs text-gray-500 uppercase">{{ artifact.type }}</span>
                  </div>
                  <div class="flex items-center space-x-2">
                    <button
                      @click.stop="downloadArtifact(artifact)"
                      class="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100"
                      title="Download file"
                    >
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                      </svg>
                    </button>
                    <button
                      @click.stop="expandArtifact(artifact)"
                      class="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100"
                      title="Expand file"
                    >
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"></path>
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
              
              <div class="p-4">
                <div v-if="artifact.loading" class="flex items-center justify-center h-40">
                  <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                </div>
                
                <!-- Image Preview -->
                <img 
                  v-else-if="artifact.type === 'image' && artifact.url"
                  :src="artifact.url" 
                  :alt="artifact.title"
                  class="w-full h-auto rounded hover:opacity-90 transition-opacity"
                  @load="artifact.loading = false"
                  @error="handleArtifactError(artifact)"
                />
                
                <!-- PDF Inline Viewer -->
                <div v-else-if="artifact.type === 'pdf'" class="w-full inline-viewer">
                  <div class="viewer-header rounded-lg p-2 mb-2">
                    <div class="flex items-center justify-between">
                      <div class="flex items-center space-x-2">
                        <svg class="w-4 h-4 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                        </svg>
                        <span class="text-sm font-medium">PDF Viewer</span>
                      </div>
                      <button 
                        @click.stop="downloadArtifact(artifact)"
                        class="text-xs bg-blue-500 text-white px-2 py-1 rounded hover:bg-blue-600 transition-colors"
                      >
                        Download
                      </button>
                    </div>
                  </div>
                  <iframe
                    :src="artifact.url"
                    class="w-full h-96 rounded border-2 border-gray-200"
                    title="PDF Viewer"
                    @load="artifact.loading = false"
                    @error="handleArtifactError(artifact)"
                  ></iframe>
                </div>
                
                <!-- PowerPoint Download Interface -->
                <div v-else-if="artifact.type === 'powerpoint'" class="bg-gray-100 rounded-lg p-4 text-center hover:bg-gray-200 transition-colors cursor-pointer"
                     @click="downloadArtifact(artifact)">
                  <svg class="w-12 h-12 mx-auto mb-3 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 8h8M8 12h8M8 16h4"></path>
                  </svg>
                  <h4 class="text-sm font-medium text-gray-900 mb-1">PowerPoint Presentation</h4>
                  <p class="text-xs text-gray-600 mb-3">{{ artifact.title }}</p>
                  <button 
                    @click.stop="downloadArtifact(artifact)"
                    class="inline-flex items-center space-x-2 bg-purple-500 text-white px-4 py-2 rounded-lg hover:bg-purple-600 transition-colors"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                    <span class="text-sm font-medium">Download Presentation</span>
                  </button>
                </div>
                
                <!-- HTML Inline Viewer -->
                <div v-else-if="artifact.type === 'html'" class="w-full inline-viewer">
                  <div class="viewer-header rounded-lg p-2 mb-2">
                    <div class="flex items-center justify-between">
                      <div class="flex items-center space-x-2">
                        <svg class="w-4 h-4 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
                        </svg>
                        <span class="text-sm font-medium">HTML Viewer</span>
                      </div>
                      <div class="flex space-x-1">
                        <button 
                          @click.stop="openInNewTab(artifact.url)"
                          class="text-xs bg-orange-500 text-white px-2 py-1 rounded hover:bg-orange-600 transition-colors"
                        >
                          Open
                        </button>
                        <button 
                          @click.stop="downloadArtifact(artifact)"
                          class="text-xs bg-gray-500 text-white px-2 py-1 rounded hover:bg-gray-600 transition-colors"
                        >
                          Download
                        </button>
                      </div>
                    </div>
                  </div>
                  <iframe
                    :src="artifact.url"
                    class="w-full h-96 rounded border-2 border-gray-200"
                    title="HTML Viewer"
                    sandbox="allow-scripts allow-same-origin"
                    @load="artifact.loading = false"
                    @error="handleArtifactError(artifact)"
                  ></iframe>
                </div>
                
                <!-- Markdown Inline Viewer -->
                <div v-else-if="artifact.type === 'markdown'" class="w-full inline-viewer">
                  <div class="viewer-header rounded-lg p-2 mb-2">
                    <div class="flex items-center justify-between">
                      <div class="flex items-center space-x-2">
                        <svg class="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
                        </svg>
                        <span class="text-sm font-medium">Markdown Viewer</span>
                      </div>
                      <button 
                        @click.stop="downloadArtifact(artifact)"
                        class="text-xs bg-gray-500 text-white px-2 py-1 rounded hover:bg-gray-600 transition-colors"
                      >
                        Download
                      </button>
                    </div>
                  </div>
                  <div class="bg-white rounded border-2 border-gray-200 p-4 h-96 overflow-y-auto">
                    <div v-if="artifact.content || artifact.preview" 
                         class="prose prose-sm max-w-none"
                         v-html="renderMarkdown(artifact.content || artifact.preview)"
                    ></div>
                    <div v-else class="flex items-center justify-center h-full text-gray-500">
                      <div class="text-center">
                        <svg class="w-8 h-8 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                        </svg>
                        <p class="text-sm">Loading markdown content...</p>
                      </div>
                    </div>
                  </div>
                </div>
                
                <!-- CSV Inline Viewer -->
                <div v-else-if="artifact.type === 'csv'" class="w-full inline-viewer">
                  <div class="viewer-header rounded-lg p-2 mb-2">
                    <div class="flex items-center justify-between">
                      <div class="flex items-center space-x-2">
                        <svg class="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                        </svg>
                        <span class="text-sm font-medium">CSV Data Viewer</span>
                      </div>
                      <button 
                        @click.stop="downloadArtifact(artifact)"
                        class="text-xs bg-green-500 text-white px-2 py-1 rounded hover:bg-green-600 transition-colors"
                      >
                        Download
                      </button>
                    </div>
                  </div>
                  <div class="bg-white rounded border-2 border-gray-200 h-96 overflow-auto">
                    <div v-if="artifact.csvData || artifact.content || artifact.preview" class="p-2">
                      <table class="csv-table min-w-full text-left border-collapse text-xs">
                        <tbody>
                          <tr v-for="(row, idx) in parseCsvData(artifact)" :key="idx" 
                              :class="idx === 0 ? 'bg-gray-50 font-medium' : 'hover:bg-gray-50'"
                              class="border-b border-gray-200">
                            <td v-for="(cell, cellIdx) in row" :key="cellIdx" 
                                class="px-3 py-2 border-r border-gray-200 last:border-r-0">
                              {{ cell }}
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <div v-else class="flex items-center justify-center h-full text-gray-500">
                      <div class="text-center">
                        <div v-if="artifact.loading" class="flex flex-col items-center">
                          <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-green-500 mb-2"></div>
                          <p class="text-sm">Loading CSV data...</p>
                        </div>
                        <div v-else>
                          <svg class="w-8 h-8 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                          </svg>
                          <p class="text-sm mb-2">Click here to load CSV data</p>
                          <button 
                            @click.stop="loadCsvContent(artifact)"
                            class="text-xs bg-green-500 text-white px-3 py-2 rounded hover:bg-green-600 transition-colors"
                          >
                            Load Data
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                
                <!-- Fallback -->
                <div v-else class="flex items-center justify-center h-40 text-gray-500">
                  <div class="text-center">
                    <svg class="w-8 h-8 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                    </svg>
                    <p class="text-sm">File not available</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <!-- Collapsed Artifacts Preview -->
          <div v-else class="grid grid-cols-2 gap-2">
            <div 
              v-for="(artifact, index) in artifacts.slice(0, 4)" 
              :key="artifact.id"
              class="bg-gray-100 rounded p-2 text-center cursor-pointer hover:bg-gray-200 transition-colors"
              @click="expandArtifact(artifact)"
            >
              <div class="flex items-center justify-center mb-1">
                <svg v-if="artifact.type === 'image'" class="w-3 h-3 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                </svg>
                <svg v-else-if="artifact.type === 'pdf'" class="w-3 h-3 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                </svg>
                <svg v-else-if="artifact.type === 'markdown'" class="w-3 h-3 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
                </svg>
                <svg v-else-if="artifact.type === 'html'" class="w-3 h-3 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
                </svg>
                                 <svg v-else-if="artifact.type === 'powerpoint'" class="w-3 h-3 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                   <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                   <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 8h8M8 12h8M8 16h4"></path>
                 </svg>
                <svg v-else-if="artifact.type === 'csv'" class="w-3 h-3 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                </svg>
                <svg v-else class="w-3 h-3 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                </svg>
              </div>
              <div class="text-xs text-gray-600 truncate">{{ artifact.title }}</div>
            </div>
            <div v-if="artifacts.length > 4" class="bg-gray-100 rounded p-2 text-center text-xs text-gray-500">
              +{{ artifacts.length - 4 }} more
            </div>
          </div>
        </div>
      </div>

      <!-- Execution Log -->
      <div v-if="executionLog.length > 0" class="p-4 border-t bg-gray-50">
        <div class="flex items-center justify-between mb-3">
          <button
            @click="toggleLogSection"
            class="flex items-center space-x-2 text-left hover:text-blue-600 transition-colors"
          >
            <svg :class="{ 'rotate-90': logExpanded }" class="w-4 h-4 transform transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
            </svg>
            <h4 class="font-medium text-gray-900 text-sm">Execution Log</h4>
            <span class="text-xs text-gray-500">({{ executionLog.length }} entries)</span>
          </button>
        </div>
        
        <div v-if="logExpanded" class="space-y-2 max-h-40 overflow-y-auto">
          <div 
            v-for="log in executionLog" 
            :key="log.id"
            class="text-xs text-gray-600 flex items-start space-x-2"
          >
            <span class="text-gray-400">{{ formatLogTime(log.timestamp) }}</span>
            <span :class="getLogClass(log.type)">{{ log.message }}</span>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Collapsed State Indicators -->
    <div v-else class="flex flex-col items-center justify-center h-full space-y-4 p-2">
      <!-- Status Indicator -->
      <div class="flex flex-col items-center space-y-2">
        <div :class="statusDotClass" class="w-4 h-4 rounded-full"></div>
        <div v-if="isProcessing" class="animate-spin">
          <svg class="w-5 h-5 text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
          </svg>
        </div>
      </div>
      
      <!-- Section Indicators -->
      <div class="flex flex-col space-y-3">
        <!-- Code Indicator -->
        <div v-if="codeContent" class="flex items-center justify-center w-8 h-8 bg-green-100 rounded-lg" title="Code Available">
          <svg class="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
          </svg>
        </div>
        
        <!-- Artifacts Indicator -->
        <div v-if="artifacts.length > 0" class="flex flex-col items-center">
          <div class="flex items-center justify-center w-8 h-8 bg-blue-100 rounded-lg" title="Files Available">
            <svg class="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
            </svg>
          </div>
          <span class="text-xs text-gray-500 mt-1">{{ artifacts.length }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  },
  streamingEvents: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['close', 'expand-chart', 'expand-artifact', 'sidebar-state-changed'])

// Reactive state
const isCollapsed = ref(false)
const currentStatus = ref('Initializing...')
const statusDetails = ref('')
const isProcessing = ref(false)

const codeContent = ref('')
const executionLog = ref([])
const artifacts = ref([])

// Section expansion states
const codeExpanded = ref(true)
const artifactsExpanded = ref(true)
const logExpanded = ref(false)

// Anti-flickering / streaming state
const lastCodeUpdate = ref('')
// Simple throttle timestamp for code streaming
const lastCodeUpdateTs = ref(0)
// Track length of processed events to detect new conversations and prevent artifacts flicker
const lastEventsLength = ref(0)

// Template refs
const codeContainer = ref(null)

// Computed properties
const statusDotClass = computed(() => {
  if (isProcessing.value) return 'bg-blue-500 animate-pulse'
  if (artifacts.value.length > 0) return 'bg-green-500'
  return 'bg-yellow-500'
})

const codeLines = computed(() => {
  return codeContent.value ? codeContent.value.split('\n').length : 0
})

const codePreview = computed(() => {
  if (!codeContent.value) return ''
  const lines = codeContent.value.split('\n')
  return lines.slice(0, 2).join(' | ') + (lines.length > 2 ? '...' : '')
})

// Watch for streaming events changes - ENHANCED FOR LOADED CONVERSATIONS
watch(() => props.streamingEvents, (newEvents) => {
  if (newEvents && newEvents.length > 0) {
    processStreamingEvents(newEvents)
  }
}, { deep: true, immediate: true })

// Watch for code content changes and auto-scroll
watch(codeContent, (newCode, oldCode) => {
  // Only auto-scroll if the content has meaningfully changed and is expanded
  if (newCode && newCode !== oldCode && codeExpanded.value) {
    nextTick(() => {
      if (codeContainer.value) {
        codeContainer.value.scrollTop = codeContainer.value.scrollHeight
      }
    })
  }
})

// Watch for artifacts changes and auto-load CSV data
watch(artifacts, (newArtifacts) => {
  if (newArtifacts && newArtifacts.length > 0) {
    newArtifacts.forEach(artifact => {
      if (artifact.type === 'csv' && !artifact.csvData && !artifact.content && !artifact.loading) {
        // Auto-load CSV data when artifact is added
        nextTick(() => {
          loadCsvContent(artifact)
        })
      }
    })
  }
}, { deep: true })

// Methods
function safeUpdateCodeContent(newCode, context = '') {
  // Prevent unnecessary updates if code hasn't changed
  if (newCode === lastCodeUpdate.value) {
    return false; // No update needed
  }

  if (context === 'streaming') {
    const now = Date.now()
    // Throttle to ~60 ms per update (about 16 FPS)
    if (now - lastCodeUpdateTs.value < 60) {
      return false
    }
    lastCodeUpdateTs.value = now
  }

  // Apply update immediately
  codeContent.value = newCode
  lastCodeUpdate.value = newCode
  return true
}

function processStreamingEvents(events) {
  try {
    if (!events || !Array.isArray(events)) return

    // Detect a brand-new conversation (events length has shrunk)
    if (events.length < lastEventsLength.value) {
      artifacts.value = []
      executionLog.value = []
      cleanupCodeUpdates()
      lastCodeUpdate.value = ''
      lastEventsLength.value = 0 // full reset
    }
    
    // Reset state when processing new events
    isProcessing.value = true
    
    // Reset anti-flickering state for fresh conversation
    cleanupCodeUpdates()
    lastCodeUpdate.value = ''
    
    let codeDetected = false
    let toolCallDetected = false
    let artifactCount = 0

    events.forEach((event, index) => {
      // Safety check for null/undefined events
      if (!event || typeof event !== 'object') {
        console.log(`Skipping invalid event at index ${index}:`, event);
        return;
      }
      
      const timestamp = event.data?.timestamp || event.timestamp || new Date().toISOString()
      
      switch (event.event) {
        case 'llm_stream_chunk':
          // Extract Python code from tool input - this is the key fix
          if (event.data?.content) {
            const content = event.data.content
            
            // Look for tool calls with code input - this is where the actual code is
            if (content.includes('<tool>DaytonaCodeSandbox</tool>')) {
              // Extract the code from tool_input
              const toolInputMatch = content.match(/<tool_input>([\s\S]*?)(?:<\/tool_input>|$)/);
              if (toolInputMatch && toolInputMatch[1]) {
                const extractedCode = toolInputMatch[1].trim()
                // Only update if this is actual Python code (contains import, def, plt, etc.)
                if (extractedCode.includes('import') || extractedCode.includes('def ') || 
                    extractedCode.includes('plt.') || extractedCode.includes('matplotlib') ||
                    extractedCode.includes('numpy') || extractedCode.includes('pandas')) {
                  if (safeUpdateCodeContent(extractedCode, 'streaming')) {
                    codeDetected = true
                    updateStatus('📝 Code generated', 'Python analysis script ready')
                    addToLog('Code generation detected', 'info', timestamp)
                  }
                }
              }
              
              toolCallDetected = true
              updateStatus('⚡ Executing code', 'Running in Daytona sandbox')
              addToLog('Tool call to DaytonaCodeSandbox detected', 'info', timestamp)
              // Remove automatic progress - let it complete naturally
            }
            
            // Also check for code blocks in regular content
            const codeMatch = content.match(/```python\n([\s\S]*?)```/)
            if (codeMatch && codeMatch[1] && !codeDetected) {
              if (safeUpdateCodeContent(codeMatch[1].trim(), 'streaming')) {
                codeDetected = true
              }
            }
          }
          break
          
        case 'agent_completion':
          // Handle both streaming and loaded conversation agent_completion events
          const eventData = event.data || event;
          
          if (eventData?.name === 'DaytonaCodeSandbox' || eventData?.agent_type === 'tool_response' || eventData?.agent_type === 'react_tool') {
            console.log('Processing Daytona agent_completion event:', eventData);
            
            // Handle tool call (react_tool) - extract code from tool input
            if (eventData?.agent_type === 'react_tool' && eventData.content && String(eventData.content).includes('DaytonaCodeSandbox')) {
              const contentStr = String(eventData.content);
              const toolInputMatch = contentStr.match(/<tool_input>([\s\S]*?)(?:<\/tool_input>|$)/);
              if (toolInputMatch && toolInputMatch[1]) {
                const extractedCode = toolInputMatch[1].trim()
                if (extractedCode.includes('import') || extractedCode.includes('def ') || 
                    extractedCode.includes('plt.') || extractedCode.includes('matplotlib') ||
                    extractedCode.includes('numpy') || extractedCode.includes('pandas')) {
                  if (safeUpdateCodeContent(extractedCode, 'loaded')) {
                    codeDetected = true
                    updateStatus('📝 Code loaded from history', 'Python analysis script')
                    addToLog('Code loaded from conversation history', 'info', timestamp)
                    console.log('Extracted code from tool call:', extractedCode.substring(0, 100) + '...');
                  }
                }
              }
            }
            
            // Extract charts from Daytona response (tool_response)
            const content = String(eventData.content || '')
            
            // Only process if content is a valid string
            if (!content || content.length === 0) {
              console.log('No content to process for charts');
              break;
            }
            
            // Look for file attachments, data URLs, and Redis file references
            const attachmentMatches = content.match(/!\[([^\]]*)\]\(attachment:([^)]+)\)/g)
            const dataUrlMatches = content.match(/!\[([^\]]*)\]\(data:image\/[^)]+\)/g)
            const redisFileMatches = content.match(/!\[([^\]]*)\]\(redis-(?:chart|file):([^:]+):([^)]+)\)/g)
            
            // Look for PDF, Markdown, and HTML file patterns  
            const pdfMatches = content.match(/!\[([^\]]*)\]\((?:attachment|redis-file):([^:)]+)(?::([^)]+))?\).*?\.pdf/gi)
            const markdownMatches = content.match(/!\[([^\]]*)\]\((?:attachment|redis-file):([^:)]+)(?::([^)]+))?\).*?\.md/gi)
            const htmlMatches = content.match(/!\[([^\]]*)\]\((?:attachment|redis-file):([^:)]+)(?::([^)]+))?\).*?\.html/gi)
            
                        // Handle attachment-based files (legacy)
              if (attachmentMatches) {
                attachmentMatches.forEach((match, idx) => {
                  const titleMatch = match.match(/!\[([^\]]*)\]/)
                  const idMatch = match.match(/attachment:([^)]+)/)
                  
                  if (idMatch) {
                    const fileId = idMatch[1]
                    const title = titleMatch && titleMatch[1] ? titleMatch[1] : `File ${idx + 1}`
                    
                    // Check if file with this ID already exists to prevent duplicates
                    const existingFile = artifacts.value.find(artifact => artifact.id === fileId)
                    if (existingFile) {
                      console.log(`Skipping duplicate attachment file with ID: ${fileId}`)
                      return;
                    }
                    
                    // Determine file type and create appropriate artifact
                    const fileType = getFileType(title, fileId)
                    // Use authenticated endpoint, not public
                    const fileUrl = `/api/files/${fileId}`
                    
                    const newArtifact = {
                      id: fileId,
                      title: title,
                      type: fileType,
                      url: fileUrl,
                      loading: true, // Set loading to true initially
                      downloadUrl: fileUrl,
                      preview: null
                    }
                    artifacts.value.push(newArtifact)
                    fetchArtifactContent(newArtifact);

                    artifactCount++
                    console.log(`Added attachment file: ${title} (${fileType}) with ID: ${fileId}`)
                  }
                })
              }
            
                        // Handle data URL-based images (legacy)
              if (dataUrlMatches) {
                dataUrlMatches.forEach((match, idx) => {
                  const titleMatch = match.match(/!\[([^\]]*)\]/)
                  const urlMatch = match.match(/\]\(([^)]+)\)/)
                  
                  if (urlMatch) {
                    const dataUrl = urlMatch[1]
                    const title = titleMatch && titleMatch[1] ? titleMatch[1] : `Image ${artifactCount + idx + 1}`
                    
                    // Check if file with this exact data URL already exists to prevent duplicates
                    const existingFile = artifacts.value.find(artifact => artifact.url === dataUrl)
                    if (existingFile) {
                      console.log(`Skipping duplicate data URL image: ${title}`)
                      return;
                    }
                    
                    const fileId = `data_image_${Date.now()}_${idx}`
                    
                    artifacts.value.push({
                      id: fileId,
                      title: title,
                      type: 'image',
                      url: dataUrl, // Use data URL directly
                      loading: false,
                      downloadUrl: dataUrl, // Data URLs can be used for download too
                      preview: null
                    })
                    artifactCount++
                    console.log(`Added data URL image: ${title}`)
                  }
                })
              }
            
                        // Handle Redis file references (new preferred method)
              if (redisFileMatches) {
                redisFileMatches.forEach((match, idx) => {
                  const titleMatch = match.match(/!\[([^\]]*)\]/)
                  const redisMatch = match.match(/redis-(?:chart|file):([^:]+):([^)]+)/)
                  
                  if (redisMatch) {
                    const fileId = redisMatch[1]
                    const userId = redisMatch[2]
                    const title = titleMatch && titleMatch[1] ? titleMatch[1] : `File ${artifactCount + idx + 1}`
                    
                    // Check if file with this ID already exists to prevent duplicates
                    const existingFile = artifacts.value.find(artifact => artifact.id === fileId)
                    if (existingFile) {
                      console.log(`Skipping duplicate Redis file with ID: ${fileId}`)
                      return;
                    }
                    
                    // Determine file type and create appropriate artifact
                    const fileType = getFileType(title, fileId)
                    const fileUrl = `/api/files/${fileId}`
                    
                    const newArtifact = {
                      id: fileId,
                      title: title,
                      type: fileType,
                      url: fileUrl, // Use authenticated endpoint
                      loading: true, // Set loading to true initially
                      downloadUrl: fileUrl,
                      preview: null
                    }
                    artifacts.value.push(newArtifact)
                    fetchArtifactContent(newArtifact);
                    
                    artifactCount++
                    console.log(`Added Redis file: ${title} (${fileType}) with ID: ${fileId} for user: ${userId}`)
                  }
                })
              }
            
            updateStatus('✅ Analysis complete', `Generated ${artifactCount} artifacts`)
            
            addToLog(`Analysis completed with ${artifactCount} files`, 'success', timestamp)
            isProcessing.value = false
          }
          break
      }
    })
    
    // Set initial status if no specific events detected
    if (!codeDetected && !toolCallDetected) {
      updateStatus('⏳ Ready for analysis', 'Waiting for code execution')
    } else if (codeDetected || artifactCount > 0) {
      // Update status to show loaded state
      updateStatus('✅ Historical analysis loaded', `Code and ${artifactCount} files from conversation`)
    }

    // Update processed length so we can detect resets next time
    lastEventsLength.value = events.length
  } catch (error) {
    console.error('Error processing streaming events in DaytonaSidebar:', error);
    updateStatus('❌ Error', 'Failed to process conversation history.')
    addToLog('Error processing streaming events: ' + error.message, 'error', new Date().toISOString())
  }
}

function createChartUrl(chartId, title) {
  // Create more realistic charts based on actual chart content
  if (title.toLowerCase().includes('tps') || title.toLowerCase().includes('throughput')) {
    return 'data:image/svg+xml;base64,' + btoa(`
      <svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
        <rect width="100%" height="100%" fill="#f8fafc"/>
        <text x="300" y="30" text-anchor="middle" font-size="18" font-weight="bold" fill="#1f2937">Tokens Per Second vs Batch Size</text>
        <text x="300" y="50" text-anchor="middle" font-size="14" fill="#6b7280">Performance Analysis Across Models</text>
        <g stroke="#e5e7eb" stroke-width="1" fill="none">
          <line x1="80" y1="80" x2="80" y2="320"/>
          <line x1="80" y1="320" x2="520" y2="320"/>
        </g>
        <g fill="#3b82f6" stroke="#3b82f6" stroke-width="2">
          <circle cx="120" cy="280" r="4"/>
          <circle cx="180" cy="240" r="4"/>
          <circle cx="240" cy="180" r="4"/>
          <circle cx="300" cy="160" r="4"/>
          <circle cx="360" cy="120" r="4"/>
          <circle cx="420" cy="140" r="4"/>
          <path d="M120,280 L180,240 L240,180 L300,160 L360,120 L420,140" fill="none"/>
        </g>
        <text x="300" y="370" text-anchor="middle" font-size="12" fill="#6b7280">Batch Size</text>
        <text x="30" y="200" text-anchor="middle" font-size="12" fill="#6b7280" transform="rotate(-90 30 200)">TPS</text>
        <text x="500" y="340" font-size="10" fill="#3b82f6">AuroraSynth-X2</text>
      </svg>
    `)
  } else if (title.toLowerCase().includes('ttfb') || title.toLowerCase().includes('latency')) {
    return 'data:image/svg+xml;base64,' + btoa(`
      <svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
        <rect width="100%" height="100%" fill="#f8fafc"/>
        <text x="300" y="30" text-anchor="middle" font-size="18" font-weight="bold" fill="#1f2937">Time to First Byte vs Batch Size</text>
        <text x="300" y="50" text-anchor="middle" font-size="14" fill="#6b7280">Latency Analysis Across Models</text>
        <g stroke="#e5e7eb" stroke-width="1" fill="none">
          <line x1="80" y1="80" x2="80" y2="320"/>
          <line x1="80" y1="320" x2="520" y2="320"/>
        </g>
        <g fill="#ef4444" stroke="#ef4444" stroke-width="2">
          <circle cx="120" cy="300" r="4"/>
          <circle cx="180" cy="290" r="4"/>
          <circle cx="240" cy="285" r="4"/>
          <circle cx="300" cy="260" r="4"/>
          <circle cx="360" cy="220" r="4"/>
          <circle cx="420" cy="180" r="4"/>
          <path d="M120,300 L180,290 L240,285 L300,260 L360,220 L420,180" fill="none"/>
        </g>
        <text x="300" y="370" text-anchor="middle" font-size="12" fill="#6b7280">Batch Size</text>
        <text x="30" y="200" text-anchor="middle" font-size="12" fill="#6b7280" transform="rotate(-90 30 200)">TTFB (seconds)</text>
        <text x="500" y="340" font-size="10" fill="#ef4444">TitanNova-200b-Guide</text>
      </svg>
    `)
  } else {
    // Generic chart
    return 'data:image/svg+xml;base64,' + btoa(`
      <svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
        <rect width="100%" height="100%" fill="#f8fafc"/>
        <text x="300" y="30" text-anchor="middle" font-size="18" font-weight="bold" fill="#1f2937">${title}</text>
        <g stroke="#e5e7eb" stroke-width="1" fill="none">
          <line x1="80" y1="80" x2="80" y2="320"/>
          <line x1="80" y1="320" x2="520" y2="320"/>
        </g>
        <g fill="#8b5cf6" stroke="#8b5cf6" stroke-width="2">
          <circle cx="120" cy="200" r="4"/>
          <circle cx="200" cy="150" r="4"/>
          <circle cx="280" cy="180" r="4"/>
          <circle cx="360" cy="120" r="4"/>
          <circle cx="440" cy="160" r="4"/>
          <path d="M120,200 L200,150 L280,180 L360,120 L440,160" fill="none"/>
        </g>
        <text x="300" y="370" text-anchor="middle" font-size="12" fill="#6b7280">Data Points</text>
        <text x="30" y="200" text-anchor="middle" font-size="12" fill="#6b7280" transform="rotate(-90 30 200)">Values</text>
      </svg>
    `)
  }
}

function getCurrentUserId() {
  // Try to extract user_id from existing Redis files in artifacts
  for (const artifact of artifacts.value) {
    if (artifact.url && artifact.url.includes('user_id=')) {
      const match = artifact.url.match(/user_id=([^&]+)/)
      if (match) {
        return match[1]
      }
    }
  }
  
  // Fallback: try to get from localStorage, sessionStorage, or other global state
  // This might need to be adjusted based on your authentication system
  if (typeof window !== 'undefined') {
    return localStorage.getItem('user_id') || sessionStorage.getItem('user_id') || 'current_user'
  }
  
  return 'current_user'
}

function getFileType(title, fileId) {
  // Determine file type based on title or file extension
  const lowerTitle = title.toLowerCase()
  const lowerFileId = fileId.toLowerCase()
  
  if (lowerTitle.includes('.pdf') || lowerFileId.includes('.pdf')) {
    return 'pdf'
  } else if (lowerTitle.includes('.md') || lowerTitle.includes('markdown') || lowerFileId.includes('.md')) {
    return 'markdown'
  } else if (lowerTitle.includes('.html') || lowerTitle.includes('.htm') || lowerFileId.includes('.html') || lowerFileId.includes('.htm')) {
    return 'html'
  } else if (lowerTitle.includes('.ppt') || lowerTitle.includes('.pptx') || lowerTitle.includes('powerpoint') || 
             lowerFileId.includes('.ppt') || lowerFileId.includes('.pptx') || lowerFileId.includes('powerpoint') ||
             lowerTitle.includes('presentation') || lowerTitle.includes('slides')) {
    return 'powerpoint'
  } else if (lowerTitle.includes('.csv') || lowerFileId.includes('.csv') || lowerTitle.includes('csv') ||
             lowerTitle.includes('comma-separated') || lowerTitle.includes('spreadsheet')) {
    return 'csv'
  } else if (lowerTitle.includes('chart') || lowerTitle.includes('graph') || lowerTitle.includes('plot') || 
             lowerTitle.includes('visualization') || lowerTitle.includes('diagram')) {
    return 'image'
  } else {
    // Default to image for backward compatibility
    return 'image'
  }
}

function updateStatus(status, details = '') {
  currentStatus.value = status
  statusDetails.value = details
  isProcessing.value = status.includes('Executing') || status.includes('Running')
}

function addToLog(message, type = 'info', timestamp) {
  executionLog.value.push({
    id: Date.now() + Math.random(),
    message,
    type,
    timestamp
  })
  
  if (executionLog.value.length > 50) {
    executionLog.value = executionLog.value.slice(-50)
  }
}

function highlightPythonCode(code) {
  if (!code) return ''
  
  // Simple approach: just escape HTML and add basic styling
  // No complex regex that can break
  return code
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
}

function parseCsvData(artifact) {
  // Enhanced CSV parsing for full viewer - handle quoted fields and edge cases
  const csvText = artifact.csvData || artifact.content || artifact.preview
  if (!csvText) return []
  
  try {
    const lines = csvText.split('\n').filter(line => line.trim()).slice(0, 50) // Show more rows
    return lines.map(line => {
      const cells = []
      let current = ''
      let inQuotes = false
      let i = 0
      
      while (i < line.length && cells.length < 10) { // Show more columns
        const char = line[i]
        
        if (char === '"' && (i === 0 || line[i-1] === ',')) {
          inQuotes = true
        } else if (char === '"' && inQuotes && (i === line.length - 1 || line[i+1] === ',')) {
          inQuotes = false
        } else if (char === ',' && !inQuotes) {
          cells.push(current.trim())
          current = ''
          i++
          continue
        } else {
          current += char
        }
        i++
      }
      
      // Add the last cell
      if (current || cells.length === 0) {
        cells.push(current.trim())
      }
      
      // Clean up cells - remove quotes and truncate long values
      return cells.map(cell => {
        cell = cell.replace(/^"|"$/g, '') // Remove surrounding quotes
        return cell.length > 30 ? cell.substring(0, 27) + '...' : cell
      })
    })
  } catch (error) {
    console.warn('Error parsing CSV data:', error)
    // Fallback to simple parsing
    const lines = csvText.split('\n').filter(line => line.trim()).slice(0, 50)
    return lines.map(line => 
      line.split(',').slice(0, 10).map(cell => {
        cell = cell.trim().replace(/^"|"$/g, '')
        return cell.length > 30 ? cell.substring(0, 27) + '...' : cell
      })
    )
  }
}



function openInNewTab(url) {
  window.open(url, '_blank', 'noopener,noreferrer')
}

async function loadCsvContent(artifact) {
  if (artifact.csvData || artifact.content) return
  
  try {
    artifact.loading = true
    const response = await fetch(artifact.url, {
        headers: {
            'Authorization': `Bearer ${await window.Clerk.session.getToken()}`
        }
    })
    if (response.ok) {
      const csvText = await response.text()
      artifact.csvData = csvText
      artifact.loading = false
    } else {
      throw new Error('Failed to load CSV data')
    }
  } catch (error) {
    console.error('Error loading CSV content:', error)
    artifact.loading = false
    addToLog(`Failed to load CSV data: ${artifact.title}`, 'error', new Date().toISOString())
  }
}

function renderMarkdown(markdownText) {
  if (!markdownText) return ''
  
  // Simple markdown to HTML conversion for basic formatting
  // This is a basic implementation - you might want to use a proper markdown library
  let html = markdownText
    .replace(/^### (.*$)/gim, '<h3 class="text-lg font-semibold mt-4 mb-2">$1</h3>')
    .replace(/^## (.*$)/gim, '<h2 class="text-xl font-semibold mt-4 mb-2">$1</h2>')
    .replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold mt-4 mb-2">$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code class="bg-gray-100 px-1 rounded text-sm">$1</code>')
    .replace(/\n\n/g, '</p><p class="mb-2">')
    .replace(/\n/g, '<br>')
  
  return `<p class="mb-2">${html}</p>`
}

function formatLogTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString([], { 
    hour: '2-digit', 
    minute: '2-digit',
    second: '2-digit'
  })
}

function getLogClass(type) {
  const classes = {
    'info': 'text-blue-600',
    'success': 'text-green-600', 
    'warning': 'text-yellow-600',
    'error': 'text-red-600'
  }
  return classes[type] || 'text-gray-600'
}

// UI interaction methods
function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}

function handleClose() {
  cleanupCodeUpdates()
  emit('close')
}

function toggleCodeSection() {
  codeExpanded.value = !codeExpanded.value
}

function toggleArtifactsSection() {
  artifactsExpanded.value = !artifactsExpanded.value
}

function toggleLogSection() {
  logExpanded.value = !logExpanded.value
}

function copyCode() {
  if (codeContent.value) {
    navigator.clipboard.writeText(codeContent.value)
  }
}

async function downloadArtifact(artifact) {
  if (!artifact.url) return;

  // For blob or data URLs, we can create a link and click it
  if (artifact.url.startsWith('blob:') || artifact.url.startsWith('data:')) {
    const link = document.createElement('a');
    link.href = artifact.url;
    const extension = getFileExtension(artifact.type);
    link.download = `${artifact.title.replace(/\s+/g, '_')}.${extension}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    return;
  }

  // For API URLs that haven't been converted to blobs yet, fetch with auth
  try {
    const response = await fetch(artifact.url, {
      headers: {
        'Authorization': `Bearer ${await window.Clerk.session.getToken()}`
      }
    });
    if (!response.ok) throw new Error('Download failed');
    
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const extension = getFileExtension(artifact.type);
    link.download = `${artifact.title.replace(/\s+/g, '_')}.${extension}`;
    document.body.appendChild(link);
    link.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(link);

  } catch (error) {
    console.error('Error downloading artifact:', error);
    addToLog(`Failed to download: ${artifact.title}`, 'error', new Date().toISOString());
  }
}

function getFileExtension(type) {
  const extensions = {
    'pdf': 'pdf',
    'markdown': 'md',
    'html': 'html',
    'powerpoint': 'pptx',
    'csv': 'csv',
    'image': 'png'
  }
  return extensions[type] || 'txt'
}

function expandArtifact(artifact) {
  console.log('Expanding artifact:', artifact)
  
  // All file types now have inline viewers in the sidebar
  // Still support the expand-artifact event for full-screen modals if needed
  
  // For backward compatibility, emit both events with proper data structure
  if (artifact.type === 'image') {
    // Ensure the artifact has all properties the modal expects
    // ArtifactCanvas expects type 'chart' for images, so we need to adapt the data
    const chartData = {
      ...artifact,
      type: 'chart', // Change type to 'chart' for ArtifactCanvas compatibility
      id: artifact.id,
      title: artifact.title,
      url: artifact.url,
      downloadUrl: artifact.downloadUrl || artifact.url
    }
    console.log('Emitting expand-chart with data:', chartData)
    emit('expand-chart', chartData)  // Keep old event for images
  }
  
  // For CSV files, ensure data is loaded
  if (artifact.type === 'csv' && !artifact.csvData && !artifact.content) {
    loadCsvContent(artifact)
  }
  
  emit('expand-artifact', artifact)
}

function handleArtifactError(artifact) {
  artifact.loading = false
  addToLog(`Failed to load file: ${artifact.title}`, 'error', new Date().toISOString())
}

function cleanupCodeUpdates() {
  // Nothing to clean since we switched to timestamp-based throttle
}

async function fetchArtifactContent(artifact) {
  // Do nothing for data URLs or if content is already a blob
  if (artifact.url.startsWith('data:') || artifact.url.startsWith('blob:')) {
    artifact.loading = false;
    return;
  }

  try {
    const response = await fetch(artifact.url, {
      headers: {
        'Authorization': `Bearer ${await window.Clerk.session.getToken()}`
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch artifact: ${response.statusText}`);
    }

    const artifactIndex = artifacts.value.findIndex(a => a.id === artifact.id);
    if (artifactIndex === -1) return;

    // Create a new object to ensure reactivity is triggered
    const updatedArtifact = { ...artifacts.value[artifactIndex] };

    if (updatedArtifact.type === 'csv' || updatedArtifact.type === 'markdown') {
      const textContent = await response.text();
      updatedArtifact.content = textContent;
      if (updatedArtifact.type === 'csv') {
        updatedArtifact.csvData = textContent;
      }
    } else {
      // For image, pdf, html, powerpoint etc.
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      updatedArtifact.url = blobUrl;
      // Also update downloadUrl to the blob so it can be downloaded directly
      updatedArtifact.downloadUrl = blobUrl;
    }
    
    updatedArtifact.loading = false;
    
    // Replace the item in the array to ensure reactivity
    artifacts.value[artifactIndex] = updatedArtifact;

  } catch (error) {
    console.error(`Error loading content for artifact ${artifact.title}:`, error);
    addToLog(`Failed to load artifact: ${artifact.title}`, 'error', new Date().toISOString());
    const artToUpdate = artifacts.value.find(a => a.id === artifact.id);
    if(artToUpdate) artToUpdate.loading = false;
  }
}

// Lifecycle - ENHANCED FOR LOADED CONVERSATIONS
onMounted(() => {
  // Process any existing streaming data (including historical data from loaded conversations)
  if (props.streamingEvents && props.streamingEvents.length > 0) {
    console.log('DaytonaSidebar: Processing existing streaming events on mount:', props.streamingEvents.length);
    processStreamingEvents(props.streamingEvents);
  }
})

onUnmounted(() => {
  // Clean up any pending debounced updates
  cleanupCodeUpdates()
})

// Watch for sidebar open/close state changes and emit to parent
watch(() => props.isOpen, (newState) => {
  emit('sidebar-state-changed', { 
    isOpen: newState, 
    isCollapsed: isCollapsed.value,
    width: newState ? (isCollapsed.value ? 64 : '50%') : 0
  })
}, { immediate: true })

watch(isCollapsed, (newCollapsed) => {
  if (props.isOpen) {
    emit('sidebar-state-changed', { 
      isOpen: props.isOpen, 
      isCollapsed: newCollapsed,
      width: newCollapsed ? 64 : '50%'
    })
  }
})
</script>

<style scoped>
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
}

::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

.transition-colors {
  transition: color 0.3s ease;
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: .5;
  }
}

.rotate-90 {
  transform: rotate(90deg);
}

/* Enhanced styles for inline viewers */
.inline-viewer {
  transition: all 0.3s ease;
}

.inline-viewer:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.viewer-header {
  background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
  border-bottom: 1px solid #e2e8f0;
}

.csv-table {
  font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
}

.csv-table tbody tr:hover {
  background-color: #f8fafc;
}

.prose h1, .prose h2, .prose h3 {
  color: #1f2937;
}

.prose code {
  background-color: #f3f4f6;
  padding: 0.125rem 0.25rem;
  border-radius: 0.25rem;
  font-size: 0.875em;
}
</style> 