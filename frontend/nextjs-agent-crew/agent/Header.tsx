"use client";

import { useState, forwardRef, useImperativeHandle } from 'react';
import { Switch } from '@headlessui/react';
import Image from 'next/image';

interface HeaderProps {
  className?: string;
  onKeysUpdated?: () => void;
  onModeToggled?: (value: boolean) => void;
}

const Header = forwardRef<any, HeaderProps>(({ 
  className = '',
  onKeysUpdated,
  onModeToggled
}, ref) => {
  const [chatMode, setChatMode] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  
  // Expose methods to parent components
  useImperativeHandle(ref, () => ({
    openSettings: () => setShowSettings(true)
  }));
  
  // Toggle between chat and workflow modes
  const toggleMode = () => {
    const newMode = !chatMode;
    setChatMode(newMode);
    onModeToggled?.(newMode);
  };
  
  return (
    <header className={`h-16 bg-white border-b border-gray-200 px-4 ${className}`}>
      <div className="h-full flex items-center justify-between">
        {/* Logo and title */}
        <div className="flex items-center space-x-2">
          <div className="h-8 w-8">
            <Image
              src="/logo-icon.svg"
              alt="Logo"
              width={32}
              height={32}
            />
          </div>
          <h1 className="text-xl font-semibold text-primary-brandTextPrimary">Agent Crew</h1>
        </div>
        
        {/* Controls */}
        <div className="flex items-center space-x-4">
          {/* Mode Toggle */}
          <div className="flex items-center space-x-2">
            <span className={`text-sm ${!chatMode ? 'text-primary-brandColor font-medium' : 'text-gray-500'}`}>Workflow</span>
            <Switch
              checked={chatMode}
              onChange={toggleMode}
              className={`${
                chatMode ? 'bg-primary-brandColor' : 'bg-gray-300'
              } relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none`}
            >
              <span
                className={`${
                  chatMode ? 'translate-x-6' : 'translate-x-1'
                } inline-block h-4 w-4 transform rounded-full bg-white transition-transform`}
              />
            </Switch>
            <span className={`text-sm ${chatMode ? 'text-primary-brandColor font-medium' : 'text-gray-500'}`}>Chat</span>
          </div>
          
          {/* Settings button */}
          <button
            onClick={() => setShowSettings(true)}
            className="p-2 rounded-full hover:bg-gray-100"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
              className="w-6 h-6 text-gray-600"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          </button>
        </div>
      </div>
      
      {/* Settings modal (simplified placeholder) */}
      {showSettings && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Settings</h2>
              <button
                onClick={() => setShowSettings(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-6 w-6"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
            
            <div className="space-y-4">
              {/* API Key fields would go here */}
              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-700">API Keys</label>
                <p className="text-sm text-gray-500">Settings UI to be implemented based on your requirements.</p>
              </div>
              
              <div className="flex justify-end">
                <button
                  onClick={() => {
                    setShowSettings(false);
                    onKeysUpdated?.();
                  }}
                  className="px-4 py-2 bg-primary-brandColor text-white rounded-md hover:bg-primary-600"
                >
                  Save Changes
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </header>
  );
});

Header.displayName = 'Header';

export default Header;