<template>

  isLoading {{ props.isLoading }}
  <div class="flex flex-col p-4">
    <!-- 1) Heading, updates to last tool name -->
    <h2 class="text-xl font-bold mb-4">
      Current Tool: {{ currentToolName || '– none –' }}
    </h2>

    <!-- 2) Timeline (static) -->
    <div class="flex space-x-6 mb-4">
      <div
        v-for="(tool, idx) in toolTimeline"
        :key="idx"
        class="relative pl-4 text-gray-700"
      >
        <!-- connector line -->
        <div class="absolute left-0 top-1/2 w-2 h-2 rounded-full border-2 border-gray-500 bg-white transform -translate-y-1/2"></div>
        {{ tool }}
      </div>
    </div>

    <!-- 3) Description box (scrollable, max-height 300px) -->
    <div
      ref="descContainer"
      class="border rounded p-3 overflow-y-auto"
      style="max-height: 300px;"
    >
      {{ description }}
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'

const props = defineProps({
  streamData: {
    type: Array,
    default: () => []
  },
   isLoading: {
    type: Boolean,
    default: false
  }
})

// helper to pull tool name out of "<tool>NAME</tool>"
function extractToolName(content) {
  const m = /<tool>(.*?)<\/tool>/.exec(content)
  return m ? m[1] : ''
}

// 1) All tool names seen so far
const toolTimeline = computed(() =>
  props.streamData
    .filter(
      i =>
        i.event === 'agent_completion' &&
        i.additional_kwargs?.agent_type === 'react_tool'
    )
    .map(i => extractToolName(i.content))
)

// 2) Current (last) tool
const currentToolName = computed(() =>
  toolTimeline.value.length
    ? toolTimeline.value[toolTimeline.value.length - 1]
    : ''
)

// 3) Full concatenated description
const description = computed(() =>
  props.streamData
    .filter(i =>
      ['stream_start', 'llm_stream_chunk', 'stream_complete'].includes(
        i.event
      )
    )
    .map(i => i.content)
    .join('')
)

// 4) Auto‐scroll description to bottom on change
const descContainer = ref(null)
watch(description, () => {
  nextTick(() => {
    if (descContainer.value) {
      descContainer.value.scrollTop = descContainer.value.scrollHeight
    }
  })
})
</script>

<style scoped>
/* you can adjust colors/sizing as you like */
</style>
