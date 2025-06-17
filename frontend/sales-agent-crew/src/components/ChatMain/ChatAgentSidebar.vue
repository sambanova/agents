<template>
  <!-- This entire sidebar is collapsible. The container must have enough height to scroll internally. -->
  <div
    ref="agentContainer"
    v-if="agentThoughtsData.length"
    :class="[
      'flex flex-col p-1 overflow-y-auto overflow-x-hidden border rounded-lg h-full border-l transition-all duration-300 bg-white dark:bg-gray-800',
      collapsed ? 'w-[64px]' : 'w-[280px]',
      'border-primary-brandFrame dark:border-gray-600'
    ]"
  >
    <!-- Collapse/Expand Button -->
    <button
      @click="collapsed = !collapsed"
      :title="collapsed ? 'Expand Agent Reasoning sidebar' : 'Collapse Agent Reasoning sidebar'"
      :class="[
        'p-2 mb-2 border flex items-center justify-between w-full text-center rounded text-sm bg-primary-brandGray text-primary-bodyText dark:bg-gray-700 dark:text-gray-200',
        'border-primary-brandFrame dark:border-gray-600',
        collapsed ? 'w-100 h-[36px] mx-auto' : ''
      ]"
    >
      <span :class="[ 'flex items-center', collapsed ? 'mx-auto' : '' ]">
        <span v-if="!collapsed">
          <!-- Expand icon -->
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-5 w-5 text-gray-700 dark:text-gray-300"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M9 5l7 7-7 7" />
          </svg>
        </span>

        <span v-else>
          <!-- Collapse icon -->
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-5 w-5 text-gray-700 dark:text-gray-300"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M15 19l-7-7 7-7" />
          </svg>
        </span>

        <span v-if="!collapsed" class="ml-2">Agent Reasoning</span>
      </span>
      <span class="hidden" v-if="!collapsed">26 sources</span>
    </button>

    <div class="mx-2">
      <ol class="relative pl-2">
        <TimelineItem
          v-for="(thought, index) in agentThoughtsData"
          :key="index"
          :data="thought"
          :isLast="index === agentThoughtsData.length - 1"
          period="Researcher"
          description="The company has high expectations and using OKRs there is a mutual understanding of expectations and performance."
          :bullets="[
            'Designed template UIs in Figma',
            'Converted UIs into responsive HTML/CSS',
          ]"
          :iconSvg="agentIcon"
          :collapsed="collapsed"
          :card="{
            href: '#',
            imgSrc:
              'https://images.unsplash.com/photo-1661956600655-e772b2b97db4?q=80&w=560&auto=format&fit=crop',
            imgAlt: 'Blog Image',
            title: 'Studio by Mailchimp',
            subtitle: 'Produce professional, reliable streams using Mailchimp.',
          }"
        />
      </ol>

      <template v-if="metadata && !collapsed">
        <!-- Render only available metadata fields -->
        <MetaData :presentMetadata="presentMetadata" class="dark:bg-gray-800" />

        <Fastest class="dark:bg-gray-800" />
        <MaximizeBox
          :token_savings="presentMetadata?.token_savings"
          class="dark:bg-gray-800"
        />
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, computed } from 'vue';
import TimelineItem from '@/components/ChatMain/TimelineItem.vue';
import MetaData from '@/components/ChatMain/MetaData.vue';
import Fastest from '@/components/ChatMain/Fastest.vue';
import MaximizeBox from '@/components/ChatMain/MaximizeBox.vue';

const agentContainer = ref(null);

// Reactive variables to store parsed data from the WebSocket.
const agentName = ref('');
const timestamp = ref(0);
const sections = ref([]);

// This ref holds all the log messages concatenated as a single string.
const logs = ref('No data received yet.\n');

// Variable to store the WebSocket instance.
let socket = null;

// Function to establish the WebSocket connection.
function connectWebSocket() {
  // Construct the base WebSocket URL with /chat endpoint
  let WEBSOCKET_URL =
    import.meta.env.VITE_WEBSOCKET_URL || 'ws://localhost:8000';
  WEBSOCKET_URL = `${WEBSOCKET_URL}/chat`;

  // Construct the full URL using query parameters.
  const fullUrl = `${WEBSOCKET_URL}?user_id=${props.userId}&conversation_id=${props.runId}`;
  console.log('Connecting to:', fullUrl);
  socket = new WebSocket(fullUrl);

  socket.onopen = () => {
    console.log('WebSocket connection opened');
    // Log the connection open event.
    logs.value += `Connection opened at ${new Date().toLocaleTimeString()}\n`;
    // Send the initial payload.
    const payload = {
      event: 'user_input',
      data: 'Iphone vs android',
    };
    socket.send(JSON.stringify(payload));
    logs.value += `Sent: ${JSON.stringify(payload)}\n`;
  };

  socket.onmessage = (event) => {
    console.log('Received message:', event.data);
    // Append the received data to the log with a newline.
    logs.value += `${event.data}\n`;

    try {
      const outerData = JSON.parse(event.data);
      // Parse the inner data string.
      const innerData = JSON.parse(outerData.data);
      // Set agent name and timestamp.
      agentName.value = innerData.agent_name;
      timestamp.value = innerData.timestamp;
      // Parse the text field into sections.
      sections.value = parseSections(innerData.text);
    } catch (error) {
      console.error('Error parsing message:', error);
    }
  };

  socket.onerror = (error) => {
    console.error('WebSocket error:', error);
    logs.value += `Error: ${error.message || 'Unknown error'}\n`;
  };

  socket.onclose = (event) => {
    console.log('WebSocket connection closed:', event);
    logs.value += `Connection closed at ${new Date().toLocaleTimeString()}\n`;
  };
}

function parseSections(text) {
  const lines = text.split(/\r?\n/);
  const result = [];
  let currentSection = { heading: '', content: '' };

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue; // skip blank lines

    // Check if the line contains a colon in the middle. If the colon is the last character, treat as a heading.
    if (trimmed.endsWith(':')) {
      // If there is an active section, push it.
      if (currentSection.heading || currentSection.content) {
        result.push({
          heading: currentSection.heading,
          content: currentSection.content.trim(),
        });
      }
      // Start new section with heading (remove the colon)
      currentSection = { heading: trimmed.slice(0, -1), content: '' };
    } else {
      // Check if the line contains a colon (e.g. "Thought: I now know the final answer")
      const colonIndex = trimmed.indexOf(':');
      if (colonIndex > 0) {
        // If the part before the colon appears to be a heading (e.g. "Thought"), then treat it as a new section.
        const potentialHeading = trimmed.slice(0, colonIndex).trim();
        const potentialContent = trimmed.slice(colonIndex + 1).trim();
        // If currentSection is not empty, push it.
        if (currentSection.heading || currentSection.content) {
          result.push({
            heading: currentSection.heading,
            content: currentSection.content.trim(),
          });
        }
        currentSection = {
          heading: potentialHeading,
          content: potentialContent + ' ',
        };
      } else {
        // Otherwise, add the line to the current section's content.
        currentSection.content += trimmed + ' ';
      }
    }
  }
  if (currentSection.heading || currentSection.content) {
    result.push({
      heading: currentSection.heading,
      content: currentSection.content.trim(),
    });
  }
  return result;
}
// PROPS
const props = defineProps({
  userId: {
    type: String,
    default: '',
  },
  conversationId: {
    type: String,
    default: '',
  },
  runId: {
    type: String,
    default: '',
  },
  agentData: {
    type: Array,
    default: () => [],
  },
  metadata: {
    type: Object, // or Array, depending on your data
    default: () => ({}), // or [] if you expect an array
  },
});
const agentThoughtsData = ref([]);
const metadata = ref(null);

watch(
  () => props.metadata,
  (newMetadata, oldMetadata) => {
    console.log(
      'Child sawold Metadata array change from',
      oldMetadata,
      'to',
      newMetadata
    );

    metadata.value = newMetadata || null;
  },
  { deep: true } // If you want to detect nested mutations
);
watch(
  () => props.agentData,
  (newAgentData, oldAgentData) => {
    console.log(
      'Child saw array change from',
      oldAgentData,
      'to',
      newAgentData
    );

    agentThoughtsData.value = newAgentData || [];
    nextTick(() => {
      setTimeout(() => {
        if (agentContainer.value) {
          agentContainer.value.scrollTo({
            top: agentContainer.value.scrollHeight,
            behavior: 'smooth',
          });
        }
      }, 100); // Adjust the delay (in ms) as needed
    });
  },
  { deep: true } // If you want to detect nested mutations
);
const collapsed = ref(false);

// SSE
const messages = ref([]);

// Refs
const scrollContainer = ref(null);

const agentIcon = `
    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-gray-600"
         fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M12 4v16m8-8H4"/>
    </svg>
  `;

/**
 * Actually scroll to bottom of the container
 */
function autoScrollToBottom() {
  if (!scrollContainer.value) return;
  // nextTick => setTimeout => do scroll
  nextTick(() => {
    setTimeout(() => {
      scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight;
    }, 50);
  });
}

/**
 * Watch messages => autoScroll #2 (in case SSE immediate wasn't enough)
 */
watch(messages, () => {
  autoScrollToBottom();
});

const presentMetadata = computed(() => {
  return props.metadata;
});

const formattedDuration = (duration) => {
  // Format duration to 2 decimal places
  return duration?.toFixed(2);
};
</script>

<style scoped>
/* The container is "h-screen", ensuring the messages can scroll within "flex-1 overflow-y-auto". */
</style>
