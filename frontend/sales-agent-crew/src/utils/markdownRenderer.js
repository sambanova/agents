// Shared markdown renderer utility
export function renderMarkdown(content) {
  if (!content) return ''
  
  // Enhanced markdown rendering with code syntax highlighting
  let html = content
    // Handle code blocks FIRST (before other processing)
    .replace(/```(\w+)?\n([\s\S]*?)```/g, (match, language, code) => {
      const lang = language || 'python'
      const highlightedCode = highlightCode(code.trim(), lang)
      return `<div class="my-4 bg-gray-900 rounded-lg overflow-hidden">
        <div class="bg-gray-800 px-4 py-2 text-xs text-gray-300 border-b border-gray-700 flex items-center space-x-2">
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
          </svg>
          <span>${lang.charAt(0).toUpperCase() + lang.slice(1)} Code</span>
        </div>
        <div class="p-4 overflow-auto">
          <pre class="text-sm"><code class="text-green-400">${highlightedCode}</code></pre>
        </div>
      </div>`
    })
    // Links MUST be processed after code blocks but before other formatting
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, text, url) => {
      // Clean the URL of any trailing characters
      const cleanUrl = url.trim()
      return `<a href="${cleanUrl}" target="_blank" rel="noopener noreferrer" class="text-blue-600 hover:text-blue-800 underline">${text}</a>`
    })
    // Bold and italic 
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    // Inline code (skip if inside existing code tags)
    .replace(/`([^`]+)`/g, '<code class="bg-gray-100 px-1 rounded text-sm font-mono">$1</code>')
    // Basic headers
    .replace(/^### (.*$)/gm, '<h3 class="text-lg font-semibold mt-4 mb-2 text-gray-900">$1</h3>')
    .replace(/^## (.*$)/gm, '<h2 class="text-xl font-semibold mt-4 mb-2 text-gray-900">$1</h2>')
    .replace(/^# (.*$)/gm, '<h1 class="text-2xl font-bold mt-4 mb-3 text-gray-900">$1</h1>')
    // Paragraphs and line breaks
    .replace(/\n\n/g, '</p><p class="mb-3">')
    .replace(/\n/g, '<br>')
  
  return `<p class="mb-3">${html}</p>`
}

function highlightCode(code, language) {
  if (!code) return ''
  
  switch (language.toLowerCase()) {
    case 'python':
      return highlightPython(code)
    case 'javascript':
    case 'js':
      return highlightJavaScript(code)
    default:
      return code // Return plain code for unsupported languages
  }
}

function highlightPython(code) {
  return code
    // Python keywords
    .replace(/(import|from|def|class|if|else|elif|for|while|try|except|with|as|return|yield|break|continue|pass|and|or|not|in|is|lambda|global|nonlocal)/g, '<span class="text-blue-400">$1</span>')
    // Python built-ins
    .replace(/(True|False|None|self|__init__|__name__|__main__)/g, '<span class="text-purple-400">$1</span>')
    // Strings (handle both single and double quotes)
    .replace(/(['"`])((?:(?!\1)[^\\]|\\.)*)(\1)/g, '<span class="text-yellow-400">$1$2$3</span>')
    // Numbers
    .replace(/\b(\d+\.?\d*)\b/g, '<span class="text-red-400">$1</span>')
    // Comments
    .replace(/(#.*$)/gm, '<span class="text-gray-500">$1</span>')
    // Function calls
    .replace(/\b(\w+)(?=\()/g, '<span class="text-cyan-400">$1</span>')
}

function highlightJavaScript(code) {
  return code
    // JavaScript keywords
    .replace(/(const|let|var|function|if|else|for|while|return|try|catch|finally|class|extends|import|export|from|default)/g, '<span class="text-blue-400">$1</span>')
    // JavaScript built-ins
    .replace(/(true|false|null|undefined|this|new|typeof|instanceof)/g, '<span class="text-purple-400">$1</span>')
    // Strings
    .replace(/(['"`])((?:(?!\1)[^\\]|\\.)*)(\1)/g, '<span class="text-yellow-400">$1$2$3</span>')
    // Numbers
    .replace(/\b(\d+\.?\d*)\b/g, '<span class="text-red-400">$1</span>')
    // Comments
    .replace(/(\/\/.*$)/gm, '<span class="text-gray-500">$1</span>')
    .replace(/(\/\*[\s\S]*?\*\/)/g, '<span class="text-gray-500">$1</span>')
} 