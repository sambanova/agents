<script setup>
import { ref } from 'vue'
import Header from '../components/Header.vue'
import SearchSection from '../components/SearchSection.vue'
import SettingsModal from '../components/SettingsModal.vue'
import CompanyResultCard from '../components/CompanyResultCard.vue'
import SearchNotification from '../components/SearchNotification.vue'

const settingsModalRef = ref(null)
const isLoading = ref(false)
const results = ref([])
const showNotification = ref(false)
const searchTime = ref(0)

const handleSearch = async (query) => {
  isLoading.value = true
  const startTime = Date.now()

  try {
    // Perform your search logic here and update 'results' accordingly
    // Example:
    // results.value = await performSearch(query)

    // Simulate search delay
    await new Promise(resolve => setTimeout(resolve, 2000))
    // Example data
    results.value = [
      {
        company_name: 'Example Company',
        funding_status: 'Series A',
        headquarters: 'San Francisco, CA',
        website: 'www.example.com',
        funding_amount: '$10M',
        product: 'AI-powered sales tool',
        relevant_trends: 'Artificial Intelligence, Sales Automation',
        opportunities: 'Expand market share',
        challenges: 'Competition from established players',
        email_subject: 'Innovative AI Solutions for Your Sales Team',
        email_body: 'Dear [Company],\n\nWe offer cutting-edge AI solutions...'
      },
      // Add more results as needed
    ]

    // Calculate search time
    const endTime = Date.now()
    searchTime.value = ((endTime - startTime) / 1000).toFixed(2)

    // Show notification
    showNotification.value = true
    setTimeout(() => {
      showNotification.value = false
    }, 5000)
  } catch (error) {
    console.error('Search error:', error)
    // Handle error (show notification, etc.)
  } finally {
    isLoading.value = false
  }
}

const openSettingsModal = () => {
  settingsModalRef.value.isOpen = true
}
</script>

<template>
  <div class="h-screen flex flex-col">
    <Header />
    <main class="flex-1 p-6 overflow-y-auto">
      <SearchSection
        @search="handleSearch"
        @openSettings="openSettingsModal"
        :isLoading="isLoading"
      />

      <!-- Search Notification -->
      <SearchNotification 
        v-if="showNotification" 
        :show="showNotification" 
        :time="searchTime" 
        :resultCount="results.length" 
      />

      <!-- Results -->
      <div v-if="results.length > 0" class="space-y-4">
        <CompanyResultCard
          v-for="(company, index) in results"
          :key="index"
          :company="company"
        />
      </div>
    </main>

    <!-- Settings Modal -->
    <SettingsModal ref="settingsModalRef" />
  </div>
</template>
