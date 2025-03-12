"use client";

import { useState, useEffect, forwardRef, useImperativeHandle } from 'react';
import { api } from '@/lib/api';
import { getUserId } from '@/lib/auth';

type Conversation = {
  conversation_id: string;
  title: string;
  timestamp: string;
};

type ChatSidebarProps = {
  onSelectConversation: (conversation: Conversation) => void;
};

const ChatSidebar = forwardRef<any, ChatSidebarProps>(({ onSelectConversation }, ref) => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Expose methods to parent components
  useImperativeHandle(ref, () => ({
    loadChats: loadConversations
  }));
  
  // Load conversations
  const loadConversations = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      // This is a placeholder - implement the actual API call
      // In a real app, you would fetch the list of conversations from your API
      const response = await fetch('/api/python/conversations');
      const data = await response.json();
      
      // Sort conversations by timestamp (newest first)
      const sortedConversations = [...data.conversations].sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
      );
      
      setConversations(sortedConversations);
    } catch (err) {
      console.error('Error loading conversations:', err);
      setError('Failed to load conversations');
      
      // For demonstration, add some mock data
      setConversations([
        {
          conversation_id: '1',
          title: 'Financial analysis of Tech Companies',
          timestamp: new Date().toISOString()
        },
        {
          conversation_id: '2',
          title: 'Research on renewable energy',
          timestamp: new Date(Date.now() - 86400000).toISOString() // 1 day ago
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };
  
  // Create a new conversation
  const createNewConversation = async () => {
    try {
      const response = await api.chat.init();
      // Navigate to the new conversation
      window.location.href = `/dashboard/${response.conversation_id}`;
    } catch (error) {
      console.error('Error creating new conversation:', error);
      setError('Failed to create new conversation');
    }
  };
  
  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, []);
  
  // Format date for display
  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    
    // If today, show time only
    if (date.toDateString() === now.toDateString()) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    
    // If this year, show month and day
    if (date.getFullYear() === now.getFullYear()) {
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
    
    // Otherwise show full date
    return date.toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' });
  };
  
  return (
    <div className="w-64 h-full bg-white border-r border-gray-200 overflow-y-auto flex-shrink-0">
      <div className="p-4">
        {/* New Chat button */}
        <button
          onClick={createNewConversation}
          className="w-full py-2 px-4 bg-primary-brandColor text-white rounded-md hover:bg-primary-600 flex items-center justify-center gap-2"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          <span>New Chat</span>
        </button>
        
        <h2 className="text-lg font-semibold text-gray-900 mt-6 mb-4">Conversations</h2>
        
        {/* Loading state */}
        {isLoading && (
          <div className="flex justify-center py-4">
            <div className="animate-spin h-5 w-5 border-2 border-gray-300 border-t-primary-brandColor rounded-full"></div>
          </div>
        )}
        
        {/* Error state */}
        {error && (
          <div className="py-4 text-center">
            <p className="text-sm text-red-500">{error}</p>
            <button
              onClick={loadConversations}
              className="mt-2 text-sm text-primary-brandColor hover:underline"
            >
              Retry
            </button>
          </div>
        )}
        
        {/* Conversation list */}
        <div className="space-y-2">
          {conversations.length === 0 && !isLoading ? (
            <p className="text-sm text-gray-500 text-center py-4">No conversations yet.</p>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.conversation_id}
                onClick={() => onSelectConversation(conv)}
                className="p-3 rounded-lg hover:bg-gray-100 cursor-pointer transition-colors"
              >
                <div className="flex items-center">
                  <div className="flex-shrink-0 mr-3">
                    <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                      />
                    </svg>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {conv.title}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {formatDate(conv.timestamp)}
                    </p>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
});

ChatSidebar.displayName = 'ChatSidebar';

export default ChatSidebar;