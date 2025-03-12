"use client";

import { useState, useRef } from 'react';
import { api } from '@/lib/api';

type SearchSectionProps = {
  keysUpdated: number;
  isLoading: boolean;
  runId: string;
  sessionId: string;
  onSearchStart: (type: string) => void;
  onSearchComplete: (results: any) => void;
  onSearchError: (error: any) => void;
  onOpenSettings: () => void;
};

export default function SearchSection({
  keysUpdated,
  isLoading,
  runId,
  sessionId,
  onSearchStart,
  onSearchComplete,
  onSearchError,
  onOpenSettings
}: SearchSectionProps) {
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [uploadedDocuments, setUploadedDocuments] = useState<any[]>([]);
  const [selectedDocuments, setSelectedDocuments] = useState<string[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);

  // Handle search submission
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    try {
      // First, route the query
      onSearchStart('routing_query');
      const routeResponse = await api.search.route(searchQuery);
      
      const detectedType = routeResponse.type;
      onSearchStart(detectedType);
      
      // Build parameters for execution
      const parameters = {
        ...routeResponse.parameters,
        document_ids: selectedDocuments
      };
      
      // Execute the query
      const results = await api.search.execute(detectedType, parameters);
      
      // Return the results
      onSearchComplete({
        type: detectedType,
        query: searchQuery,
        results
      });
      
      // Clear the search field
      setSearchQuery('');
      
    } catch (error) {
      console.error('Search error:', error);
      onSearchError(error);
    }
  };

  // Handle file upload
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    
    try {
      onSearchStart('document_upload');
      
      const document = await api.documents.upload(file);
      setUploadedDocuments(prev => [...prev, document]);
      setSelectedDocuments(prev => [...prev, document.id]);
      
      // Reset file input
      if (fileInput.current) {
        fileInput.current.value = '';
      }
      
    } catch (error) {
      console.error('Upload error:', error);
      onSearchError(error);
    }
  };

  // Handle keydown in search input
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <div className="p-4 w-full">
      <div className="relative flex items-center">
        {/* Search input */}
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask me about...companies to target, research topics, or company stocks and financials"
          disabled={isLoading}
          className="block w-full pl-4 pr-14 py-3 border border-primary-brandFrame bg-primary-brandFrame rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-brandColor"
        />
        
        {/* Action buttons */}
        <div className="absolute right-2 flex space-x-2">
          {/* File upload button */}
          <button
            onClick={() => fileInput.current?.click()}
            disabled={isLoading}
            className="p-2 text-gray-500 hover:text-gray-700 focus:outline-none"
          >
            <input
              type="file"
              ref={fileInput}
              onChange={handleFileUpload}
              className="hidden"
              accept=".pdf,.doc,.docx,.csv,.xlsx,.xls"
            />
            <svg 
              className="w-5 h-5"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
              />
            </svg>
          </button>
          
          {/* Search button */}
          <button
            onClick={handleSearch}
            disabled={isLoading || !searchQuery.trim()}
            className="p-2 text-primary-brandColor hover:text-primary-700 focus:outline-none"
          >
            {!isLoading ? (
              <svg
                className="w-5 h-5"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
            ) : (
              <svg 
                className="w-5 h-5 animate-spin"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                ></circle>
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                ></path>
              </svg>
            )}
          </button>
        </div>
      </div>
      
      {/* Document chips could go here */}
      {uploadedDocuments.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {uploadedDocuments.map((doc) => (
            <div 
              key={doc.id}
              className="inline-flex items-center px-2 py-1 bg-gray-100 rounded-full text-xs"
            >
              <span className="truncate max-w-[150px]">{doc.filename}</span>
              <button 
                className="ml-1 text-gray-500 hover:text-gray-700"
                onClick={() => {
                  setUploadedDocuments(prev => prev.filter(d => d.id !== doc.id));
                  setSelectedDocuments(prev => prev.filter(id => id !== doc.id));
                }}
              >
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M10 8.586L13.293 5.293a1 1 0 111.414 1.414L11.414 10l3.293 3.293a1 1 0 01-1.414 1.414L10 11.414l-3.293 3.293a1 1 0 01-1.414-1.414L8.586 10 5.293 6.707a1 1 0 011.414-1.414L10 8.586z"
                    clipRule="evenodd"
                  />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}