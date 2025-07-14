// src/utils/globalFunctions.js
export function formattedDuration(duration) {
    if (typeof duration !== 'number' || isNaN(duration)) return duration;
    if (duration < 60) {
      return duration.toFixed(2) + "s";
    } else {
      const minutes = Math.floor(duration / 60);
      const seconds = duration % 60;
      return `${minutes}m ${seconds.toFixed(2)}s`;
    }
  }
  
  export function isNumeric(val) {
    return !isNaN(Number(val));
  }

  /**
   * Check if an agent type represents a final/end state
   * @param {string} agentType - The agent type to check
   * @returns {boolean} - True if it's a final agent type
   */
  export function isFinalAgentType(agentType) {
    const finalAgentTypes = [
      'react_end',
      'financial_analysis_end', 
      'sales_leads_end',
      'deep_research_interrupt',
      'deep_research_end',
      'data_science_end'
    ];
    return finalAgentTypes.includes(agentType);
  }

  /**
   * Check if an agent type should be excluded from streaming group grouping
   * @param {string} agentType - The agent type to check
   * @returns {boolean} - True if it should be excluded from grouping
   */
  export function shouldExcludeFromGrouping(agentType) {
    // Currently only financial_analysis_end is excluded from grouping since it doesn't stream first
    return agentType === 'financial_analysis_end';
  }

  /**
   * Get the Auth0 authentication token
   * This should only be used from component context where useAuth0 is available
   * @param {Function} getAccessTokenSilently - The Auth0 getAccessTokenSilently function
   * @returns {Promise<string>} - The authentication token
   */
  export async function getAuth0Token(getAccessTokenSilently) {
    if (!getAccessTokenSilently) {
      throw new Error('getAccessTokenSilently function is required');
    }
    try {
      return await getAccessTokenSilently();
    } catch (error) {
      console.error('Error getting Auth0 token:', error);
      throw error;
    }
  }

  