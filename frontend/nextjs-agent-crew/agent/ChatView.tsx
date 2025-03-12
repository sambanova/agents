"use client";

import { useState, useEffect, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { marked } from 'marked';
import hljs from 'highlight.js';
import DOMPurify from 'dompurify';
import { WebSocketManager } from '@/lib/websocket';
import { api } from '@/lib/api';
import { getUserId } from '@/lib/auth';

// Placeholder components (to be implemented later)
import ChatBubble from './ChatBubble';
import ChatLoaderBubble from './ChatLoaderBubble';
import HorizontalScroll from './HorizontalScroll';

// Import necessary icons (we'll use heroicons)
import { XMarkIcon } from '@heroicons/react/24/outline';

type ChatViewProps = {
  conversationId: string;
  className?: string;
  onMetadataChanged?: (metadata: any) => void;
  onAgentThoughtsDataChanged?: (agentThoughtsData: any[]) => void;
};

export default function ChatView({
  conversationId,
  className = '',
  onMetadataChanged,
  onAgentThoughtsDataChanged
}: ChatViewProps) {
  // Basic state
  const [messagesData, setMessagesData] = useState<any[]>([]);
  const [workflowData, setWorkflowData] = useState<any[]>([]);
  const [agentThoughtsData, setAgentThoughtsData] = useState<any[]>([]);
  const [plannerTextData, setPlannerTextData] = useState<any[]>([]);
  const [completionMetaData, setCompletionMetaData] = useState<any>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [chatName, setChatName] = useState<string>('');
  const [provider, setProvider] = useState<string>('sambanova');
  const [currentMsgId, setCurrentMsgId] = useState<string>('');
  
  // Document handling state
  const [uploadedDocuments, setUploadedDocuments] = useState<any[]>([]);
  const [selectedDocuments, setSelectedDocuments] = useState<string[]>([]);
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  
  // Voice recording state
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [audioChunks, setAudioChunks] = useState<Blob[]>([]);
  
  // Status text for the agent
  const [statusText, setStatusText] = useState<string>('Loading...');
  
  // Refs
  const container = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  
  // WebSocket connection
  const [socket, setSocket] = useState<WebSocketManager | null>(null);
  
  // Function to initialize WebSocket connection
  const connectWebSocket = async () => {
    if (!conversationId) return;
    
    try {
      const wsManager = new WebSocketManager(conversationId);
      
      // Set up message handlers
      wsManager.on('completion', (data) => {
        try {
          if (data.event === "completion") {
            let metaDataCompletion = JSON.parse(data.data);
            setCompletionMetaData(metaDataCompletion.metadata);
            onMetadataChanged?.(metaDataCompletion.metadata);
          }
          setMessagesData(prev => [...prev, data]);
          setIsLoading(false);
          autoScrollToBottom();
        } catch (error) {
          console.error("Error processing completion data:", error);
        }
      });
      
      wsManager.on('user_message', (data) => {
        setMessagesData(prev => [...prev, data]);
        autoScrollToBottom();
      });
      
      wsManager.on('think', (data) => {
        try {
          const dataParsed = JSON.parse(data.data);
          setAgentThoughtsData(prev => [...prev, dataParsed]);
          setStatusText(dataParsed.agent_name);
          onAgentThoughtsDataChanged?.([...agentThoughtsData, dataParsed]);
          
          addOrUpdateModel(dataParsed.metadata);
          autoScrollToBottom();
        } catch (error) {
          console.error("Error processing think data:", error);
        }
      });
      
      wsManager.on('planner_chunk', (data) => {
        addOrUpdatePlannerText({
          message_id: currentMsgId,
          data: data.data
        });
      });
      
      wsManager.on('planner', (data) => {
        try {
          const dataParsed = JSON.parse(data.data);
          addOrUpdateModel(dataParsed.metadata);
          autoScrollToBottom();
        } catch (error) {
          console.error("Error processing planner data:", error);
        }
      });
      
      // Connect and store the manager
      await wsManager.connect();
      setSocket(wsManager);
      
    } catch (error) {
      console.error('WebSocket connection error:', error);
      setIsLoading(false);
    }
  };
  
  // Load previous chat messages
  const loadPreviousChat = async (convId: string) => {
    try {
      setIsLoading(true);
      const data = await api.chat.history(convId);
      filterChat(data);
      autoScrollToBottom(true);
      setIsLoading(false);
    } catch (error) {
      console.error('Error loading chat history:', error);
      setIsLoading(false);
    }
  };
  
  // Process the chat history data
  const filterChat = (msgData: any) => {
    // Filter user and assistant messages
    const filteredMessages = msgData.messages
      .filter((message: any) => message.event === "completion" || message.event === "user_message")
      .sort((a: any, b: any) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
    
    setMessagesData(filteredMessages);
    
    // Process planner data
    const plannerData = msgData.messages
      .filter((message: any) => message.event === "planner");
    
    plannerData.forEach((planner: any) => {
      try {
        const parsedData = JSON.parse(planner.data);
        addOrUpdateModel(parsedData.metadata, planner.message_id);
      } catch (error) {
        console.error("Error parsing planner data:", error);
      }
    });
    
    // Process agent thoughts data
    const workData = msgData.messages
      .filter((message: any) => message.event === "think");
    
    workData.forEach((work: any) => {
      try {
        const parsedData = JSON.parse(work.data);
        addOrUpdateModel(parsedData.metadata, work.message_id);
      } catch (error) {
        console.error("Error parsing think data:", error);
      }
    });
    
    // Extract and process agent thoughts data
    const thoughts = msgData.messages
      .filter((message: any) => message.event === "think")
      .sort((a: any, b: any) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
      .reduce((acc: any[], message: any) => {
        try {
          const parsed = JSON.parse(message.data);
          acc.push(parsed);
        } catch (error) {
          console.error("Failed to parse JSON for message:", message, error);
        }
        return acc;
      }, []);
    
    setAgentThoughtsData(thoughts);
    onAgentThoughtsDataChanged?.(thoughts);
    
    // Set chat name
    if (filteredMessages[0]?.data) {
      setChatName(filteredMessages[0].data);
    }
    
    autoScrollToBottom();
  };
  
  // Handle sending a new message
  const addMessage = async () => {
    if (!searchQuery.trim()) return;
    
    setWorkflowData([]);
    
    // Generate a new message ID
    const newMsgId = uuidv4();
    setCurrentMsgId(newMsgId);
    
    // Reset states
    setCompletionMetaData(null);
    setStatusText('Loading...');
    autoScrollToBottom();
    setAgentThoughtsData([]);
    onAgentThoughtsDataChanged?.([]);
    onMetadataChanged?.(null);
    
    // Create message payload
    const messagePayload = {
      event: "user_message",
      data: searchQuery,
      timestamp: new Date().toISOString(),
      provider: provider,
      planner_model: localStorage.getItem(`selected_model_${getUserId()}`) || '',
      message_id: newMsgId,
      document_ids: selectedDocuments
    };
    
    // Add message to the UI
    setMessagesData(prev => [...prev, messagePayload]);
    
    // Save chat name if this is the first message
    if (messagesData.length === 0) {
      setChatName(searchQuery);
    }
    
    try {
      setIsLoading(true);
      
      // Ensure WebSocket is connected
      if (!socket || !(await isSocketConnected())) {
        await connectWebSocket();
      }
      
      // Send the message
      socket?.send(messagePayload);
      setSearchQuery('');
    } catch (error) {
      console.error("Error sending message:", error);
      setIsLoading(false);
    }
  };
  
  // Check if socket is connected
  const isSocketConnected = async (): Promise<boolean> => {
    if (!socket) return false;
    
    try {
      await socket.waitForOpen(5000);
      return true;
    } catch (error) {
      console.error("Socket connection failed:", error);
      return false;
    }
  };
  
  // Add or update model in workflow data
  const addOrUpdateModel = (newData: any, message_id?: string) => {
    // Determine which message_id to use
    const idToUse = message_id || currentMsgId;
    
    setWorkflowData(prev => {
      // Find existing model with matching llm_name and message_id
      const existingIndex = prev.findIndex(
        item => item.llm_name === newData.llm_name && item.message_id === idToUse
      );
      
      if (existingIndex !== -1) {
        // Update existing model
        const updated = [...prev];
        updated[existingIndex] = {
          ...updated[existingIndex],
          ...newData,
          count: (updated[existingIndex].count || 1) + 1
        };
        return updated;
      } else {
        // Add new model
        return [...prev, {
          ...newData,
          count: 1,
          message_id: idToUse
        }];
      }
    });
  };
  
  // Add or update planner text
  const addOrUpdatePlannerText = (newEntry: any) => {
    setPlannerTextData(prev => {
      // Find existing entry with the same message_id
      const index = prev.findIndex(entry => entry.message_id === newEntry.message_id);
      
      if (index !== -1) {
        // Update existing entry
        const updated = [...prev];
        updated[index] = {
          ...updated[index],
          data: updated[index].data + newEntry.data
        };
        return updated;
      } else {
        // Add new entry
        return [...prev, newEntry];
      }
    });
  };
  
  // Auto scroll to bottom of chat
  const autoScrollToBottom = (smoothScrollOff = false) => {
    setTimeout(() => {
      if (container.current) {
        const targetScroll = container.current.scrollHeight - container.current.clientHeight;
        container.current.scrollTo({
          top: targetScroll,
          behavior: smoothScrollOff ? "auto" : "smooth"
        });
      }
    }, 100);
  };
  
  // Toggle document selection
  const toggleDocumentSelection = (docId: string) => {
    setSelectedDocuments(prev => {
      const index = prev.indexOf(docId);
      if (index === -1) {
        return [...prev, docId];
      } else {
        return prev.filter(id => id !== docId);
      }
    });
  };
  
  // Toggle document list expansion
  const toggleExpand = () => {
    setIsExpanded(!isExpanded);
  };
  
  // Handle file upload
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    
    try {
      const document = await api.documents.upload(file);
      setUploadedDocuments(prev => [...prev, document]);
      setSelectedDocuments(prev => [...prev, document.id]);
      
      // Reset file input
      if (fileInput.current) {
        fileInput.current.value = '';
      }
    } catch (error) {
      console.error('Error uploading document:', error);
    }
  };
  
  // Remove document
  const removeDocument = async (docId: string) => {
    try {
      await api.documents.delete(docId);
      setSelectedDocuments(prev => prev.filter(id => id !== docId));
      setUploadedDocuments(prev => prev.filter(doc => doc.id !== docId));
    } catch (error) {
      console.error('Error removing document:', error);
    }
  };
  
  // Handle keydown in textarea
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      addMessage();
    }
  };
  
  // Load documents on mount
  const loadUserDocuments = async () => {
    try {
      const documents = await api.documents.getAll();
      setUploadedDocuments(documents);
    } catch (error) {
      console.error('Error loading documents:', error);
    }
  };
  
  // Effect for conversation changes
  useEffect(() => {
    if (conversationId) {
      // Reset states when conversation changes
      setCompletionMetaData(null);
      setIsLoading(false);
      setMessagesData([]);
      setAgentThoughtsData([]);
      setSearchQuery('');
      
      // Load the conversation and connect WebSocket
      loadPreviousChat(conversationId);
      connectWebSocket();
    }
    
    return () => {
      // Clean up WebSocket on unmount
      socket?.disconnect();
    };
  }, [conversationId]);
  
  // Load documents on mount
  useEffect(() => {
    loadUserDocuments();
  }, []);
  
  return (
    <div className={`relative h-full w-full ${className}`}>
      {/* Content */}
      <div ref={container} className="relative h-full flex flex-col overflow-x-hidden overflow-y-auto">
        {/* Sticky Top Component */}
        {chatName && (
          <div className="sticky h-[62px] top-0 z-10 bg-white p-4 shadow">
            <div className="flex items-center justify-between">
              {/* Left text */}
              <div className="text-[16px] w-80 font-medium text-gray-800 line-clamp-1 overflow-hidden">
                {chatName}
              </div>
              {/* Right buttons */}
              <div className="flex hidden space-x-2">
                <button 
                  className="text-sm h-[30px] py-1 px-2.5 bg-[#EE7624] text-white rounded"
                >
                  View full report
                </button>
                <button
                  className="text-sm h-[30px] py-1 px-2.5 bg-[#EAECF0] text-[#344054] rounded"
                >
                  Download PDF
                </button>
              </div>
            </div>
          </div>
        )}
        
        <div 
          className={`flex-1 w-full flex mx-auto ${messagesData.length === 0 ? 'justify-center align-center flex-col' : ''}`}
        >
          {/* Title */}
          {messagesData.length === 0 && (
            <div className="w-full text-center">
              <h1 className="text-3xl font-bold sm:text-4xl">
                <span className="bg-clip-text text-primary-brandTextSecondary">Agents</span>
              </h1>
            </div>
          )}
          
          {/* Messages */}
          <ul className="mt-16 max-w-4xl w-full mx-auto space-y-5">
            {/* Chat Bubbles */}
            {messagesData.map((msgItem) => (
              <ChatBubble
                key={msgItem.message_id || msgItem.timestamp}
                metadata={completionMetaData}
                workflowData={workflowData.filter(item => item.message_id === msgItem.message_id)}
                plannerText={plannerTextData.find(item => item.message_id === msgItem.message_id)?.data}
                event={msgItem.event}
                data={msgItem.data}
                messageId={msgItem.message_id}
                provider={provider}
                currentMsgId={currentMsgId}
              />
            ))}
            
            {/* Loading bubble */}
            {isLoading && (
              <ChatLoaderBubble
                workflowData={workflowData.filter(item => item.message_id === currentMsgId)}
                isLoading={isLoading}
                statusText="Planning..."
                plannerText={plannerTextData.find(item => item.message_id === currentMsgId)?.data}
                provider={provider}
                messageId={currentMsgId}
              />
            )}
          </ul>
        </div>
        
        {/* Documents Section */}
        <div className="sticky z-1000 bottom-0 left-0 right-0 bg-white p-2">
          <div className="sticky bottom-0 z-10">
            {/* Textarea */}
            <div className="max-w-4xl mx-auto lg:px-0">
              {/* Uploaded Documents */}
              {uploadedDocuments.length > 0 && (
                <div className="mt-4">
                  {/* Collapsible header */}
                  <button
                    onClick={toggleExpand}
                    className="flex items-center justify-between focus:outline-none"
                  >
                    <h3 className="text-sm font-medium text-gray-700 mb-2">
                      Uploaded Documents ({uploadedDocuments.length})
                    </h3>
                    <svg
                      className={`w-5 h-5 text-gray-500 transition-transform duration-200 ${isExpanded ? 'transform rotate-180' : ''}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M19 9l-7 7-7-7"
                      />
                    </svg>
                  </button>
                  
                  {/* Collapsible content */}
                  {isExpanded && (
                    <HorizontalScroll>
                      <div className="flex space-x-4">
                        {uploadedDocuments.map((doc) => (
                          <div
                            key={doc.id}
                            className="w-48 flex-shrink-0 p-2 bg-gray-50 rounded-lg border border-gray-200 hover:bg-gray-100 relative group"
                          >
                            <div className="flex items-center space-x-3">
                              <input
                                type="checkbox"
                                checked={selectedDocuments.includes(doc.id)}
                                onChange={() => toggleDocumentSelection(doc.id)}
                                className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                              />
                              <div className="w-48 overflow-hidden">
                                <p className="text-sm font-medium text-gray-900 truncate">
                                  {doc.filename}
                                </p>
                                <p className="text-xs text-gray-500 truncate">
                                  Uploaded {new Date(doc.upload_timestamp * 1000).toLocaleString()} •
                                  {doc.num_chunks} chunks
                                </p>
                              </div>
                            </div>
                            <button
                              onClick={() => removeDocument(doc.id)}
                              className="absolute top-1 right-1 bg-orange-300 text-white rounded-full p-1 transition-opacity opacity-0 group-hover:opacity-100"
                              title="Remove document"
                            >
                              <XMarkIcon className="w-5 h-5" />
                            </button>
                          </div>
                        ))}
                      </div>
                    </HorizontalScroll>
                  )}
                </div>
              )}
              
              {/* Input */}
              <div className="relative">
                <textarea
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask me about...companies to target, research topics, or company stocks and financials"
                  disabled={isLoading}
                  className="p-4 pb-12 block w-full bg-primary-brandFrame border-primary-brandFrame rounded-lg text-sm focus:outline-none active:outline-none border focus:border-primary-brandColor disabled:opacity-50 disabled:pointer-events-none"
                />
                
                {/* Toolbar */}
                <div className="absolute bottom-px inset-x-px p-2 rounded-b-lg border-primary-brandFrame">
                  <div className="flex justify-between items-center">
                    {/* Button Group */}
                    <div className="flex items-center">
                      {/* Attach Button */}
                      <button
                        onClick={() => fileInput.current?.click()}
                        disabled={isLoading}
                        type="button"
                        className="inline-flex shrink-0 justify-center items-center size-8 rounded-lg text-gray-500 hover:bg-gray-100 focus:z-1 focus:outline-none focus:bg-gray-100"
                      >
                        <input
                          type="file"
                          ref={fileInput}
                          onChange={handleFileUpload}
                          className="hidden"
                          accept=".pdf,.doc,.docx,.csv,.xlsx,.xls"
                        />
                        <svg 
                          className="shrink-0 w-5 h-5" 
                          xmlns="http://www.w3.org/2000/svg" 
                          fill="none" 
                          viewBox="0 0 24 24" 
                          stroke="currentColor"
                        >
                          <path 
                            strokeLinecap="round" 
                            strokeLinejoin="round" 
                            strokeWidth="2" 
                            d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" 
                          />
                        </svg>
                      </button>
                    </div>
                    
                    {/* Send Button */}
                    <button
                      type="button"
                      onClick={addMessage}
                      disabled={isLoading || !searchQuery.trim()}
                      className="inline-flex shrink-0 justify-center items-center bg-transparent cursor-pointer"
                    >
                      {!isLoading ? (
                        <svg
                          width="21"
                          height="18"
                          viewBox="0 0 21 18"
                          fill="none"
                          xmlns="http://www.w3.org/2000/svg"
                        >
                          <path d="M0.00999999 18L21 9L0.00999999 0L0 7L15 9L0 11L0.00999999 18Z" fill="#EE7624" />
                        </svg>
                      ) : (
                        <svg
                          width="20"
                          height="20"
                          viewBox="0 0 20 20"
                          fill="none"
                          xmlns="http://www.w3.org/2000/svg"
                        >
                          <path
                            d="M10 0C4.48 0 0 4.48 0 10C0 15.52 4.48 20 10 20C15.52 20 20 15.52 20 10C20 4.48 15.52 0 10 0ZM10 18C5.58 18 2 14.42 2 10C2 5.58 5.58 2 10 2C14.42 2 18 5.58 18 10C18 14.42 14.42 18 10 18ZM14 14H6V6H14V14Z"
                            fill="#667085"
                          />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}