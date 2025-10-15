<template>
  <div
    v-if="isOpen"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 backdrop-blur-sm"
    @click.self="$emit('close')"
  >
    <div class="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[85vh] overflow-hidden border border-gray-200">
      <!-- Header with gradient -->
      <div class="relative bg-gradient-to-r from-primary-brandColor to-teal-600 px-6 py-5">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-2xl font-bold text-white">Latency Breakdown</h2>
            <p class="text-sm text-teal-100 mt-1">Detailed timing analysis for this workflow</p>
          </div>
          <button
            @click="$emit('close')"
            class="text-white hover:text-gray-200 transition-colors p-2 hover:bg-white/10 rounded-lg"
          >
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Content -->
      <div class="px-6 py-5 overflow-y-auto max-h-[calc(85vh-180px)]">
        <!-- Total Duration Summary Card -->
        <div class="mb-6 p-5 bg-gradient-to-br from-gray-50 to-gray-100 rounded-xl border border-gray-200">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-3">
              <div class="p-3 bg-primary-brandColor rounded-lg">
                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <span class="text-xs font-medium text-gray-600">Total Workflow Duration</span>
                <div class="flex items-baseline space-x-2 mt-0.5">
                  <span class="text-2xl font-bold text-gray-900">{{ workflowDuration.toFixed(2) }}</span>
                  <span class="text-base font-semibold text-gray-500">seconds</span>
                </div>
              </div>
            </div>
            <div class="text-right">
              <div class="text-xs text-gray-600">Total LLM Calls</div>
              <div class="text-xl font-bold text-primary-brandColor">{{ totalLLMCalls }}</div>
            </div>
          </div>
        </div>

        <!-- Hierarchical Workflow Breakdown (LangSmith-style) -->
        <div v-if="showHierarchical" class="mb-6">
          <h3 class="text-lg font-bold text-gray-900 mb-4 flex items-center">
            <svg class="w-5 h-5 mr-2 text-primary-brandColor" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7" />
            </svg>
            Workflow Hierarchy
          </h3>

          <div class="space-y-4">
            <!-- Iterate through levels (main_agent, subgraph, etc.) -->
            <div
              v-for="(level, levelIndex) in hierarchicalTiming.levels"
              :key="levelIndex"
              class="border border-gray-200 rounded-lg overflow-hidden"
            >
              <!-- Main Agent Level -->
              <div v-if="level.level === 'main_agent'">
                <!-- Debug logging for main agent data -->
                {{ logMainAgentData(level) }}
                <button
                  @click="toggleLevel(levelIndex)"
                  class="w-full px-4 py-3 bg-indigo-50 hover:bg-indigo-100 transition-colors flex items-center justify-between"
                >
                  <div class="flex items-center space-x-3">
                    <svg
                      class="w-4 h-4 text-indigo-600 transition-transform"
                      :class="{ 'rotate-90': expandedLevels[levelIndex] }"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                    <span class="text-sm font-semibold text-indigo-900">Main Agent</span>
                    <span class="text-xs text-indigo-600">{{ level.num_calls }} {{ level.num_calls === 1 ? 'call' : 'calls' }}</span>
                  </div>
                  <div class="flex items-center space-x-3">
                    <span class="text-xs font-medium text-indigo-700">{{ calculateLevelDuration(level).toFixed(2) }}s</span>
                    <span class="text-xs font-medium text-gray-500">Level 1</span>
                  </div>
                </button>

                <!-- Main Agent LLM Calls -->
                <div v-show="expandedLevels[levelIndex]" class="px-4 py-3 bg-white space-y-3">
                  <div
                    v-for="(call, callIndex) in level.llm_calls"
                    :key="callIndex"
                    class="space-y-2"
                  >
                    <div class="flex items-center justify-between text-sm">
                      <div class="flex items-center space-x-2">
                        <div class="w-2 h-2 rounded-full bg-indigo-500"></div>
                        <span class="font-medium text-gray-900">{{ call.model_name }}</span>
                        <span v-if="call.provider" class="text-xs text-gray-500">({{ call.provider }})</span>
                      </div>
                      <div class="flex items-center space-x-3 text-xs">
                        <span class="text-gray-600">{{ call.duration.toFixed(2) }}s</span>
                        <span v-if="call.percentage" class="font-medium text-primary-brandColor">{{ call.percentage.toFixed(1) }}%</span>
                      </div>
                    </div>
                    <!-- Bar rendering with defensive checks -->
                    <div class="relative h-6 bg-gray-100 rounded-md overflow-hidden">
                      <div
                        v-if="call.duration > 0 && call.start_offset !== undefined && call.start_offset !== null"
                        class="absolute top-0 h-full flex items-center justify-center text-white text-xs font-medium rounded-md bg-indigo-500"
                        :style="{
                          left: `${Math.max(0, (call.start_offset / workflowDuration) * 100)}%`,
                          width: `${Math.max(0.5, (call.duration / workflowDuration) * 100)}%`
                        }"
                      >
                        <span v-if="(call.duration / workflowDuration) > 0.05">
                          {{ call.duration.toFixed(1) }}s
                        </span>
                      </div>
                      <!-- Debug: Show warning if bar can't render -->
                      <div v-else class="text-xs text-gray-400 px-2 py-1">
                        ⚠️ Missing timing data (duration: {{ call.duration }}, start_offset: {{ call.start_offset }})
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Subgraph Level -->
              <div v-if="level.level === 'subgraph'">
                <button
                  @click="toggleLevel(levelIndex)"
                  class="w-full px-4 py-3 bg-teal-50 hover:bg-teal-100 transition-colors flex items-center justify-between"
                >
                  <div class="flex items-center space-x-3">
                    <svg
                      class="w-4 h-4 text-teal-600 transition-transform"
                      :class="{ 'rotate-90': expandedLevels[levelIndex] }"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                    </svg>
                    <span class="text-sm font-semibold text-teal-900">{{ level.subgraph_name }}</span>
                    <span class="text-xs text-teal-600">{{ level.num_llm_calls }} LLM {{ level.num_llm_calls === 1 ? 'call' : 'calls' }}</span>
                  </div>
                  <div class="flex items-center space-x-3">
                    <span class="text-xs font-medium text-teal-700">{{ level.subgraph_duration.toFixed(2) }}s</span>
                    <span class="text-xs font-medium text-gray-500">Level 2</span>
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
                        class="w-full px-4 py-2 bg-gray-50 hover:bg-gray-100 transition-colors flex items-center justify-between"
                      >
                        <div class="flex items-center space-x-3">
                          <svg
                            class="w-3 h-3 text-gray-500 transition-transform"
                            :class="{ 'rotate-90': expandedAgents[`${levelIndex}-${agentIndex}`] }"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                          </svg>
                          <span class="text-xs font-semibold text-gray-900">{{ agent.agent_name }}</span>
                          <span class="text-xs text-gray-500">{{ agent.num_calls }} {{ agent.num_calls === 1 ? 'call' : 'calls' }}</span>
                        </div>
                        <div class="flex items-center space-x-3">
                          <span class="text-xs font-medium text-gray-700">{{ agent.total_duration.toFixed(2) }}s</span>
                          <span class="text-xs font-semibold text-primary-brandColor">{{ agent.percentage.toFixed(1) }}%</span>
                        </div>
                      </button>

                      <!-- Agent Calls -->
                      <div v-show="expandedAgents[`${levelIndex}-${agentIndex}`]" class="px-4 py-2 bg-white space-y-2">
                        <div
                          v-for="(call, callIndex) in agent.calls"
                          :key="callIndex"
                          class="space-y-1"
                        >
                          <div class="flex items-center justify-between text-xs">
                            <div class="flex items-center space-x-2">
                              <div class="w-2 h-2 rounded-full" :style="{ backgroundColor: getAgentColor(agentIndex) }"></div>
                              <span class="font-medium text-gray-900">{{ call.model_name }}</span>
                              <span v-if="call.provider" class="text-xs text-gray-500">({{ call.provider }})</span>
                            </div>
                            <div class="flex items-center space-x-2 text-xs">
                              <span class="text-gray-600">{{ call.duration.toFixed(2) }}s</span>
                              <span class="font-medium text-primary-brandColor">{{ call.percentage.toFixed(1) }}%</span>
                            </div>
                          </div>
                          <div class="relative h-5 bg-gray-100 rounded-md overflow-hidden">
                            <div
                              class="absolute top-0 h-full flex items-center justify-center text-white text-xs font-medium rounded-md"
                              :style="{
                                left: `${(call.start_offset / workflowDuration) * 100}%`,
                                width: `${(call.duration / workflowDuration) * 100}%`,
                                backgroundColor: getAgentColor(agentIndex)
                              }"
                            >
                              <span v-if="(call.duration / workflowDuration) > 0.05">
                                {{ call.duration.toFixed(1) }}s
                              </span>
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
        </div>

        <!-- Agent-Based Breakdown (if available) -->
        <div v-else-if="agentBreakdown.length > 0" class="mb-6">
          <h3 class="text-lg font-bold text-gray-900 mb-4 flex items-center">
            <svg class="w-5 h-5 mr-2 text-primary-brandColor" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            Agent Timeline
          </h3>

          <div class="space-y-4">
            <div
              v-for="(agent, index) in agentBreakdown"
              :key="index"
              class="border border-gray-200 rounded-lg overflow-hidden hover:shadow-md transition-shadow"
            >
              <!-- Agent Header -->
              <button
                @click="toggleAgent(index)"
                class="w-full px-4 py-3 bg-gray-50 hover:bg-gray-100 transition-colors flex items-center justify-between"
              >
                <div class="flex items-center space-x-3">
                  <svg
                    class="w-4 h-4 text-gray-500 transition-transform"
                    :class="{ 'rotate-90': expandedAgents[index] }"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                  </svg>
                  <span class="text-sm font-semibold text-gray-900">{{ agent.agent_name }}</span>
                  <span class="text-xs text-gray-500">{{ agent.num_calls }} {{ agent.num_calls === 1 ? 'call' : 'calls' }}</span>
                </div>
                <div class="flex items-center space-x-3">
                  <span class="text-xs font-medium text-gray-700">{{ agent.total_duration.toFixed(2) }}s</span>
                  <span class="text-xs font-semibold text-primary-brandColor">{{ agent.percentage.toFixed(1) }}%</span>
                </div>
              </button>

              <!-- Agent Calls (Collapsible) -->
              <div v-show="expandedAgents[index]" class="px-4 py-3 bg-white space-y-3">
                <div
                  v-for="(call, callIndex) in agent.calls"
                  :key="callIndex"
                  class="space-y-2"
                >
                  <!-- Model Info -->
                  <div class="flex items-center justify-between text-sm">
                    <div class="flex items-center space-x-2">
                      <div class="w-2 h-2 rounded-full" :style="{ backgroundColor: getAgentColor(index) }"></div>
                      <span class="font-medium text-gray-900">{{ call.model_name }}</span>
                      <span v-if="call.provider" class="text-xs text-gray-500">({{ call.provider }})</span>
                    </div>
                    <div class="flex items-center space-x-3 text-xs">
                      <span class="text-gray-600">{{ call.duration.toFixed(2) }}s</span>
                      <span class="font-medium text-primary-brandColor">{{ call.percentage.toFixed(1) }}%</span>
                    </div>
                  </div>

                  <!-- Waterfall Bar -->
                  <div class="relative h-6 bg-gray-100 rounded-md overflow-hidden">
                    <!-- Duration Bar -->
                    <div
                      class="absolute top-0 h-full flex items-center justify-center text-white text-xs font-medium rounded-md transition-all"
                      :style="{
                        left: `${(call.start_offset / workflowDuration) * 100}%`,
                        width: `${(call.duration / workflowDuration) * 100}%`,
                        backgroundColor: getAgentColor(index)
                      }"
                    >
                      <span v-if="(call.duration / workflowDuration) > 0.05">
                        {{ call.duration.toFixed(1) }}s
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Fallback: Flat Model Breakdown (if no agent breakdown) -->
        <div v-else-if="modelBreakdown.length > 0" class="space-y-4">
          <h3 class="text-lg font-bold text-gray-900 mb-3 flex items-center">
            <svg class="w-5 h-5 mr-2 text-primary-brandColor" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Model Calls Timeline
          </h3>

          <div
            v-for="(model, index) in modelBreakdown"
            :key="index"
            class="space-y-2 p-3 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <!-- Model Info -->
            <div class="flex items-center justify-between text-xs">
              <div class="flex-1">
                <span class="font-medium text-gray-900">{{ model.model_name }}</span>
                <span v-if="model.provider" class="ml-2 text-xs text-gray-500">({{ model.provider }})</span>
                <span v-if="model.agent_name" class="ml-2 text-xs text-primary-brandColor">• {{ model.agent_name }}</span>
              </div>
              <div class="flex items-center space-x-3 text-xs">
                <span class="text-gray-600">{{ model.duration.toFixed(2) }}s</span>
                <span class="font-medium text-primary-brandColor">{{ model.percentage.toFixed(1) }}%</span>
              </div>
            </div>

            <!-- Waterfall Bar -->
            <div class="relative h-6 bg-gray-100 rounded-md overflow-hidden">
              <div
                class="absolute top-0 h-full flex items-center justify-center text-white text-xs font-medium rounded-md"
                :class="getColorClass(index)"
                :style="{
                  left: `${(model.start_offset / workflowDuration) * 100}%`,
                  width: `${(model.duration / workflowDuration) * 100}%`
                }"
              >
                <span v-if="(model.duration / workflowDuration) > 0.05">
                  {{ model.duration.toFixed(1) }}s
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-else class="text-center py-12 text-gray-500">
          <svg class="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p class="text-lg font-medium">No detailed timing breakdown available</p>
          <p class="text-sm mt-1">Timing data will appear here after workflow execution</p>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-6 py-4 border-t border-gray-200 bg-gray-50 flex items-center justify-end">
        <button
          @click="$emit('close')"
          class="px-5 py-2 bg-gradient-to-r from-primary-brandColor to-teal-600 hover:from-teal-600 hover:to-primary-brandColor text-white font-medium rounded-lg transition-all shadow-md hover:shadow-lg"
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

// Calculate total duration for a level
function calculateLevelDuration(level) {
  if (level.level === 'main_agent' && level.llm_calls) {
    return level.llm_calls.reduce((sum, call) => sum + call.duration, 0);
  } else if (level.level === 'subgraph') {
    return level.subgraph_duration || 0;
  }
  return 0;
}

// Debug: Log main agent data structure
function logMainAgentData(level) {
  if (level.llm_calls && level.llm_calls.length > 0) {
    console.log('[MAIN_AGENT_BAR_DEBUG] Main agent level data:', {
      num_calls: level.num_calls,
      llm_calls_count: level.llm_calls.length,
      first_call: level.llm_calls[0],
      has_duration: level.llm_calls[0]?.duration !== undefined,
      has_start_offset: level.llm_calls[0]?.start_offset !== undefined,
      duration_value: level.llm_calls[0]?.duration,
      start_offset_value: level.llm_calls[0]?.start_offset,
      workflow_duration: workflowDuration.value,
    });
  }
  return ''; // Return empty string so it doesn't render anything
}

// Agent color palette - more vibrant and distinct
const agentColors = [
  '#26A69A', // Teal (primary brand color)
  '#5C6BC0', // Indigo
  '#EC407A', // Pink
  '#FF7043', // Deep Orange
  '#AB47BC', // Purple
  '#42A5F5', // Blue
  '#66BB6A', // Green
  '#FFA726', // Orange
  '#8D6E63', // Brown
  '#78909C'  // Blue Grey
];

function getAgentColor(index) {
  return agentColors[index % agentColors.length];
}

// Color classes for flat model breakdown
const colorClasses = [
  'bg-teal-500',
  'bg-indigo-500',
  'bg-pink-500',
  'bg-orange-500',
  'bg-purple-500',
  'bg-blue-500',
  'bg-green-500',
  'bg-amber-500'
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
/* Smooth transitions */
* {
  transition: all 0.2s ease;
}

/* Scrollbar styling */
::-webkit-scrollbar {
  width: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 10px;
}

::-webkit-scrollbar-thumb {
  background: #26A69A;
  border-radius: 10px;
}

::-webkit-scrollbar-thumb:hover {
  background: #1F897F;
}
</style>
