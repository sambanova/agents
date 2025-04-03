<template>
  <!-- This entire sidebar is collapsible. The container must have enough height to scroll internally. -->
  <div
    ref="agentContainer"
    v-if="agentThoughtsData.length"
    class="flex flex-col p-1 overflow-y-auto overflow-x-hidden border border-primary-brandFrame bg-white rounded-lg h-full border-l transition-all duration-300"
    :class="collapsed ? 'w-[64px]  ' : 'w-[280px]'"
  >
    <!-- Collapse/Expand Button -->
    <button
      :class="collapsed ? 'w-100 h-[36px]  mx-auto' : ' '"
      class="p-2 border-primary-brandFrame mb-2 border flex items-center justify-between w-full text-center bg-primary-brandGray text-primary-bodyText rounded text-sm"
      @click="collapsed = !collapsed"
      :title="
        collapsed
          ? 'Expand Agent Reasoning sidebar'
          : 'Collapse Agent Reasoning sidebar'
      "
    >
      <span :class="collapsed ? 'mx-auto' : ''" class="flex items-center">
        <span v-if="!collapsed">
          <!-- Expand icon -->
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-5 w-5 text-gray-700"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M9 5l7 7-7 7"
            />
          </svg>
        </span>

        <span v-else :class="collapsed ? 'mx-auto' : ''">
          <!-- Collapse icon -->
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-5 w-5 text-gray-700"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </span>
        <span v-if="!collapsed" class="ml-2">Agent Reasoning</span>
      </span>
      <span class="hidden" v-if="!collapsed">26 sources</span>
    </button>
    <div></div>

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
        <MetaData :presentMetadata="presentMetadata" />

        <Fastest />
        <MaximizeBox :token_savings="presentMetadata?.token_savings" />
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, computed, inject, onMounted } from 'vue';
import { useAuth, useUser } from '@clerk/vue';
import TimelineItem from '@/components/ChatMain/TimelineItem.vue';
import MetaData from '@/components/ChatMain/MetaData.vue';
import Fastest from '@/components/ChatMain/Fastest.vue';
import MaximizeBox from '@/components/ChatMain/MaximizeBox.vue';
import emitterMitt from '@/utils/eventBus';

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

const agentContainer = ref(null);
const agentThoughtsData = ref([]);
const metadata = ref(null);

// Clerk
const { userId } = useAuth();
const { user } = useUser();
// Mixpanel
const mixpanel = inject('mixpanel');

watch(
  () => props.metadata,
  (newMetadata, oldMetadata) => {
    console.log(
      'Child saw old Metadata array change from',
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

const sendMixpanelMetrics = () => {
  const agentThoughtsDataArray = Object.values(agentThoughtsData.value);
  const runId = agentThoughtsDataArray[0].run_id;
  // TODO: Do we need uniqueness on these?
  const agentNames = agentThoughtsDataArray.map(
    (entry) => entry.metadata.agent_name
  );
  const llmNames = agentThoughtsDataArray.map(
    (entry) => entry.metadata.llm_name
  );
  const workflowNames = agentThoughtsDataArray.map(
    (entry) => entry.metadata.workflow_name
  );
  const tasks = agentThoughtsDataArray
    .map((entry) => entry.metadata.task)
    .filter((task) => task !== ''); // Some agents return with empty task key

  const formattedAgentThoughtsData = {
    'Run ID': runId,
    'LLM Name(s)': llmNames,
    'Agent Name(s)': agentNames,
    'Workflow Name(s)': workflowNames,
    'Task(s)': tasks,
  };

  try {
    if (mixpanel) {
      mixpanel.track('Workflow Completions Details', {
        'User email': user?.value.emailAddresses[0].emailAddress,
        'User ID': userId.value,
        ...formattedAgentThoughtsData,
      });
    } else {
      console.warn('Mixpanel not available');
    }
  } catch (error) {
    console.error('Failed to send tracking data to Mixpanel:', error);
  }
};

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

onMounted(() => {
  emitterMitt.on('completion-reached', sendMixpanelMetrics);
});
</script>

<style scoped>
/* The container is "h-screen", ensuring the messages can scroll within "flex-1 overflow-y-auto". */
</style>
