"use client";

import { useEffect } from 'react';

type ErrorModalProps = {
  show: boolean;
  errorMessage: string;
  onClose: () => void;
};

export default function ErrorModal({ show, errorMessage, onClose }: ErrorModalProps) {
  // Close on escape key
  useEffect(() => {
    const handleEscapeKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && show) {
        onClose();
      }
    };
    
    window.addEventListener('keydown', handleEscapeKey);
    return () => window.removeEventListener('keydown', handleEscapeKey);
  }, [show, onClose]);

  if (!show) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full">
        <div className="flex items-start mb-4">
          {/* Error icon */}
          <div className="flex-shrink-0 mr-3">
            <svg
              className="h-6 w-6 text-red-500"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
              />
            </svg>
          </div>
          
          {/* Title and message */}
          <div className="flex-1">
            <h3 className="text-lg font-medium text-gray-900">Error</h3>
            <p className="mt-1 text-sm text-gray-500">{errorMessage}</p>
          </div>
          
          {/* Close button */}
          <button
            onClick={onClose}
            className="flex-shrink-0 ml-3 text-gray-400 hover:text-gray-500"
          >
            <svg
              className="h-5 w-5"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>
        
        <div className="mt-4 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}