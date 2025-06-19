<template>
  <div class="p-2">
    <div class="timeline relative pl-4">
      <div
        v-for="(event, idx) in timelineItems"
        :key="idx"
        class="timeline-item relative mb-6 last:mb-0"
      >
        <!-- Dot -->
        <span
          class="absolute -left-4 w-3 h-3 rounded-full border-2 bg-white dark:bg-gray-800
                 border-gray-200 dark:border-gray-700"
        ></span>

        <!-- Title -->
        <h3 class="text-sm font-medium text-gray-900 dark:text-gray-100">
          {{ event.title }}
        </h3>

        <!-- Details -->
        <div class="text-sm text-gray-600 dark:text-gray-300 mt-1 mb-2">
          {{ event.details }}
        </div>

        <!-- Sub-items -->
        <div
          v-if="event.subItems?.length"
          class="ml-4 space-y-1 text-xs text-gray-600 dark:text-gray-400"
        >
          <div
            v-for="sub in event.subItems"
            :key="sub.id"
            class="flex items-start space-x-1"
          >
            <span>•</span>
            <span>
              {{ sub.title }}
              <span v-if="sub.domain">({{ sub.domain }})</span>
            </span>
          </div>
        </div>

        <!-- Meta tags -->
        <div class="text-xs text-gray-400 dark:text-gray-600 mt-1 space-x-1">
          <span class="bg-gray-100 dark:bg-gray-600 px-1 rounded">{{ event.event }}</span>
          <span v-if="event.type" class="bg-blue-100 dark:bg-blue-600 px-1 rounded">
            {{ event.type }}
          </span>
        </div>

        <!-- Timestamp -->
        <time class="block text-xs text-gray-400 dark:text-gray-500 mt-1">
          {{ formatEventTime(event.timestamp) }}
        </time>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface AuditEvent {
  title: string
  details: string
  event?: string
  type?: string
  timestamp: string
  subItems?: Array<{ id: string; title: string; domain?: string }>
}

const props = defineProps<{
  auditLogEvents: AuditEvent[]
}>()

// Always prepend a "Done" entry with current time
const timelineItems = computed<AuditEvent[]>(() => {
  const now = new Date().toISOString()
  const doneEntry: AuditEvent = {
    title: 'Done',
    details: 'Analysis concluded',
    event: 'done',
    type: 'summary',
    timestamp: now,
    subItems: []
  }
  return [ ...props.auditLogEvents, doneEntry || []]
})

function formatEventTime(ts: string) {
  return new Date(ts).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<style scoped>
.timeline {
  position: relative;
  padding-left: 1rem;
}

.timeline::before {
  content: '';
  position: absolute;
  left: 0.375rem;    /* Align with dot center */
  top: 0.375rem;     /* Start at first dot center */
  bottom: 0.375rem;  /* End at last dot center */
  width: 2px;
  background-color: rgba(229, 231, 235, var(--tw-border-opacity));
}
.dark .timeline::before {
  background-color: rgba(55, 65, 81, var(--tw-border-opacity));
}

.timeline-item {
  position: relative;
}

/* Ensure last item has no extra bottom margin */
.last\:mb-0:last-child {
  margin-bottom: 0;
}
</style>
