<template>
  <div class="parsed-content">
    <!-- Loop over parsed sections -->
    <div v-for="(section, index) in sections" :key="index" class="section mb-4">
      <!-- Render a heading if available -->
      <h3 v-if="section.title" class="section-title mb-1">
        {{ section.title }}
      </h3>
      <!-- Render the content as HTML -->
      <div class="section-content text-sm" v-html="renderMarkdown(section.content)"></div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'

// Configure a custom renderer for marked so that links are clickable and open in a new tab.
const renderer = new marked.Renderer()
renderer.link = function(href, title, text) {
  let out = `<a href="${href}" target="_blank" rel="noopener noreferrer">`
  out += text || href
  out += `</a>`
  return out
}
marked.setOptions({
  renderer,
  gfm: true,
  breaks: true
})

// Declare a prop "parsed" which can be either a string or an object.
const props = defineProps({
  parsed: {
    type: [String, Object],
    required: true
  }
})

// Helper: parse input data. If it's a string, try to JSON.parse it,
// otherwise assume it's an object.
function parseData(input) {
  if (typeof input === 'string') {
    try {
      return JSON.parse(input)
    } catch (e) {
      // If not valid JSON, return an object with raw text.
      return { text: input }
    }
  }
  return input
}

const parsedData = computed(() => parseData(props.parsed))

// If the parsed data contains a "data" property with "sections", use that;
// otherwise, assume a flat text string in "text" that needs to be parsed.
const sections = computed(() => {
  if (parsedData.value.data && Array.isArray(parsedData.value.data.sections)) {
    // Map each section in the sections array.
    // Here we assume each section object contains:
    // - title: the heading text
    // - generated_content: the content to display
    return parsedData.value.data.sections.map(sec => ({
      title: sec.title || '',
      content: sec.generated_content || ''
    }))
  } else {
    // Otherwise, use a fallback: parse a raw text (if available) from parsedData.value.text.
    const text = parsedData.value.text || ''
    return parseSections(text)
  }
})

// Fallback parser: split text into sections by headings ("Thought:" or "Final Answer:")
function parseSections(text) {
  const lines = text.split('\n')
  const sections = []
  let currentSection = { title: '', content: '' }
  for (let line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
    const match = trimmed.match(/^(Thought|Final Answer):\s*(.*)$/i)
    if (match) {
      if (currentSection.title || currentSection.content) {
        sections.push({ 
          title: currentSection.title, 
          content: currentSection.content.trim() 
        })
      }
      currentSection = { title: match[1].trim(), content: match[2] + "\n" }
    } else {
      currentSection.content += line + "\n"
    }
  }
  if (currentSection.title || currentSection.content) {
    sections.push({ 
      title: currentSection.title, 
      content: currentSection.content.trim() 
    })
  }
  return sections
}

// Render markdown to HTML using marked.
function renderMarkdown(text) {
  return marked(text || '')
}
</script>

<style scoped>
.parsed-content {
  font-family: sans-serif;
}
.section {
  margin-bottom: 1rem;
}
.section-title {
  font-weight: bold;
  font-size: 1.25rem;
  margin-bottom: 0.5rem;
}
.section-content {
  font-size: 1rem;
  line-height: 1.5;
}
</style>
