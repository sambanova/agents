<template>
  <div
    v-if="isOpen"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 backdrop-blur-sm"
    @click.self="$emit('close')"
  >
    <div class="bg-white rounded-lg shadow-lg max-w-5xl w-full max-h-[90vh] overflow-hidden border border-primary-brandFrame">
      <!-- Header - White background with purple text -->
      <div class="relative bg-white px-6 py-4 border-b border-primary-brandFrame">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-xl font-bold text-primary-brandColor">Latency Breakdown</h2>
            <p class="text-sm text-primary-brandTextSecondary mt-0.5">Detailed timing analysis for this workflow</p>
          </div>
          <button
            @click="$emit('close')"
            class="text-primary-brandTextSecondary hover:text-primary-brandColor p-2 rounded-md"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Content -->
      <div class="px-6 py-5 overflow-y-auto max-h-[calc(90vh-180px)]">
        <!-- Total Duration Summary Card -->
        <div class="mb-6 p-4 rounded-lg border border-primary-brandFrame">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-3">
              <div class="p-2.5 bg-primary-brandColor bg-opacity-10 rounded-lg">
                <svg class="w-5 h-5 text-primary-brandColor" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <span class="text-xs font-medium text-primary-brandTextSecondary">Total Workflow Duration</span>
                <div class="flex items-baseline space-x-2 mt-0.5">
                  <span class="text-2xl font-bold text-primary-bodyText">{{ workflowDuration.toFixed(2) }}</span>
                  <span class="text-sm font-medium text-primary-brandTextSecondary">seconds</span>
                </div>
              </div>
            </div>
            <div class="flex items-center gap-6">
              <div class="text-right">
                <div class="text-xs font-medium text-primary-brandTextSecondary">Total LLM Calls</div>
                <div class="text-xl font-bold text-primary-brandColor mt-0.5">{{ totalLLMCalls }}</div>
                <div v-if="totalLLMTime > 0" class="text-xs text-gray-500 mt-0.5">{{ totalLLMTime.toFixed(2) }}s</div>
              </div>
              <div v-if="toolTimings.length > 0" class="text-right">
                <div class="text-xs font-medium text-primary-brandTextSecondary">Total Tool Calls</div>
                <div class="text-xl font-bold text-orange-600 mt-0.5">{{ toolTimings.length }}</div>
                <div v-if="totalToolTime > 0" class="text-xs text-gray-500 mt-0.5">{{ totalToolTime.toFixed(2) }}s</div>
              </div>
            </div>
          </div>
        </div>

        <!-- View Mode Toggle -->
        <div v-if="showHierarchical" class="mb-4 flex items-center justify-between bg-gray-50 rounded-lg p-2">
          <span class="text-sm font-medium text-gray-700">Timeline View:</span>
          <div class="inline-flex rounded-lg border border-gray-200 bg-white">
            <button
              @click="viewMode = 'integrated'"
              class="px-4 py-1.5 text-sm font-medium rounded-l-lg transition-colors"
              :class="viewMode === 'integrated' ? 'bg-primary-brandColor text-white' : 'text-gray-700 hover:bg-gray-50'"
            >
              Integrated
            </button>
            <button
              @click="viewMode = 'separated'"
              class="px-4 py-1.5 text-sm font-medium rounded-r-lg transition-colors"
              :class="viewMode === 'separated' ? 'bg-primary-brandColor text-white' : 'text-gray-700 hover:bg-gray-50'"
            >
              Separated
            </button>
          </div>
        </div>

        <!-- INTEGRATED VIEW: All events chronologically (LangSmith-style) -->
        <div v-if="viewMode === 'integrated' && showHierarchical" class="mb-6">
          <h3 class="text-base font-bold text-primary-bodyText mb-3 flex items-center">
            <svg class="w-4 h-4 mr-2 text-primary-brandColor" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Complete Workflow Timeline
            <span class="ml-2 text-sm text-gray-500">({{ integratedTimeline.length }} total events)</span>
          </h3>

          <!-- Event type legend -->
          <div class="flex items-center space-x-4 text-xs mb-3 pb-2 border-b border-gray-200">
            <div class="flex items-center space-x-1.5">
              <div class="w-3 h-3 rounded-sm bg-primary-brandColor bg-opacity-90"></div>
              <span class="text-gray-600">LLM Calls ({{ hierarchicalTiming.total_llm_calls }})</span>
            </div>
            <div class="flex items-center space-x-1.5">
              <div class="w-3 h-3 rounded-sm bg-orange-500 bg-opacity-85"></div>
              <span class="text-gray-600">Tool Calls ({{ toolTimings.length }} total{{ numParallelGroups > 0 ? `, ${numParallelGroups} parallel ${numParallelGroups === 1 ? 'call' : 'calls'} calling ${parallelToolCount} ${parallelToolCount === 1 ? 'tool' : 'tools'}` : '' }})</span>
            </div>
          </div>

          <!-- Time Scale Ruler -->
          <div class="relative h-6 mb-1 border-b border-gray-300">
            <div
              v-for="(marker, idx) in timeScaleMarkers"
              :key="idx"
              class="absolute flex flex-col items-center"
              :style="{ left: `${marker.position}%`, transform: 'translateX(-50%)' }"
            >
              <!-- Tick mark -->
              <div class="w-px h-2 bg-gray-400"></div>
              <!-- Time label -->
              <span class="text-xs text-gray-500 mt-0.5">{{ marker.label }}</span>
            </div>
          </div>

          <!-- Compact waterfall timeline -->
          <div class="space-y-1">
            <div
              v-for="(event, idx) in integratedTimeline"
              :key="idx"
              class="relative"
            >
              <!-- LLM Call Event - Compact single row -->
              <div v-if="event.type === 'llm_call'" class="flex items-center h-8">
                <!-- Waterfall container -->
                <div class="flex-1 relative h-8 bg-gray-50 rounded-sm overflow-visible">
                  <!-- LLM Bar with content inside -->
                  <div
                    class="absolute h-full rounded-sm flex items-center px-2 bg-purple-200"
                    :style="{
                      left: `${(event.start_offset / workflowDuration) * 100}%`,
                      width: `${Math.max(2, (event.duration / workflowDuration) * 100)}%`
                    }"
                  >
                    <!-- Content INSIDE bar with dark text -->
                    <div class="flex items-center space-x-1.5 text-gray-800 text-xs font-medium whitespace-nowrap">
                      <svg class="w-3 h-3 flex-shrink-0 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                      </svg>
                      <span>{{ event.model_name }}</span>
                      <span class="text-gray-600">- {{ event.duration.toFixed(2) }}s</span>
                    </div>
                  </div>
                </div>

                <!-- Percentage on right -->
                <div class="w-12 text-xs text-primary-brandColor text-right pl-2">
                  {{ event.percentage ? event.percentage.toFixed(1) + '%' : '' }}
                </div>
              </div>

              <!-- Tool Call Event - Compact single row -->
              <div v-else class="flex items-center h-8">
                <!-- Waterfall container -->
                <div class="flex-1 relative h-8 bg-gray-50 rounded-sm overflow-visible">
                  <!-- Tool Bar with content inside -->
                  <div
                    class="absolute h-full rounded-sm flex items-center px-2"
                    :class="event.is_subgraph ? 'bg-blue-200' : 'bg-orange-200'"
                    :style="{
                      left: `${(event.start_offset / workflowDuration) * 100}%`,
                      width: `${Math.max(2, (event.duration / workflowDuration) * 100)}%`
                    }"
                  >
                    <!-- Content INSIDE bar with dark text -->
                    <div class="flex items-center space-x-1.5 text-gray-800 text-xs font-medium whitespace-nowrap">
                      <svg class="w-3 h-3 flex-shrink-0 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
                      </svg>
                      <span>{{ event.tool_name }}</span>
                      <span class="text-gray-600">- {{ event.duration.toFixed(2) }}s</span>
                    </div>
                  </div>
                </div>

                <!-- Percentage on right (like LLM calls) -->
                <div class="w-12 text-xs text-orange-600 text-right pl-2">
                  {{ event.percentage ? event.percentage.toFixed(1) + '%' : '' }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- SEPARATED VIEW: Original layout with LLM calls and tools in separate sections -->
        <div v-if="viewMode === 'separated'">

        <!-- Hierarchical Workflow Breakdown (LangSmith-style) -->
        <div v-if="showHierarchical" class="mb-6">
          <h3 class="text-base font-bold text-primary-bodyText mb-3 flex items-center">
            <svg class="w-4 h-4 mr-2 text-primary-brandColor" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7" />
            </svg>
            Workflow Hierarchy
          </h3>

          <div class="space-y-4">
            <!-- Iterate through levels (main_agent, subgraph, etc.) -->
            <div
              v-for="(level, levelIndex) in hierarchicalTiming.levels"
              :key="levelIndex"
              class="border border-gray-200 rounded-lg overflow-hidden border-l-4"
              :class="level.level === 'main_agent' ? 'border-l-primary-brandColor' : 'border-l-blue-700'"
            >
              <!-- Main Agent Level -->
              <div v-if="level.level === 'main_agent'">
                <button
                  @click="toggleLevel(levelIndex)"
                  class="w-full px-4 py-3 bg-gray-50 hover:bg-gray-100 flex items-center justify-between"
                >
                  <div class="flex items-center space-x-3">
                    <svg
                      class="w-4 h-4 text-primary-brandColor"
                      :class="{ 'rotate-90': expandedLevels[levelIndex] }"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                    <span class="text-sm font-semibold text-primary-bodyText">Main Agent</span>
                    <span class="text-xs text-primary-brandTextSecondary">{{ level.num_calls }} {{ level.num_calls === 1 ? 'call' : 'calls' }}</span>
                  </div>
                  <div class="flex items-center space-x-3">
                    <span class="text-xs font-medium text-primary-brandColor">{{ calculateLevelDuration(level).toFixed(2) }}s</span>
                    <span class="text-xs font-medium text-primary-brandTextSecondary">Level 1</span>
                  </div>
                </button>

                <!-- Main Agent LLM Calls -->
                <div v-show="expandedLevels[levelIndex]" class="px-4 py-3 bg-white">
                  <!-- Time Scale Ruler -->
                  <div class="relative h-6 mb-1 border-b border-gray-300">
                    <div
                      v-for="(marker, idx) in timeScaleMarkers"
                      :key="idx"
                      class="absolute flex flex-col items-center"
                      :style="{ left: `${marker.position}%`, transform: 'translateX(-50%)' }"
                    >
                      <!-- Tick mark -->
                      <div class="w-px h-2 bg-gray-400"></div>
                      <!-- Time label -->
                      <span class="text-xs text-gray-500 mt-0.5">{{ marker.label }}</span>
                    </div>
                  </div>

                  <div class="space-y-1">
                  <div
                    v-for="(call, callIndex) in level.llm_calls"
                    :key="callIndex"
                    class="flex items-center h-8"
                  >
                    <!-- Waterfall container -->
                    <div class="flex-1 relative h-8 bg-gray-50 rounded-sm overflow-visible">
                      <!-- LLM Bar with content inside -->
                      <div
                        v-if="call.duration > 0 && call.start_offset !== undefined && call.start_offset !== null"
                        class="absolute h-full rounded-sm flex items-center px-2 bg-purple-200"
                        :style="{
                          left: `${Math.max(0, (call.start_offset / workflowDuration) * 100)}%`,
                          width: `${Math.max(2, (call.duration / workflowDuration) * 100)}%`
                        }"
                      >
                        <!-- Content INSIDE bar with dark text -->
                        <div class="flex items-center space-x-1.5 text-gray-800 text-xs font-medium whitespace-nowrap">
                          <svg class="w-3 h-3 flex-shrink-0 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                          </svg>
                          <span>{{ call.model_name }}</span>
                          <span class="text-gray-600">- {{ call.duration.toFixed(2) }}s</span>
                        </div>
                      </div>
                      <!-- Debug: Show warning if bar can't render -->
                      <div v-else class="text-xs text-gray-400 px-2 py-1">
                        ⚠️ Missing timing data (duration: {{ call.duration }}, start_offset: {{ call.start_offset }})
                      </div>
                    </div>

                    <!-- Percentage on right -->
                    <div class="w-12 text-xs text-primary-brandColor text-right pl-2">
                      {{ call.percentage ? call.percentage.toFixed(1) + '%' : '' }}
                    </div>
                  </div>
                  </div>
                </div>
              </div>

              <!-- Subgraph Level -->
              <div v-if="level.level === 'subgraph'">
                <button
                  @click="toggleLevel(levelIndex)"
                  class="w-full px-4 py-3 bg-gray-100 hover:bg-gray-200 flex items-center justify-between"
                >
                  <div class="flex items-center space-x-3">
                    <svg
                      class="w-4 h-4 text-primary-700"
                      :class="{ 'rotate-90': expandedLevels[levelIndex] }"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                    <span class="text-sm font-semibold text-primary-bodyText">{{ level.subgraph_name }}</span>
                    <span class="text-xs text-primary-brandTextSecondary">{{ level.num_llm_calls }} LLM {{ level.num_llm_calls === 1 ? 'call' : 'calls' }}</span>
                  </div>
                  <div class="flex items-center space-x-3">
                    <span class="text-xs font-medium text-primary-700">{{ level.subgraph_duration.toFixed(2) }}s</span>
                    <span class="text-xs font-medium text-primary-brandTextSecondary">Level 2</span>
                  </div>
                </button>

                <!-- Subgraph Agent Breakdown -->
                <div v-show="expandedLevels[levelIndex]" class="bg-gray-50 p-4 pl-8">
                  <div v-if="level.agent_breakdown && level.agent_breakdown.length > 0" class="space-y-3">
                    <div
                      v-for="(agent, agentIndex) in level.agent_breakdown"
                      :key="agentIndex"
                      class="border border-gray-200 rounded-lg overflow-hidden bg-white"
                    >
                      <!-- Agent Header -->
                      <button
                        @click="toggleSubgraphAgent(levelIndex, agentIndex)"
                        class="w-full px-4 py-2 bg-gray-50 hover:bg-gray-100 flex items-center justify-between"
                      >
                        <div class="flex items-center space-x-3">
                          <svg
                            class="w-3 h-3 text-primary-brandColor"
                            :class="{ 'rotate-90': expandedAgents[`${levelIndex}-${agentIndex}`] }"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                          </svg>
                          <span class="text-xs font-semibold text-primary-bodyText">{{ agent.agent_name }}</span>
                          <span class="text-xs text-primary-brandTextSecondary">{{ agent.num_calls }} {{ agent.num_calls === 1 ? 'call' : 'calls' }}</span>
                        </div>
                        <div class="flex items-center space-x-3">
                          <span class="text-xs font-medium text-primary-brandColor">{{ agent.total_duration.toFixed(2) }}s</span>
                          <span class="text-xs font-semibold text-primary-brandColor">{{ agent.percentage.toFixed(1) }}%</span>
                        </div>
                      </button>

                      <!-- Agent Calls -->
                      <div v-show="expandedAgents[`${levelIndex}-${agentIndex}`]" class="px-4 py-2 bg-white space-y-1">
                        <div
                          v-for="(call, callIndex) in agent.calls"
                          :key="callIndex"
                          class="flex items-center h-8"
                        >
                          <!-- Waterfall container -->
                          <div class="flex-1 relative h-8 bg-gray-50 rounded-sm overflow-visible">
                            <!-- LLM Bar with content inside -->
                            <div
                              class="absolute h-full rounded-sm flex items-center px-2 bg-blue-200"
                              :style="{
                                left: `${(call.start_offset / workflowDuration) * 100}%`,
                                width: `${Math.max(2, (call.duration / workflowDuration) * 100)}%`
                              }"
                            >
                              <!-- Content INSIDE bar with dark text -->
                              <div class="flex items-center space-x-1.5 text-gray-800 text-xs font-medium whitespace-nowrap">
                                <svg class="w-3 h-3 flex-shrink-0 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                                </svg>
                                <span>{{ call.model_name }}</span>
                                <span class="text-gray-600">- {{ call.duration.toFixed(2) }}s</span>
                              </div>
                            </div>
                          </div>

                          <!-- Percentage on right -->
                          <div class="w-12 text-xs text-blue-600 text-right pl-2">
                            {{ call.percentage ? call.percentage.toFixed(1) + '%' : '' }}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Tool Calls Timeline Section (for hierarchical timing only) -->
        <div v-if="showHierarchical && toolTimings.length > 0" class="mb-6">
          <div class="border border-gray-200 rounded-lg overflow-hidden border-l-4 border-l-orange-600">
          <button
            @click="toggleToolsSection"
            class="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100"
          >
            <div class="flex items-center justify-between flex-1">
              <div class="flex items-center space-x-2">
                <svg class="w-5 h-5 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
                </svg>
                <span class="text-base font-bold text-primary-bodyText">Tool Calls Timeline</span>
                <span class="text-sm text-primary-brandTextSecondary">
                  ({{ toolTimings.length }} total{{ numParallelGroups > 0 ? `, ${numParallelGroups} parallel ${numParallelGroups === 1 ? 'call' : 'calls'} calling ${parallelToolCount} ${parallelToolCount === 1 ? 'tool' : 'tools'}` : '' }})
                </span>
              </div>
              <span class="text-xs font-medium text-orange-600 mr-2">{{ totalToolTime.toFixed(2) }}s</span>
            </div>
            <svg
              class="w-5 h-5 text-primary-brandColor transition-transform"
              :class="{ 'rotate-180': expandedToolsSection }"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          <div v-show="expandedToolsSection" class="px-4 py-3 bg-white">
            <!-- Time Scale Ruler -->
            <div class="relative h-6 mb-1 border-b border-gray-300">
              <div
                v-for="(marker, idx) in timeScaleMarkers"
                :key="idx"
                class="absolute flex flex-col items-center"
                :style="{ left: `${marker.position}%`, transform: 'translateX(-50%)' }"
              >
                <!-- Tick mark -->
                <div class="w-px h-2 bg-gray-400"></div>
                <!-- Time label -->
                <span class="text-xs text-gray-500 mt-0.5">{{ marker.label }}</span>
              </div>
            </div>

            <div class="space-y-1">
            <div
              v-for="(tool, idx) in toolTimings"
              :key="idx"
              class="relative"
            >
              <div class="flex items-center h-8">
                <!-- Waterfall container -->
                <div class="flex-1 relative h-8 bg-gray-50 rounded-sm overflow-visible">
                  <!-- Tool Bar with content inside -->
                  <div
                    class="absolute h-full rounded-sm flex items-center px-2"
                    :class="tool.is_subgraph ? 'bg-blue-200' : 'bg-orange-200'"
                    :style="{
                      left: `${(tool.start_offset / workflowDuration) * 100}%`,
                      width: `${Math.max(2, (tool.duration / workflowDuration) * 100)}%`
                    }"
                  >
                    <!-- Content INSIDE bar with dark text -->
                    <div class="flex items-center space-x-1.5 text-gray-800 text-xs font-medium whitespace-nowrap">
                      <svg class="w-3 h-3 flex-shrink-0 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
                      </svg>
                      <span>{{ tool.tool_name }}</span>
                      <span class="text-gray-600">- {{ tool.duration.toFixed(2) }}s</span>
                      <span v-if="tool.parallel_group" class="text-gray-600">• P{{ tool.parallel_group }}</span>
                    </div>
                  </div>
                </div>

                <!-- Percentage on right -->
                <div class="w-12 text-xs text-orange-600 text-right pl-2">
                  {{ (tool.duration && workflowDuration) ? ((tool.duration / workflowDuration) * 100).toFixed(1) + '%' : '' }}
                </div>
              </div>
            </div>
            </div>
          </div>
          </div>
        </div>

        <!-- Agent-Based Breakdown (if available) -->
        <div v-else-if="agentBreakdown.length > 0" class="mb-6">
          <h3 class="text-base font-bold text-primary-bodyText mb-3 flex items-center">
            <svg class="w-4 h-4 mr-2 text-primary-brandColor" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            Agent Timeline
          </h3>

          <div class="space-y-4">
            <div
              v-for="(agent, index) in agentBreakdown"
              :key="index"
              class="border border-gray-200 rounded-lg overflow-hidden border-l-4"
              :style="{ borderLeftColor: getAgentColor(index) }"
            >
              <!-- Agent Header -->
              <button
                @click="toggleAgent(index)"
                class="w-full px-4 py-3 bg-gray-50 hover:bg-gray-100 flex items-center justify-between"
              >
                <div class="flex items-center space-x-3">
                  <svg
                    class="w-4 h-4 text-primary-brandColor"
                    :class="{ 'rotate-90': expandedAgents[index] }"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                  </svg>
                  <span class="text-sm font-semibold text-primary-bodyText">{{ agent.agent_name }}</span>
                  <span class="text-xs text-primary-brandTextSecondary">{{ agent.num_calls }} {{ agent.num_calls === 1 ? 'call' : 'calls' }}</span>
                </div>
                <div class="flex items-center space-x-3">
                  <span class="text-xs font-medium text-primary-brandColor">{{ agent.total_duration.toFixed(2) }}s</span>
                  <span class="text-xs font-semibold text-primary-brandColor">{{ agent.percentage.toFixed(1) }}%</span>
                </div>
              </button>

              <!-- Agent Calls (Collapsible) -->
              <div v-show="expandedAgents[index]" class="px-4 py-3 bg-white space-y-1">
                <div
                  v-for="(call, callIndex) in agent.calls"
                  :key="callIndex"
                  class="flex items-center h-8"
                >
                  <!-- Waterfall container -->
                  <div class="flex-1 relative h-8 bg-gray-50 rounded-sm overflow-visible">
                    <!-- LLM Bar with content inside -->
                    <div
                      class="absolute h-full rounded-sm flex items-center px-2 bg-purple-200"
                      :style="{
                        left: `${(call.start_offset / workflowDuration) * 100}%`,
                        width: `${Math.max(2, (call.duration / workflowDuration) * 100)}%`
                      }"
                    >
                      <!-- Content INSIDE bar with dark text -->
                      <div class="flex items-center space-x-1.5 text-gray-800 text-xs font-medium whitespace-nowrap">
                        <svg class="w-3 h-3 flex-shrink-0 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        <span>{{ call.model_name }}</span>
                        <span class="text-gray-600">- {{ call.duration.toFixed(2) }}s</span>
                      </div>
                    </div>
                  </div>

                  <!-- Percentage on right -->
                  <div class="w-12 text-xs text-primary-brandColor text-right pl-2">
                    {{ call.percentage ? call.percentage.toFixed(1) + '%' : '' }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Fallback: Flat Model Breakdown (if no agent breakdown) -->
        <div v-else-if="modelBreakdown.length > 0" class="mb-6">
          <h3 class="text-base font-bold text-primary-bodyText mb-3 flex items-center">
            <svg class="w-4 h-4 mr-2 text-primary-brandColor" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Model Calls Timeline
          </h3>

          <div class="space-y-1">
            <div
              v-for="(model, index) in modelBreakdown"
              :key="index"
              class="flex items-center h-8"
            >
              <!-- Waterfall container -->
              <div class="flex-1 relative h-8 bg-gray-50 rounded-sm overflow-visible">
                <!-- LLM Bar with content inside -->
                <div
                  class="absolute h-full rounded-sm flex items-center px-2 bg-purple-200"
                  :style="{
                    left: `${(model.start_offset / workflowDuration) * 100}%`,
                    width: `${Math.max(2, (model.duration / workflowDuration) * 100)}%`
                  }"
                >
                  <!-- Content INSIDE bar with dark text -->
                  <div class="flex items-center space-x-1.5 text-gray-800 text-xs font-medium whitespace-nowrap">
                    <svg class="w-3 h-3 flex-shrink-0 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    <span>{{ model.model_name }}</span>
                    <span class="text-gray-600">- {{ model.duration.toFixed(2) }}s</span>
                  </div>
                </div>
              </div>

              <!-- Percentage on right -->
              <div class="w-12 text-xs text-primary-brandColor text-right pl-2">
                {{ model.percentage ? model.percentage.toFixed(1) + '%' : '' }}
              </div>
            </div>
          </div>
        </div>

        </div>
        <!-- End of SEPARATED VIEW -->
      </div>

      <!-- Footer -->
      <div class="px-6 py-4 border-t border-primary-brandFrame bg-primary-brandGray flex items-center justify-end">
        <button
          @click="$emit('close')"
          class="px-5 py-2 bg-primary-brandColor hover:bg-primary-700 text-white font-medium rounded-lg"
        >
          Close
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false
  },
  totalDuration: {
    type: Number,
    default: 0
  },
  modelBreakdown: {
    type: Array,
    default: () => []
  },
  agentBreakdown: {
    type: Array,
    default: () => []
  },
  hierarchicalTiming: {
    type: Object,
    default: null
  }
});

defineEmits(['close']);

// Computed properties for hierarchical timing
const showHierarchical = computed(() => {
  return props.hierarchicalTiming &&
         props.hierarchicalTiming.levels &&
         props.hierarchicalTiming.levels.length > 0;
});

const workflowDuration = computed(() => {
  return showHierarchical.value
    ? props.hierarchicalTiming.workflow_duration
    : props.totalDuration;
});

const totalLLMCalls = computed(() => {
  return showHierarchical.value
    ? props.hierarchicalTiming.total_llm_calls
    : props.modelBreakdown.length;
});

// Total LLM calling time (sum of all LLM durations)
const totalLLMTime = computed(() => {
  if (!showHierarchical.value) {
    // Fallback to modelBreakdown if available
    return props.modelBreakdown.reduce((sum, model) => sum + (model.duration || 0), 0);
  }

  let total = 0;

  // Sum all LLM calls from all levels
  props.hierarchicalTiming.levels?.forEach(level => {
    if (level.level === 'main_agent' && level.llm_calls) {
      total += level.llm_calls.reduce((sum, call) => sum + call.duration, 0);
    } else if (level.level === 'subgraph' && level.model_breakdown) {
      total += level.model_breakdown.reduce((sum, call) => sum + call.duration, 0);
    }
  });

  return total;
});

// Track which agents/levels are expanded
const expandedAgents = ref({});
const expandedLevels = ref({});
const expandedToolsSection = ref(true); // Expanded by default

// View mode toggle for integrated vs separated timeline
const viewMode = ref('separated'); // 'separated' or 'integrated'

// Computed properties for tool timings
const toolTimings = computed(() => {
  if (!props.hierarchicalTiming?.tool_timings) return [];
  return props.hierarchicalTiming.tool_timings;
});

const numParallelGroups = computed(() => {
  return props.hierarchicalTiming?.num_parallel_groups || 0;
});

const parallelToolCount = computed(() => {
  return props.hierarchicalTiming?.parallel_tool_calls || 0;
});

// Total tool calling time (sum of all tool durations)
const totalToolTime = computed(() => {
  if (!props.hierarchicalTiming?.tool_timings) return 0;
  return props.hierarchicalTiming.tool_timings.reduce((sum, tool) => sum + tool.duration, 0);
});

// Integrated timeline combining LLM calls and tool calls chronologically
const integratedTimeline = computed(() => {
  if (!showHierarchical.value) return [];

  const events = [];

  // Add all main agent LLM calls
  props.hierarchicalTiming.levels.forEach(level => {
    if (level.level === 'main_agent' && level.llm_calls) {
      level.llm_calls.forEach(call => {
        events.push({
          type: 'llm_call',
          category: 'Main Agent',
          ...call,
        });
      });
    }
    // Add subgraph LLM calls
    if (level.level === 'subgraph' && level.model_breakdown) {
      level.model_breakdown.forEach(call => {
        events.push({
          type: 'llm_call',
          category: level.subgraph_name,
          ...call,
        });
      });
    }
  });

  // Add all tool calls
  toolTimings.value.forEach(tool => {
    events.push({
      type: 'tool_call',
      percentage: (tool.duration / workflowDuration.value) * 100,  // Calculate percentage for tools
      ...tool,
    });
  });

  // Sort chronologically by start_offset
  return events.sort((a, b) => a.start_offset - b.start_offset);
});

// Time scale markers for waterfall timeline
const timeScaleMarkers = computed(() => {
  const duration = workflowDuration.value;
  if (duration === 0) return [];

  // Determine appropriate time increment based on duration
  let increment;
  if (duration < 5) {
    increment = 1;  // 1s increments for very short workflows
  } else if (duration < 15) {
    increment = 2;  // 2s increments
  } else if (duration < 30) {
    increment = 5;  // 5s increments
  } else if (duration < 60) {
    increment = 10;  // 10s increments
  } else if (duration < 120) {
    increment = 20;  // 20s increments
  } else if (duration < 300) {
    increment = 30;  // 30s increments
  } else {
    increment = 60;  // 60s increments for long workflows
  }

  const markers = [];
  // Always start with 0
  markers.push({
    time: 0,
    position: 0,
    label: '0s'
  });

  // Add markers at each increment
  for (let time = increment; time < duration; time += increment) {
    markers.push({
      time,
      position: (time / duration) * 100,
      label: `${time}s`
    });
  }

  // Add final marker if it's not too close to the last one
  const lastMarkerTime = markers[markers.length - 1].time;
  if (duration - lastMarkerTime > increment * 0.3) {
    markers.push({
      time: duration,
      position: 100,
      label: `${duration.toFixed(1)}s`
    });
  }

  return markers;
});

function toggleAgent(index) {
  expandedAgents.value[index] = !expandedAgents.value[index];
}

function toggleLevel(levelIndex) {
  expandedLevels.value[levelIndex] = !expandedLevels.value[levelIndex];
}

function toggleSubgraphAgent(levelIndex, agentIndex) {
  const key = `${levelIndex}-${agentIndex}`;
  expandedAgents.value[key] = !expandedAgents.value[key];
}

function toggleToolsSection() {
  expandedToolsSection.value = !expandedToolsSection.value;
}

function toggleViewMode() {
  viewMode.value = viewMode.value === 'separated' ? 'integrated' : 'separated';
}

// Tool bar styling functions
function getToolBarStyle(tool) {
  const totalDuration = workflowDuration.value;
  const startPercent = (tool.start_offset / totalDuration) * 100;
  const widthPercent = (tool.duration / totalDuration) * 100;

  return {
    left: `${startPercent}%`,
    width: `${Math.max(0.5, widthPercent)}%`,
  };
}

function getToolBarClass(tool) {
  if (tool.is_subgraph) {
    return 'bg-blue-500';  // DaytonaCodeSandbox - blue
  } else {
    return 'bg-orange-500';  // All tools - orange
  }
}

// Calculate total duration for a level
function calculateLevelDuration(level) {
  if (level.level === 'main_agent' && level.llm_calls) {
    return level.llm_calls.reduce((sum, call) => sum + call.duration, 0);
  } else if (level.level === 'subgraph') {
    return level.subgraph_duration || 0;
  }
  return 0;
}

// Agent color palette - purple-based with complementary professional colors
const agentColors = [
  '#4E226B', // Primary brand purple
  '#2C5282', // Deep blue - complements purple well
  '#374151', // Slate gray - neutral but distinct
  '#622B86', // Purple 700
  '#6366F1', // Indigo - modern tech feel
  '#475569', // Blue-gray - professional
  '#7C3AED', // Vibrant purple
  '#64748B', // Slate 500
  '#8B5CF6', // Purple 500
  '#1E40AF'  // Blue 800 - deep contrast
];

function getAgentColor(index) {
  return agentColors[index % agentColors.length];
}

// Color classes for flat model breakdown - matches agent color palette
const colorClasses = [
  'bg-primary-brandColor',   // #4E226B
  'bg-blue-800',             // Deep blue
  'bg-gray-700',             // Slate
  'bg-primary-700',          // Purple 700
  'bg-indigo-500',           // Indigo
  'bg-slate-600',            // Blue-gray
  'bg-purple-600',           // Vibrant purple
  'bg-slate-500'             // Slate 500
];

function getColorClass(index) {
  return colorClasses[index % colorClasses.length];
}

// Expand first agent/level by default
if (showHierarchical.value && props.hierarchicalTiming.levels.length > 0) {
  // Expand first level (main agent or first subgraph)
  expandedLevels.value[0] = true;
  // If there's a subgraph with agents, expand the first subgraph
  const firstSubgraphLevel = props.hierarchicalTiming.levels.findIndex(l => l.level === 'subgraph');
  if (firstSubgraphLevel >= 0) {
    expandedLevels.value[firstSubgraphLevel] = true;
  }
} else if (props.agentBreakdown.length > 0) {
  expandedAgents.value[0] = true;
}
</script>

<style scoped>
/* Scrollbar styling - minimal design */
::-webkit-scrollbar {
  width: 8px;
}

::-webkit-scrollbar-track {
  background: #F2F4F7;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb {
  background: #4E226B;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: #622B86;
}
</style>
