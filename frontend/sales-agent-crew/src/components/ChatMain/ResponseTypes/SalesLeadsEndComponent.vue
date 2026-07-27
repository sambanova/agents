<template>
    <div class="container mx-auto ">
      <!-- Display an error message if present -->
      <div v-if="error" class="bg-red-100 text-red-700 p-2 rounded mb-4">
        {{ error }}
      </div>
      <!-- Display outreach list if available -->
      <div v-if="hasOutreachData">
        <div
          v-for="(item, index) in parsed.data.outreach_list"
          :key="index"
          class="bg-white  rounded-lg p-4 mb-4 border border-primary-brandFrame"
        >
          <h2 class="text-[20px] font-bold mb-2">
            <a
              :href="item.website"
              target="_blank"
              rel="noopener noreferrer"
              class="text-primary-brandTextPrimary underline"
            >
              {{ item.company_name }}
            </a>
          </h2>
          <div class="space-y-1 text-gray-700">
            <p><strong>Headquarters:</strong> {{ item.headquarters }}</p>
            <p><strong>Key Contacts:</strong> {{ item.key_contacts }}</p>
            <p>
              <strong>Funding:</strong>
              {{ item.funding_status }} ({{ item.funding_amount }})
            </p>
            <p><strong>Product:</strong> {{ item.product }}</p>
            <p><strong>Trends:</strong> {{ item.relevant_trends }}</p>
            <p><strong>Opportunities:</strong> {{ item.opportunities }}</p>
            <p><strong>Challenges:</strong> {{ item.challenges }}</p>
            <p><strong>Email Subject:</strong> {{ item.email_subject }}</p>
            <p><strong>Email Body:</strong></p>
            <!-- Preserve newlines in the email body -->
            <p class="whitespace-pre-line text-gray-600">{{ item.email_body }}</p>
          </div>
        </div>
      </div>
      <!-- Fallback message if no outreach data is available -->
      <div v-else>
        <p class="text-gray-500">No outreach data available.</p>
      </div>
    </div>
  </template>
  
  <script>
  export default {
    name: 'SalesLeadsEndComponent',
    props: {
      parsed: {
        type: Object,
        required: true,
      },
    },
    computed: {
      error() {
        return this.parsed.data?.error || '';
      },
      hasOutreachData() {
        return (
          this.parsed.data &&
          Array.isArray(this.parsed.data.outreach_list) &&
          this.parsed.data.outreach_list.length > 0
        );
      },
    },
  };
  </script>
  
  <style scoped>
  </style> 