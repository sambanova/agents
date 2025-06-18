<template>
  <div class=" p-2">
    <!-- Timeline Header -->
    <!-- <h2 class="text-xl font-semibold text-gray-800 dark:text-gray-100 mb-1">{{ title }}</h2> -->
    <p class="text-sm text-gray-600 dark:text-gray-300 mb-4">{{ description }}</p>

    <!-- Timeline Events -->
    <div class="border-l-2 border-gray-200 dark:border-gray-700">
      <div
        v-for="(event, index) in events"
        :key="index"
        class="relative pl-4 mb-6"
      >
        <!-- Dot -->
        <span
          class="absolute -left-2 top-1 bg-white dark:bg-gray-800 border-2 border-gray-200 dark:border-gray-700 w-3 h-3 rounded-full"
        ></span>

        <!-- Title aligned with dot -->
        <div class="flex items-center">
          <h3 class="text-sm font-medium text-gray-900 dark:text-gray-100">
            {{ event.title }}
          </h3>
        </div>

        <!-- Description -->
        <p class="text-sm text-gray-600 dark:text-gray-300 mt-1 mb-2">
          {{ event.description }}
        </p>

        <!-- Date at bottom -->
        <time class="block text-xs text-gray-400 dark:text-gray-500">
          {{ event.date }}
        </time>
      </div>
    </div>



  </div>
</template>

<script setup lang="ts">
import { withDefaults, defineProps } from 'vue'

interface TimelineEvent {
  date: string;
  title: string;
  description: string;
}

const props = withDefaults(
  defineProps<{
    title?: string;
    description?: string;
    events?: TimelineEvent[];
  }>(),
  {
    title: 'Project Timeline',
    description: 'Key milestones and progress overview.',
    events: [
      { date: '2025-01-10', title: 'Kickoff', description: 'The error of kickoff meeting and planning.' },
            { date: '2025-01-10', title: 'Done', description: '' },

    //   { date: '2025-02-20', title: 'Design Phase', description: 'Wireframes and design mockups completed.' },
    //   { date: '2025-04-05', title: 'Development', description: 'Core features implemented and initial build.' },
    //   { date: '2025-06-18', title: 'Testing', description: 'QA testing and bug fixes.' },
    //   { date: '2025-07-01', title: 'Launch', description: 'Official project release.' }
    ],
  }
)

const { title, description, events } = props
</script>

<style scoped>
/* Remove extra margin on last event */
.pl-4 > div:last-child {
  margin-bottom: 0;
}
</style>
