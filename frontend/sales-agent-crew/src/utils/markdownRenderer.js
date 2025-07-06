import { marked } from 'marked'

marked.setOptions({
  // GitHub-Flavored Markdown
  gfm: true,
  tables: true,
  breaks: true,
  headerIds: true,
  mangle: false,      // leave emails intact
  smartypants: true,  // typographic replacements
  sanitize: false,    // Allow blob URLs
  // Syntax highlighting (you can swap in highlight.js or prism)
  highlight: (code, lang) => {
    // very basic example; swap for a real highlighter in prod
    return require('highlight.js').highlightAuto(code, [lang]).value;
  }
})

// Shared markdown renderer utility - simple wrapper around marked
export function renderMarkdown(content) {
  if (!content) return ''
  return marked(content)
} 