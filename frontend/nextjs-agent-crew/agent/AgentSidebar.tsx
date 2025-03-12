"use client";

import { useState, useEffect } from 'react';

type AgentSidebarProps = {
  userId: string;
  runId: string;
};

export default function AgentSidebar({ userId, runId }: AgentSidebarProps) {
  const [thoughts, setThoughts] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  
  // Load agent thoughts
  useEffect(() => {
    if (!runId) return;
    
    const fetchThoughts = async () => {
      setIsLoading(true);
      
      try {
        // In a real app, you would fetch the agent thoughts from your API
        // This is a placeholder implementation
        // const response = await fetch(`/api/agent-thoughts?userId=${userId}&runId=${runId}`);
        // const data = await response.json();
        // setThoughts(data.thoughts);
        
        // For demonstration, use mock data
        setThoughts([
          {
            agent_name: 'Research Agent',
            thought: 'Analyzing the query to determine the research focus...',
            timestamp: new Date().toISOString()
          },
          {
            agent_name: 'Data Retrieval Agent',
            thought: 'Searching for latest financial data from reliable sources...',
            timestamp: new Date(Date.now() - 30000).toISOString() // 30 seconds ago
          },
          {
            agent_name: 'Analysis Agent',
            thought: 'Compiling findings and preparing summary report...',
            timestamp: new Date(Date.now() - 60000).toISOString() // 1 minute ago
          }
        ]);
      } catch (error) {
        console.error('Error fetching agent thoughts:', error);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchThoughts();
    
    // Set up polling or WebSocket for real-time updates
    // This is just a placeholder implementation
    const interval = setInterval(fetchThoughts, 5000);
    return () => clearInterval(interval);
    
  }, [userId, runId]);
  
  return (
    <div className="w-64 h-full bg-white border-l border-gray-200 overflow-y-auto flex-shrink-0">
      <div className="p-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Agent Thoughts</h2>
        
        {/* Loading state */}
        {isLoading && thoughts.length === 0 && (
          <div className="flex justify-center py-4">
            <div className="animate-spin h-5 w-5 border-2 border-gray-300 border-t-primary-brandColor rounded-full"></div>
          </div>
        )}
        
        {/* Empty state */}
        {!isLoading && thoughts.length === 0 && (
          <p className="text-sm text-gray-500 text-center py-4">
            No agent activity yet. Start a search to see agent thoughts.
          </p>
        )}
        
        {/* Agent thoughts list */}
        <div className="space-y-4">
          {thoughts.map((thought, index) => (
            <div key={index} className="border-b border-gray-100 pb-4">
              <div className="flex items-center mb-1">
                <div className="w-2 h-2 bg-green-500 rounded-full mr-2"></div>
                <h3 className="text-sm font-medium text-gray-900">{thought.agent_name}</h3>
              </div>
              <p className="text-sm text-gray-600 pl-4">{thought.thought}</p>
              <p className="text-xs text-gray-400 mt-1 pl-4">
                {new Date(thought.timestamp).toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit'
                })}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}