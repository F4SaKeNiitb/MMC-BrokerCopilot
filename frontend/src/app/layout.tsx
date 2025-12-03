import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Providers } from './providers';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Broker Copilot - AI-Powered Insurance Workflow',
  description:
    'AI-augmented workflow platform for insurance brokers. Zero-storage, connector-driven architecture with real-time insights.',
  keywords: ['insurance', 'broker', 'AI', 'workflow', 'renewal management'],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
