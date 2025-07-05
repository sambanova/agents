// Component imports
import AssistantComponent from '@/components/ChatMain/ResponseTypes/AssistantComponent.vue'
import UnknownTypeComponent from '@/components/ChatMain/ResponseTypes/UnknownTypeComponent.vue'
import FinancialAnalysisComponent from '@/components/ChatMain/ResponseTypes/FinancialAnalysisComponent.vue'
import DeepResearchComponent from '@/components/ChatMain/ResponseTypes/DeepResearchComponent.vue'
import ErrorComponent from '@/components/ChatMain/ResponseTypes/ErrorComponent.vue'
import AssistantEndComponent from '@/components/ChatMain/ResponseTypes/AssistantEndComponent.vue'
import FinancialAnalysisEndComponent from '@/components/ChatMain/ResponseTypes/FinancialAnalysisEndComponent.vue'
import SalesLeadsEndComponent from '@/components/ChatMain/ResponseTypes/SalesLeadsEndComponent.vue'

/**
 * Get the appropriate Vue component based on agent_type
 * @param {string} agentType - The agent_type from the parsed data
 * @returns {Vue.Component} - The corresponding Vue component
 */
export function getComponentByAgentType(agentType) {
  switch (agentType) {
    case 'assistant':
      return AssistantComponent
    case 'financial_analysis':
      return FinancialAnalysisComponent
    case 'deep_research_end':
      return DeepResearchComponent
    case 'deep_research_interrupt':
      return AssistantEndComponent
    case 'react_end':
      return AssistantEndComponent
    case 'error':
      return ErrorComponent
    case 'financial_analysis_end':
      return FinancialAnalysisEndComponent
    case 'sales_leads_end':
      return SalesLeadsEndComponent
    case 'data_science_end':
      return AssistantEndComponent
    case undefined:
      return AssistantEndComponent
    default:
      return UnknownTypeComponent
  }
} 