"use client";

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

export default function Dashboard() {
  const router = useRouter();

  useEffect(() => {
    const createNewChat = async () => {
      try {
        const response = await api.chat.init();
        const conversationId = response.conversation_id;
        router.push(`/dashboard/${conversationId}`);
      } catch (error) {
        console.error('Error creating new chat:', error);
      }
    };

    // Create a new chat when the dashboard is loaded without a conversation ID
    createNewChat();
  }, [router]);

  return (
    <div className="h-full flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-3xl font-bold sm:text-4xl">
          <span className="bg-clip-text text-primary-brandTextSecondary">
            Starting a new conversation...
          </span>
        </h1>
      </div>
    </div>
  );
}