"use client";

type LoadingSpinnerProps = {
  message?: string;
  subMessage?: string;
};

export default function LoadingSpinner({ 
  message = 'Loading...', 
  subMessage 
}: LoadingSpinnerProps) {
  return (
    <div className="flex flex-col items-center justify-center py-8">
      {/* Spinner animation */}
      <div className="relative h-12 w-12 mb-4">
        <div className="absolute animate-spin h-12 w-12 rounded-full border-4 border-gray-200 border-t-primary-brandColor"></div>
      </div>
      
      {/* Messages */}
      <h3 className="text-lg font-medium text-gray-900 mt-2">{message}</h3>
      {subMessage && (
        <p className="text-sm text-gray-500 mt-1">{subMessage}</p>
      )}
    </div>
  );
}