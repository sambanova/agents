<template>
  <div class="flex flex-wrap gap-2">
    <!-- chips -->
    <a
      v-for="(src, idx) in visibleSources"
      :key="src.url + src.title"
      :href="src.url"
      target="_blank"
      rel="noopener noreferrer"
      class="inline-flex items-center mb-2 px-3 py-1 rounded-full text-sm font-medium
             bg-gray-100 dark:bg-gray-800
             text-black-500 dark:text-white-300
             hover:bg-gray-200 dark:hover:bg-gray-700
             transition"
    >
      <span v-if="src.type==='link'" class="mr-1">🌐</span>
      <span v-else-if="src.type==='arxiv'" class="mr-1">📚</span>
      {{ src.title }}
    </a>

    <!-- toggle button -->
    <button
      v-if="allSources.length > 5"
      @click="toggleShowAll"
      class="mb-2 text-sm font-medium underline
             text-orange-500 dark:text-orange-300"
    >
      {{ showAll
          ? 'Show Less'
          : `+${allSources.length - 5} More`
      }}
    </button>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

// receive allSources from parent
const props = defineProps({
  allSources: {
    type: Array,
    required: true
    // each item: { url: string, title: string, type: 'link'|'arxiv'|… }
  }
})

const showAll = ref(false)

const visibleSources = computed(() =>
  showAll.value
    ? props.allSources
    : props.allSources.slice(0, 5)
)

function toggleShowAll() {
  showAll.value = !showAll.value
}
</script>
