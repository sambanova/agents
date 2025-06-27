<template>
  <li class="py-2 relative color-primary-brandGray">
    <div
      v-if="!isLast"
      class="absolute left-0 top-0 h-full border-l-2 border-[#EAECF0]"
    ></div>

    <span
      class="absolute flex items-center justify-center w-6 h-6 bg-white rounded-full -start-3 ring-8 ring-white"
      :title="formatKey(data?.agent_name)"
    >
      <component class="size-[16px]" :is="iconComponent" />
    </span>

    <h3
      :class="collapsed ? 'invisible' : ''"
      class="flex ml-5 font-medium capitalize items-center mb-1 text-primary-brandTextPrimary text-[14px]"
    >
      {{ formatKey(data?.agent_name) }}
    </h3>

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
                <td class="px-1 py-0 font-semibold">Duration:</td>
                <td class="px-1 py-0">
                  {{ formattedDuration(data.metadata.duration) }} s
                </td>
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
import { marked } from 'marked';

import TimelineCollapsibleContent from '@/components/ChatMain/TimelineCollapsibleContent.vue';
import AggregatorAgentIcon from '@/components/icons/AggregatorAgentIcon.vue';
import CompetitorAnalysisAgentIcon from '@/components/icons/CompetitorAnalysisAgentIcon.vue';
import DataExtractionIcon from '@/components/icons/DataExtractionAgentIcon.vue';
import DefaultIcon from '@/components/icons/DefaultIcon.vue';
import EnhancedCompetitorAgentIcon from '@/components/icons/EnhancedCompetitorAgentIcon.vue';
import FinancialAnalysisAgentIcon from '@/components/icons/FinancialAnalysisAgentIcon.vue';
import FinancialNewsAgentIcon from '../icons/FinancialNewsAgentIcon.vue';
import FundamentalAnalysisAgentIcon from '@/components/icons/FundamentalAnalysisAgentIcon.vue';
import MarketTrendsAgentIcon from '@/components/icons/MarketTrendsAgentIcon.vue';
import NewsAgentIcon from '@/components/icons/NewsAgentIcon.vue';
import ResearchIcon from '@/components/icons/ResearchIcon.vue';
import RiskAssessmentAgentIcon from '@/components/icons/RiskAssessmentAgentIcon.vue';
import SpecialistIcon from '@/components/icons/SpecialistIcon.vue';
import TechIcon from '@/components/icons/TechIcon.vue';
import TechnicalAnalysisAgentIcon from '../icons/TechnicalAnalysisAgentIcon.vue';

const formattedDuration = (duration) => {
  // Format duration to 2 decimal places
  return duration.toFixed(2);
};

function formatKey(key) {
  return key.replace(/_/g, ' ');
}

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
    'Aggregator Agent': AggregatorAgentIcon,
    'Aggregator Search Agent': AggregatorAgentIcon,
    'Competitor Analysis Agent': CompetitorAnalysisAgentIcon,
    'Data Extraction Agent': DataExtractionIcon,
    'Enhanced Competitor Finder Agent': EnhancedCompetitorAgentIcon,
    'Financial Analysis Agent': FinancialAnalysisAgentIcon,
    'Financial News Agent': FinancialNewsAgentIcon,
    'Fundamental Analysis Agent': FundamentalAnalysisAgentIcon,
    'Market Trends Analyst': MarketTrendsAgentIcon,
    'News Agent': NewsAgentIcon,
    'Research Agent': ResearchIcon,
    'Risk Assessment Agent': RiskAssessmentAgentIcon,
    'Technical News Agent': TechIcon, // magnifying glass
    'Technical Analysis Agent': TechnicalAnalysisAgentIcon,
    'Outreach Specialist': SpecialistIcon,
  };
  const icon = agentIcons[agentName] || DefaultIcon;

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
  // Quick exit for non-strings
  if (typeof content !== 'string') return content;
  const trimmed = content.trim();
  // Only attempt to parse if it looks like an object/array literal
  if (
    (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
    (trimmed.startsWith('[') && trimmed.endsWith(']'))
  ) {
    // First attempt – standard JSON
    try {
      return JSON.parse(trimmed);
    } catch (eJson) {
      // Fallback: attempt to sanitise common python-dict quirks then parse again
      try {
        const sanitised = trimmed
          // convert single quotes to double quotes
          .replace(/([,{\s])'([^']*?)'(?=\s*:)/g, '$1"$2"') // keys
          .replace(/:(\s*)'([^']*?)'/g, ':$1"$2"') // string values
          // replace None / nan with null so JSON can parse
          .replace(/\bNone\b/g, 'null')
          .replace(/\bnan\b/gi, 'null');
        return JSON.parse(sanitised);
      } catch (eSanitised) {
        // Ultimate fallback – return original string so UI still renders
        console.warn('Could not parse JSON after sanitising:', eSanitised);
        return content;
      }
    }
  }
  // Not a JSON-looking string – return original
  return content;
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
