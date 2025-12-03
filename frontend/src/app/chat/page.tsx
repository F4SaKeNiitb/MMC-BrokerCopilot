'use client';

import React from 'react';
import { Layout } from '@/components/layout/Layout';
import { ChatInterface } from '@/components/chat/ChatInterface';

export default function ChatPage() {
  return (
    <Layout>
      <ChatInterface />
    </Layout>
  );
}
