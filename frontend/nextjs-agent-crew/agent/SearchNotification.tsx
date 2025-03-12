"use client";

import { useEffect, useState } from 'react';

type SearchNotificationProps = {
  show: boolean;
  time: string;
  resultCount: number;
};

export default function SearchNotification({ 
  show, 
  time, 
  resultCount 
}: SearchNotificationProps) {
  const [visible, setVisible] = useState(false);
  
  // Handle show/hide with animation
  useEffect(() => {
    if (show) {
      setVisible(true);
    } else {
      const timer = setTimeout(() => {
        setVisible(false);
      }, 300); // Short delay for animation
      return () => clearTimeout(timer);
    }
  }, [show]);
  
  if (!visible) return null;
  
  return (
    <div 
      className={`fixed bottom-20 right-4 bg-white shadow-lg rounded-lg p-4 transition-opacity duration-300 ${
        show ? 'opacity-100' : 'opacity-0'
      }`}
    >
      <div className="flex items-start">
        {/* Success icon */}
        <div className="flex-shrink-0 mr-3">
          <svg
            className="h-6 w-6 text-green-500"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        
        {/* Content */}
        <div>
          <h3 className="text-sm font-medium text-gray-900">Search Complete</h3>
          <p className="mt-1 text-xs text-gray-500">
            Found {resultCount} result{resultCount !== 1 ? 's' : ''} in {time} seconds
          </p>
        </div>
      </div>
    </div>
  );
}