<template>
    <div class="user-proxy-message">
      
      <!-- <p>{{ parsed.data?.agent_question || parsed.data?.deep_research_question }}</p> -->
      <div class="markdown-content" v-html="formattedText(parsed.data?.agent_question || parsed.data?.deep_research_question||'')"></div>

      <!-- You might also parse parsed.message if needed -->
    </div>
  </template>
  
  <script setup>

import { formattedText } from '@/utils/formatText'

  const props = defineProps({
    parsed: {
      type: Object,
      required: true
    }
  });
  </script>
  