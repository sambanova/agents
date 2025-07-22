<template>
    <div class="inline-block mx-1 my-2 p-2 bg-[#F9FAFB] border border-gray-200 rounded-lg">
      <!-- Inline metadata items with rocket icon -->
      <div class="flex items-center flex-wrap gap-x-1 text-sm text-gray-700 text-[12px] text-primary-brandTextSecondary">
  <!-- Green Rocket Icon -->
  <!-- <svg
    class="flex-shrink-0"
    width="14"
    height="14"
    viewBox="0 0 14 14"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path d="M3.00016 8.99975C2.44683 8.99975 1.94683 9.22642 1.58683 9.58642C0.800163 10.3731 0.333496 13.6664 0.333496 13.6664C0.333496 13.6664 3.62683 13.1998 4.4135 12.4131C4.7735 12.0531 5.00016 11.5531 5.00016 10.9998C5.00016 9.89308 4.10683 8.99975 3.00016 8.99975ZM3.4735 11.4731C3.28683 11.6598 2.02683 11.9798 2.02683 11.9798C2.02683 11.9798 2.34016 10.7264 2.5335 10.5331C2.64683 10.4064 2.8135 10.3331 3.00016 10.3331C3.36683 10.3331 3.66683 10.6331 3.66683 10.9998C3.66683 11.1864 3.5935 11.3531 3.4735 11.4731ZM10.6135 8.09975C14.8535 3.85975 13.4402 0.559751 13.4402 0.559751C13.4402 0.559751 10.1402 -0.853582 5.90016 3.38642L4.24016 3.05308C3.80683 2.96642 3.3535 3.10642 3.0335 3.41975L0.333496 6.12642L3.66683 7.55308L6.44683 10.3331L7.8735 13.6664L10.5735 10.9664C10.8868 10.6531 11.0268 10.1998 10.9402 9.75975L10.6135 8.09975ZM3.94016 6.21975L2.66683 5.67308L3.98016 4.35975L4.94016 4.55308C4.56016 5.10642 4.22016 5.68642 3.94016 6.21975ZM8.32683 11.3331L7.78016 10.0598C8.3135 9.77975 8.8935 9.43975 9.44016 9.05975L9.6335 10.0198L8.32683 11.3331ZM9.66683 7.15975C8.78683 8.03975 7.4135 8.75975 6.9735 8.97975L5.02016 7.02642C5.2335 6.59308 5.9535 5.21975 6.84016 4.33308C9.96016 1.21309 12.3268 1.67308 12.3268 1.67308C12.3268 1.67308 12.7868 4.03975 9.66683 7.15975ZM9.00016 6.33308C9.7335 6.33308 10.3335 5.73308 10.3335 4.99975C10.3335 4.26642 9.7335 3.66642 9.00016 3.66642C8.26683 3.66642 7.66683 4.26642 7.66683 4.99975C7.66683 5.73308 8.26683 6.33308 9.00016 6.33308Z" fill="#26A69A"/>
  </svg> -->

  <!-- Loop over metadata items -->
  <template v-for="(item, key, index) in props.presentMetadata" :key="key">

  <span v-if="key!=='token_savings'"
  :class="index===0?'items-center  flex':''"
  class="mr-1 p-0 capitalize " >
    <!-- Separator dot for every item except the first -->
    <!-- <span
      v-if="index !== 0"
      class="w-2 h-2 bg-gray-400 rounded-full inline-block "
    ></span> -->
    <!-- Each metadata item as a single inline-flex item that won't break internally -->
    
    <svg
      v-if="index === 0"
    class="flex-shrink-0 mr-2"
    width="14"
    height="14"
    viewBox="0 0 14 14"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path d="M3.00016 8.99975C2.44683 8.99975 1.94683 9.22642 1.58683 9.58642C0.800163 10.3731 0.333496 13.6664 0.333496 13.6664C0.333496 13.6664 3.62683 13.1998 4.4135 12.4131C4.7735 12.0531 5.00016 11.5531 5.00016 10.9998C5.00016 9.89308 4.10683 8.99975 3.00016 8.99975ZM3.4735 11.4731C3.28683 11.6598 2.02683 11.9798 2.02683 11.9798C2.02683 11.9798 2.34016 10.7264 2.5335 10.5331C2.64683 10.4064 2.8135 10.3331 3.00016 10.3331C3.36683 10.3331 3.66683 10.6331 3.66683 10.9998C3.66683 11.1864 3.5935 11.3531 3.4735 11.4731ZM10.6135 8.09975C14.8535 3.85975 13.4402 0.559751 13.4402 0.559751C13.4402 0.559751 10.1402 -0.853582 5.90016 3.38642L4.24016 3.05308C3.80683 2.96642 3.3535 3.10642 3.0335 3.41975L0.333496 6.12642L3.66683 7.55308L6.44683 10.3331L7.8735 13.6664L10.5735 10.9664C10.8868 10.6531 11.0268 10.1998 10.9402 9.75975L10.6135 8.09975ZM3.94016 6.21975L2.66683 5.67308L3.98016 4.35975L4.94016 4.55308C4.56016 5.10642 4.22016 5.68642 3.94016 6.21975ZM8.32683 11.3331L7.78016 10.0598C8.3135 9.77975 8.8935 9.43975 9.44016 9.05975L9.6335 10.0198L8.32683 11.3331ZM9.66683 7.15975C8.78683 8.03975 7.4135 8.75975 6.9735 8.97975L5.02016 7.02642C5.2335 6.59308 5.9535 5.21975 6.84016 4.33308C9.96016 1.21309 12.3268 1.67308 12.3268 1.67308C12.3268 1.67308 12.7868 4.03975 9.66683 7.15975ZM9.00016 6.33308C9.7335 6.33308 10.3335 5.73308 10.3335 4.99975C10.3335 4.26642 9.7335 3.66642 9.00016 3.66642C8.26683 3.66642 7.66683 4.26642 7.66683 4.99975C7.66683 5.73308 8.26683 6.33308 9.00016 6.33308Z" fill="#26A69A"/>
  </svg>
        {{
          key === 'duration' ? 'Latency:' :
          key === 'llm_name' ? 'LLM Name:' :
          key === 'llm_provider' ? 'LLM provider:' :
          key === 'workflow_name' ? 'Workflow name:' :
          key === 'agent_name' ? 'Agent name:' :
          key === 'task' ? 'Task:' :
          key === 'total_tokens' ? 'Total tokens:' :
          key === 'prompt_tokens' ? 'Total input tokens:' :
          key === 'completion_tokens' ? 'Total output tokens:' :
          formatKey(key)
        }}
      
      <span class="ml-1 capitalize font-semibold text-primary-brandTextPrimary">
        {{ key === 'duration'?formattedDuration(parseFloat(item)):formatNumber(item) }}
      </span>
    
  </span>
    </template>
</div>

    </div>
  </template>
  
  <script setup>
import { formattedDuration } from '@/utils/globalFunctions'

  const props = defineProps({
    presentMetadata: {
      type: Object,  // Adjust to Array if needed
      default: () => ({})
    }
  })
  
  
  
  // Format numbers to k notation if necessary.
  function formatNumber(value) {
    if (typeof value !== "number" || isNaN(value)) return value;
    if (value < 1000) {
      return value.toString();
    }
    const formatted = (value / 1000).toFixed(1).replace(/\.0$/, "");
    return `${formatted}k`;
  }
  
  // Format key: Replace underscores with spaces.
  function formatKey(key) {
    return key.replace(/_/g, ' ');
  }
  </script>
  
  <style scoped>
  /* No additional custom styles are required as Tailwind classes handle styling */
  </style>