'use client';

import { ReactNode } from 'react';
import { ToastProvider, ToastContainer } from '@/lib/toast';

interface ProvidersProps {
  children: ReactNode;
}

/**
 * Client-side providers wrapper
 * Wraps the application with all necessary context providers
 */
export function Providers({ children }: ProvidersProps) {
  return (
    <ToastProvider>
      {children}
      <ToastContainer />
    </ToastProvider>
  );
}
