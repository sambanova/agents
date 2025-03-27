<template>
  <!-- <div class="absolute left-3 top-0 h-full border-l-2 border-gray-200"></div> -->

  <li class="py-2 relative color-primary-brandGray">
    <div
      v-if="!isLast"
      class="absolute left-0 top-0 h-full border-l-2 border-[#EAECF0]"
    ></div>

    <span
      class="absolute flex items-center justify-center w-6 h-6 bg-white rounded-full -start-3 ring-8 ring-white"
    >
      <component class="size-[16px]" :is="iconComponent" />
    </span>

    <h3
      :class="collapsed ? 'invisible' : ''"
      class="flex ml-5 font-medium capitalize items-center mb-1 text-primary-brandTextPrimary text-[14px]"
    >
      {{ formatKey(data?.agent_name) }}
      <!-- <span class="bg-blue-100 text-blue-800 text-sm font-medium me-2 px-2.5 py-0.5 rounded-sm ms-3">Latest</span> -->
    </h3>

    <!-- <time class="block mb-2 text-sm font-normal leading-none text-gray-400">Released on January 13th, 2022</time> -->
    <div class="text-base font-normal text-gray-500">
      <div
        class="mx-2"
        v-for="(value, key) in parsedResponse"
        v-if="!collapsed"
      >
        <TimelineCollapsibleContent
          :value="value"
          :heading="key"
          :data="value"
        />
      </div>
      <div v-if="!collapsed" class="p-1 text text-right rounded text-xs">
        <button
          @click="toggleExpanded"
          class="m-0 p-0 text-primary-brandTextPrimary focus:outline-none"
        >
          {{ isExpanded ? '..hide' : 'more...' }}
        </button>
        <div v-if="isExpanded" class="bg-primary-brandGray p-2" name="slide">
          <table class="w-full text-left">
            <tbody>
              <tr>
                <td class="px-1 py-0 font-semibold">Name:</td>
                <td class="px-1 py-0">{{ data.metadata.llm_name }}</td>
              </tr>
              <tr>
                <td class="px-1 py-0 font-semibold">Task:</td>
                <td class="px-1 py-0">{{ data.metadata.task }}</td>
              </tr>
              <tr>
                <td class="px-1 py-0 font-semibold">Duration:</td>
                <td class="px-1 py-0">
                  {{ formattedDuration(data.metadata.duration) }} s
                </td>
              </tr>
              <tr>
                <td class="px-1 py-0 font-semibold">Provider:</td>
                <td class="px-1 py-0">{{ data.metadata.llm_provider }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </li>
</template>

<script setup>
import { computed, ref } from 'vue';
import TimelineCollapsibleContent from '@/components/ChatMain/TimelineCollapsibleContent.vue';
import SearchIcon from '@/components/icons/SearchIcon.vue';
import TechIcon from '@/components/icons/TechIcon.vue';
import SpecialistIcon from '@/components/icons/SpecialistIcon.vue';
import CompetitorIcon from '@/components/icons/CompetitorIcon.vue';
import NewsIcon from '@/components/icons/NewsIcon.vue';
import DataIcon from '@/components/icons/DataIcon.vue';
import RiskIcon from '@/components/icons/RiskIcon.vue';
import TrendsIcon from '@/components/icons/TrendsIcon.vue';
import DefaultIcon from '@/components/icons/DefaultIcon.vue';
import FundamentalIcon from '@/components/icons/FundamentalIcon.vue';
import ResearchIcon from '@/components/icons/ResearchIcon.vue';
import FinanceIcon from '@/components/icons/FinanceIcon.vue';
import AggregatorIcon from '@/components/icons/AggregatorIcon.vue';
import EnhancedCompetitorIcon from '@/components/icons/EnhancedCompetitorIcon.vue';
import { marked } from 'marked';

const formattedDuration = (duration) => {
  // Format duration to 2 decimal places
  return duration.toFixed(2);
};

function formatKey(key) {
  return key.replace(/_/g, ' ');
}
// State for accordion toggle (single toggle used for all sections in this example)
const isOpen = ref(false);

// Define props for TimelineItem
const props = defineProps({
  data: {
    type: Object,
    required: true,
  },
  collapsed: {
    type: Boolean,
    default: false,
  },
  isLast: {
    type: Boolean,
    default: false,
  },
});

// -------------------------------------------------------------------
// Helper Function: Return a Random Icon Based on Agent Name
// -------------------------------------------------------------------
function getAgentIcon(agentName) {
  const agentIcons = {
    'Aggregator Agent': AggregatorIcon,
    'Aggregator Search Agent': AggregatorIcon,
    'Competitor Analysis Agent': CompetitorIcon,
    'Data Extraction Agent': DataIcon,
    'Enhanced Competitor Finder Agent': EnhancedCompetitorIcon,
    'Financial Analysis Agent': FinanceIcon,
    'Financial News Agent': SearchIcon, // magnifying glass
    'Fundamental Analysis Agent': FundamentalIcon,
    'Market Trends Analyst': TrendsIcon,
    'News Agent': NewsIcon,
    'Research Agent': ResearchIcon,
    'Risk Assessment Agent': RiskIcon,
    'Technical News Agent': TechIcon, // magnifying glass
    'Outreach Specialist': SpecialistIcon,
  };
  const icon = agentIcons[agentName] || DefaultIcon;
  console.log('getAgentIcon called for agentName:', agentName, icon);

  return icon;
}

// Compute the icon component for this timeline item based on data.agent_name
const iconComponent = computed(() => getAgentIcon(props.data.agent_name));

/**
 * Parse props.data.text into sections.
 * Only lines starting with "Thought:" or "Final Answer:" (case-insensitive) start new sections.
 * All subsequent lines are appended to that section's content.
 */
const sections = computed(() => {
  // Added check: if props.data.text is an array, join it with newline.
  let text = props.data.text;
  if (Array.isArray(text)) {
    text = text.join('\n');
  }
  const lines = text.split('\n');
  const parsed = [];
  let currentSection = null;

  for (let line of lines) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    // Check for primary heading pattern
    const match = trimmed.match(
      /^(Thought|Final Answer|Action Input|Action):\s*(.*)$/i
    );

    if (match) {
      if (currentSection) {
        currentSection.content = currentSection.content.trim();
        parsed.push(currentSection);
      }
      currentSection = {
        title: match[1].trim(),
        content: match[2] ? match[2].trim() + '\n' : '\n',
      };
    } else {
      if (currentSection) {
        currentSection.content += trimmed + '\n';
      } else {
        // If there's no current section, create one with an empty title
        currentSection = { title: '', content: trimmed + '\n' };
      }
    }
  }
  if (currentSection) {
    currentSection.content = currentSection.content.trim();
    parsed.push(currentSection);
  }
  return parsed;
});

/**
 * Attempts to parse a string as JSON if it looks like a JSON block.
 * Otherwise, returns the original string.
 */
function tryParseJSON(content) {
  try {
    if (typeof content !== 'string') return content;
    const trimmed = content.trim();
    if (
      (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
      (trimmed.startsWith('[') && trimmed.endsWith(']'))
    ) {
      try {
        return JSON.parse(trimmed);
      } catch (e) {
        console.warn('Could not parse JSON:', e);
        return content;
      }
    }
    return content;
  } catch (e) {
    console.log('Error TimelineItem tryParseJSON', e);
    return content;
  }
}

/**
 * Parses the response text into sections.
 * It looks for lines that start with one of the keywords followed by a colon,
 * and then collects all subsequent lines until the next such heading.
 * If a key appears multiple times, its values are stored in an array.
 */
function parseResponseText(text) {
  // If text is an array, join it into a string.
  if (Array.isArray(text)) {
    text = text.join('\n');
  } else if (typeof text !== 'string') {
    // If text is an object and has a sections property, return that.
    if (text && typeof text === 'object' && Array.isArray(text.sections)) {
      return text.sections;
    }
    if (text && typeof text === 'object' && Array.isArray(text.queries)) {
      return text.queries;
    }
    // Otherwise, convert the text to a string.
    text = JSON.stringify(text);
  }

  // Check for special markers.
  const markers = ['Thought:', 'Final Answer:', 'Action Input:', 'Action:'];
  const hasMarker = markers.some((marker) => text.includes(marker));

  // If no marker is found but we have Markdown heading syntax.
  if (!hasMarker && /^#+\s+/m.test(text)) {
    // Split text by lines.
    const lines = text.split('\n');
    const result = {};
    let currentKey = '';
    let currentContent = '';
    lines.forEach((line) => {
      const headingMatch = line.match(/^(#+)\s+(.*)$/);
      if (headingMatch) {
        // If there is previous content, store it.
        if (currentKey || currentContent) {
          result[currentKey || 'Untitled'] = currentContent.trim();
        }
        // Set current key to heading text.
        currentKey = headingMatch[2].trim();
        currentContent = '';
      } else {
        currentContent += line + '\n';
      }
    });
    // Save last section.
    if (currentKey || currentContent) {
      result[currentKey || 'Untitled'] = currentContent.trim();
    }
    return result;
  }

  // If no markers and no markdown headings, treat entire text as one Markdown block.
  if (!hasMarker) {
    return { markdown: marked(text) };
  }
  const lines = text.split('\n');
  const keys = [
    'Thought',
    'Final Answer',
    'Action',
    'Action Input',
    'Observation',
  ];
  const result = {};
  let currentKey = null;
  let buffer = [];

  lines.forEach((line) => {
    const trimmed = line.trim();
    // Match a line that starts with one of the keys followed by a colon.
    const match = trimmed.match(/^(\w[\w\s]*):\s*(.*)$/);
    if (match && keys.includes(match[1].trim())) {
      if (currentKey) {
        const content = buffer.join('\n').trim();
        const parsedContent = tryParseJSON(content);
        if (result[currentKey]) {
          if (Array.isArray(result[currentKey])) {
            result[currentKey].push(parsedContent);
          } else {
            result[currentKey] = [result[currentKey], parsedContent];
          }
        } else {
          result[currentKey] = parsedContent;
        }
      }
      currentKey = match[1].trim();
      buffer = [];
      if (match[2]) {
        buffer.push(match[2]);
      }
    } else if (currentKey) {
      buffer.push(line);
    }
  });

  if (currentKey) {
    const content = buffer.join('\n').trim();
    const parsedContent = tryParseJSON(content);
    if (result[currentKey]) {
      if (Array.isArray(result[currentKey])) {
        result[currentKey].push(parsedContent);
      } else {
        result[currentKey] = [result[currentKey], parsedContent];
      }
    } else {
      result[currentKey] = parsedContent;
    }
  }
  return result;
}

const parsedResponse = computed(() => parseResponseText(props.data.text));

const isExpanded = ref(false);

function toggleExpanded() {
  isExpanded.value = !isExpanded.value;
}
</script>

<style scoped>
/* Adjust styles as needed */
.timeline-item {
  background-color: #fff;
}

.slide-enter-active,
.slide-leave-active {
  transition: max-height 0.3s ease, opacity 0.3s ease;
  overflow: hidden;
}
.slide-enter-from,
.slide-leave-to {
  max-height: 0;
  opacity: 0;
}
.slide-enter-to,
.slide-leave-from {
  max-height: 500px; /* adjust max-height as needed */
  opacity: 1;
}
</style>
