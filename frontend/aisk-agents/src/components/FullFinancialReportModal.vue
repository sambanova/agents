<template>
  <transition name="fade">
    <div
      v-if="open"
      class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center"
    >
      <div class="bg-white rounded-lg w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col relative">
        <!-- Modal Header -->
        <div class="flex items-center justify-between px-4 py-2 border-b border-gray-200">
          <h3 class="font-semibold text-xl text-gray-800">
            Full Financial Analysis
          </h3>
          <button
            @click="$emit('close')"
            class="text-gray-500 hover:text-gray-700 focus:outline-none"
          >
            <!-- Close icon -->
            <svg
              class="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <!-- Modal Content (scrollable) -->
        <div
          ref="modalRootRef"
          class="p-4 overflow-y-auto space-y-6 flex-1"
        >
          <!-- Title / Overview -->
          <section class="page-section border-b border-gray-200 pb-4">
            <h4 class="text-md font-bold text-gray-700 mb-2">
              {{ reportData.company_name }} ({{ reportData.ticker }})
            </h4>
            <p class="text-sm text-gray-600">
              This is the full expanded financial analysis, including competitor breakdown, fundamentals, risk metrics, quarterly data, and more.
            </p>
          </section>

          <!-- Competitor Analysis -->
          <section class="page-section">
            <h5 class="text-lg font-semibold text-gray-800 mb-2 flex items-center space-x-2">
              <svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path 
                  stroke-linecap="round" 
                  stroke-linejoin="round" 
                  stroke-width="2"
                  d="M17 20h5V4H2v16h5m10-10h.01M12 15l2.09-2.09L9 8l-2.09 2.09L12 15z"
                />
              </svg>
              <span>Competitor Analysis</span>
            </h5>
            <!-- Competitor Chart -->
            <div class="chart-container border border-gray-200 p-3 rounded-lg mb-4">
              <canvas ref="competitorModalCanvasRef" width="400" height="250"></canvas>
            </div>

            <!-- Competitor Table -->
            <table v-if="reportData?.competitor?.competitor_details?.length" class="w-full text-sm border">
              <thead class="bg-gray-50 text-gray-700">
                <tr>
                  <th class="px-2 py-1 border-r">Ticker</th>
                  <th class="px-2 py-1 border-r">Name</th>
                  <th class="px-2 py-1 border-r">Market Cap (B)</th>
                  <th class="px-2 py-1 border-r">PE Ratio</th>
                  <th class="px-2 py-1 border-r">PS Ratio</th>
                  <th class="px-2 py-1 border-r">Profit Margin</th>
                  <th class="px-2 py-1">EBITDA Margin</th>
                </tr>
              </thead>
              <tbody>
                <tr 
                  v-for="(comp, idx) in reportData.competitor.competitor_details" 
                  :key="idx"
                  class="border-b"
                >
                  <td class="px-2 py-1 border-r">{{ comp.ticker }}</td>
                  <td class="px-2 py-1 border-r">{{ comp.name }}</td>
                  <td class="px-2 py-1 border-r">
                    {{ formatBillion(comp.market_cap) }}
                  </td>
                  <td class="px-2 py-1 border-r">{{ comp.pe_ratio }}</td>
                  <td class="px-2 py-1 border-r">{{ comp.ps_ratio }}</td>
                  <td class="px-2 py-1 border-r">
                    {{ formatPct(comp.profit_margins) }}
                  </td>
                  <td class="px-2 py-1">
                    {{ formatPct(comp.ebitda_margins) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </section>

          <!-- Fundamentals -->
          <section class="page-section">
            <h5 class="text-lg font-semibold text-gray-800 mb-2 flex items-center space-x-2 mt-4">
              <svg class="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path 
                  stroke-linecap="round" 
                  stroke-linejoin="round" 
                  stroke-width="2"
                  d="M3 7h18M3 10h18M9 20V4m6 0v16"
                />
              </svg>
              <span>Fundamentals</span>
            </h5>

            <!-- Fundamentals grid -->
            <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
              <div class="border p-2 rounded bg-white shadow-sm">
                <strong class="text-gray-700 block text-sm">Market Cap</strong>
                <span class="text-gray-800 text-sm">
                  {{ formatBillion(reportData.fundamental?.market_cap) }}
                </span>
              </div>
              <div class="border p-2 rounded bg-white shadow-sm">
                <strong class="text-gray-700 block text-sm">PE Ratio</strong>
                <span class="text-gray-800 text-sm">
                  {{ formatFloat(reportData.fundamental?.pe_ratio) }}
                </span>
              </div>
              <div class="border p-2 rounded bg-white shadow-sm">
                <strong class="text-gray-700 block text-sm">Forward PE</strong>
                <span class="text-gray-800 text-sm">
                  {{ formatFloat(reportData.fundamental?.forward_pe) }}
                </span>
              </div>
              <div class="border p-2 rounded bg-white shadow-sm">
                <strong class="text-gray-700 block text-sm">PS Ratio</strong>
                <span class="text-gray-800 text-sm">
                  {{ formatFloat(reportData.fundamental?.ps_ratio) }}
                </span>
              </div>
              <div class="border p-2 rounded bg-white shadow-sm">
                <strong class="text-gray-700 block text-sm">Dividend Yield</strong>
                <span class="text-gray-800 text-sm">
                  {{ formatPct(reportData.fundamental?.dividend_yield) }}
                </span>
              </div>
              <div class="border p-2 rounded bg-white shadow-sm">
                <strong class="text-gray-700 block text-sm">Analyst Rec</strong>
                <span class="text-gray-800 text-sm">
                  {{ reportData.fundamental?.analyst_recommendation }}
                </span>
              </div>
              <div class="border p-2 rounded bg-white shadow-sm">
                <strong class="text-gray-700 block text-sm">Target Price</strong>
                <span class="text-gray-800 text-sm">
                  {{ formatFloat(reportData.fundamental?.target_price) }}
                </span>
              </div>
              <div class="border p-2 rounded bg-white shadow-sm">
                <strong class="text-gray-700 block text-sm">EPS</strong>
                <span class="text-gray-800 text-sm">
                  {{ formatFloat(reportData.fundamental?.earnings_per_share) }}
                </span>
              </div>
            </div>

            <!-- quarterly fundamentals chart -->
            <div class="chart-container mt-4 border border-gray-200 p-3 rounded">
              <canvas ref="quarterlyFundModalCanvasRef" width="400" height="200"></canvas>
            </div>

            <!-- advanced data -->
            <div class="mt-4 text-sm space-y-2">
              <p>
                <strong class="text-gray-700">Advanced Fundamentals:</strong>
              </p>
              <ul class="list-disc list-inside space-y-1">
                <li v-for="(val, key) in reportData.fundamental?.advanced_fundamentals || {}" :key="key">
                  <strong>{{ key }}:</strong> {{ val }}
                </li>
              </ul>

              <!-- dividends -->
              <div v-if="(reportData.fundamental?.dividend_history || []).length > 0" class="overflow-x-auto mt-2">
                <table class="border text-sm">
                  <thead class="bg-gray-100">
                    <tr>
                      <th class="px-2 py-1 border-r">Date</th>
                      <th class="px-2 py-1">Dividend</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr 
                      v-for="(d, dIdx) in reportData.fundamental.dividend_history" 
                      :key="dIdx"
                      class="border-b"
                    >
                      <td class="px-2 py-1 border-r">{{ d.date }}</td>
                      <td class="px-2 py-1">{{ d.dividend }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          <!-- Risk & monthly returns chart -->
          <section class="page-section">
            <h5 class="text-lg font-semibold text-gray-800 mb-2 flex items-center space-x-2 mt-4">
              <svg class="w-5 h-5 text-pink-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path 
                  stroke-linecap="round" 
                  stroke-linejoin="round" 
                  stroke-width="2"
                  d="M4 6h16M4 10h16M4 14h16M4 18h16"
                />
              </svg>
              <span>Risk & Monthly Returns</span>
            </h5>
            <div class="flex flex-wrap gap-4 text-sm text-gray-700 mb-4">
              <div><strong>Beta:</strong> {{ reportData.risk?.beta }}</div>
              <div><strong>Sharpe:</strong> {{ reportData.risk?.sharpe_ratio }}</div>
              <div><strong>VaR 95%:</strong> {{ reportData.risk?.value_at_risk_95 }}</div>
              <div><strong>Max Drawdown:</strong> {{ reportData.risk?.max_drawdown }}</div>
              <div><strong>Volatility:</strong> {{ reportData.risk?.volatility }}</div>
            </div>
            <div class="chart-container border border-gray-200 p-3 rounded">
              <canvas ref="monthlyReturnsModalCanvasRef" width="400" height="200"></canvas>
            </div>
          </section>

          <!-- Stock Price -->
          <section class="page-section">
            <h5 class="text-lg font-semibold text-gray-800 mb-2 flex items-center space-x-2 mt-4">
              <svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path 
                  stroke-linecap="round" 
                  stroke-linejoin="round" 
                  stroke-width="2"
                  d="M3 3h18M3 7h18M3 11h18M3 15h18M3 19h18"
                />
              </svg>
              <span>6-Month Weekly Stock Price</span>
            </h5>
            <div class="chart-container border border-gray-200 p-3 rounded">
              <canvas ref="stockPriceModalCanvasRef" width="400" height="200"></canvas>
            </div>
          </section>

          <!-- Comprehensive Summary -->
          <section class="page-section">
            <h5 class="text-lg font-semibold text-gray-800 mb-2 mt-4">
              Comprehensive Summary
            </h5>
            <div class="text-sm text-gray-700 leading-relaxed" v-html="formattedSummary"></div>
          </section>
        </div>

        
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import Chart from 'chart.js/auto'
import html2canvas from 'html2canvas'
import { jsPDF } from 'jspdf'

// PROPS / EMITS
const props = defineProps({
  open: { type: Boolean, default: false },
  reportData: { type: Object, required: true }
})
const emit = defineEmits(['close'])

// Format summary
const formattedSummary = computed(() => {
  if (!props.reportData?.comprehensive_summary) return ''
  const raw = marked(props.reportData.comprehensive_summary)
  return DOMPurify.sanitize(raw)
})

// Refs
const modalRootRef = ref(null)

let competitorModalChart = null
let quarterlyFundModalChart = null
let monthlyReturnsModalChart = null
let stockPriceModalChart = null

const competitorModalCanvasRef = ref(null)
const quarterlyFundModalCanvasRef = ref(null)
const monthlyReturnsModalCanvasRef = ref(null)
const stockPriceModalCanvasRef = ref(null)

// Lifecycle
onMounted(() => { setupCharts() })
onBeforeUnmount(() => { destroyCharts() })

// watch open => (re)build
watch(() => props.open, async (val) => {
  if (val) {
    await nextTick()
    setupCharts()
  } else {
    destroyCharts()
  }
}, { immediate: true })

function setupCharts() {
  if (!props.open) return
  destroyCharts()

  // competitor
  if (competitorModalCanvasRef.value && props.reportData?.competitor?.competitor_details?.length) {
    const comps = props.reportData.competitor.competitor_details
    const labels = comps.map(c => c.name)
    const mcaps = comps.map(c => parseFloat(c.market_cap||'0')/1e9)
    const pes   = comps.map(c => parseFloat(c.pe_ratio||'0'))

    competitorModalChart = new Chart(competitorModalCanvasRef.value, {
      type:'bar',
      data:{
        labels,
        datasets:[
          {
            label:'Market Cap (B)',
            data:mcaps,
            backgroundColor:'rgba(99,102,241,0.7)',
            yAxisID:'y1'
          },
          {
            type:'line',
            label:'PE Ratio',
            data:pes,
            borderColor:'rgba(255,99,132,0.8)',
            backgroundColor:'rgba(255,99,132,0.2)',
            yAxisID:'y2'
          }
        ]
      },
      options:{
        responsive:true,
        scales:{
          y1:{type:'linear',position:'left',title:{display:true,text:'Market Cap (B)'}},
          y2:{type:'linear',position:'right',grid:{drawOnChartArea:false},title:{display:true,text:'PE Ratio'}}
        }
      }
    })
  }

  // quarterly
  if (quarterlyFundModalCanvasRef.value && props.reportData?.fundamental?.quarterly_fundamentals?.length) {
    const qData = props.reportData.fundamental.quarterly_fundamentals.filter(q=>q.total_revenue!=null && q.net_income!=null)
    if(qData.length>0){
      const labels = qData.map(q=>q.date)
      const revs = qData.map(q=> parseFloat(q.total_revenue||'0')/1e9)
      const incs = qData.map(q=> parseFloat(q.net_income||'0')/1e9)

      quarterlyFundModalChart = new Chart(quarterlyFundModalCanvasRef.value, {
        type:'bar',
        data:{
          labels,
          datasets:[
            {
              type:'bar',
              label:'Revenue (B)',
              data:revs,
              backgroundColor:'rgba(59,130,246,0.7)',
              yAxisID:'y1'
            },
            {
              type:'bar',
              label:'Net Income (B)',
              data:incs,
              backgroundColor:'rgba(16,185,129,0.7)',
              yAxisID:'y2'
            }
          ]
        },
        options:{
          responsive:true,
          scales:{
            y1:{type:'linear',position:'left',title:{display:true,text:'Revenue (B)'}},
            y2:{type:'linear',position:'right',grid:{drawOnChartArea:false},title:{display:true,text:'Net Income (B)'}}
          }
        }
      })
    }
  }

  // monthly
  if (monthlyReturnsModalCanvasRef.value && props.reportData?.risk?.daily_returns?.length) {
    const arr = props.reportData.risk.daily_returns
    const xLabels = arr.map(a=>a.date)
    const yVals   = arr.map(a=>parseFloat(a.daily_return||'0')*100)

    monthlyReturnsModalChart = new Chart(monthlyReturnsModalCanvasRef.value, {
      type:'line',
      data:{
        labels:xLabels,
        datasets:[{
          label:'Avg Monthly Return (%)',
          data:yVals,
          borderColor:'rgba(75,192,192,0.8)',
          backgroundColor:'rgba(75,192,192,0.2)',
          tension:0.2
        }]
      },
      options:{
        responsive:true,
        scales:{
          y:{title:{display:true,text:'Return (%)'}},
          x:{title:{display:true,text:'Month'}}
        }
      }
    })
  }

  // stock price
  if (stockPriceModalCanvasRef.value && props.reportData?.stock_price_data?.length) {
    const sp = props.reportData.stock_price_data
    const xLabels = sp.map(s=>s.date)
    const closes  = sp.map(s=>parseFloat(s.close||'0'))

    stockPriceModalChart = new Chart(stockPriceModalCanvasRef.value, {
      type:'line',
      data:{
        labels:xLabels,
        datasets:[{
          label:'Weekly Close',
          data:closes,
          borderColor:'rgba(234,179,8,0.9)',
          backgroundColor:'rgba(234,179,8,0.2)',
          tension:0.2
        }]
      },
      options:{
        responsive:true,
        scales:{
          y:{title:{display:true,text:'Price (USD)'}},
          x:{title:{display:true,text:'Week'}}
        }
      }
    })
  }
}

function destroyCharts(){
  competitorModalChart?.destroy()
  competitorModalChart=null
  quarterlyFundModalChart?.destroy()
  quarterlyFundModalChart=null
  monthlyReturnsModalChart?.destroy()
  monthlyReturnsModalChart=null
  stockPriceModalChart?.destroy()
  stockPriceModalChart=null
}

/**
 * The "chunked" approach with jsPDF+html2canvas:
 * 1) For each .page-section in the modal, we create an image with html2canvas
 * 2) We add that image to the PDF on a new page
 * This ensures truly multiple pages for the final PDF, including large charts.
 */
const isGeneratingPDF = ref(false);

async function downloadPDF() {
  if (isGeneratingPDF.value) return;
  
  try {
    isGeneratingPDF.value = true;
    
    // Create PDF document
    const doc = new jsPDF('p', 'pt', 'a4');
    const pageWidth = doc.internal.pageSize.getWidth();
    const pageHeight = doc.internal.pageSize.getHeight();
    const margins = { top: 40, bottom: 40, left: 40, right: 40 };
    const contentWidth = pageWidth - margins.left - margins.right;

    // Get the modal content
    const modalContent = modalRootRef.value;
    
    // Create a temporary container for better rendering
    const tempContainer = document.createElement('div');
    tempContainer.style.width = `${contentWidth}px`;
    tempContainer.style.position = 'absolute';
    tempContainer.style.left = '-9999px';
    tempContainer.style.top = '-9999px';
    tempContainer.style.backgroundColor = '#ffffff';
    
    // Clone the content
    const contentClone = modalContent.cloneNode(true);
    contentClone.style.overflow = 'visible';
    contentClone.style.maxHeight = 'none';
    tempContainer.appendChild(contentClone);
    document.body.appendChild(tempContainer);

    // Wait for charts to render in cloned content
    await new Promise(resolve => setTimeout(resolve, 500));

    // Convert all canvases to images first
    const canvases = tempContainer.querySelectorAll('canvas');
    for (const canvas of canvases) {
      const img = document.createElement('img');
      img.src = canvas.toDataURL('image/png');
      img.style.width = '100%';
      img.style.maxWidth = `${contentWidth}px`;
      canvas.parentNode.replaceChild(img, canvas);
    }

    // Get all sections
    const sections = tempContainer.querySelectorAll('.page-section');
    let currentPage = 1;

    for (const section of sections) {
      // Generate image of the section
      const canvas = await html2canvas(section, {
        scale: 2,
        useCORS: true,
        logging: false,
        backgroundColor: '#ffffff',
        width: contentWidth,
        windowWidth: contentWidth
      });

      const imgData = canvas.toDataURL('image/jpeg', 1.0);
      
      // Calculate image dimensions
      const imgWidth = contentWidth;
      const imgHeight = (canvas.height * imgWidth) / canvas.width;

      // Add new page if not first page
      if (currentPage > 1) {
        doc.addPage();
      }

      // Add image to PDF
      doc.addImage(
        imgData,
        'JPEG',
        margins.left,
        margins.top,
        imgWidth,
        imgHeight,
        undefined,
        'FAST'
      );

      currentPage++;
    }

    // Cleanup
    document.body.removeChild(tempContainer);

    // Save the PDF
    const fileName = `${props.reportData.company_name || 'financial'}_analysis.pdf`;
    doc.save(fileName);

    isGeneratingPDF.value = false;
  } catch (error) {
    console.error('Error generating PDF:', error);
    isGeneratingPDF.value = false;
  }
}

/** Formatters */
function formatFloat(num, decimals=2){
  if(!num || isNaN(num)) return '-'
  return parseFloat(num).toFixed(decimals)
}
function formatPct(num, decimals=2){
  if(!num || isNaN(num)) return '-'
  const val = parseFloat(num)*100
  return val.toFixed(decimals)+'%'
}
function formatBillion(num){
  const n = parseFloat(num||'0')
  if(isNaN(n)||n<=0) return '-'
  return (n/1e9).toFixed(2)+'B'
}
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity .2s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.chart-container {
  overflow-x: auto;
}

/* 
We rely on .page-section for chunk-based approach
*/
.page-section {
  margin-bottom: 40px;
}
</style>
