<template>
 <!-- Parsed message {{ parsed?.content }} -->
  
  <div class="assistant-message">
    
    <!-- Use consistent markdown rendering like the streaming section -->
    <div class="prose prose-sm max-w-none">
      <div 
        class="text-gray-800"
        v-html="processedContent"
        style="word-wrap: break-word;"
        @click="handleChartLinkClick"
      ></div>
    </div>

    <!-- Chart Modal -->
    <div 
      v-if="showModal" 
      class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 modal-backdrop"
      @click="closeModal"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="'modal-title-' + Date.now()"
    >
      <div 
        class="bg-white rounded-lg p-6 max-w-4xl max-h-[90vh] overflow-auto modal-content"
        @click.stop
      >
        <div class="flex justify-between items-center mb-4">
          <h3 
            :id="'modal-title-' + Date.now()"
            class="text-lg font-semibold text-gray-900"
          >
            {{ modalChartTitle }}
          </h3>
          <button 
            @click="closeModal"
            class="text-gray-500 hover:text-gray-700 text-xl font-bold w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-100 transition-colors"
            aria-label="Close modal"
          >
            ×
          </button>
        </div>
        <div class="text-center">
          <img 
            v-if="modalChartUrl"
            :src="modalChartUrl" 
            :alt="modalChartTitle"
            class="max-w-full h-auto rounded-lg shadow-lg"
          />
          <div v-else class="text-gray-500 py-8">
            <div class="animate-pulse">Loading chart...</div>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script>
import { marked } from 'marked'
import { formattedText } from '@/utils/formatText'
import { renderMarkdown } from '@/utils/markdownRenderer'
import api from '@/services/api'
import { useAuth0 } from '@auth0/auth0-vue'

export default {
  setup() {
    const { getAccessTokenSilently } = useAuth0();
    return {
      getAccessTokenSilently
    };
  },
  props: {
    // Expecting an object with the API response, e.g., { data: { response: "..." } }
    parsed: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      chartCache: new Map(), // Cache for fetched chart content
      loadingCharts: new Set(), // Track which charts are being loaded
      renderedContent: '', // Store the processed content
      blobUrls: new Map(), // Store blob URLs for cleanup
      showModal: false, // Modal visibility
      modalChartUrl: '', // URL for chart in modal
      modalChartTitle: '', // Title for chart in modal
      chartLinks: new Map(), // Store chart link data for click handling
    }
  },
  methods: {
    formattedText,  // Register the imported function here.
    renderMarkdown, // Use the shared markdown renderer
    
    /**
     * Enhanced markdown renderer that handles redis-chart patterns
     */
    async renderMarkdownWithCharts(content) {
      // Find all redis-chart patterns to fetch the chart data
      const combinedPattern = /(!?)\[([^\]]*)\]\(\[([^\]]+)\]\(redis-chart:([^)]+)\)\)/g;
      
      const chartPromises = [];
      let match;
      
      // We need to create a new copy of the regex for each loop
      const finderPattern = new RegExp(combinedPattern.source, 'g');
      
      while ((match = finderPattern.exec(content)) !== null) {
        const [fullMatch, exclamation, text, filename, chartId] = match;
        
        const parts = chartId.split(':');
        if (parts.length >= 2) {
          const fileId = parts[0];
          
          if (!this.chartCache.has(fileId) && !this.loadingCharts.has(fileId)) {
            chartPromises.push(this.fetchChartContent(fileId, filename));
          }
        }
      }
      
      // Start chart fetching in background
      if (chartPromises.length > 0) {
        Promise.all(chartPromises).then(() => {
          this.updateRenderedContent(content);
        });
      }
      
      // Update rendered content immediately
      this.updateRenderedContent(content);
    },
    
    /**
     * Update the rendered content with current chart data
     */
    updateRenderedContent(content) {
      // Replace the invalid nested markdown with valid markdown or HTML
      // before it ever gets to the `marked` library.
      const combinedPattern = /(!?)\[([^\]]*)\]\(\[([^\]]+)\]\(redis-chart:([^)]+)\)\)/g;
      
      let processedContent = content.replace(combinedPattern, (fullMatch, exclamation, text, filename, chartId) => {
        const parts = chartId.split(':');
        if (parts.length >= 2) {
          const fileId = parts[0];
          
          if (this.chartCache.has(fileId)) {
            const chartData = this.chartCache.get(fileId);
            
            if (chartData.error) {
              return `[Chart: ${filename}] (Error: ${chartData.message})`;
            }
            
            if (exclamation === '!') {
              // This is an image. Replace with valid markdown image syntax.
              const altText = text || filename;
              return `![${altText}](${chartData.blobUrl})`;
            } else {
              // This is a link. Replace with an HTML <a> tag directly.
              const linkId = `chart-link-${fileId}`;
              this.chartLinks.set(linkId, {
                fileId,
                title: text || filename,
                filename,
                url: chartData.blobUrl
              });
              return `<a href="#" class="chart-link text-blue-600 hover:text-blue-800 underline" data-chart-id="${linkId}">${text || filename}</a>`;
            }
          }
        }
        
        // If chart is not cached yet, return a loading placeholder text
        return `[Chart: ${filename}] (Loading...)`;
      });
      
      // Now, process the cleaned-up content with the standard markdown renderer.
      // Since we replaced links with raw HTML, `marked` will pass them through.
      this.renderedContent = this.renderMarkdown(processedContent);
      
      this.$forceUpdate();
    },
    
    /**
     * Fetch chart content from backend
     */
    async fetchChartContent(fileId, filename) {
      if (this.loadingCharts.has(fileId)) {
        return; // Already loading
      }
      
      this.loadingCharts.add(fileId);
      
      try {
        const token = await this.getAccessTokenSilently();
        const response = await api.get(`/files/${fileId}`, {
          headers: {
            'Authorization': `Bearer ${token}`
          },
          responseType: 'blob'
        });
        
        // Create blob URL
        const blob = response.data;
        const blobUrl = URL.createObjectURL(blob);
        const contentType = response.headers['content-type'] || 'image/png';
        
        // Store blob URL for cleanup
        this.blobUrls.set(fileId, blobUrl);
        
        // Cache the chart data
        this.chartCache.set(fileId, {
          blobUrl,
          contentType,
          filename
        });
         
        // Re-render content with the new chart data
        this.updateRenderedContent(this.parsed?.content || '');
        
      } catch (error) {
        console.error('Error fetching chart:', error);
        // Cache an error state
        this.chartCache.set(fileId, {
          error: true,
          message: 'Failed to load chart'
        });
        // Re-render to show error
        this.updateRenderedContent(this.parsed?.content || '');
      } finally {
        this.loadingCharts.delete(fileId);
      }
    },
    
    /**
     * Cleanup blob URLs to prevent memory leaks
     */
    cleanup() {
      this.blobUrls.forEach(url => URL.revokeObjectURL(url));
      this.blobUrls.clear();
      this.chartLinks.clear();
    },
    
    /**
     * Handle clicks on chart links
     */
    handleChartLinkClick(event) {
      const target = event.target;
      
      // Safety check: prevent any redis-chart URLs from being navigated to
      if (target.tagName === 'A' && target.href && target.href.includes('redis-chart:')) {
        console.warn('Preventing redis-chart URL navigation:', target.href);
        event.preventDefault();
        return;
      }
      
      // Check if clicked element is a chart link
      if (target.classList.contains('chart-link')) {
        event.preventDefault();
        
        const chartId = target.getAttribute('data-chart-id');
        const chartData = this.chartLinks.get(chartId);
        
        if (chartData) {
          this.modalChartTitle = chartData.title;
          this.modalChartUrl = chartData.url;
          this.showModal = true;
        }
      }
    },
    
    /**
     * Close the chart modal
     */
    closeModal() {
      this.showModal = false;
      this.modalChartUrl = '';
      this.modalChartTitle = '';
    },
    
    /**
     * Handle keyboard events (ESC to close modal)
     */
    handleKeydown(event) {
      if (event.key === 'Escape' && this.showModal) {
        this.closeModal();
      }
    }
  },
  computed: {
    processedContent() {
      // Return the rendered content or render basic content if no charts are being processed
      if (this.renderedContent) {
        return this.renderedContent;
      }
      
      // Fallback to basic markdown rendering
      return this.renderMarkdown(this.parsed?.content || '');
    },
    
    formattedTextOld() {
      // Extract the text from parsed.message.response or use an empty string
      const text = this.parsed.message?.response || '';
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
  },
  
  async mounted() {
    // Process any redis-chart patterns when component mounts
    if (this.parsed?.content) {
      this.renderMarkdownWithCharts(this.parsed.content);
    }
    
    // Add keyboard event listener for ESC key
    document.addEventListener('keydown', this.handleKeydown);
  },
  
  beforeUnmount() {
    // Clean up blob URLs to prevent memory leaks
    this.cleanup();
    
    // Remove keyboard event listener
    document.removeEventListener('keydown', this.handleKeydown);
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
  margin-top: 0px!important;
}

/* Styling for chart images */
:deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  margin: 1rem 0;
}

/* Styling for chart links */
:deep(.chart-link) {
  color: #2563eb;
  text-decoration: underline;
  cursor: pointer;
  transition: color 0.2s ease;
}

:deep(.chart-link:hover) {
  color: #1d4ed8;
  text-decoration: underline;
}

/* Modal styling */
.modal-backdrop {
  backdrop-filter: blur(4px);
}

.modal-content {
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
  border: 1px solid #e5e7eb;
}

</style> 