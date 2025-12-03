'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  FileText,
  MessageSquare,
  TrendingUp,
  AlertCircle,
  Calendar,
  DollarSign,
  ArrowRight,
  Shield,
  Zap,
  Eye,
} from 'lucide-react';
import { Layout } from '@/components/layout/Layout';
import { Card, CardHeader, CardContent, Button, Badge, Skeleton } from '@/components/ui';
import { BriefModal } from '@/components/brief/BriefModal';
import { getRenewals, checkHealth } from '@/lib/api';
import { formatCurrency, getPriorityLabel } from '@/lib/utils';
import type { Policy } from '@/lib/types';

export default function DashboardPage() {
  const [renewals, setRenewals] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [selectedPolicy, setSelectedPolicy] = useState<string | null>(null);

  useEffect(() => {
    async function init() {
      // Check backend health
      try {
        await checkHealth();
        setBackendStatus('online');
      } catch {
        setBackendStatus('offline');
      }

      // Fetch renewals
      try {
        const data = await getRenewals({ days_window: 90, sort_by: 'score' });
        setRenewals(data.renewals);
      } catch (err) {
        console.error('Failed to fetch renewals:', err);
      } finally {
        setLoading(false);
      }
    }

    init();
  }, []);

  const criticalCount = renewals.filter((r) => (r.score || 0) >= 0.7).length;
  const totalPremium = renewals.reduce((sum, r) => sum + r.premium_at_risk, 0);
  const avgDaysToExpiry = renewals.length
    ? Math.round(renewals.reduce((sum, r) => sum + r.days_to_expiry, 0) / renewals.length)
    : 0;

  return (
    <Layout>
      {/* Backend status banner */}
      {backendStatus === 'offline' && (
        <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-yellow-600" />
          <div>
            <p className="font-medium text-yellow-800">Backend Offline</p>
            <p className="text-sm text-yellow-700">
              The backend server is not responding. Start it with: <code className="bg-yellow-100 px-1 rounded">uvicorn app.main:app</code>
            </p>
          </div>
        </div>
      )}

      {/* Welcome section */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Welcome to Broker Copilot</h1>
        <p className="text-gray-600">
          AI-powered insights for your insurance renewal pipeline
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Total Renewals</p>
                {loading ? (
                  <Skeleton className="h-8 w-16 mt-1" />
                ) : (
                  <p className="text-2xl font-bold text-gray-900">{renewals.length}</p>
                )}
              </div>
              <div className="p-3 bg-blue-100 rounded-lg">
                <FileText className="w-6 h-6 text-blue-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Critical Priority</p>
                {loading ? (
                  <Skeleton className="h-8 w-16 mt-1" />
                ) : (
                  <p className="text-2xl font-bold text-red-600">{criticalCount}</p>
                )}
              </div>
              <div className="p-3 bg-red-100 rounded-lg">
                <AlertCircle className="w-6 h-6 text-red-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Premium at Risk</p>
                {loading ? (
                  <Skeleton className="h-8 w-24 mt-1" />
                ) : (
                  <p className="text-2xl font-bold text-gray-900">{formatCurrency(totalPremium)}</p>
                )}
              </div>
              <div className="p-3 bg-green-100 rounded-lg">
                <DollarSign className="w-6 h-6 text-green-600" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Avg. Days to Expiry</p>
                {loading ? (
                  <Skeleton className="h-8 w-16 mt-1" />
                ) : (
                  <p className="text-2xl font-bold text-gray-900">{avgDaysToExpiry}</p>
                )}
              </div>
              <div className="p-3 bg-orange-100 rounded-lg">
                <Calendar className="w-6 h-6 text-orange-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent renewals */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Priority Renewals</h2>
              <Link href="/renewals">
                <Button variant="ghost" size="sm">
                  View All
                  <ArrowRight className="w-4 h-4 ml-1" />
                </Button>
              </Link>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="space-y-4">
                  {[...Array(3)].map((_, i) => (
                    <div key={i} className="flex items-center gap-4 p-4 border rounded-lg">
                      <Skeleton className="h-12 w-12 rounded-lg" />
                      <div className="flex-1">
                        <Skeleton className="h-5 w-32 mb-2" />
                        <Skeleton className="h-4 w-48" />
                      </div>
                      <Skeleton className="h-8 w-20 rounded-lg" />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="space-y-3">
                  {renewals.slice(0, 5).map((policy) => (
                    <div
                      key={policy.id}
                      className="flex items-center gap-4 p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      <div
                        className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                          (policy.score || 0) >= 0.7
                            ? 'bg-red-100'
                            : (policy.score || 0) >= 0.5
                            ? 'bg-orange-100'
                            : 'bg-green-100'
                        }`}
                      >
                        <TrendingUp
                          className={`w-6 h-6 ${
                            (policy.score || 0) >= 0.7
                              ? 'text-red-600'
                              : (policy.score || 0) >= 0.5
                              ? 'text-orange-600'
                              : 'text-green-600'
                          }`}
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900 truncate">{policy.client_name}</p>
                        <p className="text-sm text-gray-500">
                          {policy.policy_number} • {formatCurrency(policy.premium_at_risk)} • {policy.days_to_expiry} days
                        </p>
                      </div>
                      <Badge
                        variant={
                          (policy.score || 0) >= 0.7
                            ? 'danger'
                            : (policy.score || 0) >= 0.5
                            ? 'warning'
                            : 'success'
                        }
                      >
                        {getPriorityLabel(policy.score || 0)}
                      </Badge>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedPolicy(policy.id)}
                      >
                        <Eye className="w-4 h-4" />
                      </Button>
                    </div>
                  ))}
                  {renewals.length === 0 && (
                    <p className="text-center text-gray-500 py-8">
                      No renewals found. Connect your CRM to get started.
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Quick actions */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold text-gray-900">Quick Actions</h2>
            </CardHeader>
            <CardContent className="space-y-3">
              <Link href="/chat" className="block">
                <Button variant="secondary" className="w-full justify-start">
                  <MessageSquare className="w-4 h-4 mr-3" />
                  Ask Copilot
                </Button>
              </Link>
              <Link href="/renewals" className="block">
                <Button variant="secondary" className="w-full justify-start">
                  <FileText className="w-4 h-4 mr-3" />
                  View Pipeline
                </Button>
              </Link>
              <Link href="/connections" className="block">
                <Button variant="secondary" className="w-full justify-start">
                  <Shield className="w-4 h-4 mr-3" />
                  Manage Connections
                </Button>
              </Link>
            </CardContent>
          </Card>

          {/* Feature highlights */}
          <Card className="bg-gradient-to-br from-primary-50 to-blue-50 border-primary-200">
            <CardContent className="p-6">
              <Zap className="w-8 h-8 text-primary-600 mb-3" />
              <h3 className="font-semibold text-gray-900 mb-2">AI-Powered Insights</h3>
              <p className="text-sm text-gray-600 mb-4">
                Get instant one-page briefs, priority scoring, and answers to complex questions about your policies.
              </p>
              <ul className="text-sm text-gray-600 space-y-2">
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 bg-primary-500 rounded-full" />
                  Real-time data from CRM & Email
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 bg-primary-500 rounded-full" />
                  Source links for every fact
                </li>
                <li className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 bg-primary-500 rounded-full" />
                  Zero data storage
                </li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Brief modal */}
      {selectedPolicy && (
        <BriefModal
          policyId={selectedPolicy}
          onClose={() => setSelectedPolicy(null)}
        />
      )}
    </Layout>
  );
}
