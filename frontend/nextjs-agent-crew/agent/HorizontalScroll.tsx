"use client";

import { useRef, useState, useEffect } from 'react';

type HorizontalScrollProps = {
  children: React.ReactNode;
};

export default function HorizontalScroll({ children }: HorizontalScrollProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [showLeftArrow, setShowLeftArrow] = useState(false);
  const [showRightArrow, setShowRightArrow] = useState(false);

  // Check if scroll arrows should be shown
  const checkScrollPosition = () => {
    if (!containerRef.current) return;
    
    const { scrollLeft, scrollWidth, clientWidth } = containerRef.current;
    
    // Show left arrow if we're not at the start
    setShowLeftArrow(scrollLeft > 0);
    
    // Show right arrow if we're not at the end
    setShowRightArrow(scrollLeft < scrollWidth - clientWidth - 10); // 10px buffer
  };

  // Add scroll event listener
  useEffect(() => {
    const container = containerRef.current;
    if (container) {
      container.addEventListener('scroll', checkScrollPosition);
      
      // Initial check
      setTimeout(checkScrollPosition, 100);
      
      // Check if content overflows
      if (container.scrollWidth > container.clientWidth) {
        setShowRightArrow(true);
      }
    }
    
    return () => {
      if (container) {
        container.removeEventListener('scroll', checkScrollPosition);
      }
    };
  }, []);

  // Handle scroll arrows
  const scrollLeft = () => {
    if (containerRef.current) {
      containerRef.current.scrollBy({ left: -200, behavior: 'smooth' });
    }
  };

  const scrollRight = () => {
    if (containerRef.current) {
      containerRef.current.scrollBy({ left: 200, behavior: 'smooth' });
    }
  };

  return (
    <div className="relative">
      {/* Left arrow */}
      {showLeftArrow && (
        <button
          onClick={scrollLeft}
          className="absolute left-0 top-1/2 transform -translate-y-1/2 z-10 bg-white/80 rounded-full p-1 shadow-md"
          aria-label="Scroll left"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-gray-600" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd" />
          </svg>
        </button>
      )}
      
      {/* Scrollable container */}
      <div
        ref={containerRef}
        className="overflow-x-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent pb-2"
      >
        {children}
      </div>
      
      {/* Right arrow */}
      {showRightArrow && (
        <button
          onClick={scrollRight}
          className="absolute right-0 top-1/2 transform -translate-y-1/2 z-10 bg-white/80 rounded-full p-1 shadow-md"
          aria-label="Scroll right"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-gray-600" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
          </svg>
        </button>
      )}
    </div>
  );
}