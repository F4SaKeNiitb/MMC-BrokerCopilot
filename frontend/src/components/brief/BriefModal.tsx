'use client';

import React, { useState, useEffect, useRef } from 'react';
import { X, FileText, ExternalLink, AlertCircle, CheckCircle, Loader2, Copy, Check } from 'lucide-react';
import { Card, CardHeader, CardContent, Button, Badge, Skeleton } from '@/components/ui';
import { streamBrief } from '@/lib/api';
import { cn } from '@/lib/utils';

interface BriefModalProps {
  policyId: string;
  onClose: () => void;
}

export function BriefModal({ policyId, onClose }: BriefModalProps) {
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchBrief() {
      setLoading(true);
      setError(null);
      setContent('');

      try {
        for await (const chunk of streamBrief(policyId)) {
          if (cancelled) break;
          setContent((prev) => prev + chunk);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load brief');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchBrief();

    return () => {
      cancelled = true;
    };
  }, [policyId]);

  // Auto-scroll as content streams
  useEffect(() => {
    if (contentRef.current && loading) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight;
    }
  }, [content, loading]);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Parse markdown-like content for basic rendering
  const renderContent = (text: string) => {
    const lines = text.split('\n');
    return lines.map((line, i) => {
      // Headers
      if (line.startsWith('# ')) {
        return (
          <h1 key={i} className="text-2xl font-bold text-gray-900 mt-6 mb-3">
            {line.substring(2)}
          </h1>
        );
      }
      if (line.startsWith('## ')) {
        return (
          <h2 key={i} className="text-xl font-semibold text-gray-900 mt-5 mb-2">
            {line.substring(3)}
          </h2>
        );
      }
      if (line.startsWith('### ')) {
        return (
          <h3 key={i} className="text-lg font-medium text-gray-900 mt-4 mb-2">
            {line.substring(4)}
          </h3>
        );
      }
      // Bold text
      if (line.startsWith('**') && line.endsWith('**')) {
        return (
          <p key={i} className="font-semibold text-gray-800 my-2">
            {line.slice(2, -2)}
          </p>
        );
      }
      // List items
      if (line.startsWith('- ') || line.startsWith('* ')) {
        return (
          <li key={i} className="ml-4 text-gray-700">
            {line.substring(2)}
          </li>
        );
      }
      // Numbered list
      if (/^\d+\.\s/.test(line)) {
        return (
          <li key={i} className="ml-4 text-gray-700 list-decimal">
            {line.replace(/^\d+\.\s/, '')}
          </li>
        );
      }
      // Citations (formatted as [Source: ...])
      if (line.includes('[Source:') || line.includes('[Citation:')) {
        return (
          <p key={i} className="text-sm text-blue-600 bg-blue-50 px-2 py-1 rounded my-1 inline-block">
            {line}
          </p>
        );
      }
      // Empty lines
      if (line.trim() === '') {
        return <br key={i} />;
      }
      // Regular paragraphs
      return (
        <p key={i} className="text-gray-700 my-1">
          {line}
        </p>
      );
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <Card className="relative w-full max-w-4xl max-h-[90vh] flex flex-col animate-slide-up">
        <CardHeader className="flex flex-row items-center justify-between sticky top-0 bg-white z-10 border-b">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary-100 rounded-lg">
              <FileText className="w-5 h-5 text-primary-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                One-Page Brief
              </h2>
              <p className="text-sm text-gray-500">Policy: {policyId}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {loading && (
              <Badge variant="info" className="animate-pulse">
                <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                Generating...
              </Badge>
            )}
            {!loading && !error && (
              <Badge variant="success">
                <CheckCircle className="w-3 h-3 mr-1" />
                Complete
              </Badge>
            )}
            <Button variant="ghost" size="sm" onClick={handleCopy} disabled={!content}>
              {copied ? (
                <Check className="w-4 h-4 text-green-600" />
              ) : (
                <Copy className="w-4 h-4" />
              )}
            </Button>
            <Button variant="ghost" size="sm" onClick={onClose}>
              <X className="w-4 h-4" />
            </Button>
          </div>
        </CardHeader>

        <div
          ref={contentRef}
          className="flex-1 overflow-y-auto p-6"
        >
          {error ? (
            <div className="flex flex-col items-center justify-center py-12">
              <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
              <p className="text-red-600 font-medium">{error}</p>
              <Button
                variant="secondary"
                size="sm"
                className="mt-4"
                onClick={() => window.location.reload()}
              >
                Try Again
              </Button>
            </div>
          ) : content ? (
            <div className="prose prose-sm max-w-none">
              {renderContent(content)}
              {loading && (
                <span className="inline-block w-2 h-4 bg-primary-500 animate-pulse ml-1" />
              )}
            </div>
          ) : loading ? (
            <div className="space-y-4">
              <Skeleton className="h-8 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-6 w-1/2 mt-6" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
            </div>
          ) : null}
        </div>

        {/* Footer with provenance info */}
        <div className="border-t border-gray-100 px-6 py-3 bg-gray-50">
          <p className="text-xs text-gray-500">
            This brief is generated from live data sources. All facts are linked to their sources.
            <a href="#" className="text-primary-600 ml-1 hover:underline">
              View Data Provenance
            </a>
          </p>
        </div>
      </Card>
    </div>
  );
}
