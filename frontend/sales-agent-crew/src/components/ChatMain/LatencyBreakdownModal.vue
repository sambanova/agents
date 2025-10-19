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
              </div>
              <div v-if="toolTimings.length > 0" class="text-right">
                <div class="text-xs font-medium text-primary-brandTextSecondary">Total Tool Calls</div>
                <div class="text-xl font-bold text-orange-600 mt-0.5">{{ toolTimings.length }}</div>
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
              <span class="text-gray-600">Tool Calls ({{ toolTimings.length }})</span>
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
                    class="absolute h-full rounded-sm flex items-center px-2 bg-primary-brandColor bg-opacity-90"
                    :style="{
                      left: `${(event.start_offset / workflowDuration) * 100}%`,
                      width: `${Math.max(2, (event.duration / workflowDuration) * 100)}%`
                    }"
                  >
                    <!-- Content INSIDE bar, flows to right when narrow -->
                    <div class="flex items-center space-x-1.5 text-white text-xs font-medium whitespace-nowrap">
                      <svg class="w-3 h-3 flex-shrink-0 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                      </svg>
                      <span>{{ event.model_name }}</span>
                      <span class="text-white text-opacity-70">- {{ event.duration.toFixed(2) }}s</span>
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
                    class="absolute h-full rounded-sm flex items-center px-2 bg-opacity-85"
                    :class="event.is_subgraph ? 'bg-blue-500' : 'bg-orange-500'"
                    :style="{
                      left: `${(event.start_offset / workflowDuration) * 100}%`,
                      width: `${Math.max(2, (event.duration / workflowDuration) * 100)}%`
                    }"
                  >
                    <!-- Content INSIDE bar, flows to right when narrow -->
                    <div class="flex items-center space-x-1.5 text-white text-xs font-medium whitespace-nowrap">
                      <svg class="w-3 h-3 flex-shrink-0 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      <span>{{ event.tool_name }}</span>
                      <span class="text-white text-opacity-70">- {{ event.duration.toFixed(2) }}s</span>
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
                <div v-show="expandedLevels[levelIndex]" class="px-4 py-3 bg-white space-y-1">
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
                        class="absolute h-full rounded-sm flex items-center px-2 bg-primary-brandColor bg-opacity-90"
                        :style="{
                          left: `${Math.max(0, (call.start_offset / workflowDuration) * 100)}%`,
                          width: `${Math.max(2, (call.duration / workflowDuration) * 100)}%`
                        }"
                      >
                        <!-- Content INSIDE bar, flows to right when narrow -->
                        <div class="flex items-center space-x-1.5 text-white text-xs font-medium whitespace-nowrap">
                          <svg class="w-3 h-3 flex-shrink-0 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                          </svg>
                          <span>{{ call.model_name }}</span>
                          <span class="text-white text-opacity-70">- {{ call.duration.toFixed(2) }}s</span>
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
                              class="absolute h-full rounded-sm flex items-center px-2 bg-opacity-90"
                              :style="{
                                left: `${(call.start_offset / workflowDuration) * 100}%`,
                                width: `${Math.max(2, (call.duration / workflowDuration) * 100)}%`,
                                backgroundColor: getAgentColor(agentIndex)
                              }"
                            >
                              <!-- Content INSIDE bar, flows to right when narrow -->
                              <div class="flex items-center space-x-1.5 text-white text-xs font-medium whitespace-nowrap">
                                <svg class="w-3 h-3 flex-shrink-0 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                                </svg>
                                <span>{{ call.model_name }}</span>
                                <span class="text-white text-opacity-70">- {{ call.duration.toFixed(2) }}s</span>
                              </div>
                            </div>
                          </div>

                          <!-- Percentage on right -->
                          <div class="w-12 text-xs text-right pl-2" :style="{ color: getAgentColor(agentIndex) }">
                            {{ call.percentage.toFixed(1) }}%
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
          <button
            @click="toggleToolsSection"
            class="w-full flex items-center justify-between mb-3 px-4 py-2 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <div class="flex items-center justify-between flex-1">
              <div class="flex items-center space-x-2">
                <svg class="w-5 h-5 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
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

          <div v-show="expandedToolsSection" class="space-y-1">
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
                    class="absolute h-full rounded-sm flex items-center px-2 bg-opacity-85"
                    :class="tool.is_subgraph ? 'bg-blue-500' : 'bg-orange-500'"
                    :style="{
                      left: `${(tool.start_offset / workflowDuration) * 100}%`,
                      width: `${Math.max(2, (tool.duration / workflowDuration) * 100)}%`
                    }"
                  >
                    <!-- Content INSIDE bar, flows to right when narrow -->
                    <div class="flex items-center space-x-1.5 text-white text-xs font-medium whitespace-nowrap">
                      <svg class="w-3 h-3 flex-shrink-0 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      <span>{{ tool.tool_name }}</span>
                      <span class="text-white text-opacity-70">- {{ tool.duration.toFixed(2) }}s</span>
                      <span v-if="tool.parallel_group" class="text-white text-opacity-70">• P{{ tool.parallel_group }}</span>
                    </div>
                  </div>
                </div>

                <!-- Percentage on right -->
                <div class="w-12 text-xs text-orange-600 text-right pl-2">
                  {{ ((tool.duration / workflowDuration) * 100).toFixed(1) }}%
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
                      class="absolute h-full rounded-sm flex items-center px-2 bg-opacity-90"
                      :style="{
                        left: `${(call.start_offset / workflowDuration) * 100}%`,
                        width: `${Math.max(2, (call.duration / workflowDuration) * 100)}%`,
                        backgroundColor: getAgentColor(index)
                      }"
                    >
                      <!-- Content INSIDE bar, flows to right when narrow -->
                      <div class="flex items-center space-x-1.5 text-white text-xs font-medium whitespace-nowrap">
                        <svg class="w-3 h-3 flex-shrink-0 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        <span>{{ call.model_name }}</span>
                        <span class="text-white text-opacity-70">- {{ call.duration.toFixed(2) }}s</span>
                      </div>
                    </div>
                  </div>

                  <!-- Percentage on right -->
                  <div class="w-12 text-xs text-right pl-2" :style="{ color: getAgentColor(index) }">
                    {{ call.percentage.toFixed(1) }}%
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
                  class="absolute h-full rounded-sm flex items-center px-2 bg-primary-brandColor bg-opacity-90"
                  :style="{
                    left: `${(model.start_offset / workflowDuration) * 100}%`,
                    width: `${Math.max(2, (model.duration / workflowDuration) * 100)}%`
                  }"
                >
                  <!-- Content INSIDE bar, flows to right when narrow -->
                  <div class="flex items-center space-x-1.5 text-white text-xs font-medium whitespace-nowrap">
                    <svg class="w-3 h-3 flex-shrink-0 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    <span>{{ model.model_name }}</span>
                    <span class="text-white text-opacity-70">- {{ model.duration.toFixed(2) }}s</span>
                  </div>
                </div>
              </div>

              <!-- Percentage on right -->
              <div class="w-12 text-xs text-primary-brandColor text-right pl-2">
                {{ model.percentage.toFixed(1) }}%
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
