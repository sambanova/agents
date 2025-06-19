<template>

  <!-- The root container for your chat-based financial report -->
  <div
    id="financial-analysis-report-root"
    class="bg-white my-4 p-0 pdf-report-container w-full"
  >
    <!-- HEADER -->
    <div class="flex items-center space-x-3 mb-4 pdf-section">
      <PresentationChartLineIcon class="w-6 h-6 text-purple-600" />
      <h2 class="text-[20px] text-[#101828] font-bold">
        Financial Analysis: {{ parsed.content.company_name }}
      </h2>
    </div>

    <!-- OVERVIEW -->
    <section class="pdf-section">
      <h3
        class="text-[16px] font-semibold text-[#101828] mb-2 flex items-center space-x-2"
      >
        <GlobeAmericasIcon class="w-5 h-5 text-blue-500" />
        <span>Overview</span>
      </h3>
      <div v-if="error" class="bg-red-100 text-red-700 p-2 rounded mb-4">
        {{ error }}
      </div>
      <p v-else class="text-[16px] text-primary-brandTextPrimary">
        <strong>Ticker:</strong> {{ parsed.content.ticker }} |
        <strong>Company Name:</strong> {{ parsed.content.company_name }}
      </p>
    </section>

    <!-- FUNDAMENTALS -->
    <section v-if="parsed.content.fundamental" class="pdf-section">
      <h3
        class="text-lg font-semibold text-primary-brandTextPrimary mb-2 flex items-center space-x-2"
      >
        <Bars3Icon class="w-5 h-5 text-purple-500" />
        <span>Fundamentals</span>
      </h3>

      <!-- row of margins at top -->
      <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
        <div :class="sectionClasses">
          <div :class="textClasses.margin">
            <CheckCircleIcon class="w-4 h-4 text-green-600" />
            <span>Profit Margin</span>
          </div>
          <div :class="textClasses.value">
            {{
              formatMetric(
                'profit_margins',
                parsed.content.fundamental.profit_margins
              )
            }}
          </div>
        </div>
        <div :class="sectionClasses">
          <div :class="textClasses.margin">
            <CheckCircleIcon class="w-4 h-4 text-green-600" />
            <span>Operating Margin</span>
          </div>
          <div :class="textClasses.value">
            {{
              formatMetric(
                'operating_margins',
                parsed.content.fundamental.operating_margins
              )
            }}
          </div>
        </div>
        <div :class="sectionClasses">
          <div :class="textClasses.margin">
            <CheckCircleIcon class="w-4 h-4 text-green-600" />
            <span>EBITDA Margin</span>
          </div>
          <div :class="textClasses.value">
            {{
              formatMetric(
                'ebitda_margins',
                parsed.content.fundamental.ebitda_margins
              )
            }}
          </div>
        </div>
      </div>

      <!-- big grid of fundamentals -->
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 mt-4">
        <div :class="sectionClasses">
          <div :class="textClasses.bigGrid">
            <BanknotesIcon class="w-4 h-4 text-blue-600" />
            <span>Market Cap</span>
          </div>
          <div :class="textClasses.value">
            {{ formatMetric('market_cap', parsed.content.fundamental.market_cap) }}
          </div>
        </div>
        <div :class="sectionClasses">
          <div :class="textClasses.bigGrid">
            <ArrowTrendingUpIcon class="w-4 h-4 text-red-600" />
            <span>PE Ratio</span>
          </div>
          <div :class="textClasses.value">
            {{ formatMetric('pe_ratio', parsed.content.fundamental.pe_ratio) }}
          </div>
        </div>
        <div :class="sectionClasses">
          <div :class="textClasses.bigGrid">
            <ArrowTrendingUpIcon class="w-4 h-4 text-red-600" />
            <span>Forward PE</span>
          </div>
          <div :class="textClasses.value">
            {{ formatMetric('forward_pe', parsed.content.fundamental.forward_pe) }}
          </div>
        </div>
        <div :class="sectionClasses">
          <div :class="textClasses.bigGrid">
            <ArrowTrendingUpIcon class="w-4 h-4 text-red-600" />
            <span>PEG Ratio</span>
          </div>
          <div :class="textClasses.value">
            {{ formatMetric('peg_ratio', parsed.content.fundamental.peg_ratio) }}
          </div>
        </div>
        <div :class="sectionClasses">
          <div :class="textClasses.bigGrid">
            <ArrowTrendingUpIcon class="w-4 h-4 text-blue-600" />
            <span>P/B Ratio</span>
          </div>
          <div :class="textClasses.value">
            {{
              formatMetric(
                'price_to_book',
                parsed.content.fundamental.price_to_book
              )
            }}
          </div>
        </div>
        <div :class="sectionClasses">
          <div :class="textClasses.bigGrid">
            <ArrowTrendingDownIcon class="w-4 h-4 text-green-600" />
            <span>Dividend Yield</span>
          </div>
          <div :class="textClasses.value">
            {{
              formatMetric(
                'dividend_yield',
                parseFloat(parsed.content.fundamental.dividend_yield / 100)
              )
            }}
          </div>
        </div>
        <div :class="sectionClasses">
          <div :class="textClasses.bigGrid">
            <ArrowTrendingUpIcon class="w-4 h-4 text-orange-600" />
            <span>Beta</span>
          </div>
          <div :class="textClasses.value">
            {{ formatMetric('beta', parsed.content.fundamental.beta) }}
          </div>
        </div>
        <div class="p-4 border rounded-md bg-white col-span-1 sm:col-span-2">
          <div :class="textClasses.bigGrid">
            <ArrowTrendingUpIcon class="w-4 h-4 text-red-600" />
            <span>52wk Range</span>
          </div>
          <div :class="textClasses.value">
            High: {{ parsed.content.fundamental.year_high || '-' }} / Low:
            {{ parsed.content.fundamental.year_low || '-' }}
          </div>
        </div>
        <div :class="sectionClasses">
          <div :class="textClasses.bigGrid">
            <LightBulbIcon class="w-4 h-4 text-yellow-500" />
            <span>Analyst Rec</span>
          </div>
          <div class="text-lg font-bold text-gray-900 capitalize">
            {{ parsed.content.fundamental.analyst_recommendation || '-' }}
          </div>
        </div>
        <div :class="sectionClasses">
          <div :class="textClasses.bigGrid">
            <ArrowTrendingUpIcon class="w-4 h-4 text-purple-600" />
            <span>Target Price</span>
          </div>
          <div :class="textClasses.value">
            {{
              formatMetric('target_price', parsed.content.fundamental.target_price)
            }}
          </div>
        </div>
        <div :class="sectionClasses">
          <div :class="textClasses.bigGrid">
            <ArrowTrendingUpIcon class="w-4 h-4 text-red-600" />
            <span>EPS</span>
          </div>
          <div :class="textClasses.value">
            {{
              formatMetric(
                'earnings_per_share',
                parsed.content.fundamental.earnings_per_share
              )
            }}
          </div>
        </div>
        <!-- Return on Assets -->
        <div :class="sectionClasses">
          <div :class="textClasses.bigGrid">
            <CheckCircleIcon class="w-4 h-4 text-blue-600" />
            <span>ROA</span>
          </div>
          <div
            :class="textClasses.value"
            :title="parsed.content.fundamental.return_on_assets"
          >
            {{
              formatMetric(
                'return_on_assets',
                parsed.content.fundamental.return_on_assets
              )
            }}
          </div>
        </div>
        <!-- Return on Equity -->
        <div :class="sectionClasses">
          <div :class="textClasses.bigGrid">
            <CheckCircleIcon class="w-4 h-4 text-blue-600" />
            <span>ROE</span>
          </div>
          <div :class="textClasses.value">
            {{
              formatMetric(
                'return_on_equity',
                parsed.content.fundamental.return_on_equity
              )
            }}
          </div>
        </div>
        <!-- Current Ratio -->
        <div :class="sectionClasses">
          <div :class="textClasses.bigGrid">
            <CheckCircleIcon class="w-4 h-4 text-green-600" />
            <span>Current Ratio</span>
          </div>
          <div :class="textClasses.value">
            {{
              formatMetric(
                'current_ratio',
                parsed.content.fundamental.current_ratio
              )
            }}
          </div>
        </div>
        <!-- Debt to Equity -->
        <div :class="sectionClasses">
          <div :class="textClasses.bigGrid">
            <ExclamationTriangleIcon class="w-4 h-4 text-orange-600" />
            <span>Debt to Equity</span>
          </div>
          <div :class="textClasses.value">
            {{
              formatMetric(
                'debt_to_equity',
                parsed.content.fundamental.debt_to_equity
              )
            }}
          </div>
        </div>
      </div>

      <!-- QUARTERLY FUNDAMENTALS CHART -->
      <div
        class="mt-6 border border-primary-brandFrame p-4 rounded-lg chart-container pdf-section"
      >
        <div
          class="flex items-center space-x-2 mb-2 text-[16px] text-primary-brandTextPrimary"
        >
          <ChartBarIcon class="w-4 h-4 text-purple-600" />
          <span>Quarterly Fundamentals</span>
        </div>
        <div style="width: 100%; height: 300px">
          <canvas ref="quarterlyFundCanvasRef"></canvas>
        </div>
      </div>

      <!-- ADVANCED DATA & DIVIDEND HISTORY -->
      <div
        class="mt-6 border border-primary-brandFrame p-4 rounded-lg pdf-section"
      >
        <div
          class="flex items-center space-x-2 mb-2 text-[16px] text-primary-brandTextPrimary"
        >
          <CircleStackIcon class="w-4 h-4 text-pink-600" />
          <span>Advanced Data</span>
        </div>
        <!-- advanced_fundamentals as a list -->
        <div class="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
          <div
            v-for="(val, key) in parsed.content.fundamental
              .advanced_fundamentals || {}"
            :key="key"
            class="p-2 border rounded-md bg-white text-[14px] min-w-[160px]"
          >
            <strong class="text-primary-brandTextPrimary">{{ key }}: </strong>
            <span class="text-primary-brandTextPrimary">{{ val }}</span>
          </div>
        </div>
        <!-- dividend_history as a table -->
        <div
          v-if="(parsed.content.fundamental.dividend_history || []).length > 0"
          class="overflow-x-auto"
        >
          <table class="min-w-full border text-[16px]">
            <thead class="bg-gray-100 border-b text-left">
              <tr>
                <th class="px-3 py-2 border-r">Date</th>
                <th class="px-3 py-2">Dividend</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(divItem, index) in parsed.content.fundamental
                  .dividend_history"
                :key="index"
                class="border-b"
              >
                <td class="px-3 py-2 border-r">{{ divItem.date }}</td>
                <td class="px-3 py-2">{{ divItem.dividend }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else>
          <p class="text-gray-500">No dividend history available.</p>
        </div>
      </div>
    </section>

    <!-- RISK & AVG MONTHLY RETURNS -->
    <section v-if="parsed.content.risk" class="pdf-section">
      <h3
        class="text-lg font-semibold text-primary-brandTextPrimary mb-2 flex items-center space-x-2"
      >
        <ShieldCheckIcon class="w-5 h-5 text-pink-600 flex-shrink-0" />
        <span>Risk & Avg Monthly Returns</span>
      </h3>
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-4">
        <!-- Beta -->
        <div class="risk-card">
          <div :class="textClasses.cardTitle">
            <ArrowTrendingUpIcon
              class="w-4 h-4 text-orange-600 flex-shrink-0"
            />
            <span class="overflow-hidden text-ellipsis" title="Beta">Beta</span>
          </div>
          <div :class="textClasses.value">
            {{ formatFloat(parsed.content.risk.beta, 2) }}
          </div>
        </div>
        <!-- Sharpe -->
        <div class="risk-card">
          <div :class="textClasses.cardTitle">
            <ArrowTrendingUpIcon class="w-4 h-4 text-red-600 flex-shrink-0" />
            <span class="overflow-hidden text-ellipsis" title="Sharpe">
              Sharpe
            </span>
          </div>
          <div :class="textClasses.value">
            {{ formatFloat(parsed.content.risk.sharpe_ratio, 2) }}
          </div>
        </div>
        <!-- VaR 95% -->
        <div class="risk-card">
          <div :class="textClasses.cardTitle">
            <ExclamationTriangleIcon
              class="w-4 h-4 text-orange-600 flex-shrink-0"
            />
            <span class="overflow-hidden text-ellipsis" title="VaR 95%">
              VaR 95%
            </span>
          </div>
          <div :class="textClasses.value">
            {{ formatFloat(parsed.content.risk.value_at_risk_95, 4) }}
          </div>
        </div>
        <!-- Max Drawdown -->
        <div class="risk-card">
          <div :class="textClasses.cardTitle">
            <ArrowTrendingDownIcon class="w-4 h-4 text-red-600 flex-shrink-0" />
            <span class="overflow-hidden text-ellipsis" title="Max Drawdown">
              Max Drawdown
            </span>
          </div>
          <div :class="textClasses.value">
            {{ formatPercentage(parsed.content.risk.max_drawdown, 2) }}
          </div>
        </div>
        <!-- Volatility -->
        <div class="risk-card">
          <div :class="textClasses.cardTitle">
            <ArrowTrendingDownIcon
              class="w-4 h-4 text-orange-600 flex-shrink-0"
            />
            <span class="overflow-hidden text-ellipsis" title="Volatility">
              Volatility
            </span>
          </div>
          <div :class="textClasses.value">
            {{ formatPercentage(parsed.content.risk.volatility, 2) }}
          </div>
        </div>
      </div>
      <!-- monthly returns chart -->
      <div
        class="border border-primary-brandFrame p-4 rounded-lg chart-container"
      >
        <div style="width: 100%; height: 300px">
          <canvas ref="monthlyReturnsCanvasRef"></canvas>
        </div>
      </div>
    </section>

    <!-- 6-MONTH WEEKLY STOCK PRICE -->
    <section v-if="parsed.content.stock_price_data" class="pdf-section">
      <h3
        class="text-lg font-semibold text-primary-brandTextPrimary mb-2 flex items-center space-x-2"
      >
        <CursorArrowRaysIcon class="w-5 h-5 text-green-600" />
        <span>Stock Price (6-Month Weekly)</span>
      </h3>
      <div
        class="border border-primary-brandFrame p-4 rounded-lg chart-container"
      >
        <div style="width: 100%; height: 300px">
          <canvas ref="stockPriceCanvasRef"></canvas>
        </div>
      </div>
    </section>

    <!-- NEWS SECTION -->
    <section
      v-if="
        parsed.content?.news?.news_items && parsed.content.news.news_items.length > 0
      "
      class="pdf-section"
    >
      <h3
        class="text-lg font-semibold text-gray-700 mb-2 flex items-center space-x-2"
      >
        <GlobeAmericasIcon class="w-5 h-5 text-blue-600" />
        <span>Recent News</span>
      </h3>

      <!-- News Summary -->
      <div v-if="newsSummaryHtml" class="mb-4 p-4 border rounded-md bg-white">
        <h4
          class="text-[16px] font-semibold text-gray-700 mb-2 flex items-center space-x-2"
        >
          <DocumentTextIcon class="w-4 h-4 text-blue-600" />
          <span>News Summary</span>
        </h4>
        <div class="text-[16px] text-gray-700 prose max-w-none">
          <div v-html="newsSummaryHtml"></div>
        </div>
      </div>

      <!-- News Items -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
        <div
          v-for="(newsItem, index) in uniqueNewsItems"
          :key="index"
          class="p-1.5 border rounded-md bg-white hover:bg-gray-50 transition-colors"
        >
          <a
            :href="newsItem.link"
            target="_blank"
            rel="noopener noreferrer"
            class="text-xs font-medium text-blue-600 hover:underline flex items-center justify-between"
          >
            <span class="truncate mr-2">{{ newsItem.title }}</span>
            <svg
              class="w-3 h-3 flex-shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
              />
            </svg>
          </a>
        </div>
      </div>
    </section>
    <!-- COMPETITOR ANALYSIS -->
    <section v-if="parsed.content.competitor" class="pdf-section">
      <h3
        class="text-lg font-semibold text-primary-brandTextPrimary mb-2 flex items-center space-x-2"
      >
        <UsersIcon class="w-5 h-5 text-green-500" />
        <span>Competitor Analysis</span>
      </h3>

      <!-- Chart (optional) -->
      <div
        class="border border-primary-brandFrame p-4 rounded-lg chart-container mb-6"
      >
        <div style="width: 100%; height: 300px">
          <canvas ref="competitorCanvasRef"></canvas>
        </div>
      </div>

      <!-- Competitor List -->
      <div
        v-if="parsed.content.competitor?.competitor_details?.length"
        class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
      >
        <div
          v-for="(comp, idx) in parsed.content.competitor.competitor_details"
          :key="idx"
          class="p-4 border rounded-lg bg-white"
        >
          <div class="mb-2">
            <h4 class="font-semibold text-primary-brandTextPrimary">
              {{ comp.ticker }} - {{ comp.name }}
            </h4>
            <p class="text-xs text-gray-500">
              {{ comp.industry }}, {{ comp.sector }}
            </p>
          </div>
          <div class="space-y-1 text-[16px]">
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-1">
                <BanknotesIcon class="w-4 h-4 text-blue-500" />
                <span>Market Cap</span>
              </div>
              <strong>{{ formatMetric('market_cap', comp.market_cap) }}</strong>
            </div>
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-1">
                <ArrowTrendingUpIcon class="w-4 h-4 text-red-500" />
                <span>PE Ratio</span>
              </div>
              <strong>{{ formatMetric('pe_ratio', comp.pe_ratio) }}</strong>
            </div>
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-1">
                <ArrowTrendingUpIcon class="w-4 h-4 text-red-500" />
                <span>PS Ratio</span>
              </div>
              <strong>{{ formatMetric('ps_ratio', comp.ps_ratio) }}</strong>
            </div>
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-1">
                <CheckCircleIcon class="w-4 h-4 text-green-500" />
                <span>Profit Margin</span>
              </div>
              <strong>{{ formatPercentage(comp.profit_margins, 2) }}</strong>
            </div>
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-1">
                <CheckCircleIcon class="w-4 h-4 text-green-500" />
                <span>EBITDA Margin</span>
              </div>
              <strong>{{ formatPercentage(comp.ebitda_margins, 2) }}</strong>
            </div>
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-1">
                <LightBulbIcon class="w-4 h-4 text-yellow-500" />
                <span>Rev Growth</span>
              </div>
              <strong>{{ formatPercentage(comp.revenue_growth, 2) }}</strong>
            </div>
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-1">
                <LightBulbIcon class="w-4 h-4 text-yellow-500" />
                <span>EPS Growth</span>
              </div>
              <strong>{{ formatPercentage(comp.earnings_growth, 2) }}</strong>
            </div>
            <div class="flex items-center justify-between">
              <div class="flex items-center space-x-1">
                <ExclamationTriangleIcon class="w-4 h-4 text-orange-500" />
                <span>Short Ratio</span>
              </div>
              <strong>{{ formatFloat(comp.short_ratio, 2) }}</strong>
            </div>
          </div>
        </div>
      </div>
    </section>
    <!-- COMPREHENSIVE SUMMARY -->
    <section class="pdf-section">
      <h3
        class="text-lg font-semibold text-primary-brandTextPrimary mb-2 flex items-center space-x-2"
      >
        <DocumentTextIcon class="w-5 h-5 text-purple-600" />
        <span>Comprehensive Summary</span>
      </h3>
      <div class="text-[16px] text-primary-brandTextPrimary prose max-w-none">
        <div v-html="comprehensiveSummaryHtml"></div>
      </div>
    </section>
  </div>
</template>

<script setup>
import {
  ref,
  onMounted,
  onBeforeUnmount,
  watch,
  nextTick,
  computed,
} from 'vue';
import html2pdf from 'html2pdf.js';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import Chart from 'chart.js/auto';

import {
  DocumentTextIcon,
  PresentationChartLineIcon,
  UsersIcon,
  ShieldCheckIcon,
  BanknotesIcon,
  ArrowTrendingUpIcon,
  LightBulbIcon,
  ArrowTrendingDownIcon,
  ExclamationTriangleIcon,
  CursorArrowRaysIcon,
  CheckCircleIcon,
  ChartBarIcon,
  Bars3Icon,
  GlobeAmericasIcon,
  CircleStackIcon,
} from '@heroicons/vue/24/outline';

/* --------------------------------------
 * Props
 * -------------------------------------- */
const props = defineProps({
  parsed: {
    type: Object,
    required: true,
  },
});

/* --------------------------------------
 * State for Full Report modal
 * -------------------------------------- */
const isFullReportOpen = ref(false);

/* --------------------------------------
 * Chart references
 * -------------------------------------- */
let competitorChart = null;
let monthlyReturnsChart = null;
let quarterlyFundamentalsChart = null;
let stockPriceChart = null;

const competitorCanvasRef = ref(null);
const monthlyReturnsCanvasRef = ref(null);
const quarterlyFundCanvasRef = ref(null);
const stockPriceCanvasRef = ref(null);

/* --------------------------------------
 * Styling helpers
 * -------------------------------------- */
const sectionClasses = 'p-4 border rounded-md  bg-white';
const textClasses = {
  margin:
    'text-[16px] text-primary-brandTextPrimary flex items-center space-x-2 mb-1',
  cardTitle:
    'text-[16px] text-primary-brandTextPrimary flex items-center space-x-2 mb-1',
  value: 'text-lg overflow-hidden text-ellipsis font-bold text-gray-900',
  bigGrid:
    'flex items-center space-x-2 text-[16px] text-primary-brandTextPrimary mb-1',
};

/* --------------------------------------
 * Paragraph splitting & summary (Markdown + sanitize)
 * -------------------------------------- */
function breakLargeBlocks(text) {
  if (!text) return '';
  if (text.includes('\n\n')) return text;

  const sentenceRegex = /(?<!\d)[.!?]+(?:\s+|$)/g;
  const sentences = text.split(sentenceRegex).filter((s) => s.trim());

  if (sentences.length <= 3) return text;

  const paragraphs = [];
  const SENTENCES_PER_PARAGRAPH = 8;
  for (let i = 0; i < sentences.length; i += SENTENCES_PER_PARAGRAPH) {
    const paragraph = sentences
      .slice(i, i + SENTENCES_PER_PARAGRAPH)
      .map((s) => s.trim())
      .join('. ');
    if (paragraph) paragraphs.push(paragraph + '.');
  }
  return paragraphs.join('\n\n');
}

const comprehensiveSummaryHtml = computed(() => {
  let raw = props.parsed.content?.comprehensive_summary || '';
  let splitted = breakLargeBlocks(raw);
  return DOMPurify.sanitize(marked(splitted));
});

const uniqueNewsItems = computed(() => {
  if (!props.parsed.content?.news?.news_items) return [];

  const seen = new Set();
  return props.parsed.content.news.news_items.filter((item) => {
    if (seen.has(item.link)) return false;
    seen.add(item.link);
    return true;
  });
});

const newsSummaryHtml = computed(() => {
  let raw = props.parsed.content?.news?.news_summary || '';
  if (!raw) return '';

  let splitted = breakLargeBlocks(raw);
  return DOMPurify.sanitize(marked(splitted));
});

/* --------------------------------------
 * Formatters
 * -------------------------------------- */
function formatLargeNumber(num) {
  if (!num || isNaN(num)) return '-';
  const n = parseFloat(num);
  if (n >= 1e12) return (n / 1e12).toFixed(2) + 'T';
  if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  return n.toFixed(2);
}

function formatFloat(num, decimals = 2) {
  if (!num || isNaN(num)) return '-';
  return parseFloat(num).toFixed(decimals);
}

function formatPercentage(num, decimals = 2) {
  if (!num || isNaN(num)) return '-';
  const val = parseFloat(num) * 100;
  return val.toFixed(decimals) + '%';
}

function formatMetric(key, value) {
  if (key === 'market_cap') return formatLargeNumber(value);
  if (
    [
      'pe_ratio',
      'ps_ratio',
      'forward_pe',
      'price_to_book',
      'short_ratio',
      'target_price',
      'earnings_per_share',
      'beta',
      'current_ratio',
      'debt_to_equity',
    ].includes(key)
  ) {
    return formatFloat(value, 2);
  }
  if (
    [
      'profit_margins',
      'operating_margins',
      'ebitda_margins',
      'dividend_yield',
      'revenue_growth',
      'net_income_growth',
      'return_on_assets',
      'return_on_equity',
    ].includes(key)
  ) {
    return formatPercentage(value, 2);
  }
  return value || '-';
}

/* --------------------------------------
 * Chart creation / teardown watchers
 * -------------------------------------- */
onMounted(() => {
  createOrUpdateCharts();
});
onBeforeUnmount(() => {
  destroyCharts();
});
watch(
  () => props.parsed,
  async () => {
    await createOrUpdateCharts();
  },
  { deep: true }
);

function destroyCharts() {
  if (competitorChart) {
    competitorChart.destroy();
    competitorChart = null;
  }
  if (monthlyReturnsChart) {
    monthlyReturnsChart.destroy();
    monthlyReturnsChart = null;
  }
  if (quarterlyFundamentalsChart) {
    quarterlyFundamentalsChart.destroy();
    quarterlyFundamentalsChart = null;
  }
  if (stockPriceChart) {
    stockPriceChart.destroy();
    stockPriceChart = null;
  }
}

async function createOrUpdateCharts() {
  destroyCharts();
  await nextTick();

  // #1 Competitor Chart
  if (
    competitorCanvasRef.value &&
    props.parsed.content?.competitor?.competitor_details?.length
  ) {
    const competitorDetails = props.parsed.content.competitor.competitor_details;
    const competitorNames = competitorDetails.map((c) => c.name);
    const marketCaps = competitorDetails.map(
      (c) => parseFloat(c.market_cap || '0') / 1e9
    );
    const peRatios = competitorDetails.map((c) =>
      parseFloat(c.pe_ratio || '0')
    );

    competitorChart = new Chart(competitorCanvasRef.value.getContext('2d'), {
      data: {
        labels: competitorNames,
        datasets: [
          {
            type: 'bar',
            label: 'Market Cap (B)',
            data: marketCaps,
            backgroundColor: 'rgba(99, 102, 241, 0.8)',
            yAxisID: 'y1',
          },
          {
            type: 'line',
            label: 'PE Ratio',
            data: peRatios,
            borderColor: 'rgba(255, 99, 132, 0.8)',
            backgroundColor: 'rgba(255, 99, 132, 0.4)',
            yAxisID: 'y2',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y1: {
            type: 'linear',
            position: 'left',
            title: { display: true, text: 'Market Cap (B)' },
          },
          y2: {
            type: 'linear',
            position: 'right',
            title: { display: true, text: 'PE Ratio' },
            grid: { drawOnChartArea: false },
          },
        },
      },
    });
  }

  // #2 Monthly Returns Chart
  if (
    monthlyReturnsCanvasRef.value &&
    props.parsed.content?.risk?.daily_returns?.length
  ) {
    const dailyData = props.parsed.content.risk.daily_returns;
    const xLabels = dailyData.map((d) => d.date);
    const returnsData = dailyData.map(
      (d) => parseFloat(d.daily_return || '0') * 100
    );

    monthlyReturnsChart = new Chart(
      monthlyReturnsCanvasRef.value.getContext('2d'),
      {
        type: 'line',
        data: {
          labels: xLabels,
          datasets: [
            {
              label: 'Avg Monthly Return %',
              data: returnsData,
              borderColor: 'rgba(75, 192, 192, 0.8)',
              backgroundColor: 'rgba(75, 192, 192, 0.2)',
              tension: 0.2,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { title: { display: true, text: 'Avg Monthly Return (%)' } },
            x: { title: { display: true, text: 'Month' } },
          },
        },
      }
    );
  }

  // #3 Quarterly Fundamentals Chart
  if (
    quarterlyFundCanvasRef.value &&
    props.parsed.content?.fundamental?.quarterly_fundamentals?.length
  ) {
    const qData = props.parsed.content.fundamental.quarterly_fundamentals.filter(
      (q) => q.total_revenue != null && q.net_income != null
    );
    if (qData.length > 0) {
      const labels = qData.map((q) => q.date);
      const revenues = qData.map(
        (q) => parseFloat(q.total_revenue || '0') / 1e9
      );
      const incomes = qData.map((q) => parseFloat(q.net_income || '0') / 1e9);

      quarterlyFundamentalsChart = new Chart(
        quarterlyFundCanvasRef.value.getContext('2d'),
        {
          data: {
            labels,
            datasets: [
              {
                type: 'bar',
                label: 'Revenue (B)',
                data: revenues,
                backgroundColor: 'rgba(59,130,246,0.7)',
                yAxisID: 'y1',
              },
              {
                type: 'bar',
                label: 'Net Income (B)',
                data: incomes,
                backgroundColor: 'rgba(16,185,129,0.7)',
                yAxisID: 'y2',
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              y1: {
                type: 'linear',
                position: 'left',
                title: { display: true, text: 'Revenue (B)' },
              },
              y2: {
                type: 'linear',
                position: 'right',
                title: { display: true, text: 'Net Income (B)' },
                grid: { drawOnChartArea: false },
              },
            },
          },
        }
      );
    }
  }

  // #4 Stock Price Chart
  if (
    stockPriceCanvasRef.value &&
    props.parsed.content?.stock_price_data?.length
  ) {
    const spData = props.parsed.content.stock_price_data;
    const xLabels = spData.map((d) => d.date);
    const closePrices = spData.map((d) => parseFloat(d.close || '0'));

    stockPriceChart = new Chart(stockPriceCanvasRef.value.getContext('2d'), {
      type: 'line',
      data: {
        labels: xLabels,
        datasets: [
          {
            label: 'Weekly Close',
            data: closePrices,
            borderColor: 'rgba(234,179,8,0.9)',
            backgroundColor: 'rgba(234,179,8,0.2)',
            tension: 0.2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { title: { display: true, text: 'Stock Price (USD)' } },
          x: { title: { display: true, text: 'Week' } },
        },
      },
    });
  }
}

/* --------------------------------------
 * Modal & PDF actions
 * -------------------------------------- */
function viewFullReport() {
  isFullReportOpen.value = true;
}
function closeFullReport() {
  isFullReportOpen.value = false;
}

async function downloadPDF() {
  const rootElem = document.querySelector('#financial-analysis-report-root');
  if (!rootElem) return;

  const pdfOpts = {
    margin: [10, 10],
    filename: 'financial_analysis.pdf',
    pagebreak: { mode: ['css', 'legacy'] },
    image: { type: 'jpeg', quality: 0.98 },
    html2canvas: {
      scale: 2,
      useCORS: true,
      letterRendering: true,
    },
    jsPDF: {
      unit: 'mm',
      format: 'a4',
      orientation: 'portrait',
    },
  };

  try {
    await html2pdf().set(pdfOpts).from(rootElem).save();
  } catch (e) {
    console.error('PDF error:', e);
  }
}

/* --------------------------------------
 * Computed error (like original chat)
 * -------------------------------------- */
const error = computed(() => {
  return props.parsed.content?.error || '';
});
</script>

<style scoped>
/* Avoid page-break inside these sections so the PDF won't split them awkwardly */
.pdf-section {
  page-break-inside: avoid;
  margin-bottom: 1rem;
}

/* Force each chart container to avoid page breaks inside. */
.chart-container {
  overflow-x: auto;
  page-break-inside: avoid;
}

/* Force each canvas to scale to fit the PDF page better. */
.chart-container canvas {
  width: 100% !important;
  height: 100% !important;
  max-width: 600px; /* optional limit if you want smaller charts */
  display: block;
  margin: 0 auto;
}

/* Paragraph styling in summary. */
.prose p {
  margin-bottom: 1rem;
  /* line-height: 24px!important; */
}

.risk-card {
  padding: 1rem /* 16px */;
  border-width: 1px;
  border-radius: 0.375rem /* 6px */;
  --tw-bg-opacity: 1;
  background-color: rgb(255 255 255 / var(--tw-bg-opacity, 1)) /* #ffffff */;
}

.risk-card-text {
  font-size: 16px;
  display: flex;
  align-items: center;
  --tw-space-x-reverse: 0;
  margin-right: calc(0.5rem /* 8px */ * var(--tw-space-x-reverse));
  margin-left: calc(0.5rem /* 8px */ * calc(1 - var(--tw-space-x-reverse)));
  margin-bottom: 0.25rem /* 4px */;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
