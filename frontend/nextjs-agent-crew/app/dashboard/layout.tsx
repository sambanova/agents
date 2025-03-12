"use client";

import { useState, useRef, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { v4 as uuidv4 } from 'uuid';
import { getUserId } from '@/lib/auth';
import { useReportStore } from '@/lib/store';

// This is a placeholder for the components we need to implement
// We'll implement these later
const Header = dynamic(() => import('@/agent/Header'));
const Sidebar = dynamic(() => import('@/agent/Sidebar'));
const ChatSidebar = dynamic(() => import('@/agent/ChatSidebar'));
const ChatView = dynamic(() => import('@/agent/ChatView'));
const AgentSidebar = dynamic(() => import('@/agent/AgentSidebar'));
const ChatAgentSidebar = dynamic(() => import('@/agent/ChatAgentSidebar'));
const SearchSection = dynamic(() => import('@/agent/SearchSection'));
const SearchNotification = dynamic(() => import('@/agent/SearchNotification'));
const LoadingSpinner = dynamic(() => import('@/agent/LoadingSpinner'));
const ErrorModal = dynamic(() => import('@/agent/ErrorModal'));

import dynamic from 'next/dynamic';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // State for managing the UI mode (chat vs workflow)
  const [chatMode, setChatMode] = useState<boolean>(true);
  const [selectedConversationId, setSelectedConversationId] = useState<string>('');
  const [selectedOption, setSelectedOption] = useState({ label: 'SambaNova', value: 'sambanova' });
  
  // Loading state
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [loadingMessage, setLoadingMessage] = useState<string>('');
  const [loadingSubMessage, setLoadingSubMessage] = useState<string>('');
  
  // Error state
  const [showError, setShowError] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string>('');
  
  // Results state
  const [queryType, setQueryType] = useState<string>('');
  const [results, setResults] = useState<any>(null);
  
  // Search notification state
  const [showNotification, setShowNotification] = useState<boolean>(false);
  const [searchTime, setSearchTime] = useState<string>('0.0');
  const [resultCount, setResultCount] = useState<number>(0);
  
  // Key tracking (for updates)
  const [keysUpdateCounter, setKeysUpdateCounter] = useState<number>(0);
  
  // User ID
  const userId = getUserId();
  
  // Run ID and session ID
  const [currentRunId, setCurrentRunId] = useState<string>('');
  const [sessionId, setSessionId] = useState<string>('');
  
  // Metadata and agent data
  const [metadata, setMetadata] = useState<any>(null);
  const [agentData, setAgentData] = useState<any[]>([]);
  
  // Refs
  const headerRef = useRef<any>(null);
  const chatSideBarRef = useRef<any>(null);
  
  // Access the report store
  const reportStore = useReportStore();
  
  // Initialize on component mount
  useEffect(() => {
    // Generate a new session ID (this was in onMounted in Vue)
    setSessionId(uuidv4());
    // Load saved reports
    // This is already handled by the persist middleware in Zustand
  }, []);

  // Handle keys updated (from Header component)
  const handleKeysUpdated = () => {
    setKeysUpdateCounter(prev => prev + 1);
  };

  // Handle mode toggled (from Header component)
  const handleModeToggled = (value: boolean) => {
    setChatMode(value);
  };

  // Handle conversation selection (from ChatSidebar component)
  const handleSelectConversation = (conversation: any) => {
    setSelectedConversationId(conversation.conversation_id);
  };

  // Handle saved report selection (from Sidebar component)
  const handleSavedReportSelect = (savedReport: any) => {
    setQueryType(savedReport.type);
    setResults(savedReport.results);
  };

  // Function to check if we have results to display
  const hasResults = () => {
    if (queryType === 'sales_leads') {
      return results?.results && Array.isArray(results.results) && results.results.length > 0;
    }
    if (queryType === 'educational_content') {
      return Array.isArray(results) && results.length > 0;
    }
    if (queryType === 'financial_analysis') {
      return !!(results && Object.keys(results).length > 0);
    }
    return false;
  };

  // Handle search start
  const handleSearchStart = (type: string) => {
    console.log('[DashboardLayout] handleSearchStart called with type:', type);
    
    // For document uploads, use the sessionId as the runId
    if (type === 'document_upload') {
      setCurrentRunId(sessionId);
    }
    // For searches, generate a new runId
    else if (type === 'routing_query' || !currentRunId) {
      setCurrentRunId(uuidv4());
    }

    // Only show spinner and clear results for actual searches
    if (type !== 'document_upload') {
      // Show spinner
      setIsLoading(true);
      setResults(null);
      setQueryType(type);
    }
  };

  // Handle search complete
  const handleSearchComplete = (searchResults: any) => {
    setQueryType(searchResults.type);
    setResults(searchResults.results);

    // Save final report
    reportStore.saveReport(searchResults.type, searchResults.query, searchResults.results);

    // Turn off spinner
    setIsLoading(false);

    // Update result count for notification
    let count = 0;
    if (Array.isArray(searchResults.results)) {
      count = searchResults.results.length;
    } else if (searchResults.results?.results && Array.isArray(searchResults.results.results)) {
      count = searchResults.results.results.length;
    } else {
      count = Object.keys(searchResults.results || {}).length;
    }
    
    setResultCount(count);
    setShowNotification(true);
    
    // Hide notification after 5 seconds
    setTimeout(() => {
      setShowNotification(false);
    }, 5000);
  };

  // Handle search error
  const handleSearchError = (error: any) => {
    console.error('[DashboardLayout] Search error:', error);
    setIsLoading(false);
    setLoadingMessage('');
    setLoadingSubMessage('');
    setShowError(true);
    setErrorMessage(error?.message || 'An unexpected error occurred');
  };

  // Handle agent thoughts data changed (from ChatView component)
  const handleAgentThoughtsDataChanged = (data: any) => {
    setAgentData(data);
    if (chatSideBarRef.current && typeof chatSideBarRef.current.loadChats === 'function') {
      chatSideBarRef.current.loadChats();
    }
  };

  // Handle metadata changed (from ChatView component)
  const handleMetadataChanged = (data: any) => {
    setMetadata(data);
  };

  // Open settings
  const openSettings = () => {
    if (headerRef.current) {
      headerRef.current.openSettings();
    }
  };

  return (
    <div className="min-h-screen transition-all bg-primary-bodyBg duration-300 flex flex-col">
      {/* PAGE HEADER */}
      <Header
        ref={headerRef}
        className="flex-none"
        onKeysUpdated={handleKeysUpdated}
        onModeToggled={handleModeToggled}
      />

      {/* MAIN COLUMN */}
      <div className="flex gap-2 p-2 h-[calc(100vh-4rem)]">
        {/* LEFT SIDEBAR */}
        {chatMode ? (
          <ChatSidebar
            ref={chatSideBarRef}
            onSelectConversation={handleSelectConversation}
          />
        ) : (
          <Sidebar
            onSelectReport={handleSavedReportSelect}
          />
        )}

        {/* MAIN CONTENT WRAPPER */}
        <main className="overflow-hidden transition-all duration-300 border border-primary-brandFrame rounded-lg relative flex-1 flex flex-col h-full">
          <div className="flex-1 h-full bg-white">
            <div className="flex-1 h-full w-full">
              {chatMode ? (
                <div className="flex h-full justify-center">
                  {/* ChatView for conversation */}
                  <ChatView
                    conversationId={selectedConversationId}
                    onMetadataChanged={handleMetadataChanged}
                    className="flex-1"
                    onAgentThoughtsDataChanged={handleAgentThoughtsDataChanged}
                  />
                </div>
              ) : (
                <div className="flex h-full w-full justify-center items-center overflow-y-auto">
                  {/* Search notification */}
                  <SearchNotification
                    show={showNotification}
                    time={searchTime}
                    resultCount={resultCount}
                  />

                  {/* Loading spinner */}
                  {isLoading && !chatMode && (
                    <div className="mt-8 w-full">
                      <LoadingSpinner
                        message={loadingMessage}
                        subMessage={loadingSubMessage}
                      />
                    </div>
                  )}

                  {/* Error modal */}
                  {!chatMode && (
                    <ErrorModal
                      show={showError}
                      errorMessage={errorMessage}
                      onClose={() => setShowError(false)}
                    />
                  )}

                  {/* Results section */}
                  {hasResults() && (
                    <div className="mt-6 w-full h-full space-y-6">
                      <div className="grid grid-cols-1 pb-[200px] gap-6">
                        {/* We'll implement these components later */}
                        {children}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Search section in workflow mode */}
          {!chatMode && (
            <div className="sticky bottom-0 left-0 right-0 bg-white border-t border-gray-200">
              <SearchSection
                keysUpdated={keysUpdateCounter}
                isLoading={isLoading}
                runId={currentRunId}
                sessionId={sessionId}
                onSearchStart={handleSearchStart}
                onSearchComplete={handleSearchComplete}
                onSearchError={handleSearchError}
                onOpenSettings={openSettings}
              />
            </div>
          )}
        </main>

        {/* RIGHT SIDEBAR */}
        {!chatMode ? (
          <AgentSidebar
            userId={userId}
            runId={currentRunId}
          />
        ) : (
          <ChatAgentSidebar
            userId={userId}
            runId={currentRunId}
            agentData={agentData}
            metadata={metadata}
          />
        )}
      </div>
    </div>
  );
}