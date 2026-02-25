import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({
  gfm: true,
  tables: true,
  breaks: true,
  headerIds: true,
  mangle: false,
  smartypants: true,
})

// Shared markdown renderer utility — all output sanitized via DOMPurify
export function renderMarkdown(content) {
  if (!content) return ''
  return DOMPurify.sanitize(marked(content))
}
