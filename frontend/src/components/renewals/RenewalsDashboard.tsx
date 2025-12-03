'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Filter, SortAsc, RefreshCw, Search, List, LayoutGrid } from 'lucide-react';
import { Card, CardHeader, CardContent, Button, Select, Input, Badge } from '@/components/ui';
import { PolicyCard, PolicyCardSkeleton } from './PolicyCard';
import { getRenewals } from '@/lib/api';
import type { Policy, RenewalFilter } from '@/lib/types';
import { cn } from '@/lib/utils';

interface RenewalsDashboardProps {
  onViewBrief?: (policyId: string) => void;
}

export function RenewalsDashboard({ onViewBrief }: RenewalsDashboardProps) {
  const [renewals, setRenewals] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  
  const [filters, setFilters] = useState<RenewalFilter>({
    days_window: 90,
    sort_by: 'score',
  });
  
  const [searchQuery, setSearchQuery] = useState('');

  const fetchRenewals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getRenewals(filters);
      setRenewals(data.renewals);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch renewals');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchRenewals();
  }, [fetchRenewals]);

  const filteredRenewals = renewals.filter((policy) =>
    searchQuery
      ? policy.client_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        policy.policy_number.toLowerCase().includes(searchQuery.toLowerCase())
      : true
  );

  // Group renewals by priority for Kanban view
  const groupedRenewals = {
    critical: filteredRenewals.filter((p) => (p.score || 0) >= 0.7),
    high: filteredRenewals.filter((p) => (p.score || 0) >= 0.5 && (p.score || 0) < 0.7),
    medium: filteredRenewals.filter((p) => (p.score || 0) >= 0.3 && (p.score || 0) < 0.5),
    low: filteredRenewals.filter((p) => (p.score || 0) < 0.3),
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Renewals Pipeline</h1>
          <p className="text-gray-500">
            {filteredRenewals.length} policies requiring attention
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={fetchRenewals} disabled={loading}>
            <RefreshCw className={cn('w-4 h-4 mr-2', loading && 'animate-spin')} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="py-4">
          <div className="flex flex-col lg:flex-row gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  placeholder="Search by client or policy number..."
                  className="pl-10"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Select
                options={[
                  { value: '30', label: '30 days' },
                  { value: '60', label: '60 days' },
                  { value: '90', label: '90 days' },
                  { value: '180', label: '180 days' },
                ]}
                value={String(filters.days_window)}
                onChange={(e) =>
                  setFilters((f) => ({ ...f, days_window: Number(e.target.value) }))
                }
              />
              <Select
                options={[
                  { value: 'score', label: 'Sort by Priority' },
                  { value: 'expiry', label: 'Sort by Expiry' },
                  { value: 'premium', label: 'Sort by Premium' },
                ]}
                value={filters.sort_by}
                onChange={(e) =>
                  setFilters((f) => ({
                    ...f,
                    sort_by: e.target.value as RenewalFilter['sort_by'],
                  }))
                }
              />
              <div className="flex items-center border border-gray-300 rounded-lg overflow-hidden">
                <button
                  className={cn(
                    'p-2',
                    viewMode === 'grid'
                      ? 'bg-primary-50 text-primary-600'
                      : 'text-gray-500 hover:bg-gray-100'
                  )}
                  onClick={() => setViewMode('grid')}
                >
                  <LayoutGrid className="w-4 h-4" />
                </button>
                <button
                  className={cn(
                    'p-2',
                    viewMode === 'list'
                      ? 'bg-primary-50 text-primary-600'
                      : 'text-gray-500 hover:bg-gray-100'
                  )}
                  onClick={() => setViewMode('list')}
                >
                  <List className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Error state */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="py-4">
            <p className="text-red-700">{error}</p>
            <Button variant="secondary" size="sm" className="mt-2" onClick={fetchRenewals}>
              Try Again
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Loading state */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {[...Array(8)].map((_, i) => (
            <PolicyCardSkeleton key={i} />
          ))}
        </div>
      )}

      {/* Kanban / Grid view */}
      {!loading && !error && viewMode === 'grid' && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Critical */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-red-500 rounded-full" />
              <h2 className="font-semibold text-gray-900">Critical</h2>
              <Badge variant="danger">{groupedRenewals.critical.length}</Badge>
            </div>
            <div className="space-y-3">
              {groupedRenewals.critical.map((policy) => (
                <PolicyCard key={policy.id} policy={policy} onViewBrief={onViewBrief} />
              ))}
              {groupedRenewals.critical.length === 0 && (
                <p className="text-sm text-gray-500 text-center py-4">No critical renewals</p>
              )}
            </div>
          </div>

          {/* High */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-orange-500 rounded-full" />
              <h2 className="font-semibold text-gray-900">High</h2>
              <Badge variant="warning">{groupedRenewals.high.length}</Badge>
            </div>
            <div className="space-y-3">
              {groupedRenewals.high.map((policy) => (
                <PolicyCard key={policy.id} policy={policy} onViewBrief={onViewBrief} />
              ))}
              {groupedRenewals.high.length === 0 && (
                <p className="text-sm text-gray-500 text-center py-4">No high priority renewals</p>
              )}
            </div>
          </div>

          {/* Medium */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-yellow-500 rounded-full" />
              <h2 className="font-semibold text-gray-900">Medium</h2>
              <Badge>{groupedRenewals.medium.length}</Badge>
            </div>
            <div className="space-y-3">
              {groupedRenewals.medium.map((policy) => (
                <PolicyCard key={policy.id} policy={policy} onViewBrief={onViewBrief} />
              ))}
              {groupedRenewals.medium.length === 0 && (
                <p className="text-sm text-gray-500 text-center py-4">No medium priority renewals</p>
              )}
            </div>
          </div>

          {/* Low */}
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-green-500 rounded-full" />
              <h2 className="font-semibold text-gray-900">Low</h2>
              <Badge variant="success">{groupedRenewals.low.length}</Badge>
            </div>
            <div className="space-y-3">
              {groupedRenewals.low.map((policy) => (
                <PolicyCard key={policy.id} policy={policy} onViewBrief={onViewBrief} />
              ))}
              {groupedRenewals.low.length === 0 && (
                <p className="text-sm text-gray-500 text-center py-4">No low priority renewals</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* List view */}
      {!loading && !error && viewMode === 'list' && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredRenewals.map((policy) => (
            <PolicyCard key={policy.id} policy={policy} onViewBrief={onViewBrief} />
          ))}
          {filteredRenewals.length === 0 && (
            <Card className="col-span-full">
              <CardContent className="py-12 text-center">
                <p className="text-gray-500">No renewals match your filters</p>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
