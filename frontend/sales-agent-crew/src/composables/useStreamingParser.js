import { ref } from 'vue'

export function useStreamingParser() {
  const accumulatedContent = ref('')
  const toolCallBuffer = ref('')
  const isInToolCall = ref(false)

  // Regex patterns for detecting tool calls
  const TOOL_CALL_PATTERNS = {
    // Pattern: <tool>toolname</tool><tool_input>input
    xml_pattern: /<tool>([^<]+)<\/tool><tool_input>(.+?)(?=<\/tool_input>|$)/s,
    
    // Pattern: <tool>toolname</tool><tool_input>input</tool_input>
    xml_complete_pattern: /<tool>([^<]+)<\/tool><tool_input>(.*?)<\/tool_input>/s,
    
    // Alternative patterns for different formats
    function_call_pattern: /function_call:\s*(\w+)\s*\((.*?)\)/s,
    action_pattern: /Action:\s*(\w+)\s*Action Input:\s*(.*?)(?=\n|$)/s
  }

  const parseToolCall = (content) => {
    if (!content) return null

    // Accumulate content for parsing
    accumulatedContent.value += content

    // Try different patterns
    for (const [patternName, pattern] of Object.entries(TOOL_CALL_PATTERNS)) {
      const match = accumulatedContent.value.match(pattern)
      if (match) {
        const toolName = match[1].trim()
        const input = match[2].trim()
        
        // Clear accumulated content after successful parse
        accumulatedContent.value = ''
        
        return {
          toolName,
          input,
          pattern: patternName,
          fullMatch: match[0]
        }
      }
    }

    // Check for partial tool calls to determine if we're in the middle of one
    if (isPartialToolCall(accumulatedContent.value)) {
      isInToolCall.value = true
    } else if (!content.includes('<tool>') && !content.includes('Action:')) {
      // If we're not seeing tool indicators, reset
      isInToolCall.value = false
      // Keep only recent content to prevent unbounded growth
      if (accumulatedContent.value.length > 1000) {
        accumulatedContent.value = accumulatedContent.value.slice(-500)
      }
    }

    return null
  }

  const isPartialToolCall = (content) => {
    // Check for incomplete tool call patterns
    const partialPatterns = [
      /<tool>[^<]*$/,  // Started tool tag but not complete
      /<tool>[^<]+<\/tool><tool_input>.*$/,  // Has tool name, started input
      /Action:\s*\w*$/,  // Started action
      /function_call:\s*\w*$/  // Started function call
    ]

    return partialPatterns.some(pattern => pattern.test(content))
  }

  const parseSearchQuery = (input) => {
    // Extract search query from various input formats
    try {
      // Try parsing as JSON first
      const parsed = JSON.parse(input)
      return parsed.query || parsed.search_query || parsed.q || input
    } catch {
      // If not JSON, treat as plain text
      return input.replace(/^["']|["']$/g, '').trim()
    }
  }

  const parseCodeInput = (input) => {
    // Extract code from sandbox input
    try {
      const parsed = JSON.parse(input)
      return parsed.code || parsed.python_code || input
    } catch {
      return input
    }
  }

  const extractSources = (content) => {
    // Extract source information from tool responses
    if (!content) return []

    try {
      // Try parsing as JSON array of sources
      if (content.startsWith('[') && content.endsWith(']')) {
        const sources = JSON.parse(content)
        return sources.map(source => ({
          title: source.title || 'Untitled',
          url: source.url || '#',
          content: source.content || '',
          snippet: (source.content || '').substring(0, 200) + '...'
        }))
      }

      // Try parsing structured text
      if (content.includes('Title:') && content.includes('URL:')) {
        const sources = []
        const sections = content.split(/\n\s*\n/)
        
        for (const section of sections) {
          const titleMatch = section.match(/Title:\s*(.+?)(?=\n|$)/i)
          const urlMatch = section.match(/URL:\s*(.+?)(?=\n|$)/i)
          const contentMatch = section.match(/Content:\s*([\s\S]+?)(?=\n\s*Title:|$)/i)
          
          if (titleMatch) {
            sources.push({
              title: titleMatch[1].trim(),
              url: urlMatch ? urlMatch[1].trim() : '#',
              content: contentMatch ? contentMatch[1].trim() : '',
              snippet: contentMatch ? contentMatch[1].trim().substring(0, 200) + '...' : ''
            })
          }
        }
        
        return sources
      }

      return []
    } catch (error) {
      console.error('Error extracting sources:', error)
      return []
    }
  }

  const extractArtifacts = (content) => {
    // Extract artifact references like ![title](attachment:id)
    if (!content) return []

    const artifactPattern = /!\[([^\]]*)\]\(attachment:([^)]+)\)/g
    const artifacts = []
    let match

    while ((match = artifactPattern.exec(content)) !== null) {
      artifacts.push({
        type: 'image', // Default to image, could be chart, table, etc.
        title: match[1] || 'Untitled',
        id: match[2],
        url: `attachment:${match[2]}`,
        htmlContent: `<img src="attachment:${match[2]}" alt="${match[1]}" class="max-w-full h-auto" />`
      })
    }

    return artifacts
  }

  const detectStreamingToolCall = (chunk) => {
    // More sophisticated detection for streaming tool calls
    const indicators = [
      '<tool>',
      'Action:',
      'function_call:',
      'Thought:',
      'search_tavily',
      'arxiv',
      'DaytonaCodeSandbox'
    ]

    return indicators.some(indicator => chunk.includes(indicator))
  }

  const getToolType = (toolName) => {
    // Categorize tools for better UI handling
    const toolTypes = {
      'search_tavily': 'search',
      'search_tavily_answer': 'search',
      'arxiv': 'research',
      'DaytonaCodeSandbox': 'code',
      'wikipedia': 'research',
      'ddg_search': 'search'
    }

    return toolTypes[toolName] || 'unknown'
  }

  const formatToolInput = (toolName, input) => {
    // Format tool input for display
    const toolType = getToolType(toolName)
    
    switch (toolType) {
      case 'search':
        return parseSearchQuery(input)
      case 'code':
        return parseCodeInput(input)
      case 'research':
        return parseSearchQuery(input)
      default:
        return input
    }
  }

  const reset = () => {
    accumulatedContent.value = ''
    toolCallBuffer.value = ''
    isInToolCall.value = false
  }

  return {
    parseToolCall,
    parseSearchQuery,
    parseCodeInput,
    extractSources,
    extractArtifacts,
    detectStreamingToolCall,
    getToolType,
    formatToolInput,
    isPartialToolCall,
    reset,
    
    // Reactive state
    accumulatedContent,
    toolCallBuffer,
    isInToolCall
  }
} 