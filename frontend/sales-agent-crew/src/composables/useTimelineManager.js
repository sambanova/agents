import { ref, computed } from 'vue'
import { v4 as uuidv4 } from 'uuid'

export function useTimelineManager() {
  const items = ref([])
  const activeItem = ref(null)

  const createTimelineItem = (options = {}) => {
    const {
      type = 'unknown',
      title = 'Timeline Item',
      content = '',
      timestamp = new Date().toISOString(),
      status = 'pending',
      data = {},
      ...extraProps
    } = options

    const item = {
      id: uuidv4(),
      type,
      title,
      content,
      timestamp,
      status,
      data,
      createdAt: Date.now(),
      updatedAt: Date.now(),
      ...extraProps
    }

    return item
  }

  const addItem = (item) => {
    items.value.push(item)
    return item
  }

  const updateItem = (id, updates) => {
    const index = items.value.findIndex(item => item.id === id)
    if (index > -1) {
      items.value[index] = {
        ...items.value[index],
        ...updates,
        updatedAt: Date.now()
      }
      return items.value[index]
    }
    return null
  }

  const removeItem = (id) => {
    const index = items.value.findIndex(item => item.id === id)
    if (index > -1) {
      const removed = items.value.splice(index, 1)[0]
      if (activeItem.value?.id === id) {
        activeItem.value = null
      }
      return removed
    }
    return null
  }

  const findItem = (predicate) => {
    return items.value.find(predicate)
  }

  const findItems = (predicate) => {
    return items.value.filter(predicate)
  }

  const getItemById = (id) => {
    return items.value.find(item => item.id === id)
  }

  const getItemsByType = (type) => {
    return items.value.filter(item => item.type === type)
  }

  const getItemsByStatus = (status) => {
    return items.value.filter(item => item.status === status)
  }

  const getLatestItem = () => {
    if (items.value.length === 0) return null
    return items.value[items.value.length - 1]
  }

  const getItemsInRange = (startTime, endTime) => {
    return items.value.filter(item => {
      const itemTime = new Date(item.timestamp).getTime()
      return itemTime >= startTime && itemTime <= endTime
    })
  }

  const clearItems = () => {
    items.value = []
    activeItem.value = null
  }

  const setActiveItem = (id) => {
    const item = getItemById(id)
    if (item) {
      activeItem.value = item
    }
  }

  const clearActiveItem = () => {
    activeItem.value = null
  }

  // Tool-specific item creators
  const createToolCallItem = (toolName, input, options = {}) => {
    return createTimelineItem({
      type: 'tool_call',
      title: `Calling ${toolName}`,
      toolName,
      input,
      status: 'executing',
      ...options
    })
  }

  const createToolResponseItem = (toolName, content, options = {}) => {
    return createTimelineItem({
      type: 'tool_response',
      title: `${toolName} Response`,
      toolName,
      content,
      status: 'completed',
      ...options
    })
  }

  const createSearchItem = (query, options = {}) => {
    return createTimelineItem({
      type: 'search',
      title: `Searching: "${query}"`,
      searchQuery: query,
      status: 'searching',
      ...options
    })
  }

  const createCodeExecutionItem = (code, options = {}) => {
    return createTimelineItem({
      type: 'code_execution',
      title: 'Executing Code',
      code,
      status: 'executing',
      ...options
    })
  }

  const createStreamChunkItem = (content, chunkId, options = {}) => {
    return createTimelineItem({
      type: 'llm_chunk',
      title: 'AI Response',
      content,
      chunkId,
      status: 'streaming',
      ...options
    })
  }

  const createArtifactItem = (artifact, options = {}) => {
    return createTimelineItem({
      type: 'artifact',
      title: artifact.title || 'Artifact Created',
      artifact,
      status: 'completed',
      ...options
    })
  }

  // Status management
  const updateItemStatus = (id, status, additionalUpdates = {}) => {
    return updateItem(id, { status, ...additionalUpdates })
  }

  const markItemAsCompleted = (id, result = null) => {
    const updates = { status: 'completed' }
    if (result !== null) {
      updates.result = result
    }
    return updateItem(id, updates)
  }

  const markItemAsError = (id, error) => {
    return updateItem(id, { status: 'error', error })
  }

  // Computed properties
  const itemCount = computed(() => items.value.length)
  
  const itemsByType = computed(() => {
    const grouped = {}
    items.value.forEach(item => {
      if (!grouped[item.type]) {
        grouped[item.type] = []
      }
      grouped[item.type].push(item)
    })
    return grouped
  })

  const pendingItems = computed(() => 
    items.value.filter(item => item.status === 'pending' || item.status === 'executing')
  )

  const completedItems = computed(() => 
    items.value.filter(item => item.status === 'completed')
  )

  const errorItems = computed(() => 
    items.value.filter(item => item.status === 'error')
  )

  const sortedItems = computed(() => {
    return [...items.value].sort((a, b) => 
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    )
  })

  // Statistics
  const getStatistics = () => {
    const stats = {
      total: items.value.length,
      byType: {},
      byStatus: {},
      timeRange: null
    }

    items.value.forEach(item => {
      // Count by type
      stats.byType[item.type] = (stats.byType[item.type] || 0) + 1
      
      // Count by status
      stats.byStatus[item.status] = (stats.byStatus[item.status] || 0) + 1
    })

    // Calculate time range
    if (items.value.length > 0) {
      const timestamps = items.value.map(item => new Date(item.timestamp).getTime())
      stats.timeRange = {
        start: Math.min(...timestamps),
        end: Math.max(...timestamps),
        duration: Math.max(...timestamps) - Math.min(...timestamps)
      }
    }

    return stats
  }

  // Export timeline data
  const exportTimeline = () => {
    return {
      version: '1.0',
      exportedAt: new Date().toISOString(),
      items: items.value,
      statistics: getStatistics()
    }
  }

  // Import timeline data
  const importTimeline = (data) => {
    if (data.version === '1.0' && Array.isArray(data.items)) {
      items.value = data.items
      return true
    }
    return false
  }

  return {
    // State
    items,
    activeItem,

    // Core methods
    createTimelineItem,
    addItem,
    updateItem,
    removeItem,
    findItem,
    findItems,
    getItemById,
    getItemsByType,
    getItemsByStatus,
    getLatestItem,
    getItemsInRange,
    clearItems,
    setActiveItem,
    clearActiveItem,

    // Tool-specific creators
    createToolCallItem,
    createToolResponseItem,
    createSearchItem,
    createCodeExecutionItem,
    createStreamChunkItem,
    createArtifactItem,

    // Status management
    updateItemStatus,
    markItemAsCompleted,
    markItemAsError,

    // Computed properties
    itemCount,
    itemsByType,
    pendingItems,
    completedItems,
    errorItems,
    sortedItems,

    // Utilities
    getStatistics,
    exportTimeline,
    importTimeline
  }
} 