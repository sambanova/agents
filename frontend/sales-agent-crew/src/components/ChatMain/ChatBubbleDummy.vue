<template>
  <pre>{{ JSON.stringify(props, null, 2) }}</pre>
</template>

<script setup>
import { defineProps } from 'vue'

const props = defineProps({
  data:      { type: [String, Object], required: true },
  agent_type:{ type: String,          required: true },
  event:     { type: String,          required: true },
  messageId: { type: String,          required: true },
  provider:  { type: String,          required: true },
  isLoading: { type: Boolean,         default: false },
  streamData:{ type: Array,           default: () => [] },
  workflowData: { type: Array,        default: () => [] },
  plannerText:  { type: String,       default: '' },
  metadata:     { type: Object,       default: () => ({}) },
})
</script>
