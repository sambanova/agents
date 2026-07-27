<template>
  <div class="assistant-message">
    
    <!-- Use consistent markdown rendering like the streaming section -->
    <div class="prose prose-sm max-w-none">
      <div 
        class="text-gray-800"
        v-html="renderMarkdown(parsed?.data?.response || parsed?.content || '')"
      ></div>
    </div>
  </div>
</template>

<script>

import { formattedText } from '@/utils/formatText'
import { renderMarkdown } from '@/utils/markdownRenderer'

export default {
  props: {
    // Expecting an object with the API response, e.g., { data: { response: "..." } }
    parsed: {
      type: Object,
      required: true,
    },
  },
  methods: {
    formattedText,  // Register the imported function here.
    renderMarkdown, // Use the shared markdown renderer
  },
  computed: {
    formattedTextOld() {
      // Extract the text from parsed.data.response or use an empty string
      const text = this.parsed.data?.response || '';
      const lines = text.split("\n");
      let html = "";
      let inList = false;
      // Match bullet lines starting with *, +, or -
      const bulletRegex = /^([*+-])\s+(.*)/;
      
      lines.forEach(line => {
        const trimmed = line.trim();
        const bulletMatch = trimmed.match(bulletRegex);
        if (bulletMatch) {
          if (!inList) {
            html += "<ul class='my-2'>";
            inList = true;
          }
          // Each bullet item gets an inline span for the bullet marker
          html += `<li class="custom-bullet"><span class="bullet-marker">•</span> ${bulletMatch[2]}</li>`;
        } else {
          if (inList) {
            html += "</ul>";
            inList = false;
          }
          if (trimmed.length > 0) {
            // If the line ends with a colon, treat it as a heading
            if (trimmed.endsWith(":")) {
              html += `<h2 class="md-heading text-[16px] font-semibold">${trimmed}</h2>`;
            } else {
              html += `<p class="md-paragraph">${trimmed}</p>`;
            }
          }
        }
      });
      
      if (inList) {
        html += "</ul>";
      }
      
      return html;
    }
  }
};



</script>

<style scoped>
/* Styling for headings (lines ending with a colon) */
.md-heading {
  color: #101828;
  font-family: 'Inter', sans-serif;
  font-weight: 600; /* Semibold */
  font-size: 16px;
  line-height: 24px;
  letter-spacing: 0;
  margin-bottom: 1rem;
  text-align: left;
}

/* Styling for normal paragraphs */
.md-paragraph {
  color: #101828;
  font-family: 'Inter', sans-serif;
  font-weight: 400;
  font-size: 16px;
  line-height: 24px;
  letter-spacing: 0;
  /* margin-bottom: 1rem; */
}

/* Remove default list styles */
.markdown-content ul {
  list-style: none;
  padding: 0;
  margin-bottom: 1rem;
}

/* Styling for bullet list items */
.custom-bullet {
  display: flex;
  align-items: center;
  font-family: 'Inter', sans-serif;
  font-weight: 600;
  font-size: 16px;
  line-height: 24px;
  letter-spacing: 0;
  color: #101828;
  margin-bottom: 0.5rem;
  position: relative;
  padding-right: 1.5rem; /* Reserve space for the inline bullet marker */
}

/* Inline bullet marker positioned on the right */
.bullet-marker {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  color: #101828;
  font-weight: 600;
  font-size: 32px;
  line-height: 24px;
  letter-spacing: 0;
  margin-left: 0.5rem;
}

p{
  line-height: 24px;
}

</style>
