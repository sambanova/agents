"use client";

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { hasAccessToken } from '@/lib/auth';

export default function Home() {
  const router = useRouter();
  
  useEffect(() => {
    // Create a default conversation and redirect to it
    // In the Vue app, this was done with the App.vue component
    // For now, we'll just redirect to the main layout
    if (hasAccessToken()) {
      router.push('/dashboard');
    }
  }, [router]);

  return (
    <div className="h-screen flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-3xl font-bold">
          <span className="bg-clip-text text-primary-brandTextSecondary">
            Loading Agent Crew...
          </span>
        </h1>
      </div>
    </div>
  );
}