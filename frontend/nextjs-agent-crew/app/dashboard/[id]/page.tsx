"use client";

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { useParams } from 'next/navigation';

// Import components dynamically to avoid server-side rendering issues
const ChatView = dynamic(() => import('@/agent/ChatView'), { ssr: false });

export default function ConversationPage() {
  const params = useParams();
  const conversationId = params?.id as string;

  return (
    <div className="h-full flex justify-center">
      {conversationId ? (
        <ChatView 
          conversationId={conversationId}
          className="flex-1"
        />
      ) : (
        <div className="flex items-center justify-center">
          <p>No conversation selected</p>
        </div>
      )}
    </div>
  );
}