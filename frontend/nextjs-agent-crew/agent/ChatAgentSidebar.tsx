"use client";

import { useState, useEffect } from 'react';

type ChatAgentSidebarProps = {
  userId: string;
  runId: string;
  agentData: any[];
  metadata: any;
};

export default function ChatAgentSidebar({ 
  userId, 
  runId, 
  agentData = [], 
  metadata 
}: ChatAgentSidebarProps) {
  // Group agent thoughts by agent name
  const groupedThoughts = agentData.reduce((groups: Record<string, any[]>, thought) => {
    const agentName = thought.agent_name || 'Unknown Agent';
    if (!groups[agentName]) {
      groups[agentName] = [];
    }
    groups[agentName].push(thought);
    return groups;
  }, {});
  
  return (
    <div className="w-64 h-full bg-white border-l border-gray-200 overflow-y-auto flex-shrink-0">
      <div className="p-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Agent Thoughts</h2>
        
        {/* Metadata display if available */}
        {metadata && (
          <div className="mb-4 p-3 bg-gray-50 rounded-lg">
            <h3 className="text-sm font-medium text-gray-900 mb-1">Metadata</h3>
            <div className="space-y-1">
              {Object.entries(metadata).map(([key, value]) => (
                <p key={key} className="text-xs text-gray-600">
                  <span className="font-medium">{key}:</span>{' '}
                  {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                </p>
              ))}
            </div>
          </div>
        )}
        
        {/* Empty state */}
        {agentData.length === 0 && (
          <p className="text-sm text-gray-500 text-center py-4">
            No agent activity yet. Start a conversation to see agent thoughts.
          </p>
        )}
        
        {/* Agent thoughts grouped by agent */}
        <div className="space-y-4">
          {Object.entries(groupedThoughts).map(([agentName, thoughts]) => (
            <div key={agentName} className="border-b border-gray-100 pb-4">
              <div className="flex items-center mb-2">
                <div className="w-2 h-2 bg-green-500 rounded-full mr-2"></div>
                <h3 className="text-sm font-medium text-gray-900">{agentName}</h3>
              </div>
              
              <div className="space-y-2 pl-4">
                {thoughts.map((thought, idx) => (
                  <div key={idx} className="text-sm">
                    <p className="text-gray-600">{thought.thought || thought.message || 'No thought content'}</p>
                    <p className="text-xs text-gray-400 mt-1">
                      {new Date(thought.timestamp || Date.now()).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit'
                      })}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}