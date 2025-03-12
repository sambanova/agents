"use client";

import { useState, useEffect } from 'react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js';
import 'highlight.js/styles/github.css';

type ChatBubbleProps = {
  event: string;
  data: string;
  metadata?: any;
  workflowData?: any[];
  plannerText?: string;
  messageId: string;
  provider: string;
  currentMsgId: string;
};

export default function ChatBubble({
  event,
  data,
  metadata,
  workflowData = [],
  plannerText,
  messageId,
  provider,
  currentMsgId
}: ChatBubbleProps) {
  const [htmlContent, setHtmlContent] = useState<string>('');
  const [parsedContent, setParsedContent] = useState<any>(null);
  
  // Setup Markdown renderer
  useEffect(() => {
    if (event === 'completion') {
      try {
        // Try to parse the data as JSON
        const parsed = JSON.parse(data);
        setParsedContent(parsed);
        
        if (parsed.content) {
          // Render the content field from the parsed data
          renderMarkdown(parsed.content);
        } else {
          // If no content field, render the whole data as string
          renderMarkdown(JSON.stringify(parsed, null, 2));
        }
      } catch (error) {
        // If not JSON, render as markdown
        renderMarkdown(data);
      }
    } else {
      // For user messages, just set the data
      setHtmlContent(data);
    }
  }, [data, event]);
  
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
  
  return (
    <li className="flex flex-col max-w-4xl mx-auto w-full">
      <div className={`flex ${event === 'user_message' ? 'justify-end' : 'justify-start'}`}>
        <div 
          className={`relative flex flex-col p-4 gap-4 rounded-lg ${
            event === 'user_message' 
              ? 'bg-primary-brandColor text-white self-end max-w-[85%]' 
              : 'bg-primary-brandFrame text-gray-800 max-w-[95%]'
          }`}
        >
          {event === 'user_message' ? (
            <div className="prose prose-sm text-white">{data}</div>
          ) : (
            <div 
              className="prose prose-sm max-w-none"
              dangerouslySetInnerHTML={{ __html: htmlContent }}
            />
          )}
          
          {/* Workflow data indicators - can be implemented based on your requirements */}
          {workflowData && workflowData.length > 0 && event !== 'user_message' && (
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