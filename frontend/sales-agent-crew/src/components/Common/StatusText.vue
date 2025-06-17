<template>
  <div v-if="!streamData?.length" class="p-6 text-center text-gray-500 dark:text-gray-400">
    No streaming events to display.
  </div>

  <div v-else>
    <div class="flex flex-col p-4 border rounded mb-6">
      <!-- animated header -->
      <h2
        class="capitalize text-xl font-bold mb-4 box-progress"
        :class="{ 'box-progress': isLoading }"
        :data-text="`Current Tool: ${currentToolName || '– none –'}`"
      >
        Current Tool: {{ currentToolName || '– none –' }}
      </h2>

      <!-- static timeline -->
      <div class="flex space-x-6 mb-4">
        <div
          v-for="(tool, idx) in toolTimeline"
          :key="idx"
          class="relative pl-4 text-gray-700"
        >
          <div
            class="absolute left-0 top-1/2 w-2 h-2 rounded-full border-2 border-gray-500 bg-white transform -translate-y-1/2"
          ></div>
          {{ tool }}
        </div>
      </div>

      <!-- description box -->
      <div
        ref="descContainer"
        class="p-3 overflow-y-auto bg-gray-50 dark:bg-gray-800 rounded"
        style="max-height: 150px;"
      >
        {{ description || (isLoading ? 'Waiting for stream…' : '') }}
        <div class="markdown-content" v-html="renderMarkdown(description||'')"></div>
      </div>
    </div>

    <!-- ... your toolSources and auditLogEvents remain unchanged ... -->
  </div>
</template>

<script setup>
import { computed, ref, watch, nextTick } from 'vue'

const props = defineProps({
  streamData:   { type: Array,  default: () => [] },
  workflowData: { type: Array,  default: () => [] },
  isLoading:    { type: Boolean, default: false },
})

function extractToolName(content) {
  const m = /<tool>(.*?)<\/tool>/.exec(content)
  return m?.[1] ?? ''
}

const toolTimeline = computed(() =>
  props.streamData
    .filter(i => i.event === 'agent_completion' && i.additional_kwargs?.agent_type === 'react_tool')
    .map(i => extractToolName(i.content))
)

const currentToolName = computed(() =>
  toolTimeline.value.length
    ? toolTimeline.value[toolTimeline.value.length - 1]
    : ''
)

const description = computed(() =>
  props.streamData
    .filter(i => ['stream_start','llm_stream_chunk','stream_complete'].includes(i.event))
    .map(i => i.content)
    .join('')
)

const descContainer = ref(null)
watch(description, () => {
  nextTick(() => {
    if (descContainer.value) {
      descContainer.value.scrollTop = descContainer.value.scrollHeight
    }
  })
})

// (toolSources & auditLogEvents as before)
</script>

<style scoped>
.box-progress {
  position: relative;
  overflow: hidden;      /* hide the real text */
  color: transparent;    /* make the original invisible */
}

.box-progress::before {
  content: attr(data-text);
  position: absolute;
  top: 0;
  left: 0;               /* align with the hidden text */
  white-space: nowrap;
  overflow: hidden;
  max-width: 0;          /* start fully hidden */
  color: #101828;        /* reveal color */
  animation: loading 2s steps(30) infinite;
}

@keyframes loading {
  to { max-width: 100%; }
}
</style>
