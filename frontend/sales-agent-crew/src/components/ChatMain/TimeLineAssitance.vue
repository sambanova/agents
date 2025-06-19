<template>
  <div class="p-2">
    <div class="timeline relative">
      <div
        v-for="(event, idx) in timelineItems"
        :key="idx"
        class="timeline-item relative pl-4 mb-2 last:mb-0"
      >
        <!-- Dot -->
        <span
          class="absolute left-1 w-3 h-3 rounded-full border-2 bg-white dark:bg-gray-800
                         border-gray-200 dark:border-gray-700"
        ></span>

        <!-- Title -->
        <h3 class="text-sm ml-2 font-medium text-gray-900 dark:text-gray-100">
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
          <span
            v-if="event.type"
            class="bg-blue-100 dark:bg-blue-600 px-1 rounded"
          >
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
import { computed, withDefaults, defineProps } from 'vue'

interface AuditEvent {
  title: string
  details: string
  event?: string
  type?: string
  timestamp: string
  subItems?: Array<{ id: string; title: string; domain?: string }>
}

const props = withDefaults(
  defineProps<{
    toolSources?: Array<{ title: string; url: string }>
    allSources?: Array<{ title: string; url: string }>
      toolCalls?: Array<{ title: string; url: string }>
    auditLogEvents?: AuditEvent[]
  }>(),
  {
    toolSources: () => [],
    allSources: () => [],
    toolCalls: () => [],
    auditLogEvents: () => []
  }
)

const timelineItems = computed<AuditEvent[]>(() => {
  const now = new Date().toISOString()
  const items: AuditEvent[] = []

if(props.toolCalls&&props.toolCalls.length)
  for (const call of props.toolCalls) {
  items.push({
    title: call.title,
    details: call.details,
    event: call.event,
    type: call.type,
    timestamp: '',
    subItems: []
  })
}

   
  if (props.allSources.length > 0) {
    items.push({
      title: `${props.allSources.length} Web source${props.allSources.length > 1 ? 's' : ''} searched`,
      details: `Found ${props.allSources.length} unique website${props.allSources.length > 1 ? 's' : ''}`,
      event: 'summary',
      type: 'summary',
      timestamp: now,
      subItems: []
    })
  }

  if (props.toolSources.length > 0) {
    items.push({
      title: `Searched ${props.toolSources.length} research paper${props.toolSources.length > 1 ? 's' : ''}`,
      details: `Found ${props.toolSources.length} paper${props.toolSources.length > 1 ? 's' : ''}`,
      event: 'summary',
      type: 'summary',
      timestamp: now,
      subItems: []
    })
  }

  items.push(...props.auditLogEvents)

  items.push({
    title: 'Done',
    details: 'Analysis concluded',
    event: 'done',
    type: 'summary',
    timestamp: '',
    subItems: []
  })

  return items
})

function formatEventTime(ts: string): string {
  const date = new Date(ts)
  // if `date` is invalid, getTime() will be NaN
  if (isNaN(date.getTime())) {
    return ''
  }
  return date.toLocaleTimeString([], {
    hour:   '2-digit',
    minute: '2-digit'
  })
}

</script>

<style scoped>
.timeline {
  /* no padding here */
}

.timeline-item {
  position: relative;
  /* pl-4 moves content right, leaving 1rem gutter for dot+line */
}

/* Connector between dots */
.timeline-item:not(:last-child)::after {
  content: '';
  position: absolute;
  left: 0.5rem;               /* 8px in = center of dot at -left-2 */
  top: 0.5rem;                /* 8px down = center of dot (24px hi dot) */
  width: 2px;
  height: calc(100% + 1.5rem);/* spans this item + mb-6 (1.5rem) */
  background-color: rgba(229, 231, 235, var(--tw-border-opacity));
}
.dark .timeline-item:not(:last-child)::after {
  background-color: rgba(55, 65, 81, var(--tw-border-opacity));
}

/* Dot */
.timeline-item > span {
  /* already absolute -left-2 w-3 h-3 */
}

/* Remove bottom margin on last item */
.timeline-item.last\:mb-0:last-child {
  margin-bottom: 0;
}
</style>
