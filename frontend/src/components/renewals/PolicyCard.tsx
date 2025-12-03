'use client';

import React from 'react';
import Link from 'next/link';
import {
  AlertCircle,
  ArrowRight,
  Calendar,
  DollarSign,
  ExternalLink,
  TrendingUp,
} from 'lucide-react';
import { Card, CardContent, Badge, Button, Skeleton, Tooltip } from '@/components/ui';
import { cn, formatCurrency, formatDate, getPriorityColor, getPriorityLabel } from '@/lib/utils';
import type { Policy } from '@/lib/types';

interface PolicyCardProps {
  policy: Policy;
  onViewBrief?: (policyId: string) => void;
}

export function PolicyCard({ policy, onViewBrief }: PolicyCardProps) {
  const priorityColor = getPriorityColor(policy.score || 0);
  const priorityLabel = getPriorityLabel(policy.score || 0);

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="font-semibold text-gray-900">{policy.client_name}</h3>
            <p className="text-sm text-gray-500">{policy.policy_number}</p>
          </div>
          <Badge
            variant={
              policy.score! >= 0.7
                ? 'danger'
                : policy.score! >= 0.5
                ? 'warning'
                : 'success'
            }
          >
            {priorityLabel}
          </Badge>
        </div>

        <div className="space-y-2 mb-4">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500 flex items-center gap-1">
              <DollarSign className="w-4 h-4" />
              Premium at Risk
            </span>
            <span className="font-medium text-gray-900">
              {formatCurrency(policy.premium_at_risk)}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500 flex items-center gap-1">
              <Calendar className="w-4 h-4" />
              Expiry Date
            </span>
            <span className="font-medium text-gray-900">
              {formatDate(policy.expiry_date)}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500 flex items-center gap-1">
              <AlertCircle className="w-4 h-4" />
              Days to Expiry
            </span>
            <span
              className={cn(
                'font-medium',
                policy.days_to_expiry <= 30
                  ? 'text-red-600'
                  : policy.days_to_expiry <= 60
                  ? 'text-orange-600'
                  : 'text-gray-900'
              )}
            >
              {policy.days_to_expiry} days
            </span>
          </div>
        </div>

        {/* Score breakdown */}
        {policy.score_breakdown && (
          <div className="mb-4 p-3 bg-gray-50 rounded-lg">
            <p className="text-xs font-medium text-gray-700 mb-2">Priority Score: {Math.round((policy.score || 0) * 100)}%</p>
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500">Premium</span>
                <div className="w-24 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full"
                    style={{ width: `${policy.score_breakdown.premium_score * 100}%` }}
                  />
                </div>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500">Urgency</span>
                <div className="w-24 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-orange-500 rounded-full"
                    style={{ width: `${policy.score_breakdown.urgency_score * 100}%` }}
                  />
                </div>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500">Claims</span>
                <div className="w-24 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-red-500 rounded-full"
                    style={{ width: `${policy.score_breakdown.claims_score * 100}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {policy.priority_explanation && (
          <p className="text-sm text-gray-600 mb-4">{policy.priority_explanation}</p>
        )}

        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            size="sm"
            className="flex-1"
            onClick={() => onViewBrief?.(policy.id)}
          >
            View Brief
            <ArrowRight className="w-4 h-4 ml-1" />
          </Button>
          {policy.link && (
            <Tooltip content="Open in CRM">
              <a
                href={policy.link}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
              >
                <ExternalLink className="w-4 h-4" />
              </a>
            </Tooltip>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function PolicyCardSkeleton() {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div>
            <Skeleton className="h-5 w-32 mb-1" />
            <Skeleton className="h-4 w-20" />
          </div>
          <Skeleton className="h-5 w-16 rounded-full" />
        </div>
        <div className="space-y-2 mb-4">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
        </div>
        <Skeleton className="h-9 w-full rounded-lg" />
      </CardContent>
    </Card>
  );
}
