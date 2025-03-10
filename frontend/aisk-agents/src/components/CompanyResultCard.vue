<script setup>
import { ref, watch } from 'vue'
import { 
  ClipboardIcon, 
  BuildingOffice2Icon, 
  GlobeAltIcon, 
  CurrencyDollarIcon, 
  CpuChipIcon,
  ChartBarIcon,
  LightBulbIcon,
  ExclamationTriangleIcon,
  UserIcon
} from '@heroicons/vue/24/outline'

const props = defineProps({
  company: {
    type: Object,
    required: true
  }
})



const isExpanded = ref(false)

const toggleExpand = () => {
  isExpanded.value = !isExpanded.value
}

const copyEmailBody = () => {
  navigator.clipboard.writeText(props.company.email_body)
    .then(() => {
      alert('Email body copied to clipboard!')
    })
    .catch(err => {
      console.error('Failed to copy: ', err)
    })
}

const formatUrl = (url) => {
  if (!url) return ''
  // Add https:// if no protocol is specified
  return url.startsWith('http') ? url : `https://${url}`
}
</script>

<template>
  <div class="border border-gray-200 rounded-lg overflow-hidden shadow-sm">
    <!-- Card Header -->
    <div 
      @click="toggleExpand" 
      class="p-4 flex justify-between items-center cursor-pointer hover:bg-gray-50 transition group"
    >
      <div class="flex-grow">
        <h3 class="text-lg font-semibold text-blue-600 flex items-center">
          {{ company.company_name }}
          <span class="ml-2 text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
            {{ company.funding_status }}
          </span>
        </h3>
        <div class="mt-2 space-y-1 text-gray-600">
          <div class="flex items-center">
            <BuildingOffice2Icon class="w-4 h-4 mr-2 text-gray-400" />
            <span>{{ company.headquarters }}</span>
          </div>
          <div class="flex items-center">
            <GlobeAltIcon class="w-4 h-4 mr-2 text-gray-400" />
            <a 
              :href="formatUrl(company.website)" 
              target="_blank" 
              class="text-blue-500 hover:underline"
              @click.stop
            >
              {{ company.website }}
            </a>
          </div>
        </div>
      </div>
      <svg 
        :class="[
          'w-6 h-6 text-gray-400 transition-transform', 
          isExpanded ? 'rotate-180' : ''
        ]"
        fill="none" 
        stroke="currentColor" 
        viewBox="0 0 24 24" 
        xmlns="http://www.w3.org/2000/svg"
      >
        <path 
          stroke-linecap="round" 
          stroke-linejoin="round" 
          stroke-width="2" 
          d="M19 9l-7 7-7-7"
        />
      </svg>
    </div>

    <!-- Expanded Content -->
    <div 
      v-if="isExpanded" 
      class="p-4 bg-gray-50 border-t space-y-6"
    >
      <!-- Funding Amount -->
      <div>
        <div class="flex items-center mb-1">
          <CurrencyDollarIcon class="w-5 h-5 mr-2 text-gray-500" />
          <h4 class="font-semibold text-gray-700">
            Funding Amount
          </h4>
        </div>
        <p class="text-gray-600 pl-7">
          {{ company.funding_amount }}
        </p>
      </div>

      <!-- Key Contacts -->
      <div>
        <div class="flex items-center mb-1">
          <UserIcon class="w-5 h-5 mr-2 text-gray-500" />
          <h4 class="font-semibold text-gray-700">
            Key Contacts
          </h4>
        </div>
        <p class="text-gray-600 pl-7">
          {{ company.key_contacts }}
        </p>
      </div>

      <!-- Product -->
      <div>
        <div class="flex items-center mb-1">
          <CpuChipIcon class="w-5 h-5 mr-2 text-gray-500" />
          <h4 class="font-semibold text-gray-700">
            Product
          </h4>
        </div>
        <p class="text-gray-600 pl-7">
          {{ company.product }}
        </p>
      </div>

      <!-- Relevant Trends -->
      <div>
        <div class="flex items-center mb-1">
          <ChartBarIcon class="w-5 h-5 mr-2 text-gray-500" />
          <h4 class="font-semibold text-gray-700">
            Relevant Trends
          </h4>
        </div>
        <p class="text-gray-600 pl-7">
          {{ company.relevant_trends }}
        </p>
      </div>

      <!-- Opportunities -->
      <div>
        <div class="flex items-center mb-1">
          <LightBulbIcon class="w-5 h-5 mr-2 text-gray-500" />
          <h4 class="font-semibold text-gray-700">
            Opportunities
          </h4>
        </div>
        <p class="text-gray-600 pl-7">
          {{ company.opportunities }}
        </p>
      </div>

      <!-- Challenges -->
      <div>
        <div class="flex items-center mb-1">
          <ExclamationTriangleIcon class="w-5 h-5 mr-2 text-gray-500" />
          <h4 class="font-semibold text-gray-700">
            Challenges
          </h4>
        </div>
        <p class="text-gray-600 pl-7">
          {{ company.challenges }}
        </p>
      </div>

      <!-- Email Subject -->
      <div>
        <div class="flex items-center mb-1">
          <CurrencyDollarIcon class="w-5 h-5 mr-2 text-gray-500" />
          <h4 class="font-semibold text-gray-700">
            Email Subject
          </h4>
        </div>
        <p class="text-gray-600 pl-7">
          {{ company.email_subject }}
        </p>
      </div>

      <!-- Email Body with Copy Button -->
      <div class="relative">
        <div class="flex items-center mb-1">
          <ClipboardIcon class="w-5 h-5 mr-2 text-gray-500" />
          <h4 class="font-semibold text-gray-700">
            Email Body
          </h4>
        </div>
        <p class="text-gray-600 pl-7 mb-2 whitespace-pre-line">
          {{ company.email_body }}
        </p>
        <button 
          @click="copyEmailBody"
          class="absolute top-0 right-0 text-gray-500 hover:text-blue-600 transition"
          title="Copy Email Body"
        >
          <ClipboardIcon class="w-6 h-6" />
        </button>
      </div>
    </div>
  </div>
</template>
