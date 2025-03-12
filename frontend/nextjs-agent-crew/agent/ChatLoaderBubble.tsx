"use client";

import { useState, useEffect } from 'react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js';

type ChatLoaderBubbleProps = {
  isLoading: boolean;
  statusText: string;
  workflowData?: any[];
  plannerText?: string;
  provider: string;
  messageId: string;
};

export default function ChatLoaderBubble({
  isLoading,
  statusText,
  workflowData = [],
  plannerText,
  provider,
  messageId
}: ChatLoaderBubbleProps) {
  const [htmlContent, setHtmlContent] = useState<string>('');
  
  // Update planner text display when it changes
  useEffect(() => {
    if (plannerText) {
      renderMarkdown(plannerText);
    }
  }, [plannerText]);
  
  // Function to render markdown
  const renderMarkdown = (content: string) => {
    marked.setOptions({
      gfm: true,
      breaks: true,
      smartypants: true,
      highlight: (code, lang) => {
        if (lang && hljs.getLanguage(lang)) {
          return hljs.highlight(code, { language: lang }).value;
        }
        return hljs.highlightAuto(code).value;
      }
    });
    
    // Sanitize the HTML to prevent XSS
    const html = DOMPurify.sanitize(marked(content || ''));
    setHtmlContent(html);
  };
  
  if (!isLoading) return null;
  
  return (
    <li className="flex flex-col max-w-4xl mx-auto w-full">
      <div className="flex justify-start">
        <div className="relative flex flex-col p-4 gap-4 rounded-lg bg-primary-brandFrame text-gray-800 max-w-[95%]">
          {/* Loading animation */}
          <div className="flex items-center space-x-2">
            <div className="flex">
              <div className="h-2 w-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
              <div className="h-2 w-2 bg-gray-400 rounded-full animate-bounce mx-1" style={{ animationDelay: '150ms' }}></div>
              <div className="h-2 w-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
            </div>
            <span className="text-sm text-gray-500">{statusText}</span>
          </div>
          
          {/* Display planner text if available */}
          {plannerText && (
            <div 
              className="prose prose-sm max-w-none mt-2 border-t pt-2 border-gray-200"
              dangerouslySetInnerHTML={{ __html: htmlContent }}
            />
          )}
          
          {/* Workflow data indicators - similar to ChatBubble */}
          {workflowData && workflowData.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2">
              {workflowData.map((item, index) => (
                <span 
                  key={index}
                  className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-full"
                >
                  {item.llm_name || 'Model'} • {item.count || 1}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </li>
  );
}