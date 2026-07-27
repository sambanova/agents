<template>
       <li  
      class="px-4 items-start gap-x-2 sm:gap-x-4">
      <div class="w-full flex items-center ">
      

        <UserAvatar :type="provider" />  
      <div class="grow text-start space-y-3">
      <!-- Card -->
      <div class="inline-block" >
     <div class=" p-4 capitalize space-y-3 font-inter font-semibold text-[16px] leading-[18px] tracking-[0px] text-center">{{ provider==="sambanova"?"SambaNova":provider }} Agent</div>
</div>

</div>
      </div>
      <div class="w-full bg-white  ">
          <AnalysisTimeline 
      :isLoading="isLoading" 
      :workflowData="workflowData" 
      :plannerText="plannerText" 
      :statusText="statusText"
       :defaultCollapsed="false"
      isOpen="'true'"
    />
     
    
      </div>
    </li>
    
  </template>
  
  <script setup>

import AnalysisTimeline from '@/components/ChatMain/AnalysisTimeline.vue'

  import UserAvatar from '@/components/Common/UIComponents/UserAvtar.vue'


  // Define props
  const props = defineProps({
    plannerText: {
    type: String,
    required: false // Ensure it's always provided
  },
  statusText: {
    type: String,
    required: false // Ensure it's always provided
  },
  
  isLoading: {
    type: Boolean,
    required: false // Ensure it's always provided
  },
   
  workflowData: {
    type: Array,
    required: false // Ensure it's always provided
  },
  provider: {
      type: String,
      required: false
    },
 
  })
  
  

  function fetchProvider() {
    // Check if workflowData is an array and has elements
    if (!props.workflowData || !Array.isArray(props.workflowData)) {
      return null;
    }
    for (let i = 0; i < props.workflowData.length; i++) {
      if (props.workflowData[i].hasOwnProperty('llm_provider')) {
        return props.workflowData[i].llm_provider;
      }
    }
    // Return null if no object with 'llm_provider' is found
    return null;
  }
  
  </script>
  <style>
  @keyframes loaderAnimation {
    0% {
      width: 0%;
    }
    100% {
      width: 100%;
    }
  }
  .animate-loader {
    animation: loaderAnimation 2s linear infinite;
  }
</style>