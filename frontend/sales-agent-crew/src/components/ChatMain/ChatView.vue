<template>
  <div class="relative h-full w-full">
    <!-- Share notification toast -->
    <div 
      v-if="shareNotification"
      class="fixed top-4 right-4 z-[60] px-4 py-3 rounded-lg shadow-lg transition-all duration-300"
      :class="shareNotification.type === 'success' ? 'bg-gray-600 text-white' : 'bg-red-500 text-white'"
    >
      <div class="flex items-center space-x-2">
        <svg v-if="shareNotification.type === 'success'" class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
        </svg>
        <svg v-else class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
        </svg>
        <span>{{ shareNotification.message }}</span>
      </div>
    </div>

    <!-- Content -->
    <div
      ref="container"
      class="relative h-full flex flex-col overflow-x-hidden overflow-y-auto"
    >
      <!-- Sticky Top Component -->
      <div
        class="sticky top-0 z-10 bg-white p-4 shadow"
      >
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-4 min-h-[2rem]">
          <!-- Left side - Token Usage Display -->
          <div class="flex-1 min-w-0">
            <div v-if="cumulativeTokenUsage.total_tokens > 0" class="flex flex-wrap items-center gap-1 sm:gap-2 text-sm text-gray-600">
              <span class="font-medium whitespace-nowrap">Chat Usage Tokens:</span>
              <span class="bg-gray-100 text-gray-700 px-2 py-1 rounded text-xs whitespace-nowrap">
                {{ cumulativeTokenUsage.input_tokens.toLocaleString() }} input
              </span>
              <span class="bg-gray-100 text-gray-700 px-2 py-1 rounded text-xs whitespace-nowrap">
                {{ cumulativeTokenUsage.output_tokens.toLocaleString() }} output
              </span>
              <span class="bg-gray-100 text-gray-700 px-2 py-1 rounded text-xs whitespace-nowrap">
                {{ cumulativeTokenUsage.total_tokens.toLocaleString() }} total
              </span>
            </div>
          </div>
          
          <!-- Right side - Buttons (fixed position) -->
          <div class="flex space-x-2 flex-shrink-0">
            <!-- Shared conversation indicator -->
            <div v-if="isSharedConversation" class="flex items-center space-x-2 text-sm text-gray-600 bg-gray-100 px-2.5 py-1 rounded">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.367 2.684 3 3 0 00-5.367-2.684z" />
              </svg>
              <span class="font-medium">Shared conversation</span>
            </div>
            
            <!-- Share button - only show if conversation has messages and is not a shared conversation -->
            <button
              v-if="messagesData.length > 0 && conversationId && !isSharedConversation"
              @click="shareConversation"
              :disabled="isSharing"
              class="text-sm h-[30px] py-1 px-2.5 bg-gray-500 hover:bg-gray-600 disabled:bg-gray-300 text-white rounded flex items-center space-x-1"
              title="Share conversation"
            >
              <svg v-if="!isSharing" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.367 2.684 3 3 0 00-5.367-2.684z" />
              </svg>
              <svg v-else class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span>{{ isSharing ? 'Sharing...' : 'Share' }}</span>
            </button>
            
            <button
              class="hidden text-sm h-[30px] py-1 px-2.5 bg-[#EE7624] text-white rounded"
            >
              View full report
            </button>
            <button
              @click="genPDF"
              class="hidden text-sm h-[30px] py-1 px-2.5 bg-[#EAECF0] text-[#344054] rounded"
            >
              Download PDF
            </button>
          </div>
        </div>
      </div>

      <!-- Voice Status Badge -->
      <div v-if="showVoiceStatus" class="sticky top-[72px] z-10 px-4 py-2">
        <VoiceStatusBadge
          :voice-status="voiceStatus"
          :current-transcript="currentTranscript"
          :agent-update="agentUpdate"
          :is-visible="showVoiceStatus"
          @close="showVoiceStatus = false"
        />
      </div>

      <div
        class="flex-1 w-full flex mx-auto"
        :class="
          messagesData.length == 0 ? 'justify-center align-center flex-col' : ''
        "
      >
        <!-- Title -->
        <div v-if="messagesData.length == 0" class="w-full text-center">
          <h1 v-if="!initialLoading" class="text-3xl font-bold sm:text-3xl">
            <span class="bg-clip-text text-primary-brandTextSecondary">
              Hey {{ userFirstName || 'there' }},<br />
              What can I help you with today?
            </span>
          </h1>
        </div>
        <!-- End Title -->
        
        <transition-group
          name="chat"
          tag="ul"
          class="mt-16 max-w-4xl w-full mx-auto space-y-5"
        >
          <!-- Chat Bubble -->
          <li v-for="msgItem in filteredMessages" :key="msgItem.message_id || msgItem.id || msgItem.timestamp || Math.random()">
            <ChatBubble
              :workflowData="workflowDataByMessageId[msgItem.message_id || msgItem.messageId] || []"
              :plannerText="
                plannerTextData.filter(
                  (item) => item.message_id === (msgItem.message_id || msgItem.messageId)
                )[0]?.data || ''
              "
              :event="msgItem.event || 'unknown'"
              :data="formatMessageData(msgItem)"
              :messageId="msgItem.message_id || msgItem.messageId || msgItem.id"
              :streamingEvents="msgItem.type === 'streaming_group' ? msgItem.events : null"
              :provider="provider"
              :sidebarOpen="showDaytonaSidebar"
              :isInDeepResearch="isInDeepResearch"
              :isInDataScience="isInDataScience"
              :isSharedConversation="isSharedConversation"
              :shareToken="shareToken"
              @open-daytona-sidebar="handleOpenDaytonaSidebar"
              @open-artifact-canvas="handleOpenArtifactCanvas"
            />
            
            <!-- Token Usage Display for Final Messages -->
            <div v-if="isFinalMessage(msgItem) && getRunSummary(msgItem)?.total_tokens > 0" class="mt-2">
              <!-- Run Summary Metrics -->
              <div class="bg-gradient-to-r from-gray-50 to-gray-100 border border-gray-200 rounded-lg px-3 py-2 block shadow-sm hover:shadow-md transition-shadow duration-200 max-w-full w-fit">
                <div class="flex flex-wrap items-center gap-2 sm:gap-3">
                  <!-- Run Summary Label -->
                  
                                      <!-- Input Tokens -->
                    <div class="flex flex-col items-center w-[50px] sm:w-[55px]">
                      <span class="text-xs font-semibold text-gray-800">{{ getRunSummary(msgItem).input_tokens.toLocaleString() }}</span>
                      <span class="text-2xs text-gray-600">input</span>
                    </div>
                    
                    <!-- Divider -->
                    <div class="h-4 w-px bg-gradient-to-b from-transparent via-gray-300 to-transparent hidden sm:block"></div>
                    
                    <!-- Output Tokens -->
                    <div class="flex flex-col items-center w-[50px] sm:w-[55px]">
                      <span class="text-xs font-semibold text-gray-800">{{ getRunSummary(msgItem).output_tokens.toLocaleString() }}</span>
                      <span class="text-2xs text-gray-600">output</span>
                    </div>
                    
                    <!-- Divider -->
                    <div class="h-4 w-px bg-gradient-to-b from-transparent via-gray-300 to-transparent hidden sm:block"></div>
                    
                    <!-- Total Tokens -->
                    <div class="flex flex-col items-center w-[50px] sm:w-[55px]">
                      <span class="text-xs font-semibold text-gray-800">{{ getRunSummary(msgItem).total_tokens.toLocaleString() }}</span>
                      <span class="text-2xs text-gray-600">total</span>
                    </div>

                  <!-- Performance Metrics Summary -->
                  <template v-if="getRunSummary(msgItem).total_latency > 0">
                    <!-- Performance Section Divider -->
                    <div class="h-4 w-px bg-gradient-to-b from-transparent via-gray-300 to-transparent hidden sm:block"></div>

                    <!-- Total Latency - Clickable -->
                    <button
                      @click="openLatencyBreakdown(msgItem)"
                      class="flex flex-col items-center justify-center w-[45px] sm:w-[50px] cursor-pointer hover:bg-gray-100 rounded transition-colors group relative"
                      :title="getRunSummary(msgItem).model_breakdown.length > 0 ? 'Click to see detailed breakdown' : 'Total latency'"
                    >
                      <span class="text-xs font-semibold text-gray-800 group-hover:text-primary-brandColor">{{ getRunSummary(msgItem).total_latency.toFixed(2) }}s</span>
                      <span class="text-2xs text-gray-600 group-hover:text-primary-brandColor">latency</span>
                      <!-- Small icon to indicate clickable if breakdown available -->
                      <svg v-if="getRunSummary(msgItem).model_breakdown.length > 0" class="w-2.5 h-2.5 text-gray-400 group-hover:text-primary-brandColor absolute -bottom-1 right-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                      </svg>
                    </button>

                    <!-- Divider -->
                    <div class="h-4 w-px bg-gradient-to-b from-transparent via-gray-300 to-transparent hidden sm:block"></div>
                    
                    <!-- Total Time to First Token -->
                    <div v-if="getRunSummary(msgItem).total_ttft > 0" class="flex flex-col items-center w-[45px] sm:w-[50px]">
                      <span class="text-xs font-semibold text-gray-800">{{ getRunSummary(msgItem).total_ttft.toFixed(2) }}s</span>
                      <span class="text-2xs text-gray-600">TTFT</span>
                    </div>
                    
                    <!-- Divider -->
                    <div v-if="getRunSummary(msgItem).total_ttft > 0 && getRunSummary(msgItem).avg_throughput > 0" class="h-4 w-px bg-gradient-to-b from-transparent via-gray-300 to-transparent hidden sm:block"></div>
                    
                    <!-- Average Throughput -->
                    <div v-if="getRunSummary(msgItem).avg_throughput > 0" class="flex flex-col items-center w-[45px] sm:w-[50px]">
                      <span class="text-xs font-semibold text-gray-800">{{ getRunSummary(msgItem).avg_throughput.toFixed(1) }}</span>
                      <span class="text-2xs text-gray-600">avg t/s</span>
                    </div>
                  </template>

                  <!-- Divider -->
                  <div class="h-4 w-px bg-gradient-to-b from-transparent via-gray-300 to-transparent hidden sm:block"></div>
                  
                  <!-- Event Count -->
                  <div class="flex flex-col items-center w-[40px] sm:w-[50px]">
                    <span class="text-xs font-semibold text-gray-800">{{ getRunSummary(msgItem).event_count }}</span>
                    <span class="text-2xs text-gray-600">LLM calls</span>
                  </div>
                </div>
              </div>
            </div>
          </li>
          
                      <ChatLoaderBubble
            :workflowData="workflowDataByMessageId[currentMsgId] || []"
            v-if="isLoading && !hasActiveStreamingGroup && (workflowDataByMessageId[currentMsgId] || []).length > 0"
            :isLoading="isLoading"
            :statusText="'Planning...'"
            :plannerText="
              plannerTextData.filter(
                (item) => item.message_id === currentMsgId
              )[0]?.data
            "
            :provider="provider"
            :messageId="currentMsgId"
          />
          
          <!-- End Chat Bubble -->
        </transition-group>
      </div>

      <!-- Single Daytona Sidebar at ChatView level (persistent across messages) -->
      <DaytonaSidebar 
        :isOpen="showDaytonaSidebar"
        :streamingEvents="currentDaytonaEvents"
        :isSharedConversation="isSharedConversation"
        :shareToken="shareToken"
        @close="closeDaytonaSidebar"
        @expand-chart="openArtifact"
        @expand-artifact="openArtifact"
        @sidebar-state-changed="emit('daytona-sidebar-state-changed', $event)"
      />
      
      <!-- Artifact Canvas Modal (fallback for non-Daytona artifacts) -->
      <ArtifactCanvas
        :isOpen="showArtifactCanvas"
        :artifact="selectedArtifact"
        @close="closeArtifactCanvas"
      />

      <!-- Latency Breakdown Modal -->
      <LatencyBreakdownModal
        :isOpen="showLatencyModal"
        :totalDuration="selectedLatencyData.totalDuration"
        :modelBreakdown="selectedLatencyData.modelBreakdown"
        :agentBreakdown="selectedLatencyData.agentBreakdown"
        :hierarchicalTiming="selectedLatencyData.hierarchicalTiming"
        @close="closeLatencyModal"
      />

      <!-- Documents Section -->
      <div class="sticky z-1000 bottom-0 left-0 right-0 bg-white p-2">
        <div class="sticky bottom-0 z-10">
          <!-- Textarea -->
          <div class="max-w-4xl mx-auto lg:px-0">
            <div v-if="errorMessage" class="m-1 w-full mx-auto space-y-5">
              <ErrorComponent :parsed="{ data: { error: errorMessage } }" />
            </div>

            <div v-if="uploadedDocuments.length > 0" class="mt-4 border-t border-gray-200 pt-4">
              <!-- Refined collapsible header -->
              <button
                @click="toggleExpand"
                class="flex items-center justify-between w-full focus:outline-none mb-3"
              >
                <h3 class="text-sm font-semibold text-gray-800">
                  User Artifacts
                </h3>
                <div class="flex items-center space-x-2">
                  <span class="text-xs text-gray-500">{{ uploadedDocuments.length }} files</span>
                  <svg
                    :class="{ 'transform rotate-180': isExpanded }"
                    class="w-4 h-4 text-gray-500 transition-transform duration-200"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M19 9l-7 7-7-7"
                    />
                  </svg>
                </div>
              </button>

              <!-- Refined collapsible content -->
              <div v-if="isExpanded" class="space-y-2">
                <!-- Uploaded Documents Section -->
                <div v-if="uploadedFiles.length > 0">
                  <div class="flex items-center justify-between mb-2">
                    <h4 class="text-xs font-medium text-gray-600">Uploaded</h4>
                    <div class="flex items-center space-x-2">
                      <button
                        v-if="uploadedFiles.length > 1"
                        @click="toggleSelectAllUploaded"
                        class="text-xs text-primary-brandColor hover:underline focus:outline-none font-medium"
                      >
                        {{ allUploadedSelected ? 'Deselect All' : 'Select All' }}
                      </button>
                    </div>
                  </div>
                  <HorizontalScroll>
                    <div class="flex space-x-2 pb-2">
                      <div
                        v-for="doc in uploadedFiles"
                        :key="doc.file_id"
                        class="w-32 flex-shrink-0 p-2 bg-white rounded-lg border border-gray-200 hover:border-primary-brandColor hover:shadow-sm relative group transition-all duration-200"
                      >
                        <div class="flex items-start space-x-2">
                          <input
                            type="checkbox"
                            :checked="selectedDocuments.includes(doc.file_id)"
                            @change="toggleDocumentSelection(doc.file_id)"
                            class="h-3.5 w-3.5 text-primary-brandColor focus:ring-primary-brandColor/50 border-gray-300 rounded mt-0.5"
                          />
                          <div class="w-3.5 h-3.5 flex-shrink-0 flex items-center justify-center rounded-sm bg-gray-100 mt-0.5">
                            <component :is="getFileIcon(doc.format, doc.filename)" class="w-2.5 h-2.5 text-gray-500" />
                          </div>
                          <div class="flex-1 min-w-0">
                            <p class="text-xs font-medium text-gray-800 truncate" :title="doc.filename">
                              {{ doc.filename }}
                            </p>
                            <p class="text-2xs text-gray-500">
                              {{ formatFileSize(doc.file_size) }}
                            </p>
                          </div>
                        </div>
                        <button
                          @click="removeDocument(doc.file_id)"
                          class="absolute top-1 right-1 bg-white text-gray-500 rounded-full p-0.5 transition-all opacity-0 group-hover:opacity-100 hover:bg-red-500 hover:text-white shadow"
                          title="Remove document"
                        >
                          <XMarkIcon class="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  </HorizontalScroll>
                </div>

                <!-- Generated Files Section -->
                <div v-if="generatedFiles.length > 0">
                  <div class="flex items-center justify-between mb-2">
                    <h4 class="text-xs font-medium text-gray-600">Generated</h4>
                  </div>
                  <HorizontalScroll>
                    <div class="flex space-x-2 pb-2">
                      <div
                        v-for="doc in generatedFiles"
                        :key="doc.file_id"
                        class="w-32 flex-shrink-0 p-2 bg-primary-50/50 rounded-lg border border-primary-brandBorder/30 hover:border-primary-brandColor hover:shadow-sm relative group cursor-pointer transition-all duration-200"
                        @click="viewGeneratedFile(doc)"
                      >
                        <div class="flex items-start space-x-2">
                           <div class="w-3.5 h-3.5 flex-shrink-0 flex items-center justify-center rounded-sm bg-primary-100 mt-0.5">
                              <component :is="getFileIcon(doc.format, doc.filename)" class="w-2.5 h-2.5 text-primary-brandColor" />
                           </div>
                           <div class="flex-1 min-w-0">
                            <p class="text-xs font-medium text-gray-800 truncate" :title="doc.filename">
                              {{ doc.filename }}
                            </p>
                            <p class="text-2xs text-gray-500">
                              {{ formatFileSize(doc.file_size) }}
                            </p>
                          </div>
                        </div>
                        <div class="absolute top-1 right-1 flex space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            @click.stop="downloadFile(doc)"
                            class="bg-white text-gray-500 rounded-full p-0.5 hover:bg-primary-brandColor hover:text-white shadow"
                            title="Download file"
                          >
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                               <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                            </svg>
                          </button>
                          <button
                            @click.stop="removeDocument(doc.file_id)"
                            class="bg-white text-gray-500 rounded-full p-0.5 hover:bg-red-500 hover:text-white shadow"
                            title="Delete file"
                          >
                            <XMarkIcon class="w-3 h-3" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </HorizontalScroll>
                </div>
              </div>
            </div>

            <!-- Upload Status -->
            <div
              v-if="uploadStatus"
              class="mt-2 text-sm text-center"
              :class="{
                'text-red-500': uploadStatus.type === 'error',
                'text-green-600': uploadStatus.type === 'success',
                'text-gray-500': uploadStatus.type === 'info',
              }"
            >
              {{ uploadStatus.message }}
            </div>

            <!-- Input -->
            <div class="relative">
              <textarea
                @focus="checkAndOpenSettings"
                @keydown="handleKeyDown"
                v-model="searchQuery"
                type="search"
                :placeholder="isSharedConversation ? 'This is a shared conversation (read-only)' : 'Ask me about...companies to target, research topics, or company stocks and financials'"
                :disabled="isLoading || isSharedConversation"
                class="p-4 pb-12 block min-h-[106px] w-full bg-primary-brandFrame border-primary-brandFrame rounded-lg text-sm focus:outline-none active:outline-none border focus:border-primary-brandColor disabled:opacity-50 disabled:pointer-events-none resize-y"
              ></textarea>

              <!-- Toolbar -->
              <div
                class="absolute bottom-px inset-x-px p-2 rounded-b-lg border-primary-brandFrame pointer-events-none"
              >
                <div class="flex justify-between items-center">
                  <!-- Button Group -->
                  <div class="flex items-center">
                    <!-- Attach Button -->
                    <button
                      @click="$refs.fileInput.click()"
                      :disabled="isLoading || isUploading"
                      type="button"
                      class="inline-flex shrink-0 justify-center items-center size-8 rounded-lg text-gray-500 hover:bg-gray-100 focus:z-1 focus:outline-none focus:bg-gray-100 pointer-events-auto"
                    >
                      <input
                        type="file"
                        ref="fileInput"
                        @change="handleFileUpload"
                        class="hidden"
                        accept=".pdf,.doc,.docx,.csv,.xlsx,.xls,.jpeg,.jpg,.png,.gif,.webp"
                        multiple
                      />
                      <svg
                        v-if="!isUploading"
                        class="shrink-0 w-5 h-5"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="2"
                          d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
                        />
                      </svg>

                      <svg
                        v-if="isUploading"
                        class="shrink-0 w-5 h-5 animate-spin"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="2"
                          d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"
                        />
                      </svg>
                    </button>
                    <!-- End Attach Button -->

                    <!-- Connector Toggle Button -->
                    <div class="relative">
                      <button
                        ref="connectorButtonElement"
                        @click.stop="toggleConnectorPanel"
                        type="button"
                        :disabled="isLoading"
                        data-connector-button
                        class="inline-flex shrink-0 justify-center items-center size-8 rounded-lg text-gray-500 hover:bg-gray-100 focus:z-1 focus:outline-none focus:bg-gray-100 pointer-events-auto"
                      >
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                        </svg>
                      </button>
                    </div>
                    <!-- End Connector Toggle Button -->

                    <!-- Mic Button (Legacy - Hidden) -->
                    <button
                      v-if="false"
                      type="button"
                      @click="toggleRecording"
                      :disabled="isLoading"
                      :class="{
                        'text-gray-500': !isRecording,
                        'text-orange-500': isRecording,
                      }"
                      class="inline-flex shrink-0 justify-center items-center size-8 rounded-lg text-gray-500 hover:bg-gray-100 focus:z-1 focus:outline-none focus:bg-gray-100 pointer-events-auto"
                    >
                      <svg
                        v-if="!isRecording"
                        class="shrink-0"
                        width="24"
                        height="20"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="#667085"
                        stroke-width="2"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          d="M12 2c-1.7 0-3 1.2-3 2.6v6.8c0 1.4 1.3 2.6 3 2.6s3-1.2 3-2.6V4.6C15 3.2 13.7 2 12 2z"
                        />
                        <path
                          d="M19 10v1a7 7 0 0 1-14 0v-1M12 18.4v3.3M8 22h8"
                        />
                      </svg>

                      <svg
                        v-else
                        class="w-6 h-6 text-gray-800"
                        aria-hidden="true"
                        xmlns="http://www.w3.org/2000/svg"
                        width="24"
                        height="24"
                        fill="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          d="M7 5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H7Z"
                        />
                      </svg>
                    </button>
                    <!-- End Mic Button -->
                  </div>
                  <!-- End Button Group -->
                  <!-- Button Group -->
                  <div class="flex items-center gap-x-1">
                    <!-- Mic Button (Legacy - Hidden) -->
                    <Tooltip
                      v-if="false"
                      text="Use voice mode"
                      position="top"
                      color="bg-black text-white"
                    >
                      <button
                        type="button"
                        @click="toggleRecording"
                        :disabled="isLoading"
                        :class="{
                          'text-gray-500': !isRecording,
                          'text-orange-500': isRecording,
                        }"
                        class="inline-flex hidden shrink-0 justify-center items-center size-8 rounded-lg text-gray-500 hover:bg-gray-100 focus:z-1 focus:outline-none focus:bg-gray-100 pointer-events-auto"
                      >
                        <svg
                          v-if="!isRecording"
                          class="w-6 h-6 text-gray-800"
                          aria-hidden="true"
                          xmlns="http://www.w3.org/2000/svg"
                          width="24"
                          height="24"
                          fill="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            fill-rule="evenodd"
                            d="M5 8a1 1 0 0 1 1 1v3a4.006 4.006 0 0 0 4 4h4a4.006 4.006 0 0 0 4-4V9a1 1 0 1 1 2 0v3.001A6.006 6.006 0 0 1 14.001 18H13v2h2a1 1 0 1 1 0 2H9a1 1 0 1 1 0-2h2v-2H9.999A6.006 6.006 0 0 1 4 12.001V9a1 1 0 0 1 1-1Z"
                            clip-rule="evenodd"
                          />
                          <path
                            d="M7 6a4 4 0 0 1 4-4h2a4 4 0 0 1 4 4v5a4 4 0 0 1-4 4h-2a4 4 0 0 1-4-4V6Z"
                          />
                        </svg>
                        <svg
                          v-else
                          class="w-6 h-6 text-gray-800"
                          aria-hidden="true"
                          xmlns="http://www.w3.org/2000/svg"
                          width="24"
                          height="24"
                          fill="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            d="M7 5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H7Z"
                          />
                        </svg>
                      </button>
                    </Tooltip>
                    <!-- End Mic Button -->

                    <!-- Voice Control -->
                    <VoiceControl
                      v-if="isVoiceSupported"
                      :conversation-id="currentId"
                      @voice-mode-starting="handleVoiceModeStarting"
                      @voice-status-changed="handleVoiceStatusChange"
                    />

                    <!-- Send Button -->
                    <button
                      type="button"
                      @click="addMessage"
                      :disabled="isLoading || !searchQuery.trim() || isSharedConversation"
                      class="inline-flex shrink-0 justify-center items-center bg-transparent cursor-pointer pointer-events-auto"
                    >
                      <svg
                        id="send-button"
                        v-if="!isLoading"
                        width="21"
                        height="18"
                        viewBox="0 0 21 18"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          d="M0.00999999 18L21 9L0.00999999 0L0 7L15 9L0 11L0.00999999 18Z"
                          fill="#250E36"
                        />
                      </svg>
                      <svg
                        id="stop-button"
                        v-if="isLoading"
                        width="20"
                        height="20"
                        viewBox="0 0 20 20"
                        fill="none"
                        xmlns="http://www.w3.org/2000/svg"
                      >
                        <path
                          d="M10 0C4.48 0 0 4.48 0 10C0 15.52 4.48 20 10 20C15.52 20 20 15.52 20 10C20 4.48 15.52 0 10 0ZM10 18C5.58 18 2 14.42 2 10C2 5.58 5.58 2 10 2C14.42 2 18 5.58 18 10C18 14.42 14.42 18 10 18ZM14 14H6V6H14V14Z"
                          fill="#667085"
                        />
                      </svg>
                    </button>
                    <!-- End Send Button -->
                  </div>
                  <!-- End Button Group -->
                </div>
              </div>
              <!-- End Toolbar -->
            </div>
            <!-- End Input -->
          </div>
          <!-- End Textarea -->
        </div>
      </div>

      <!-- Connector Panel Dropdown (outside of pointer-events-none container) -->
      <div
        v-if="showConnectorPanel"
        ref="connectorPanelElement"
        data-connector-panel
        class="absolute bottom-20 left-4 z-[9999] w-72 bg-white border border-gray-200 rounded-lg shadow-lg p-3"
      >
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold text-gray-800">Connected Apps</h3>
          <button
            @click.stop="showConnectorPanel = false"
            class="text-gray-400 hover:text-gray-600"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <ConnectorTogglePanel
          ref="connectorPanelRef"
          @manage-connectors="openSettingsForConnectors"
          @add-connectors="openSettingsForConnectors"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  ref,
  watch,
  onMounted,
  nextTick,
  onBeforeUnmount,
  onUnmounted,
  inject,
  computed,
} from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';
import ChatBubble from '@/components/ChatMain/ChatBubble.vue';
import ChatLoaderBubble from '@/components/ChatMain/ChatLoaderBubble.vue';
import ConnectorTogglePanel from '@/components/ChatMain/ConnectorTogglePanel.vue';
const router = useRouter();
const route = useRoute();
import { useAuth0 } from '@auth0/auth0-vue';
import { decryptKey } from '../../utils/encryption';
import Tooltip from '@/components/Common/UIComponents/CustomTooltip.vue';

import { 
  XMarkIcon, 
  DocumentIcon,
  DocumentTextIcon,
  PhotoIcon,
  TableCellsIcon,
  CodeBracketIcon
} from '@heroicons/vue/24/outline';
import HorizontalScroll from '@/components/Common/UIComponents/HorizontalScroll.vue';
import emitterMitt from '@/utils/eventBus.js';
import ErrorComponent from '@/components/ChatMain/ResponseTypes/ErrorComponent.vue';
import DaytonaSidebar from '@/components/ChatMain/DaytonaSidebar.vue';
import ArtifactCanvas from '@/components/ChatMain/ArtifactCanvas.vue';
import VoiceControl from '@/components/ChatMain/VoiceControl.vue';
import VoiceStatusBadge from '@/components/ChatMain/VoiceStatusBadge.vue';
import LatencyBreakdownModal from '@/components/ChatMain/LatencyBreakdownModal.vue';
import { isFinalAgentType, shouldExcludeFromGrouping } from '@/utils/globalFunctions.js';
import { sharing } from '@/services/api.js';
import { useVoiceChat } from '@/composables/useVoiceChat';

// Access Auth0 user for personalization
const { user } = useAuth0();
const userFirstName = computed(() => {
  if (user && user.value) {
    return user.value.given_name || user.value.name?.split(' ')[0] || '';
  }
  return '';
});

// Inject the shared selectedOption from MainLayout.vue.
const selectedOption = inject('selectedOption');

// Make Heroicons available for dynamic component resolution
const iconComponents = {
  DocumentIcon,
  DocumentTextIcon,
  PhotoIcon,
  TableCellsIcon,
  CodeBracketIcon
};
async function handleButtonClick(data) {
  // Check if user is authenticated
  if (!isAuthenticated.value) {
    console.log('Skipping handleButtonClick - user not authenticated');
    return;
  }

  chatName.value = '';
  
  // Create new chat instead of just going to home
  await createNewChat();
}

async function genPDF() {
  try {
    const sampleContent = {
      report: [
        {
          title: 'Introduction',
          high_level_goal: 'Understand the basics of Vue 3',
          why_important:
            'Vue 3 is a modern framework with reactivity features.',
          generated_content:
            '## Vue 3 Overview\nVue 3 introduces Composition API, better performance, and more...',
        },
      ],
    };

    downloadPDF(sampleContent);
  } catch (e) {
    console.log('PDF gen error', e);
  }
}

async function createNewChat() {
  // Check if user is authenticated
  if (!isAuthenticated.value) {
    console.log('Skipping createNewChat - user not authenticated');
    return;
  }

  try {
    const resp = await axios.post(
      `${import.meta.env.VITE_API_URL}/chat/init`,
      {},
      {
        headers: {
          Authorization: `Bearer ${await getAccessTokenSilently()}`,
        },
      }
    );
    const cid = resp.data.conversation_id;
    router.push(`/${cid}`);
  } catch (err) {
    console.error('Error creating new chat:', err);
    errorMessage.value =
      'Failed to create new conversation. Check keys or console.';
    isLoading.value = false;
  }
}

// Share conversation functionality
async function shareConversation() {
  if (!conversationId.value) {
    console.error('No conversation ID available');
    return;
  }

  isSharing.value = true;
  
  try {
    const result = await sharing.createShare(conversationId.value, getAccessTokenSilently);
    const shareUrl = `${window.location.origin}/share/${result.share_token}`;
    
    // Copy to clipboard
    await navigator.clipboard.writeText(shareUrl);
    
    // Show success notification
    showNotification('success', 'Share link copied to clipboard!');
    
  } catch (error) {
    console.error('Error creating share:', error);
    
    // Show error notification
    showNotification('error', 'Failed to create share link');
    
  } finally {
    isSharing.value = false;
  }
}

// Notification helper
function showNotification(type, message) {
  shareNotification.value = { type, message };
  
  // Auto-hide after 3 seconds
  setTimeout(() => {
    shareNotification.value = null;
  }, 3000);
}

// Watch for changes to the selection and load data accordingly.
const provider = ref('');
const chatName = ref('');
watch(
  selectedOption,
  (newVal) => {
    provider.value = newVal.value;
  },
  { immediate: true }
);

const socket = ref(null); // WebSocket reference
const container = ref(null);
const isExpanded = ref(false);
let pingInterval = null;

function toggleExpand() {
  isExpanded.value = !isExpanded.value;
}

function handleKeyDown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();

    addMessage();
  }
}



function AutoScrollToBottom(smoothScrollOff = false) {
  nextTick(() => {
    setTimeout(() => {
      if (container.value) {
        const targetScroll =
          container.value.scrollHeight - container.value.clientHeight;
        container.value.scrollTo({
          top: targetScroll,
          behavior: smoothScrollOff ? 'auto' : 'smooth',
        });
      }
    }, 100); // Adjust timeout as needed
  });
}

const emit = defineEmits([
  'searchStart',
  'messagesChanged',
  'searchComplete',
  'searchError',
  'openSettings',
  'agentThoughtsDataChanged',
  'daytona-sidebar-state-changed',
  'open-artifact-canvas',
  'stream-started',
  'stream-completed',
]);
const props = defineProps({
  conversationId: {
    type: String,
    default: '',
  },
  userId: {
    type: String,
    default: 'anonymous',
  },
  keysUpdated: {
    type: Number,
    default: 0,
  },
  runId: {
    type: String,
    default: '',
  },
  sessionId: {
    type: String,
    default: '',
  },
});

const isLoading = ref(false);
const initialLoading = ref(false);
const showConnectorPanel = ref(false);
const justOpenedConnectorPanel = ref(false);
const connectorPanelRef = ref(null);
const connectorPanelElement = ref(null);
const connectorButtonElement = ref(null);

// Conversation change watcher:
watch(
  () => route.params.id,
  (newId, oldId) => {
    if (newId !== oldId) {
      // Clear all previous data
      initialLoading.value = true;
      errorMessage.value = '';
      completionMetaData.value = null;
      messagesData.value = [];
      agentThoughtsData.value = [];
      workflowData.value = [];
      plannerTextData.value = [];
      searchQuery.value = '';
      chatName.value = '';
      isLoading.value = false;
      cumulativeTokenUsage.value = {
        input_tokens: 0,
        output_tokens: 0,
        total_tokens: 0
      };
      
      // Clear run metrics for new conversation
      runMetrics.value.clear();
      
      // Reset deep research state for new conversation
      isInDeepResearch.value = false;
      
      // Reset data science state for new conversation
      isInDataScience.value = false;
      
      // Reset sidebar state when switching conversations
      showDaytonaSidebar.value = false;
      currentDaytonaEvents.value = [];
      showArtifactCanvas.value = false;
      selectedArtifact.value = null;
      daytonaSidebarClosed.value = false; // Reset manual close flag for new conversation
      
      // Note: We intentionally don't clear selectedDocuments here
      // The document selection should persist across conversation switches
      // Only clear it if the user manually deselects or removes documents

      // Load new conversation data
      if (newId) {
        loadPreviousChat(newId);
      } else {
        // No conversation ID - clear everything and set to ready state
        initialLoading.value = false;
      }
    }
    currentId.value = newId || '';

    // Close existing socket and reconnect
    if (socket.value) {
      closeSocket();
    }
    if (newId) {
      connectWebSocket();
    }
  }
);



const checkAndOpenSettings = () => {
  emitterMitt.emit('check-keys', { message: 'check keys!' });
};

async function loadSharedConversation() {
  try {
    initialLoading.value = true;
    console.log('Loading shared conversation');
    
    const data = await sharing.getSharedConversation(shareToken.value);
    
    if (data && data.messages) {
      // Set conversation ID for the shared conversation
      conversationId.value = data.conversation_id;
      currentId.value = data.conversation_id;
      
      // Format the data to match our existing structure
      const formattedData = {
        messages: data.messages,
        is_owner: false,
        is_public: true
      };
      
      await filterChat(formattedData);
      
      // Set page title
      if (data.title) {
        document.title = `${data.title} - Shared Conversation`;
      }
      
      AutoScrollToBottom(true);
    } else {
      console.warn('No messages found in shared conversation');
      messagesData.value = [];
      errorMessage.value = 'No messages found in this shared conversation.';
    }
  } catch (err) {
    console.error('Error loading shared conversation:', err);
    errorMessage.value = 'Failed to load shared conversation. It may have been removed or is no longer available.';
    messagesData.value = [];
  } finally {
    initialLoading.value = false;
    isLoading.value = false;
    statusText.value = '';
  }
}

async function loadPreviousChat(convId) {
  if (!convId) {
    initialLoading.value = false;
    return;
  }

  try {
    initialLoading.value = true;
    // Prevent auto-opening sidebar from historical data
    daytonaSidebarClosed.value = true;

    const resp = await axios.get(
      `${import.meta.env.VITE_API_URL}/chat/history/${convId}`,
      {
        headers: {
          Authorization: `Bearer ${await getAccessTokenSilently()}`,
        },
      }
    );

    if (resp.data && resp.data.messages) {
      await filterChat(resp.data);

      const lastMessage = messagesData.value[messagesData.value.length - 1];
      if (lastMessage) {
        const lastKwargs = getAdditionalKwargs(lastMessage);
        if (isFinalAgentType(lastKwargs.agent_type) || lastMessage.event === 'stream_complete') {
          emit('stream-completed');
        }
      }
    } else {
      console.warn('No messages found in chat history response');
      messagesData.value = [];
    }
    
    AutoScrollToBottom(true);
  } catch (err) {
    console.error('Error loading previous chat:', err);
    // Don't show error message for specific DaytonaSidebar errors
    if (!err.message?.includes('content.match is not a function')) {
      // Check if it's a 404 error (conversation not found)
      if (err.response?.status === 404) {
        // Clear the current route and create a new chat
        router.push('/');
        await createNewChat();
      } else {
        errorMessage.value = 'Failed to load conversation history. Please try again.';
      }
    }
    messagesData.value = [];
  } finally {
    initialLoading.value = false;
    isLoading.value = false;
    // Clear any status text that might be showing "generating" or "processing"
    statusText.value = '';
  }
}
const currentId = ref(route.params.id || '');

const messagesData = ref([]);
const workflowData = ref([]);
const completionMetaData = ref(null);
const agentThoughtsData = ref([]);
const cumulativeTokenUsage = ref({
  input_tokens: 0,
  output_tokens: 0,
  total_tokens: 0
});

// Sharing functionality
const isSharing = ref(false);
const shareNotification = ref(null);

// Conversation ID for sharing
const conversationId = ref(route.params.id || '');
const isSharedConversation = ref(false);
const shareToken = ref('');

// Track metrics per run_id
const runMetrics = ref(new Map());

// Track deep research state
const isInDeepResearch = ref(false);

// Track data science state
const isInDataScience = ref(false);

// Voice chat integration
const {
  isVoiceMode,
  voiceStatus,
  currentTranscript,
  agentUpdate,
  error: voiceError,
  audioLevel,
  isSupported: isVoiceSupported
} = useVoiceChat(computed(() => currentId.value));

// Voice status badge visibility
const showVoiceStatus = ref(false);

// Watch for voice mode changes to auto-show/hide status badge
watch(isVoiceMode, (newValue) => {
  showVoiceStatus.value = newValue;
});

// Handle voice mode starting (before activation)
async function handleVoiceModeStarting() {
  // If no conversation exists, create one first (same pattern as addMessage)
  if (!route.params.id && !isSharedConversation.value) {
    try {
      await createNewChat();
      await nextTick();
      // After createNewChat, the router push should update the conversation id
      conversationId.value = route.params.id;
    } catch (error) {
      console.error('Failed to create new chat for voice mode:', error);
      throw new Error('Failed to create conversation for voice mode');
    }
  }

  // Ensure main chat WebSocket is connected
  if (!socket.value || socket.value.readyState !== WebSocket.OPEN) {
    await connectWebSocket();
    await waitForSocketOpen();
  }
}

// Handle voice status changes
async function handleVoiceStatusChange(event) {
  // Set isLoading based on voice status to trigger Daytona sidebar and other UI
  if (event.status === 'thinking' || event.status === 'processing') {
    isLoading.value = true;
  } else if (event.status === 'idle' || event.status === 'listening' || event.status === 'error') {
    isLoading.value = false;
  }

  // Note: Don't set isLoading=false for 'speaking' status - we want sidebar to stay open while EVI speaks
}

watch(
  () => agentThoughtsData.value,
  (newThoughts) => {
    emit('agentThoughtsDataChanged', newThoughts);
  },
  { deep: true }
);

// Helper function to safely access additional_kwargs from either location
// (handles both live WebSocket messages and stored database messages)
const getAdditionalKwargs = (message) => {
  return message.additional_kwargs || message.data?.additional_kwargs || {};
};

async function filterChat(msgData) {
  // First pass: identify conversation turns for run grouping
  let currentRunId = null;
  const messageToRunMap = new Map();

  // Sort messages by timestamp to ensure proper ordering
  const sortedMessages = msgData.messages.sort((a, b) =>
    new Date(a.timestamp || 0).getTime() - new Date(b.timestamp || 0).getTime()
  );

  sortedMessages.forEach(message => {
    const additionalKwargs = getAdditionalKwargs(message);
    const isUserMessage = additionalKwargs.agent_type === 'human' || message.type === 'HumanMessage';
    
    if (isUserMessage) {
      // Start a new conversation turn
      currentRunId = message.message_id;
    }
    
    // Map this message to the current run
    if (currentRunId) {
      messageToRunMap.set(message.message_id, currentRunId);
    }
  });
  


  // Second pass: track ALL metrics for ALL messages BEFORE filtering
  sortedMessages.forEach(message => {
    // Count events that contribute to the conversation run
    const shouldTrackEvent = ['agent_completion', 'llm_stream_chunk', 'stream_complete', 'think'].includes(message.event);

    if (shouldTrackEvent) {
      const runId = messageToRunMap.get(message.message_id) || message.message_id;
      const additionalKwargs = getAdditionalKwargs(message);

      // Track metrics for think events (CrewAI agent thoughts from Financial Analysis only)
      if (message.event === 'think') {
        try {
          const dataParsed = typeof message.data === 'string' ? JSON.parse(message.data) : message.data;
          // ONLY track Financial Analysis workflow think events (not deep research)
          if (dataParsed.metadata && dataParsed.metadata.llm_name && dataParsed.metadata.workflow_name === "Financial Analysis") {
            trackRunMetrics(
              runId,
              null,  // No usage_metadata in think events
              {
                model_name: dataParsed.metadata.llm_name,
                usage: {
                  total_latency: dataParsed.metadata.duration || 0
                }
              },
              {
                agent_type: "crewai_think_event",  // Same tag as live events
                agent_name: dataParsed.agent_name
              }
            );
          }
        } catch (error) {
          console.error('Error tracking think event metrics on reload:', error);
        }
      }
      // Track metrics if they exist (for agent_completion events)
      else if (message.event === 'agent_completion') {
        // CRITICAL DEBUG: Log what additionalKwargs contains
        console.log('[TIMING_DEBUG] Processing agent_completion event:', {
          message_id: message.message_id,
          runId: runId,
          agent_type: additionalKwargs?.agent_type,
          has_workflow_timing: !!additionalKwargs?.workflow_timing,
          workflow_timing: additionalKwargs?.workflow_timing,
          additionalKwargs_keys: additionalKwargs ? Object.keys(additionalKwargs) : null,
          raw_message_additional_kwargs: message.additional_kwargs,
          raw_message_data_additional_kwargs: message.data?.additional_kwargs
        });

        // Debug: Log CrewAI tracking events
        if (additionalKwargs.agent_type === 'crewai_llm_call') {
          console.log('[ChatView] Found CrewAI tracking event:', {
            model_name: message.response_metadata?.model_name,
            message_id: message.message_id,
            runId: runId,
            response_metadata: message.response_metadata
          });
        }

        // Check if we have token usage, performance metrics, or model name to track
        const hasUsageMetadata = message.usage_metadata;
        const hasPerformanceMetrics = message.response_metadata?.usage;
        const hasModelName = message.response_metadata?.model_name;

        if (hasUsageMetadata || hasPerformanceMetrics || hasModelName) {
          trackRunMetrics(runId, message.usage_metadata, message.response_metadata, additionalKwargs);
        } else {
          // Still count the event even without usage metadata
          trackRunMetrics(runId, null, null, additionalKwargs);
        }
      } else {
        // For other events, still count the event even without usage metadata
        trackRunMetrics(runId, null, null, null);
      }
    }
  });

  messagesData.value = msgData.messages
    .map(message => {
      // For agent_completion events, handle LangGraph format
      if (message.event === 'agent_completion') {
        const additionalKwargs = getAdditionalKwargs(message);

        // For tool calls and tool results, preserve them for comprehensive audit log and Daytona sidebar
        // but only filter them from main chat display if they're tool-related
        const isToolCall = message.content && typeof message.content === 'string' && (message.content.includes('<tool>') || message.content.includes('<subgraph>'));
        const isToolResult = Array.isArray(message.content) || (additionalKwargs.agent_type === 'react_tool') || (additionalKwargs.agent_type === 'react_subgraph_DaytonaCodeSandbox');
        const isToolResponse = additionalKwargs.agent_type === 'tool_response';

        // For Daytona sandbox tool calls/results, always preserve them for sidebar processing
        const isDaytonaRelated = (isToolCall && message.content.includes('DaytonaCodeSandbox')) ||
                                 (message.type === 'LiberalFunctionMessage' && message.name === 'DaytonaCodeSandbox');

        if (isToolCall || isToolResult || isToolResponse || isDaytonaRelated) {
          // Preserve tool-related messages for comprehensive audit log and Daytona processing

          // Create structured data for tool events matching the live streaming format
          const toolData = {
            content: message.content || '',
            additional_kwargs: additionalKwargs,
            response_metadata: message.response_metadata || {},
            type: message.type || 'AIMessage',
            id: message.id || message.message_id,
            name: message.name || null,
            agent_type: additionalKwargs.agent_type || 'tool'
          };

          return {
            event: 'agent_completion',
            data: toolData,
            message_id: message.message_id,
            conversation_id: message.conversation_id,
            timestamp: message.timestamp || new Date().toISOString(),
            isToolRelated: true, // Flag for filtering in chat display but preserving for audit
            isDaytonaRelated: isDaytonaRelated
          };
        }

        // Only show user messages and final responses in main chat bubbles
        const isUserMessage = additionalKwargs.agent_type === 'human' || message.type === 'HumanMessage';
        const isFinalResponse = isFinalAgentType(additionalKwargs.agent_type);
        const isRegularAIMessage = message.type === 'AIMessage' && !isToolCall && !isToolResult && !isToolResponse;
        const isReactSubgraph = additionalKwargs.agent_type === 'react_subgraph';
        
        if (!isUserMessage && !isFinalResponse && !isRegularAIMessage && !isReactSubgraph) {
          return null; // Filter out intermediate agent responses that aren't tool-related
        }
        
        // For human messages, keep new format
        if (isUserMessage) {
          return {
            event: 'agent_completion',
            content: message.content || '',
            additional_kwargs: additionalKwargs,
            response_metadata: message.response_metadata || {},
            type: message.type || 'HumanMessage',
            name: message.name || null,
            id: message.id || message.message_id,
            message_id: message.message_id,
            conversation_id: message.conversation_id,
            timestamp: message.timestamp || new Date().toISOString()
          };
        }

        // For final responses, keep as agent_completion
        const messageContent = {
          content: message.content || '',
          additional_kwargs: additionalKwargs,
          response_metadata: message.response_metadata || {},
          type: message.type || 'AIMessage',
          id: message.id || message.message_id,
          agent_type: additionalKwargs.agent_type || 'assistant'
        };
        
        const restoredMessage = {
          event: 'agent_completion',
          data: messageContent,
          message_id: message.message_id,
          conversation_id: message.conversation_id,
          timestamp: message.timestamp || new Date().toISOString()
        };
        
        // Metrics tracking is now done in the pre-filter pass above
        
        // Restore token usage data in the same structure as live messages
        if (message.usage_metadata || message.cumulative_usage_metadata || message.response_metadata) {
          if (!restoredMessage.response_metadata) {
            restoredMessage.response_metadata = {};
          }
          if (!restoredMessage.response_metadata.usage) {
            restoredMessage.response_metadata.usage = {};
          }
          
          // Store token usage data from historical message
          if (message.usage_metadata) {
            restoredMessage.response_metadata.usage.input_tokens = message.usage_metadata.input_tokens || 0;
            restoredMessage.response_metadata.usage.output_tokens = message.usage_metadata.output_tokens || 0;
            restoredMessage.response_metadata.usage.total_tokens = message.usage_metadata.total_tokens || 0;
          }
          
          // Store performance metrics if they exist
          if (message.response_metadata?.usage) {
            Object.assign(restoredMessage.response_metadata.usage, message.response_metadata.usage);
          }
          
          // Store cumulative usage separately for header display
          if (message.cumulative_usage_metadata) {
            restoredMessage.cumulative_usage_metadata = message.cumulative_usage_metadata;
          }
        }
        
        return restoredMessage;
      }

      // Handle completion events (legacy)
      else if (message.event === 'completion') {
        return {
          event: 'completion',
          data: message.data,
          message_id: message.message_id,
          conversation_id: message.conversation_id,
          timestamp: message.timestamp || new Date().toISOString()
        };
      }
      // Handle think events (agent thoughts)
      else if (message.event === 'think') {
        return {
          event: 'think',
          data: message.data,
          message_id: message.message_id,
          conversation_id: message.conversation_id,
          timestamp: message.timestamp || new Date().toISOString()
        };
      }
      // Handle planner events
      else if (message.event === 'planner') {
        return {
          event: 'planner',
          data: message.data,
          message_id: message.message_id,
          conversation_id: message.conversation_id,
          timestamp: message.timestamp || new Date().toISOString()
        };
      }
      // Handle streaming events that might be in stored data - CRITICAL FOR PERSISTENCE
      else if (['llm_stream_chunk', 'stream_complete', 'stream_start'].includes(message.event)) {
        return {
          event: message.event,
          data: message.data || message,
          message_id: message.message_id,
          conversation_id: message.conversation_id,
          timestamp: message.timestamp || new Date().toISOString()
        };
      }

      // For any other events, include them as well
      else {
        return {
          event: message.event,
          data: message.data || message,
          message_id: message.message_id,
          conversation_id: message.conversation_id,
          timestamp: message.timestamp || new Date().toISOString()
        };
      }
    })
    .filter(Boolean)  // Remove null values
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

  // Process planner data for workflow metadata
  let plannerData = msgData.messages.filter(
    (message) => message.event === 'planner'
  );
  plannerData.forEach((planner) => {
    try {
      const parsedData = JSON.parse(planner.data);
      if (parsedData.metadata) {

      }
    } catch (error) {
      console.error('Failed to parse planner data:', error);
    }
  });

  // Process think events for workflow metadata
  let workData = msgData.messages.filter(
    (message) => message.event === 'think'
  );
  workData.forEach((work) => {
    try {
      const parsedData = JSON.parse(work.data);
      if (parsedData.metadata) {

      }
    } catch (error) {
      console.error('Failed to parse think data:', error);
    }
  });

  // Process agent_completion events for workflow metadata (tool calls/results) - ENHANCED FOR PERSISTENCE
  let agentCompletionData = msgData.messages.filter(
    (message) => {
      if (message.event !== 'agent_completion') return false;
      const msgKwargs = getAdditionalKwargs(message);
      return (
        (message.content && typeof message.content === 'string' && message.content.includes('<tool>')) ||
        Array.isArray(message.content) ||
        (message.type === 'LiberalFunctionMessage') ||
        (msgKwargs.agent_type === 'react_tool' || msgKwargs.agent_type === 'react_subgraph_DaytonaCodeSandbox') ||
        (msgKwargs.agent_type === 'tool_response') ||
        (message.name === 'DaytonaCodeSandbox')
      );
    }
  );
  agentCompletionData.forEach((completion) => {
    try {
      // Enhanced metadata for different tool types
      let metadata = {
        workflow_name: "Agent Workflow",
        agent_name: "Research Agent", 
        task: "tool_execution",
        llm_name: completion.response_metadata?.model_name || "none",
        llm_provider: "agent",
        duration: 0
      };

      // Specific handling for different tool types
      if (completion.name === 'DaytonaCodeSandbox' || 
          (completion.content && completion.content.includes('DaytonaCodeSandbox'))) {
        metadata.task = "code_execution";
        metadata.agent_name = "Daytona Sandbox";
        metadata.tool_name = "DaytonaCodeSandbox";
      } else if (completion.name === 'search_tavily' || 
                 (completion.content && completion.content.includes('search_tavily'))) {
        metadata.task = "web_search";
        metadata.tool_name = "search_tavily";
      } else if (completion.name === 'arxiv' || 
                 (completion.content && completion.content.includes('arxiv'))) {
        metadata.task = "arxiv_search";
        metadata.tool_name = "arxiv";
      } else if (Array.isArray(completion.content)) {
        metadata.task = "search_results";
      } else if (completion.content && completion.content.includes('<tool>')) {
        metadata.task = "tool_call";
      }


    } catch (error) {
      console.error('Failed to process agent completion data:', error);
    }
  });

  // Process completion events for metadata - ENHANCED FOR COMPREHENSIVE LOG SUMMARY PERSISTENCE
  let completionData = msgData.messages.filter(
    (message) => message.event === 'completion' || message.event === 'stream_complete'
  );
  completionData.forEach((completion) => {
    try {
      // Skip if completion or its data is undefined/null
      if (!completion || !completion.data) {
        return;
      }
      
      let parsedData;
      if (typeof completion.data === 'string') {
        parsedData = JSON.parse(completion.data);
      } else {
        parsedData = completion.data;
      }
      
      // Additional safety check for parsedData
      if (parsedData && parsedData.metadata) {
        completionMetaData.value = parsedData.metadata;
        emit('metadataChanged', completionMetaData.value);
      }
      
      // Also check for stream_complete events that might contain final metadata
      if (completion.event === 'stream_complete' && parsedData) {
        // Create synthetic completion metadata if not present
        if (!completionMetaData.value && workflowData.value.length > 0) {
          const totalDuration = workflowData.value.reduce((sum, item) => sum + (item?.duration || 0), 0);
          const uniqueProviders = [...new Set(workflowData.value.map(item => item?.llm_provider).filter(Boolean))];
          const uniqueModels = [...new Set(workflowData.value.map(item => item?.llm_name).filter(Boolean))];
          
          completionMetaData.value = {
            total_duration: totalDuration,
            providers_used: uniqueProviders,
            models_used: uniqueModels,
            total_tools: workflowData.value.length,
            completion_status: 'completed'
          };
          emit('metadataChanged', completionMetaData.value);
        }
      }
    } catch (error) {
      console.error('Failed to parse completion data:', error);
    }
  });

  // Process agent_completion events for cumulative token usage restoration
  let latestCumulativeUsage = null;
  
  msgData.messages
    .filter((message) => message.event === 'agent_completion')
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .forEach((completion) => {
      // Check for cumulative_usage_metadata for header display
      if (completion && completion.cumulative_usage_metadata) {
        latestCumulativeUsage = completion.cumulative_usage_metadata;
      }
    });
  
  // Restore the latest cumulative token usage for header display
  if (latestCumulativeUsage) {
    cumulativeTokenUsage.value = {
      input_tokens: latestCumulativeUsage.input_tokens || 0,
      output_tokens: latestCumulativeUsage.output_tokens || 0,
      total_tokens: latestCumulativeUsage.total_tokens || 0
    };
  }

  // Restore deep research state by checking the last agent_completion message
  msgData.messages
    .filter((message) => message.event === 'agent_completion')
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .forEach((completion) => {
      const completionKwargs = getAdditionalKwargs(completion);
      const agentType = completionKwargs.agent_type;
      if (agentType === 'deep_research_interrupt') {
        isInDeepResearch.value = true;
      } else if (agentType === 'deep_research_end') {
        isInDeepResearch.value = false;
      }

      // Restore data science state
      if (agentType === 'deep_research_interrupt') {
        isInDataScience.value = true;
      } else if (agentType === 'data_science_end') {
        isInDataScience.value = false;
      }
    });

  AutoScrollToBottom();

  // Process agent thoughts data
  agentThoughtsData.value = msgData.messages
    .filter((message) => message.event === 'think')
    .sort(
      (a, b) =>
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    )
    .reduce((acc, message) => {
      try {
        const parsed = JSON.parse(message.data);
        acc.push(parsed);
      } catch (error) {
        console.error('Failed to parse JSON for message:', message, error);
      }
      return acc;
    }, []);
  emit('agentThoughtsDataChanged', agentThoughtsData.value);

  // Process planner text data
  let plannerTextMessages = msgData.messages.filter(
    (message) => message.event === 'planner'
  );
  plannerTextMessages.forEach((planner) => {
    try {
      const parsedData = JSON.parse(planner.data);
      if (parsedData.content || parsedData.message) {
        addOrUpdatePlannerText({
          message_id: planner.message_id,
          data: parsedData.content || parsedData.message || ''
        });
      }
    } catch (error) {
      console.error('Failed to parse planner text data:', error);
    }
  });

  let userMessages = messagesData.value
    .filter((message) => {
      const msgKwargs = getAdditionalKwargs(message);
      return msgKwargs.agent_type === 'human' || message.type === 'HumanMessage';
    })
    .sort(
      (a, b) =>
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );

  if (userMessages[0]?.content) {
    chatName.value = userMessages[0].content;
  }

  AutoScrollToBottom();
  await nextTick();
}





// Reactive state for voice and file uploads
const searchQuery = ref('');
const isRecording = ref(false);
const mediaRecorder = ref(null);
const audioChunks = ref([]);
const sambanovaKey = ref(null);
const exaKey = ref(null);
const serperKey = ref(null);
const fireworksKey = ref(null);
const errorMessage = ref('');
const fileInput = ref(null);
const uploadStatus = ref(null);
const isUploading = ref(false);

// Document-related reactive state
const uploadedDocuments = ref([]);
const selectedDocuments = ref([]);
const manualSocketClose = ref(false);

// Computed properties to split documents by source
const uploadedFiles = computed(() => {
  return uploadedDocuments.value.filter(doc => doc.source === 'upload');
});

const generatedFiles = computed(() => {
  return uploadedDocuments.value.filter(doc => doc.source === 'daytona');
});

// Select All functionality for uploaded files
const allUploadedSelected = computed(() => {
  return (
    uploadedFiles.value.length > 0 &&
    uploadedFiles.value.every(doc => selectedDocuments.value.includes(doc.file_id))
  );
});

function toggleSelectAllUploaded() {
  if (allUploadedSelected.value) {
    // Deselect all uploaded files
    selectedDocuments.value = selectedDocuments.value.filter(
      id => !uploadedFiles.value.some(doc => doc.file_id === id)
    );
  } else {
    // Select all uploaded files
    const ids = uploadedFiles.value.map(doc => doc.file_id);
    selectedDocuments.value = Array.from(new Set([...selectedDocuments.value, ...ids]));
  }
}

// Auth0
const { user: auth0User, getAccessTokenSilently, isAuthenticated } = useAuth0();
const userId = computed(() => auth0User.value?.sub);

async function loadKeys() {
  // Check if user is authenticated
  if (!isAuthenticated.value) {
    console.log('Skipping loadKeys - user not authenticated');
    return;
  }

  try {
    const encryptedSambanovaKey = localStorage.getItem(
      `sambanova_key_${userId.value}`
    );
    const encryptedExaKey = localStorage.getItem(`exa_key_${userId.value}`);
    const encryptedSerperKey = localStorage.getItem(
      `serper_key_${userId.value}`
    );
    const encryptedFireworksKey = localStorage.getItem(
      `fireworks_key_${userId.value}`
    );

    if (encryptedSambanovaKey) {
      sambanovaKey.value = await decryptKey(encryptedSambanovaKey);
    } else {
      sambanovaKey.value = null;
    }

    if (encryptedExaKey) {
      exaKey.value = await decryptKey(encryptedExaKey);
    } else {
      exaKey.value = null;
    }

    if (encryptedSerperKey) {
      serperKey.value = await decryptKey(encryptedSerperKey);
    } else {
      serperKey.value = null;
    }

    if (encryptedFireworksKey) {
      fireworksKey.value = await decryptKey(encryptedFireworksKey);
    } else {
      fireworksKey.value = null;
    }
  } catch (error) {
    console.error('Error loading keys:', error);
    errorMessage.value = 'Error loading API keys';
    showErrorModal.value = true;
    isLoading.value = false;
  }
}

onMounted(async () => {
  // Check if this is a shared conversation first
  const path = route.path;
  if (path.startsWith('/share/')) {
    isSharedConversation.value = true;
    shareToken.value = route.params.shareToken;
    await loadSharedConversation();
  } else {
    // Normal conversation - load keys and user data only if authenticated
    if (isAuthenticated.value) {
      await loadKeys();
      await loadUserDocuments();
    }
    
    const routeConversationId = route.params.id;
    conversationId.value = routeConversationId || '';
    currentId.value = routeConversationId || '';

    if (routeConversationId) {
      await loadPreviousChat(routeConversationId);
    } else {
      initialLoading.value = false;
    }
  }

  emitterMitt.on('new-chat', handleButtonClick);
  emitterMitt.on('reload-user-documents', loadUserDocuments);

  // Listen for voice agent triggered events
  window.addEventListener('voice-agent-triggered', handleVoiceAgentTriggered);

  // Listen for voice workflow messages to show in chat UI
  window.addEventListener('voice-workflow-message', handleVoiceWorkflowMessage);

  // Listen for Daytona tool call detection in voice mode
  window.addEventListener('voice-daytona-detected', handleVoiceDaytonaDetected);

  // Click outside handler for connector panel - TEMPORARILY DISABLED FOR TESTING
  // document.addEventListener('click', handleClickOutside);
});

// Handler for voice agent triggered events
function handleVoiceAgentTriggered(event) {
  // CRITICAL: Always use the fresh message_id from the agent_triggered event
  // This ensures each new voice query gets its own unique message_id
  // and prevents Query 2 from reusing Query 1's message_id due to race conditions
  currentMsgId.value = event.detail.message_id;

  // Show agent workflow on screen - same as regular chat
  // The conversation will already be displayed in messages
  // Just ensure UI is in active state
  isLoading.value = true;
}

// Handler for voice workflow messages - inject into chat UI
function handleVoiceWorkflowMessage(event) {
  const message = event.detail;

  try {
    // Ensure message has a valid ID before pushing to messagesData
    const messageWithId = {
      ...message,
      message_id: message.message_id || message.id || `voice_wf_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    };

    // Add to messagesData so it shows in the chat
    messagesData.value.push(messageWithId);
  } catch (error) {
    console.error('Error adding voice workflow message to chat:', error);
  }
}

// Handler for Daytona tool call detection in voice mode
function handleVoiceDaytonaDetected(event) {
  // In voice mode, when user explicitly invokes Daytona via voice command,
  // we should open the sidebar even if they previously closed it in another context.
  // This is a NEW explicit request from the user.
  // Only skip during initial page load (loading old messages)
  if (!initialLoading.value) {
    // Reset the closed flag since this is a new explicit Daytona request via voice
    daytonaSidebarClosed.value = false
    showDaytonaSidebar.value = true
    updateCurrentDaytonaEvents()
    // Close artifact canvas if it's open since we're using sidebar now
    showArtifactCanvas.value = false
  }
}

onUnmounted(() => {
  window.removeEventListener('voice-agent-triggered', handleVoiceAgentTriggered);
  window.removeEventListener('voice-workflow-message', handleVoiceWorkflowMessage);
  window.removeEventListener('voice-daytona-detected', handleVoiceDaytonaDetected);
  emitterMitt.off('new-chat', handleButtonClick);
  emitterMitt.off('reload-user-documents', loadUserDocuments);
  // document.removeEventListener('click', handleClickOutside);
});

// Handle click outside to close connector panel
function handleClickOutside(event) {
  // Don't close if we just opened the panel
  if (justOpenedConnectorPanel.value) {
    console.log('Ignoring click - panel just opened');
    return;
  }

  // Check if click is on the button or panel using refs
  const isButtonClick = connectorButtonElement.value?.contains(event.target);
  const isPanelClick = connectorPanelElement.value?.contains(event.target);

  console.log('handleClickOutside called', {
    isButtonClick,
    isPanelClick,
    showConnectorPanel: showConnectorPanel.value,
    target: event.target,
    panelElement: connectorPanelElement.value
  });

  // Only close if clicking outside both button and panel
  if (!isButtonClick && !isPanelClick && showConnectorPanel.value) {
    console.log('Closing connector panel');
    showConnectorPanel.value = false;
  }
}

watch(
  () => props.keysUpdated,
  async () => {
    await loadKeys();
  },
  { immediate: true }
);

// Watch for route changes to update conversationId
watch(
  () => route.params.id,
  (newId) => {
    conversationId.value = newId || '';
  }
);

// Watch for route changes to handle shared conversations
watch(
  () => route.path,
  async (newPath) => {
    if (newPath.startsWith('/share/')) {
      isSharedConversation.value = true;
      shareToken.value = route.params.shareToken;
      await loadSharedConversation();
    } else {
      isSharedConversation.value = false;
      shareToken.value = '';
    }
  }
);



const statusText = ref('Loading...');
const plannerTextData = ref([]);


function toggleRecording() {
  if (isRecording.value) {
    stopRecording();
  } else {
    startRecordingFlow();
  }
}

// Connector panel methods
function toggleConnectorPanel() {
  if (!showConnectorPanel.value) {
    showConnectorPanel.value = true;
    justOpenedConnectorPanel.value = true;
    // Reset the flag after event propagation completes
    requestAnimationFrame(() => {
      setTimeout(() => {
        justOpenedConnectorPanel.value = false;
      }, 0);
    });
    console.log('Connector panel opened');
  } else {
    showConnectorPanel.value = false;
  }
}

function openSettingsForConnectors() {
  console.log('openSettingsForConnectors called');
  showConnectorPanel.value = false;
  // Open settings modal to connectors tab
  console.log('Emitting open-settings event with tab: connectors');
  emitterMitt.emit('open-settings', { tab: 'connectors' });
}

async function startRecordingFlow() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    startRecording(stream);
  } catch (error) {
    console.error('Error accessing microphone:', error);
    alert('Unable to access microphone. Please check your permissions.');
  }
}

function startRecording(stream) {
  audioChunks.value = [];
  const options = { mimeType: 'audio/webm' };
  if (!MediaRecorder.isTypeSupported(options.mimeType)) {
    console.warn(
      `${options.mimeType} is not supported, using default MIME type.`
    );
    delete options.mimeType;
  }
  mediaRecorder.value = new MediaRecorder(stream, options);
  mediaRecorder.value.ondataavailable = (event) => {
    if (event.data.size > 0) {
      audioChunks.value.push(event.data);
    }
  };
  mediaRecorder.value.onstop = async () => {
    const audioBlob = new Blob(audioChunks.value, { type: 'audio/webm' });
    await transcribeAudio(audioBlob);
    stream.getTracks().forEach((track) => track.stop());
  };
  mediaRecorder.value.start();
  isRecording.value = true;
}

function stopRecording() {
  if (mediaRecorder.value && mediaRecorder.value.state !== 'inactive') {
    mediaRecorder.value.stop();
    isRecording.value = false;
  }
}

async function transcribeAudio(audioBlob) {
  try {
    if (!sambanovaKey.value) {
      throw new Error(
        'SambaNova API key is missing. Please add it in the settings.'
      );
    }
    const audioArrayBuffer = await audioBlob.arrayBuffer();
    const audioBase64 = btoa(
      new Uint8Array(audioArrayBuffer).reduce(
        (data, byte) => data + String.fromCharCode(byte),
        ''
      )
    );
    const requestBody = {
      model: 'Whisper-Large-v3',
      messages: [
        {
          role: 'user',
          content: [
          {
            type: 'text',
            text: 'Transcribe the following audio',
          },
          {
            type: 'audio_content',
            audio_content: {
              content: `data:audio/webm;base64,${audioBase64}`,
            },
          },
          ],
        },
      ],
      stream: true,
      max_tokens: 200,
    };
    const response = await fetch(
      'https://api.sambanova.ai/v1/audio/reasoning',
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${sambanovaKey.value}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      }
    );
    if (!response.ok) {
      const errorText = await response.text();
      console.error('API Error:', response.status, errorText);
      alert(
        `Transcription failed with status ${response.status}: ${errorText}`
      );
      throw new Error(`Transcription failed: ${errorText}`);
    }
    const streamReader = response.body.getReader();
    let transcribedText = '';
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await streamReader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      const lines = chunk.split('\n').filter((line) => line.trim());
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6).trim();
          if (dataStr === '[DONE]') break;
          try {
            const data = JSON.parse(dataStr);
            if (data.choices?.[0]?.delta?.content) {
              transcribedText += data.choices[0].delta.content;
            }
          } catch (e) {
            console.error('Error parsing JSON:', e, 'Data string:', dataStr);
          }
        }
      }
    }
    const cleanedText = cleanTranscription(transcribedText);
    searchQuery.value = cleanedText.trim();
    if (searchQuery.value) {
      addMessage();
    }
  } catch (error) {
    console.error('Transcription error:', error);
    alert(error.message || 'Failed to transcribe audio. Please try again.');
  }
}

function cleanTranscription(transcribedText) {
  let cleanedText = transcribedText.trim();
  
  // Remove whisper tags like <|0.50|> from the beginning
  cleanedText = cleanedText.replace(/^<\|[^|]*\|>\s*/, '');
  
  const prefixes = [
    'The transcription of the audio is:',
    'The transcription is:',
  ];
  for (const prefix of prefixes) {
    if (cleanedText.startsWith(prefix)) {
      cleanedText = cleanedText.slice(prefix.length).trim();
      break;
    }
  }
  if (
    (cleanedText.startsWith("'") && cleanedText.endsWith("'")) ||
    (cleanedText.startsWith('"') && cleanedText.endsWith('"'))
  ) {
    cleanedText = cleanedText.slice(1, -1).trim();
  }
  return cleanedText;
}

async function handleFileUpload(event) {
  const files = Array.from(event.target.files || []);
  console.log('[ChatView] Upload triggered, files:', files.length);
  if (files.length === 0) return;

  isUploading.value = true;
  try {
    for (const file of files) {
      console.log('[ChatView] Uploading file:', file.name, 'size:', file.size, 'type:', file.type);
      const formData = new FormData();
      formData.append('file', file);

      const uploadUrl = `${import.meta.env.VITE_API_URL}/upload`;
      console.log('[ChatView] Upload URL:', uploadUrl);

      const response = await axios.post(
        uploadUrl,
        formData,
        {
          headers: {
            Authorization: `Bearer ${await getAccessTokenSilently()}`,
          },
        }
      );

      console.log('[ChatView] Upload response:', response.status, response.data);

      const document = response.data.document || response.data.file;
      if (!document) {
        console.error('[ChatView] No document in response:', response.data);
        throw new Error('Invalid upload response - no document returned');
      }

      console.log('[ChatView] Document uploaded:', document.file_id);
      uploadedDocuments.value.unshift(document);
      if (!selectedDocuments.value.includes(document.file_id)) {
        selectedDocuments.value.push(document.file_id);
      }
    }

    await loadUserDocuments();
    console.log('[ChatView] Upload complete, total documents:', uploadedDocuments.value.length);
  } catch (error) {
    console.error('[ChatView] Upload error:', error);
    console.error('[ChatView] Error details:', {
      message: error.message,
      response: error.response,
      status: error.response?.status,
      data: error.response?.data,
      headers: error.response?.headers,
    });
    uploadStatus.value = {
      type: 'error',
      message: error.response?.data?.error || error.message || 'Failed to upload document(s)',
    };
    setTimeout(() => {
      uploadStatus.value = null;
    }, 5000);
  } finally {
    isUploading.value = false;
    if (fileInput.value) fileInput.value.value = '';
  }
}

async function loadUserDocuments() {
  // Check if user is authenticated
  if (!isAuthenticated.value) {
    console.log('Skipping loadUserDocuments - user not authenticated');
    return;
  }

  try {
    const response = await axios.get(
      `${import.meta.env.VITE_API_URL}/files`,
      {
        headers: {
          Authorization: `Bearer ${await getAccessTokenSilently()}`,
        },
      }
    );
    uploadedDocuments.value = response.data.documents;
  } catch (error) {
    console.error('[SearchSection] Error loading documents:', error);
  }
}

function toggleDocumentSelection(docId) {
  const index = selectedDocuments.value.indexOf(docId);
  if (index === -1) {
    selectedDocuments.value.push(docId);
  } else {
    selectedDocuments.value.splice(index, 1);
  }
}

function waitForSocketOpen(timeout = 5000) {
  return new Promise((resolve, reject) => {
    const interval = 50;
    let elapsed = 0;
    const checkInterval = setInterval(() => {
      if (socket.value && socket.value.readyState === WebSocket.OPEN) {
        clearInterval(checkInterval);
        resolve();
      }
      elapsed += interval;
      if (elapsed >= timeout) {
        clearInterval(checkInterval);
        errorMessage.value = 'WebSocket connection error occurred.';
        isLoading.value = false;
        reject(new Error('Socket connection timeout'));
      }
    }, interval);
  });
}

const currentMsgId = ref('');
const addMessage = async () => {
  emit('stream-started');
  
  isLoading.value = true;
  errorMessage.value = '';
  
  // Reset manual close flag when starting new streaming - allow auto-open for new streams
  daytonaSidebarClosed.value = false;

  workflowData.value = [];

  // If no conversation exists, create a new chat first.
  if (!route.params.id && !isSharedConversation.value) {
    try {
      await createNewChat();
      await nextTick();
      // After createNewChat, the router push should update the conversation id.
      currentId.value = route.params.id; // update currentId from router params
      console.log('New chat created');
    } catch (error) {
      console.error('Failed to create new chat:', error);
      errorMessage.value = 'Failed to create new conversation. Please try again.';
      isLoading.value = false;
      return;
    }
  }

  if (messagesData.value.length === 0) {
    chatName.value = searchQuery.value;
  }

  // plannerText.value = null
  statusText.value = 'Loading...';
  AutoScrollToBottom();
  agentThoughtsData.value = [];
  // workflowData.value = []
  emit('agentThoughtsDataChanged', agentThoughtsData.value);
  if (!searchQuery.value.trim()) return;

  currentMsgId.value = uuidv4();
  
  
  // Check if the last agent_completion message is a deep_research_interrupt and user typed something
  let shouldResume = false;
  if (messagesData.value.length > 0) {
    // Find the last agent_completion message (not stream_complete)
    for (let i = messagesData.value.length - 1; i >= 0; i--) {
      const message = messagesData.value[i];
      if (message.event === 'agent_completion') {
        // Check if this agent_completion has deep_research_interrupt agent_type
        if (message.data && message.data.additional_kwargs.agent_type === 'deep_research_interrupt') {
          // If user typed something, set resume to true
          shouldResume = searchQuery.value.trim().length > 0;
        }
        break; // Found the last agent_completion, stop looking
      }
    }
  }
  
  const messagePayload = {
    event: 'user_message',
    data: searchQuery.value,
    timestamp: new Date().toISOString(),
    provider: provider.value,
    planner_model: localStorage.getItem(`selected_model_${userId.value}`) || '',
    message_id: currentMsgId.value,
    conversation_id: currentId.value,
    resume: shouldResume,
  };

  console.log('[ChatView] selectedDocuments.value:', selectedDocuments.value);
  console.log('[ChatView] uploadedDocuments.value:', uploadedDocuments.value);

  if (selectedDocuments.value && selectedDocuments.value.length > 0) {
    messagePayload.document_ids = selectedDocuments.value
      .map((docId) => {
        // Find the full document object from uploadedDocuments
        const fullDoc = uploadedDocuments.value.find(doc => doc.file_id === docId);
        console.log('[ChatView] Processing docId:', docId, 'Found fullDoc:', fullDoc);
        if (fullDoc) {
          return {
            format: fullDoc.format || 'unknown',
            id: fullDoc.file_id,
            indexed: fullDoc.indexed || false,
            filename: fullDoc.filename || 'unknown',
          };
        }
        return null;
      })
      .filter(doc => doc !== null);
    console.log('[ChatView] Final document_ids in payload:', messagePayload.document_ids);
  } else {
    console.log('[ChatView] No selectedDocuments, setting document_ids to []');
    messagePayload.document_ids = [];
  }

  if (!socket.value || socket.value.readyState !== WebSocket.OPEN) {
    try {
      console.log('Socket not connected. Connecting...');
      connectWebSocket();
      await waitForSocketOpen();

      socket.value.send(JSON.stringify(messagePayload));
      messagesData.value.push(messagePayload);
      searchQuery.value = '';
      // Remove images from selectedDocuments but keep other files selected
      selectedDocuments.value = selectedDocuments.value.filter(docId => {
        const doc = uploadedDocuments.value.find(d => d.file_id === docId);
        return doc && !isImageFile(doc.format, doc.filename);
      });

      // Refresh chat list after first message is sent
      if (messagesData.value.length === 1) {
        emitterMitt.emit('refresh-chat-list');
      }

      console.log('Message sent after connecting:', messagePayload);
    } catch (error) {
      errorMessage.value = 'WebSocket connection error occurred.';
      isLoading.value = false;
      console.error('Failed to connect and send message:', error);
    }
  } else {
    try {
      isLoading.value = true;
      socket.value.send(JSON.stringify(messagePayload));
      messagesData.value.push(messagePayload);
      searchQuery.value = '';
      // Remove images from selectedDocuments but keep other files selected
      selectedDocuments.value = selectedDocuments.value.filter(docId => {
        const doc = uploadedDocuments.value.find(d => d.file_id === docId);
        return doc && !isImageFile(doc.format, doc.filename);
      });

      // Refresh chat list after first message is sent
      if (messagesData.value.length === 1) {
        emitterMitt.emit('refresh-chat-list');
      }
    } catch (e) {
      console.error('ChatView error', e);
      isLoading.value = false;
    }
  }
};



async function connectWebSocket() {
  // Check if user is authenticated
  if (!isAuthenticated.value) {
    console.log('Skipping WebSocket connection - user not authenticated');
    return;
  }

  // Check if admin panel is enabled
  const isAdminPanelEnabled = import.meta.env.VITE_SHOW_ADMIN_PANEL === 'true'

  try {
    await loadKeys();

    // Only call /set_api_keys if admin panel is disabled
    // When admin panel is enabled, keys are managed through /admin/config
    if (!isAdminPanelEnabled) {
      await axios.post(
        `${import.meta.env.VITE_API_URL}/set_api_keys`,
        {
          sambanova_key: sambanovaKey.value || '',
          serper_key: serperKey.value || '',
          exa_key: exaKey.value || '',
          fireworks_key: fireworksKey.value || '',
      },
      {
        headers: {
          Authorization: `Bearer ${await getAccessTokenSilently()}`,
        },
      }
    );
    }

    // Use the same proxy pattern as API calls - let Vite proxy handle it
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.host;
    const WEBSOCKET_URL = `${wsProtocol}//${wsHost}/api/chat`;
    const token = await getAccessTokenSilently();
    const fullUrl = `${WEBSOCKET_URL}?conversation_id=${currentId.value}`;
    socket.value = new WebSocket(fullUrl);
    socket.value.onopen = () => {
      console.log('WebSocket connection opened');
      socket.value.send(
        JSON.stringify({
          type: 'auth',
          token: `Bearer ${token}`,
        })
      );
      // Start sending pings
      pingInterval = setInterval(() => {
        if (socket.value && socket.value.readyState === WebSocket.OPEN) {
          socket.value.send(JSON.stringify({ type: 'ping' }));
        }
      }, 30000); // Send a ping every 30 seconds
    };
    socket.value.onmessage = async (event) => {
      try {
        const receivedData = JSON.parse(event.data);

        // CRITICAL: Handle stream_start FIRST to set correct message_id for voice mode
        // This event arrives before any messages, ensuring the right ID is used from the start
        if (receivedData.event === 'stream_start') {
          if (receivedData.message_id) {
            currentMsgId.value = receivedData.message_id;
          }
          // Don't return - let the event propagate in case other handlers need it
        }

        if (receivedData.type === 'pong') {
          // Pong received, connection is alive.
          return;
        }

        // Handle streaming events
        if (receivedData.event === 'agent_completion') {
          
          // Update deep research state based on agent type
          const agentType = receivedData.additional_kwargs?.agent_type;
          if (agentType === 'react_subgraph_deep_research') {
            isInDeepResearch.value = true;
          } else if (agentType === 'deep_research_end') {
            isInDeepResearch.value = false;
          }
          
          // Update data science state based on agent type
          if (agentType === 'react_subgraph_data_science') {
            isInDataScience.value = true;
          } else if (agentType === 'data_science_end') {
            isInDataScience.value = false;
          }
          
          // Update cumulative token usage if present
          if (receivedData.cumulative_usage_metadata) {
            cumulativeTokenUsage.value = {
              input_tokens: receivedData.cumulative_usage_metadata.input_tokens || 0,
              output_tokens: receivedData.cumulative_usage_metadata.output_tokens || 0,
              total_tokens: receivedData.cumulative_usage_metadata.total_tokens || 0
            };
          }
      

          
          // Check if this is a final response event
          const isFinalResponse = isFinalAgentType(receivedData.additional_kwargs?.agent_type);

          // Generate proper message ID
          // CRITICAL: Use currentMsgId.value FIRST to ensure all streaming events in a conversation turn
          // share the SAME message_id so they group into ONE bubble in filteredMessages.
          // If we use receivedData.id or receivedData.message_id first, backend might send different IDs
          // for each event, creating separate bubbles instead of grouping!
          const messageId = currentMsgId.value || receivedData.message_id || receivedData.id || `agent_completion_${Date.now()}`;

          // Validate message ID - must be defined and non-empty
          if (!messageId || messageId === 'undefined' || messageId === 'null') {
            console.warn('[ChatView] Rejecting message with invalid ID:', {
              id: receivedData.id,
              message_id: receivedData.message_id,
              currentMsgId: currentMsgId.value,
              agent_type: agentType,
            });
            return;
          }

          // Check if message has meaningful content - skip empty intermediate messages
          const hasContent = (receivedData.content && receivedData.content.trim() !== '') ||
                            (receivedData.data?.content && receivedData.data.content.trim() !== '') ||
                            (receivedData.text && receivedData.text.trim() !== '');

          // Skip empty agent_completion messages (intermediate steps without output)
          // UNLESS it's a final response or has special metadata we need to track
          // Note: We should NOT filter based on isIntermediateAgentStep here because
          // those messages need to be added to messagesData for proper streaming grouping
          if (!hasContent && !isFinalResponse && !receivedData.usage_metadata && !receivedData.cumulative_usage_metadata) {
            return;
          }

          // Create message object and attach token usage data directly to it
          const messageData = {
            event: 'agent_completion',
            data: receivedData || {},
            message_id: messageId,
            id: messageId, // Also set 'id' for compatibility
            conversation_id: currentId.value,
            timestamp: receivedData.timestamp || new Date().toISOString(),
            agent_type: receivedData.agent_type,
            isFinalResponse: isFinalResponse
          };
          
          // Store token usage and performance metrics together in response_metadata.usage
          if (receivedData.usage_metadata || receivedData.response_metadata) {
            if (!messageData.response_metadata) {
              messageData.response_metadata = {};
            }
            if (!messageData.response_metadata.usage) {
              messageData.response_metadata.usage = {};
            }
            
            // Store token usage data
            if (receivedData.usage_metadata) {
              messageData.response_metadata.usage.input_tokens = receivedData.usage_metadata.input_tokens || 0;
              messageData.response_metadata.usage.output_tokens = receivedData.usage_metadata.output_tokens || 0;
              messageData.response_metadata.usage.total_tokens = receivedData.usage_metadata.total_tokens || 0;
            }
            
            // Store performance metrics if they exist
            if (receivedData.response_metadata?.usage) {
              Object.assign(messageData.response_metadata.usage, receivedData.response_metadata.usage);
            }
            
            // Track metrics for run summary
            // Use currentMsgId as the run identifier to group all events from this conversation turn
            const runId = currentMsgId.value;
            trackRunMetrics(runId, receivedData.usage_metadata, receivedData.response_metadata, receivedData.additional_kwargs);
          }
          
          // Still store cumulative usage separately for header display
          if (receivedData.cumulative_usage_metadata) {
            messageData.cumulative_usage_metadata = receivedData.cumulative_usage_metadata;
          }
          
          try {
            messagesData.value.push(messageData);
          } catch (error) {
            console.error('Error pushing message data:', error);
            isLoading.value = false;
            return;
          }
          
          // Set loading to false when we receive a final response
          if (isFinalResponse) {
            isLoading.value = false;
          }
        } else if (receivedData.event === 'llm_stream_chunk') {
          // VOICE MODE FIX: If currentMsgId is not set, this is the start of voice mode streaming
          // Set it now (before processing) so isDaytonaActiveGlobal watch can trigger sidebar opening
          if (!currentMsgId.value && receivedData.message_id) {
            currentMsgId.value = receivedData.message_id;
            isLoading.value = true;
          }

          // CRITICAL: Use currentMsgId.value as the message_id so all stream chunks
          // in this conversation turn group with agent_completion events into ONE bubble!
          const streamMessageId = currentMsgId.value || receivedData.message_id || receivedData.id || `chunk_${Date.now()}`;

          // Validate message ID
          if (!streamMessageId || streamMessageId === 'undefined' || streamMessageId === 'null') {
            console.warn('[ChatView] Rejecting stream chunk with invalid ID');
            return;
          }

          // Use a unique chunk identifier for content accumulation, but share message_id for grouping
          const chunkIdentifier = receivedData.id || `${streamMessageId}_${Date.now()}`;

          // Find existing chunk with the same identifier to accumulate content
          const existingIndex = messagesData.value.findIndex(
            (msg) => msg.event === 'llm_stream_chunk' && msg.data?.id === chunkIdentifier
          );

          if (existingIndex !== -1) {
            // Accumulate content for existing chunk
            try {
              const existingContent = messagesData.value[existingIndex].data?.content || '';
              const newContent = receivedData.content || '';
              messagesData.value[existingIndex].data.content = existingContent + newContent;

              // Track metrics if this chunk has response_metadata (e.g., final chunk with metadata)
              if (receivedData.response_metadata || receivedData.usage_metadata) {
                trackRunMetrics(
                  streamMessageId,
                  receivedData.usage_metadata,
                  receivedData.response_metadata,
                  receivedData.additional_kwargs
                );
              }
            } catch (error) {
              console.error('Error updating stream chunk:', error);
            }
          } else {
            // Create new chunk with shared message_id for grouping
            try {
              const chunkData = {
                event: 'llm_stream_chunk',
                data: { ...receivedData, id: chunkIdentifier },
                message_id: streamMessageId,  // SHARED message_id for grouping!
                conversation_id: currentId.value,
                timestamp: receivedData.timestamp || new Date().toISOString()
              };
              messagesData.value.push(chunkData);

              // CRITICAL: Track metrics for llm_stream_chunk if it has response_metadata
              // This enables live model count updates during streaming
              if (receivedData.response_metadata || receivedData.usage_metadata) {
                trackRunMetrics(
                  streamMessageId,
                  receivedData.usage_metadata,
                  receivedData.response_metadata,
                  receivedData.additional_kwargs
                );
              }
            } catch (error) {
              console.error('Error adding new stream chunk:', error);
            }
          }
        } else if (receivedData.event === 'stream_complete') {
          emit('stream-completed');
          try {
            messagesData.value.push({
              event: 'stream_complete',
              data: receivedData || {},
              message_id: currentMsgId.value,
              conversation_id: currentId.value,
              timestamp: new Date().toISOString()
            });
          } catch (error) {
            console.error('Error adding stream complete message:', error);
          }
          isLoading.value = false;

          // CRITICAL: Reset currentMsgId for voice mode so next query uses fresh backend message_id
          // This prevents message grouping issues where Query 2 reuses Query 1's message_id
          currentMsgId.value = null;

          // Reload user documents (artifacts) after chat completion
          if (!isSharedConversation.value && isAuthenticated.value) {
            console.log('Reloading user documents after chat completion');
            await loadUserDocuments();
          }
        } else if (receivedData.event === 'planner_chunk') {
          addOrUpdatePlannerText({
            message_id: currentMsgId.value,
            data: receivedData.data,
          });
        } else if (receivedData.event === 'think') {
          let dataParsed = JSON.parse(receivedData.data);
          agentThoughtsData.value.push(dataParsed);

          statusText.value = dataParsed.agent_name;
          emit('agentThoughtsDataChanged', agentThoughtsData.value);

          // CRITICAL: Track metrics from think events for model counts
          // ONLY track Financial Analysis workflow think events (not deep research)
          if (dataParsed.metadata && dataParsed.metadata.llm_name && dataParsed.metadata.workflow_name === "Financial Analysis") {
            const runId = receivedData.message_id || currentMsgId.value;
            trackRunMetrics(
              runId,
              null,  // No usage_metadata in think events
              {
                model_name: dataParsed.metadata.llm_name,
                usage: {
                  total_latency: dataParsed.metadata.duration || 0
                }
              },
              {
                agent_type: "crewai_think_event",  // Tag for live think events (different from batch "crewai_llm_call")
                agent_name: dataParsed.agent_name
              }
            );
          }

          try {

            // Add think event to messages for persistence
            try {
              messagesData.value.push({
                event: 'think',
                data: receivedData.data || {},
                message_id: receivedData.message_id || currentMsgId.value,
                conversation_id: receivedData.conversation_id || currentId.value,
                timestamp: receivedData.timestamp || new Date().toISOString()
              });
            } catch (error) {
              console.error('Error adding think message:', error);
            }

            AutoScrollToBottom();
          } catch (e) {
            console.log('model error', e);
            isLoading.value = false;
          }
        } else if (receivedData.event === 'planner') {
          let dataParsed = JSON.parse(receivedData.data);
          
          // Add planner event to messages for persistence
          try {
            messagesData.value.push({
              event: 'planner',
              data: receivedData.data || {},
              message_id: receivedData.message_id || currentMsgId.value,
              conversation_id: receivedData.conversation_id || currentId.value,
              timestamp: receivedData.timestamp || new Date().toISOString()
            });
          } catch (error) {
            console.error('Error adding planner message:', error);
          }

          AutoScrollToBottom();
        }
        
        // Auto scroll after any message
        AutoScrollToBottom();
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
        isLoading.value = false;
      }
    };
    socket.value.onerror = (error) => {
      console.error('WebSocket error:', error);
      if (!manualSocketClose.value)
        errorMessage.value = 'WebSocket connection error occurred.';

      isLoading.value = false;
    };
    socket.value.onclose = () => {
      console.log('WebSocket closed, attempting to reconnect...');
      isLoading.value = false;
    };
  } catch (error) {
    console.error('WebSocket connection error:', error);
    isLoading.value = false;
  }
}

function closeSocket() {
  manualSocketClose.value = true;
  if (socket.value) {
    socket.value.close();
  }
  clearInterval(pingInterval);
}
onBeforeUnmount(() => {
  closeSocket();
});
function addOrUpdatePlannerText(newEntry) {
  // Find the index of an existing entry with the same message_id
  const index = plannerTextData.value.findIndex(
    (entry) => entry.message_id === newEntry.message_id
  );

  if (index !== -1) {
    // Concatenate the new data with the existing data
    plannerTextData.value[index].data += newEntry.data;
  } else {
    // Add new entry
    plannerTextData.value.push(newEntry);
  }
}

async function removeDocument(docId) {
  try {
    // Check if this is a shared conversation
    if (isSharedConversation.value) {
      uploadStatus.value = {
        type: 'error',
        message: 'Cannot delete files in shared conversations',
      };
      return;
    }

    await axios.delete(`${import.meta.env.VITE_API_URL}/files/${docId}`, {
      headers: {
        Authorization: `Bearer ${await getAccessTokenSilently()}`,
      },
    });
    const selectedIndex = selectedDocuments.value.indexOf(docId);
    if (selectedIndex !== -1) {
      selectedDocuments.value.splice(selectedIndex, 1);
    }
    uploadedDocuments.value = uploadedDocuments.value.filter(
      (doc) => doc.file_id !== docId
    );
    
  } catch (error) {
    console.error('[ChatView] Error removing document:', error);
    uploadStatus.value = {
      type: 'error',
      message: error.response?.data?.error || 'Failed to remove document',
    };
    
    // Clear error message after 5 seconds
    setTimeout(() => {
      uploadStatus.value = null;
    }, 5000);
  }
}

function formatMessageData(msgItem) {
  try {

    switch (msgItem.event) {
      case 'agent_completion':
        // Check if this is a user message in new format
        if (msgItem.additional_kwargs?.agent_type === 'human' || msgItem.type === 'HumanMessage') {
          const formatted = {
            content: msgItem.content || '',
            data: msgItem.content || '',
            message: msgItem.content || '',
            agent_type: 'human',
            metadata: msgItem.response_metadata || null,
            additional_kwargs: msgItem.additional_kwargs || {},
            timestamp: msgItem.timestamp || new Date().toISOString(),
            type: msgItem.type || 'HumanMessage',
            id: msgItem.id
          };
          return JSON.stringify(formatted);
        }
        
        // agent_completion events from LangGraph have structured data
        if (msgItem.data && typeof msgItem.data === 'object') {
          const agentType = msgItem.data.agent_type || msgItem.data.additional_kwargs?.agent_type || 'assistant';
          
          // Special handling for financial_analysis_end - preserve structured data
          if (agentType === 'financial_analysis_end') {
            const formatted = {
              content: msgItem.data.content, // Keep the full structured content for FinancialAnalysisEndComponent
              data: msgItem.data.content,
              message: msgItem.data.content,
              agent_type: agentType,
              metadata: msgItem.data.response_metadata || null,
              additional_kwargs: msgItem.data.additional_kwargs || {},
              timestamp: msgItem.timestamp || new Date().toISOString(),
              type: msgItem.data.type || 'AIMessage',
              id: msgItem.data.id
            };
            return JSON.stringify(formatted);
          }
          
          // Default handling for other agent types
          const formatted = {
            content: msgItem.data.content || '',
            data: msgItem.data.content || '',
            message: msgItem.data.content || '',
            agent_type: agentType,
            metadata: msgItem.data.response_metadata || null,
            additional_kwargs: msgItem.data.additional_kwargs || {},
            timestamp: msgItem.timestamp || new Date().toISOString(),
            type: msgItem.data.type || 'AIMessage',
            id: msgItem.data.id
          };
          return JSON.stringify(formatted);
        }
        // Fallback for unexpected format
        return JSON.stringify({
          message: msgItem.data || msgItem.content || '',
          agent_type: 'assistant',
          timestamp: msgItem.timestamp || new Date().toISOString()
        });
      
      case 'completion':
        try {
          const parsed = typeof msgItem.data === 'string' ? JSON.parse(msgItem.data) : msgItem.data;
          return JSON.stringify({
            message: parsed.message || parsed,
            agent_type: parsed.agent_type || 'assistant',
            metadata: parsed.metadata || null,
            timestamp: msgItem.timestamp || new Date().toISOString()
          });
                  } catch (error) {
            console.error('Error parsing completion data:', error);
          return JSON.stringify({
            message: msgItem.data,
            agent_type: 'assistant',
            timestamp: msgItem.timestamp || new Date().toISOString()
          });
        }
      
      case 'llm_stream_chunk':
      case 'stream_complete':
        return JSON.stringify({
          message: msgItem.data?.content || msgItem.data,
          agent_type: 'assistant',
          timestamp: msgItem.timestamp || new Date().toISOString(),
          is_streaming: true
        });
      

      
      default:
        return JSON.stringify({
          message: msgItem.data,
          agent_type: 'assistant',
          timestamp: msgItem.timestamp || new Date().toISOString()
        });
    }
  } catch (error) {
    console.error('Error formatting message data:', error, msgItem);
    return JSON.stringify({ error: 'Failed to format message data', original: msgItem });
  }
}



// Check if we have an active streaming group for the current message
const hasActiveStreamingGroup = computed(() => {
  if (!messagesData.value || messagesData.value.length === 0) {
    return false;
  }

  // Check if filteredMessages contains any streaming_group
  // This is more reliable than checking message_id matches because
  // backend might send different message_ids than frontend currentMsgId
  return filteredMessages.value.some(item => item.type === 'streaming_group');
});



// Computed property to create reactive mapping of workflow data by message_id
const workflowDataByMessageId = computed(() => {
  const result = {};
  // Group workflowData by message_id
  workflowData.value.forEach(item => {
    if (!result[item.message_id]) {
      result[item.message_id] = [];
    }
    result[item.message_id].push(item);
  });
  return result;
});

const filteredMessages = computed(() => {
  if (!messagesData.value || messagesData.value.length === 0) {
    return [];
  }

  try {
    const grouped = new Map();
    const streamingEvents = ['agent_completion', 'llm_stream_chunk', 'stream_complete'];

    // First pass: identify distinct conversation turns and streaming groups
    const messageIdCounts = {};
    const userMessages = new Set(); // Track user messages
    const aiMessages = new Set(); // Track AI messages
    const userMessageIds = new Map(); // Track user message_ids to detect duplicates

    messagesData.value.forEach(msg => {
      if (!msg) return;

      // Identify user messages (these should always be separate)
      // Check both top-level and nested data properties
      const isUserMsg = msg.type === 'HumanMessage' ||
                        msg.agent_type === 'human' ||
                        msg.additional_kwargs?.agent_type === 'human' ||
                        msg.data?.type === 'HumanMessage' ||
                        msg.data?.additional_kwargs?.agent_type === 'human';

      if (isUserMsg) {
        userMessages.add(msg.message_id);
        // Track backend user messages (canonical source)
        if (msg.event === 'agent_completion') {
          userMessageIds.set(msg.message_id, 'backend');
        }
      }
      // Also track local user messages
      if (msg.event === 'user_message') {
        // Don't overwrite backend version if it exists
        if (!userMessageIds.has(msg.message_id)) {
          userMessageIds.set(msg.message_id, 'local');
        }
      }

      // Identify AI messages (these should be separate unless they're truly streaming)
      if (msg.type === 'AIMessage' || isFinalAgentType(msg.agent_type)) {
        aiMessages.add(msg.message_id);
      }

      if (streamingEvents.includes(msg.event) && msg.message_id) {
        // Count ALL streaming events for grouping - we want everything in one bubble
        messageIdCounts[msg.message_id] = (messageIdCounts[msg.message_id] || 0) + 1;
      }
    });
    
    // Second pass: group or separate messages
    messagesData.value.forEach((msg, index) => {
      if (!msg || msg === null || msg === undefined) {
        console.warn('Skipping null/undefined message at index:', index);
        return; // Skip null/undefined messages
      }

      const msgId = msg.message_id;

      // Decide whether this message should always render its own bubble
      const agentType = msg.agent_type || msg.additional_kwargs?.agent_type || msg.data?.additional_kwargs?.agent_type || msg.data?.agent_type


      // Skip duplicate user messages - prefer backend version over local
      // If this is a local user_message and we have a backend version with the same message_id, skip it
      if (msg.event === 'user_message' && userMessageIds.get(msgId) === 'backend') {
        return;
      }

      // Always separate genuine user inputs
      const isUserInput = agentType === 'human' ||
                         msg.type === 'HumanMessage' ||
                         msg.data?.type === 'HumanMessage' ||
                         msg.event === 'user_message';

      if (isUserInput) {
        const uniqueKey = `${msg.type || msg.event}_${msgId}_${index}`;
        grouped.set(uniqueKey, msg);
        return;
      }

      if (streamingEvents.includes(msg.event) &&
          msgId &&
          !(agentType === 'human' || msg.type === 'HumanMessage' || msg.data?.type === 'HumanMessage')) {

        const groupKey = `streaming_${msgId}`;

        if (!grouped.has(groupKey)) {
          grouped.set(groupKey, {
            type: 'streaming_group',
            message_id: msgId,
            events: [],
            timestamp: msg.timestamp || new Date().toISOString()
          });
        }

        const group = grouped.get(groupKey);
        if (group && group.events) {
          group.events.push(msg);



          // Sort inside the group chronologically
          group.events.sort((a, b) => {
            const aTime = new Date(a.timestamp || 0).getTime();
            const bTime = new Date(b.timestamp || 0).getTime();
            return aTime - bTime;
          });
        }
        return;
      }

      // Fallback: render as individual bubble - but only if it has meaningful content
      const hasContent = (msg.data?.content && msg.data.content.trim() !== '') ||
                        (msg.content && typeof msg.content === 'string' && msg.content.trim() !== '') ||
                        (msg.text && msg.text.trim() !== '') ||
                        (msg.event === 'user_message' && msg.data && typeof msg.data === 'string' && msg.data.trim() !== '') ||
                        (msg.event === 'user_message' && msg.document_ids && msg.document_ids.length > 0);

      // Skip agent_completion messages with empty content (intermediate steps without output)
      if (msg.event === 'agent_completion' && !hasContent) {
        console.debug('Skipping empty agent_completion message', {
          message_id: msgId,
          agent_type: agentType,
        });
        return;
      }

      if (hasContent) {
        const uniqueKey = `${msg.type || msg.event}_${msgId}_${index}`;
        grouped.set(uniqueKey, msg);
      }
      
    });
    
    // Convert to array and sort by timestamp
    const result = Array.from(grouped.values()).sort((a, b) => {
      const aTime = new Date(a.timestamp || 0).getTime();
      const bTime = new Date(b.timestamp || 0).getTime();
      return aTime - bTime;
    });

    return result;
  } catch (error) {
    console.error('Error in filteredMessages computed:', error);
    // Fallback: return safe messages array filtering out null/undefined values
    const safeMessages = (messagesData.value || []).filter(msg => msg !== null && msg !== undefined);
    return safeMessages;
  }
});

// Single Daytona sidebar state management (moved from ChatBubble)
const showDaytonaSidebar = ref(false)
const currentDaytonaEvents = ref([])
const daytonaSidebarClosed = ref(false) // Track if user manually closed it

// Artifact canvas state
const showArtifactCanvas = ref(false)
const selectedArtifact = ref(null)

// Latency breakdown modal state
const showLatencyModal = ref(false)
const selectedLatencyData = ref({
  totalDuration: 0,
  modelBreakdown: [],
  agentBreakdown: [],
  hierarchicalTiming: null  // New: hierarchical timing data
})

// Functions for managing the single DaytonaSidebar
function closeDaytonaSidebar() {
  showDaytonaSidebar.value = false
  daytonaSidebarClosed.value = true // Prevent auto-opens until user starts new streaming or manually reopens
}

function handleOpenDaytonaSidebar(specificEvents = null) {
  showDaytonaSidebar.value = true
  daytonaSidebarClosed.value = false // Allow future auto-opens since user manually opened

  // Use specific events if provided, otherwise collect all events
  if (specificEvents && specificEvents.length > 0) {
    currentDaytonaEvents.value = specificEvents
  } else {
    updateCurrentDaytonaEvents()
  }
}

function handleOpenArtifactCanvas(artifact) {
  openArtifact(artifact)
}

function openArtifact(artifact) {
  selectedArtifact.value = artifact
  showArtifactCanvas.value = true
}

function closeArtifactCanvas() {
  showArtifactCanvas.value = false
  selectedArtifact.value = null
}

// Functions for managing latency breakdown modal
function openLatencyBreakdown(msgItem) {
  console.log('[TIMING_DEBUG] openLatencyBreakdown called:', {
    msgItem_message_id: msgItem.message_id,
    msgItem_type: msgItem.type
  });

  const summary = getRunSummary(msgItem);

  console.log('[TIMING_DEBUG] openLatencyBreakdown got summary:', {
    has_hierarchical_timing: !!summary.hierarchical_timing,
    hierarchical_timing: summary.hierarchical_timing,
    summary_keys: Object.keys(summary)
  });

  // Check if we have hierarchical timing data (new format)
  const hierarchical = summary.hierarchical_timing || null;

  console.log('[TIMING_DEBUG] openLatencyBreakdown extracted hierarchical:', {
    has_hierarchical: !!hierarchical,
    hierarchical_data: hierarchical,
    workflow_duration: hierarchical?.workflow_duration,
    total_llm_calls: hierarchical?.total_llm_calls,
    num_levels: hierarchical?.levels?.length || 0
  });

  selectedLatencyData.value = {
    totalDuration: hierarchical ? hierarchical.workflow_duration : (summary.total_latency || 0),
    modelBreakdown: summary.model_breakdown || [],
    agentBreakdown: summary.agent_breakdown || [],
    hierarchicalTiming: hierarchical  // Pass the full hierarchical structure
  };

  console.log('[TIMING_DEBUG] openLatencyBreakdown set selectedLatencyData:', {
    selectedLatencyData: selectedLatencyData.value,
    has_hierarchicalTiming: !!selectedLatencyData.value.hierarchicalTiming,
    hierarchicalTiming: selectedLatencyData.value.hierarchicalTiming
  });

  showLatencyModal.value = true;
}

function closeLatencyModal() {
  showLatencyModal.value = false;
}

// Watch for Daytona activity across all messages and manage single sidebar
const isDaytonaActiveGlobal = computed(() => {
  return filteredMessages.value.some(msg => {
    if (msg.type === 'streaming_group' && msg.events) {
      return msg.events.some(event => {
        // Check for Daytona tool calls in streaming content
        if (event.event === 'llm_stream_chunk' && event.data?.content) {
          return event.data.content.includes('<tool>DaytonaCodeSandbox</tool>') || event.data.content.includes('<subgraph>DaytonaCodeSandbox</subgraph>')
        }
        
        // Check for Daytona tool results
        if (event.event === 'agent_completion' && event.data?.name === 'DaytonaCodeSandbox') {
          return true
        }
        
        // Check our custom flag for loaded conversations
        if (event.isDaytonaRelated) {
          return true
        }
        
        return false
      })
    }
    return false
  })
})

// Watch for Daytona activity and automatically open sidebar
watch(isDaytonaActiveGlobal, (isActive) => {
  // Only auto-open the sidebar if:
  // 1. Daytona activity is detected
  // 2. User hasn't manually closed it
  // 3. We're currently actively streaming (not loading historical data)
  // 4. Not during initial page load
  if (isActive &&
      !daytonaSidebarClosed.value &&
      isLoading.value &&
      !initialLoading.value) {
    showDaytonaSidebar.value = true
    updateCurrentDaytonaEvents()
    // Close artifact canvas if it's open since we're using sidebar now
    showArtifactCanvas.value = false
  }
})

// Also watch filteredMessages to update Daytona events when new messages arrive
watch(filteredMessages, () => {
  if (showDaytonaSidebar.value) {
    updateCurrentDaytonaEvents()
  }
}, { deep: true })

// Function to collect all Daytona-related events from all messages
function updateCurrentDaytonaEvents() {
  const allDaytonaEvents = []
  filteredMessages.value.forEach(msg => {
    if (msg.type === 'streaming_group' && msg.events) {
      const daytonaEvents = msg.events.filter(event => {
        return (event.event === 'llm_stream_chunk' && event.data?.content?.includes('DaytonaCodeSandbox')) ||
               (event.event === 'agent_completion' && event.data?.name === 'DaytonaCodeSandbox') ||
               event.isDaytonaRelated
      })
      allDaytonaEvents.push(...daytonaEvents)
    }
  })
  currentDaytonaEvents.value = allDaytonaEvents
}

// Function to check if a message is a final message that should show current token usage
function isFinalMessage(msgItem) {
  // Check for final response events in streaming groups
  if (msgItem.type === 'streaming_group' && msgItem.events) {
    return msgItem.events.some(event => {
      const agentType = event.data?.additional_kwargs?.agent_type || event.data?.agent_type || event.additional_kwargs?.agent_type
      return isFinalAgentType(agentType) || event.isFinalResponse
    })
  }
  
  // Check for direct final response messages
  const agentType = msgItem.data?.additional_kwargs?.agent_type || 
                   msgItem.data?.agent_type || 
                   msgItem.additional_kwargs?.agent_type ||
                   msgItem.agent_type
  
  return isFinalAgentType(agentType) || msgItem.isFinalResponse
}

// Function to extract token usage for a specific message
function getMessageTokenUsage(msgItem) {
  // For streaming groups, look for the final agent_completion event
  if (msgItem.type === 'streaming_group' && msgItem.events) {
    // Find the last agent_completion event with token usage in response_metadata.usage
    for (let i = msgItem.events.length - 1; i >= 0; i--) {
      const event = msgItem.events[i]
      
      // Check if token usage is stored in response_metadata.usage (same as performance metrics)
      if (event.response_metadata?.usage && event.response_metadata.usage.total_tokens > 0) {
        return {
          input_tokens: event.response_metadata.usage.input_tokens || 0,
          output_tokens: event.response_metadata.usage.output_tokens || 0,
          total_tokens: event.response_metadata.usage.total_tokens || 0
        }
      }
      
      // Fallback: check other possible locations
      if (event.data?.response_metadata?.usage && event.data.response_metadata.usage.total_tokens > 0) {
        return {
          input_tokens: event.data.response_metadata.usage.input_tokens || 0,
          output_tokens: event.data.response_metadata.usage.output_tokens || 0,
          total_tokens: event.data.response_metadata.usage.total_tokens || 0
        }
      }
    }
  }
  
  // For direct messages, check response_metadata.usage first (same as performance metrics)
  if (msgItem.response_metadata?.usage && msgItem.response_metadata.usage.total_tokens > 0) {
    return {
      input_tokens: msgItem.response_metadata.usage.input_tokens || 0,
      output_tokens: msgItem.response_metadata.usage.output_tokens || 0,
      total_tokens: msgItem.response_metadata.usage.total_tokens || 0
    }
  }
  
  // Return empty if no token data found
  return { input_tokens: 0, output_tokens: 0, total_tokens: 0 }
}



// Function to extract response metadata for a specific message
function getMessageResponseMetadata(msgItem) {
  // For streaming groups, look for the final agent_completion event
  if (msgItem.type === 'streaming_group' && msgItem.events) {
    // Find the last agent_completion event with response_metadata
    for (let i = msgItem.events.length - 1; i >= 0; i--) {
      const event = msgItem.events[i]
      
      let responseMetadata = null
      
      // Check if the event itself has response metadata (new direct attachment)
      if (event.response_metadata) {
        responseMetadata = event.response_metadata
      } else if (event.data?.response_metadata) {
        responseMetadata = event.data.response_metadata
      }
      
      if (responseMetadata) {
        return responseMetadata
      }
    }
  }
  
  // For direct messages, check the message itself (including new direct attachment)
  if (msgItem.response_metadata) {
    return msgItem.response_metadata
  } else if (msgItem.data?.response_metadata) {
    return msgItem.data.response_metadata
  }
  
  // Return null if no response metadata found
  return null
}

// Function to track metrics for a run_id
function trackRunMetrics(runId, tokenUsage, responseMetadata, additionalKwargs = null) {
  if (!runId) return;

  if (!runMetrics.value.has(runId)) {
    runMetrics.value.set(runId, {
      input_tokens: [],
      output_tokens: [],
      total_tokens: [],
      latencies: [],
      ttfts: [],
      throughputs: [],
      event_count: 0,
      models: new Map(), // Track model names and their counts
      workflow_duration: null, // Store workflow-level duration
      model_breakdown: [], // Store per-model breakdown for waterfall
      agent_breakdown: [], // Store per-agent breakdown for hierarchical display
      hierarchical_timing: null // Store complete hierarchical timing structure
    });
  }

  const runData = runMetrics.value.get(runId);

  // Check for workflow timing data in additional_kwargs
  if (additionalKwargs?.workflow_timing) {
    const timing = additionalKwargs.workflow_timing;

    console.log('[TIMING_DEBUG] trackRunMetrics received workflow_timing:', {
      runId: runId,
      has_timing: !!timing,
      workflow_duration: timing.workflow_duration,
      total_llm_calls: timing.total_llm_calls,
      num_levels: timing.levels?.length || 0,
      levels: timing.levels,
      raw_timing: JSON.stringify(timing),
      agent_type: additionalKwargs.agent_type
    });

    runData.workflow_duration = timing.workflow_duration;

    // Store the complete hierarchical timing structure (new format)
    runData.hierarchical_timing = timing;

    console.log('[TIMING_DEBUG] Stored hierarchical_timing in runData:', {
      runId: runId,
      stored_timing: runData.hierarchical_timing,
      total_llm_calls: runData.hierarchical_timing?.total_llm_calls,
      num_levels: runData.hierarchical_timing?.levels?.length || 0
    });

    if (timing.model_breakdown && Array.isArray(timing.model_breakdown)) {
      runData.model_breakdown = timing.model_breakdown;
      // Don't overwrite event_count - keep the live-tracked value for UI display
    }
    if (timing.agent_breakdown && Array.isArray(timing.agent_breakdown)) {
      runData.agent_breakdown = timing.agent_breakdown;
    }

    // LIVE COUNT FIX: If this is a timing message from deep_research_timing or financial_analysis_end agent,
    // use its authoritative deduplicated count instead of live-counted duplicates
    const isTimingMessage = additionalKwargs.agent_type === 'deep_research_timing' ||
                           additionalKwargs.agent_type === 'financial_analysis_end';

    if (isTimingMessage && timing.total_llm_calls) {
      console.log('[LIVE_COUNT_FIX] Detected timing message, using authoritative count:', {
        runId: runId,
        agent_type: additionalKwargs.agent_type,
        authoritative_count: timing.total_llm_calls,
        previous_live_count: runData.event_count,
        will_update_workflowData: true
      });

      // Update the event_count with authoritative deduplicated count
      runData.event_count = timing.total_llm_calls;

      // Update workflowData entries to reflect the correct deduplicated count
      // We need to replace the live-counted values with the authoritative breakdown
      if (timing.model_breakdown && timing.model_breakdown.length > 0) {
        // Clear existing entries for this run
        workflowData.value = workflowData.value.filter(item => item.message_id !== runId);

        // Group model_breakdown by model_name to get per-model counts
        const modelCounts = new Map();
        timing.model_breakdown.forEach(breakdown => {
          const modelName = breakdown.model_name;
          const currentCount = modelCounts.get(modelName) || 0;
          modelCounts.set(modelName, currentCount + 1);
        });

        // Add new entries with correct deduplicated counts
        modelCounts.forEach((count, modelName) => {
          workflowData.value.push({
            llm_name: modelName,
            count: count,
            message_id: runId
          });

          // Also update runData.models to match
          runData.models.set(modelName, count);
        });

        console.log('[LIVE_COUNT_FIX] Updated workflowData with deduplicated counts:', {
          runId: runId,
          agent_type: additionalKwargs.agent_type,
          model_counts: Object.fromEntries(modelCounts),
          workflowData_entries: workflowData.value.filter(item => item.message_id === runId)
        });
      }
    }
  } else {
    console.log('[TIMING_DEBUG] trackRunMetrics NO workflow_timing found:', {
      runId: runId,
      has_additionalKwargs: !!additionalKwargs,
      additionalKwargs_keys: additionalKwargs ? Object.keys(additionalKwargs) : null,
      has_workflow_timing: additionalKwargs?.workflow_timing !== undefined
    });
  }

  // Track token usage
  if (tokenUsage) {
    if (tokenUsage.input_tokens > 0) runData.input_tokens.push(tokenUsage.input_tokens);
    if (tokenUsage.output_tokens > 0) runData.output_tokens.push(tokenUsage.output_tokens);
    if (tokenUsage.total_tokens > 0) runData.total_tokens.push(tokenUsage.total_tokens);
  }

  // Track performance metrics
  if (responseMetadata?.usage) {
    // Check if this is workflow-level timing (has total_latency matching workflow_duration)
    // If so, store it as the workflow duration instead of adding to latencies array
    if (responseMetadata.usage.total_latency > 0) {
      // Store as workflow duration if it's significantly larger than individual LLM calls
      // Or if we don't have a workflow duration yet
      if (!runData.workflow_duration || responseMetadata.usage.total_latency > 5) {
        runData.workflow_duration = responseMetadata.usage.total_latency;
      } else {
        // Otherwise, it's a per-LLM-call latency
        runData.latencies.push(responseMetadata.usage.total_latency);
      }
    }
    if (responseMetadata.usage.time_to_first_token > 0) {
      runData.ttfts.push(responseMetadata.usage.time_to_first_token);
    }
    if (responseMetadata.usage.completion_tokens_per_sec > 0) {
      runData.throughputs.push(responseMetadata.usage.completion_tokens_per_sec);
    }
  }
  
  // DEBUG: Log every message being evaluated for counting
  console.log('[LLM_COUNT_DEBUG] Evaluating message for counting:', {
    runId: runId,
    has_responseMetadata: !!responseMetadata,
    model_name: responseMetadata?.model_name,
    has_additionalKwargs: additionalKwargs !== null && additionalKwargs !== undefined,
    agent_type: additionalKwargs?.agent_type,
    additional_kwargs_keys: additionalKwargs ? Object.keys(additionalKwargs) : null,
    // Try to extract message ID if available
    message_id_from_response: responseMetadata?.id,
    current_count: runData.event_count
  });

  // Only increment event count if event has both response_metadata and model_name, since we are counting llm calls
  // IMPORTANT: Exclude timing messages (they don't have model_name anymore, but keep this check for backwards compatibility)
  const isTimingMessage = additionalKwargs?.agent_type === 'deep_research_timing' ||
                         additionalKwargs?.agent_type === 'financial_analysis_end';

  // SUPER PRECISE FIX: Filter out messages that have model_name but NO additional_kwargs
  // These are duplicate messages that lost their metadata when re-streamed by LangGraph's operator.add
  // Legitimate LLM calls always have additional_kwargs with agent_type or timing metadata
  const hasAdditionalKwargs = additionalKwargs !== null && additionalKwargs !== undefined;
  const isDuplicateWithoutMetadata = !hasAdditionalKwargs;

  // CRITICAL FIX: Filter out batch CrewAI messages from graph state (agent_type === "crewai_llm_call")
  // We already count these live via think events (agent_type === "crewai_think_event")
  // Batch messages arrive at the end and would create duplicates
  const isBatchCrewAIMessage = additionalKwargs?.agent_type === 'crewai_llm_call';

  if (responseMetadata && responseMetadata.model_name && !isTimingMessage && !isDuplicateWithoutMetadata && !isBatchCrewAIMessage) {
    runData.event_count++;

    console.log('[LLM_COUNT_DEBUG] ✅ COUNTED THIS MESSAGE:', {
      runId: runId,
      new_count: runData.event_count,
      model_name: responseMetadata.model_name,
      agent_type: additionalKwargs?.agent_type,
      was_filtered: false
    });

    // Track model usage
    const modelName = responseMetadata.model_name;
    const currentCount = runData.models.get(modelName) || 0;
    runData.models.set(modelName, currentCount + 1);

    // CRITICAL: Also update workflowData array for reactive updates
    // Vue tracks array changes, so updating this will trigger re-renders
    const existingIndex = workflowData.value.findIndex(
      item => item.message_id === runId && item.llm_name === modelName
    );

    if (existingIndex !== -1) {
      // Update existing entry
      workflowData.value[existingIndex].count = currentCount + 1;
    } else {
      // Add new entry
      workflowData.value.push({
        llm_name: modelName,
        count: currentCount + 1,
        message_id: runId
      });
    }
  } else {
    // Log why message was NOT counted
    console.log('[LLM_COUNT_DEBUG] ❌ FILTERED OUT (not counted):', {
      runId: runId,
      reason: !responseMetadata ? 'no responseMetadata' :
              !responseMetadata.model_name ? 'no model_name' :
              isTimingMessage ? 'is timing message' :
              isDuplicateWithoutMetadata ? 'duplicate without metadata (no additional_kwargs)' :
              'unknown',
      model_name: responseMetadata?.model_name,
      agent_type: additionalKwargs?.agent_type,
      isTimingMessage: isTimingMessage,
      isDuplicateWithoutMetadata: isDuplicateWithoutMetadata,
      current_count: runData.event_count
    });
  }
}

// Function to get run summary for display
function getRunSummary(msgItem) {
  console.log('[TIMING_DEBUG] getRunSummary called:', {
    msgItem_type: msgItem.type,
    msgItem_message_id: msgItem.message_id,
    msgItem_keys: Object.keys(msgItem)
  });

  // For final messages, we want to show the summary for the entire conversation turn
  // Find the run ID by looking backwards in messagesData to find the user message that started this turn
  let runId = null;

  if (msgItem.type === 'streaming_group') {
    runId = msgItem.message_id;
  } else {
    // For individual messages, find the conversation turn they belong to
    const currentMessageIndex = messagesData.value.findIndex(msg =>
      msg.message_id === msgItem.message_id ||
      (msg.type === 'streaming_group' && msg.message_id === msgItem.message_id)
    );

    // Look backwards to find the user message that started this conversation turn
    for (let i = currentMessageIndex; i >= 0; i--) {
      const msg = messagesData.value[i];
      const isUserMessage = msg.additional_kwargs?.agent_type === 'human' || 
                           msg.type === 'HumanMessage' ||
                           (msg.type === 'streaming_group' && msg.events?.some(e => 
                             e.additional_kwargs?.agent_type === 'human' || e.type === 'HumanMessage'
                           ));
      
      if (isUserMessage) {
        runId = msg.message_id;
        break;
      }
    }
    
    // Fallback to the message's own ID
    if (!runId) {
      runId = msgItem.message_id;
    }
  }
  

  
  if (!runId || !runMetrics.value.has(runId)) {
    return { input_tokens: 0, output_tokens: 0, total_tokens: 0, event_count: 0 };
  }
  
  const runData = runMetrics.value.get(runId);

  // Calculate sums and averages
  // CRITICAL FIX: Use workflow_duration if available, instead of summing individual latencies
  const summary = {
    input_tokens: runData.input_tokens.reduce((sum, val) => sum + val, 0),
    output_tokens: runData.output_tokens.reduce((sum, val) => sum + val, 0),
    total_tokens: runData.total_tokens.reduce((sum, val) => sum + val, 0),
    total_latency: runData.workflow_duration !== null ? runData.workflow_duration : runData.latencies.reduce((sum, val) => sum + val, 0),
    total_ttft: runData.ttfts.reduce((sum, val) => sum + val, 0),
    avg_latency: runData.latencies.length > 0 ? runData.latencies.reduce((sum, val) => sum + val, 0) / runData.latencies.length : 0,
    avg_throughput: runData.throughputs.length > 0 ? runData.throughputs.reduce((sum, val) => sum + val, 0) / runData.throughputs.length : 0,
    event_count: runData.event_count,
    model_breakdown: runData.model_breakdown || [], // Include model breakdown for waterfall viz
    agent_breakdown: runData.agent_breakdown || [], // Include agent breakdown for hierarchical display
    hierarchical_timing: runData.hierarchical_timing || null  // Include new hierarchical timing structure
  };

  console.log('[TIMING_DEBUG] getRunSummary returning:', {
    runId: runId,
    has_hierarchical_timing: !!summary.hierarchical_timing,
    hierarchical_timing: summary.hierarchical_timing,
    total_llm_calls: summary.hierarchical_timing?.total_llm_calls,
    num_levels: summary.hierarchical_timing?.levels?.length || 0,
    levels: summary.hierarchical_timing?.levels
  });

  return summary;
}

// Get model data from workflowData array for display
// Using the reactive array instead of Map ensures Vue detects changes
function getModelData(message_id) {
  const runId = message_id || currentMsgId.value;

  if (!runId) {
    return [];
  }

  // Filter workflowData array by message_id
  // Vue tracks array access, so this will be reactive!
  return workflowData.value.filter(item => item.message_id === runId);
}

// File utility functions
function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + sizes[i];
}

function getFileIcon(format, filename = '') {
  if (!format && !filename) return DocumentIcon;
  
  const type = (format || '').toLowerCase();
  const name = (filename || '').toLowerCase();
  
  if (type.includes('pdf') || name.includes('.pdf')) {
    return DocumentTextIcon;
  } else if (type.includes('image') || type.includes('jpeg') || type.includes('png') || type.includes('gif') || type.includes('webp') ||
             name.includes('.jpg') || name.includes('.jpeg') || name.includes('.png') || name.includes('.gif') || name.includes('.webp')) {
    return PhotoIcon;
  } else if (type.includes('csv') || type.includes('excel') || type.includes('sheet') || name.includes('.csv') || name.includes('.xlsx') || name.includes('.xls')) {
    return TableCellsIcon;
  } else if (type.includes('json') || name.includes('.json')) {
    return CodeBracketIcon;
  } else if (type.includes('text') || type.includes('txt') || name.includes('.txt') || name.includes('.md') || type.includes('markdown')) {
    return DocumentTextIcon;
  } else {
    return DocumentIcon;
  }
}

function getFileIconBackground(format, filename = '') {
  if (!format && !filename) return 'bg-gray-100';
  
  const type = (format || '').toLowerCase();
  const name = (filename || '').toLowerCase();
  
  if (type.includes('pdf') || name.includes('.pdf')) {
    return 'bg-red-100';
  } else if (type.includes('image') || type.includes('jpeg') || type.includes('png') || type.includes('gif') || type.includes('webp') ||
             name.includes('.jpg') || name.includes('.jpeg') || name.includes('.png') || name.includes('.gif') || name.includes('.webp')) {
    return 'bg-green-100';
  } else if (type.includes('csv') || type.includes('excel') || type.includes('sheet') || name.includes('.csv') || name.includes('.xlsx') || name.includes('.xls')) {
    return 'bg-emerald-100';
  } else if (type.includes('json') || name.includes('.json')) {
    return 'bg-blue-100';
  } else if (type.includes('text') || type.includes('txt') || name.includes('.txt') || name.includes('.md') || type.includes('markdown')) {
    return 'bg-yellow-100';
  } else {
    return 'bg-gray-100';
  }
}

function getFileIconColor(format, filename = '') {
  if (!format && !filename) return 'text-gray-600';
  
  const type = (format || '').toLowerCase();
  const name = (filename || '').toLowerCase();
  
  if (type.includes('pdf') || name.includes('.pdf')) {
    return 'text-red-600';
  } else if (type.includes('image') || type.includes('jpeg') || type.includes('png') || type.includes('gif') || type.includes('webp') ||
             name.includes('.jpg') || name.includes('.jpeg') || name.includes('.png') || name.includes('.gif') || name.includes('.webp')) {
    return 'text-green-600';
  } else if (type.includes('csv') || type.includes('excel') || type.includes('sheet') || name.includes('.csv') || name.includes('.xlsx') || name.includes('.xls')) {
    return 'text-emerald-600';
  } else if (type.includes('json') || name.includes('.json')) {
    return 'text-blue-600';
  } else if (type.includes('text') || type.includes('txt') || name.includes('.txt') || name.includes('.md') || type.includes('markdown')) {
    return 'text-yellow-600';
  } else {
    return 'text-gray-600';
  }
}

function isImageFile(format, filename = '') {
  if (!format && !filename) return false;
  
  const type = (format || '').toLowerCase();
  const name = (filename || '').toLowerCase();
  
  return type.includes('image') || type.includes('jpeg') || type.includes('png') || type.includes('gif') || type.includes('webp') ||
         name.includes('.jpg') || name.includes('.jpeg') || name.includes('.png') || name.includes('.gif') || name.includes('.webp');
}

async function viewGeneratedFile(doc) {
  // Check if we can preview the file inline (like DaytonaSidebar does)
  const previewableTypes = ['image', 'pdf', 'csv', 'markdown', 'html'];
  const fileType = getGeneratedFileType(doc.format, doc.filename);
  
  if (previewableTypes.includes(fileType)) {
    // Create a preview artifact and emit to open in sidebar/modal
    let fileUrl;
    let downloadUrl;
    
    // Use different endpoint based on whether this is a shared conversation
    if (isSharedConversation.value && shareToken.value) {
      // Use the public shared file endpoint
      fileUrl = `${import.meta.env.VITE_API_URL}/share/${shareToken.value}/files/${doc.file_id}`;
      downloadUrl = fileUrl;
    } else {
      // Use the authenticated endpoint
      fileUrl = `${import.meta.env.VITE_API_URL}/files/${doc.file_id}`;
      downloadUrl = fileUrl;
    }
    
    const artifact = {
      id: doc.file_id,
      title: doc.filename,
      type: fileType,
      url: fileUrl,
      loading: true,
      downloadUrl: downloadUrl,
      preview: null
    };
    
    // Emit to parent to handle preview (could open Daytona sidebar or artifact canvas)
    emit('open-artifact-canvas', artifact);
  } else {
    // For non-previewable files, download directly
    await downloadFile(doc);
  }
}

async function downloadFile(doc) {
  try {
    const response = await axios.get(
      `${import.meta.env.VITE_API_URL}/files/${doc.file_id}`,
      {
        headers: {
          Authorization: `Bearer ${await getAccessTokenSilently()}`,
        },
        responseType: 'blob'
      }
    );
    
    if (!response.data) {
      throw new Error('No file data received');
    }
    
    // Create download link using the same approach as DaytonaSidebar
    const blob = new Blob([response.data]);
    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    
    // Use original filename with proper extension
    const extension = getFileExtensionFromFormat(doc.format);
    const filename = doc.filename.includes('.') ? doc.filename : `${doc.filename}.${extension}`;
    link.download = filename;
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(blobUrl);
   
    
  } catch (error) {
    console.error('Error downloading file:', error);
    uploadStatus.value = {
      type: 'error',
      message: `Failed to download ${doc.filename}: ${error.response?.data?.error || error.message}`
    };
    
    // Clear error after 5 seconds
    setTimeout(() => {
      uploadStatus.value = null;
    }, 5000);
  }
}

function getGeneratedFileType(format, filename) {
  if (!format && !filename) return 'unknown';
  
  const type = (format || '').toLowerCase();
  const name = (filename || '').toLowerCase();
  
  if (type.includes('pdf') || name.includes('.pdf')) {
    return 'pdf';
  } else if (type.includes('image') || type.includes('jpeg') || type.includes('png') || type.includes('gif') || type.includes('webp') ||
             name.includes('.jpg') || name.includes('.jpeg') || name.includes('.png') || name.includes('.gif') || name.includes('.webp')) {
    return 'image';
  } else if (type.includes('csv') || name.includes('.csv')) {
    return 'csv';
  } else if (type.includes('markdown') || name.includes('.md')) {
    return 'markdown';
  } else if (type.includes('html') || name.includes('.html') || name.includes('.htm')) {
    return 'html';
  } else if (type.includes('powerpoint') || type.includes('presentation') || 
             name.includes('.ppt') || name.includes('.pptx')) {
    return 'powerpoint';
  } else {
    return 'unknown';
  }
}

function getFileExtensionFromFormat(format) {
  if (!format) return 'txt';
  
  const type = format.toLowerCase();
  const extensions = {
    'application/pdf': 'pdf',
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/gif': 'gif',
    'image/webp': 'webp',
    'text/csv': 'csv',
    'text/markdown': 'md',
    'text/html': 'html',
    'application/vnd.ms-powerpoint': 'ppt',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx'
  };
  
  return extensions[type] || 'txt';
}


</script>

<style scoped>
/* New message enter/leave transitions */
.chat-enter-from,
.chat-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
.chat-enter-active,
.chat-leave-active {
  transition: all 0.3s ease;
}

/* Extra small text size */
.text-2xs {
  font-size: 0.625rem; /* 10px */
  line-height: 0.75rem; /* 12px */
}

/* Ensure consistent file icon sizes */
.file-icon-container {
  transition: all 0.2s ease;
}

.file-icon-container:hover {
  transform: scale(1.05);
}
</style>