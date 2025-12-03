'use client';

import React, { useState, useEffect } from 'react';
import {
  Mail,
  Calendar,
  Clock,
  Send,
  Trash2,
  Eye,
  Plus,
  Filter,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2,
  ChevronRight,
} from 'lucide-react';
import { Layout } from '@/components/layout/Layout';
import { Card, CardHeader, CardContent, Button, Badge, Skeleton } from '@/components/ui';
import {
  getScheduledEmails,
  getEmailStats,
  getEmailTemplates,
  cancelScheduledEmail,
  sendEmailNow,
} from '@/lib/api';
import type { ScheduledEmail, EmailTemplate, EmailStatsResponse, EmailStatus } from '@/lib/types';
import { ScheduleEmailModal } from '@/components/email/ScheduleEmailModal';

const STATUS_COLORS: Record<EmailStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  queued: 'bg-blue-100 text-blue-800',
  sending: 'bg-blue-100 text-blue-800',
  sent: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-800',
};

const STATUS_ICONS: Record<EmailStatus, React.ReactNode> = {
  pending: <Clock className="w-3 h-3" />,
  queued: <Loader2 className="w-3 h-3 animate-spin" />,
  sending: <Send className="w-3 h-3" />,
  sent: <CheckCircle className="w-3 h-3" />,
  failed: <XCircle className="w-3 h-3" />,
  cancelled: <XCircle className="w-3 h-3" />,
};

export default function EmailPage() {
  const [emails, setEmails] = useState<ScheduledEmail[]>([]);
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [stats, setStats] = useState<EmailStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<EmailStatus | undefined>(undefined);
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // Mock user ID - in production this would come from auth context
  const userId = 'broker-001';

  const fetchData = async () => {
    try {
      setError(null);
      const [emailsRes, statsRes, templatesRes] = await Promise.all([
        getScheduledEmails(userId, statusFilter),
        getEmailStats(userId),
        getEmailTemplates(),
      ]);
      setEmails(emailsRes.emails);
      setStats(statsRes);
      setTemplates(templatesRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchData();
  }, [statusFilter]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  const handleCancel = async (emailId: string) => {
    try {
      await cancelScheduledEmail(emailId);
      fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel email');
    }
  };

  const handleSendNow = async (emailId: string) => {
    try {
      await sendEmailNow(emailId);
      fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send email');
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Email Scheduling</h1>
            <p className="text-sm text-gray-500 mt-1">
              Schedule and manage automated email communications
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleRefresh}
              disabled={refreshing}
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button size="sm" onClick={() => setShowScheduleModal(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Schedule Email
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
              <CardContent className="py-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-blue-500 rounded-lg">
                    <Mail className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-blue-900">{stats.total_scheduled}</p>
                    <p className="text-sm text-blue-700">Total Scheduled</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-gradient-to-br from-green-50 to-green-100 border-green-200">
              <CardContent className="py-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-green-500 rounded-lg">
                    <CheckCircle className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-green-900">{stats.total_sent}</p>
                    <p className="text-sm text-green-700">Sent</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-gradient-to-br from-yellow-50 to-yellow-100 border-yellow-200">
              <CardContent className="py-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-yellow-500 rounded-lg">
                    <Clock className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-yellow-900">{stats.total_pending}</p>
                    <p className="text-sm text-yellow-700">Pending</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-gradient-to-br from-red-50 to-red-100 border-red-200">
              <CardContent className="py-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-red-500 rounded-lg">
                    <XCircle className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-red-900">{stats.total_failed}</p>
                    <p className="text-sm text-red-700">Failed</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card className="bg-gradient-to-br from-gray-50 to-gray-100 border-gray-200">
              <CardContent className="py-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-gray-500 rounded-lg">
                    <XCircle className="w-5 h-5 text-white" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-gray-900">{stats.total_cancelled}</p>
                    <p className="text-sm text-gray-700">Cancelled</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Filter Bar */}
        <Card>
          <CardContent className="py-3">
            <div className="flex items-center gap-4">
              <Filter className="w-4 h-4 text-gray-500" />
              <span className="text-sm text-gray-600">Filter by status:</span>
              <div className="flex gap-2">
                <Button
                  variant={statusFilter === undefined ? 'primary' : 'ghost'}
                  size="sm"
                  onClick={() => setStatusFilter(undefined)}
                >
                  All
                </Button>
                {(['pending', 'sent', 'failed', 'cancelled'] as EmailStatus[]).map((status) => (
                  <Button
                    key={status}
                    variant={statusFilter === status ? 'primary' : 'ghost'}
                    size="sm"
                    onClick={() => setStatusFilter(status)}
                  >
                    {status.charAt(0).toUpperCase() + status.slice(1)}
                  </Button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Error Alert */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-500" />
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* Email List */}
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">Scheduled Emails</h2>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-4">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg">
                    <Skeleton className="w-10 h-10 rounded-full" />
                    <div className="flex-1 space-y-2">
                      <Skeleton className="h-4 w-3/4" />
                      <Skeleton className="h-3 w-1/2" />
                    </div>
                    <Skeleton className="h-8 w-20" />
                  </div>
                ))}
              </div>
            ) : emails.length === 0 ? (
              <div className="text-center py-12">
                <Mail className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">No scheduled emails found</p>
                <Button
                  variant="secondary"
                  size="sm"
                  className="mt-4"
                  onClick={() => setShowScheduleModal(true)}
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Schedule Your First Email
                </Button>
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {emails.map((email) => (
                  <div
                    key={email.id}
                    className="flex items-center gap-4 py-4 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex-shrink-0">
                      <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
                        <Mail className="w-5 h-5 text-primary-600" />
                      </div>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900 truncate">{email.subject}</p>
                      <p className="text-sm text-gray-500 truncate">
                        To: {email.recipients.map((r) => r.email).join(', ')}
                      </p>
                      <div className="flex items-center gap-2 mt-1">
                        <Calendar className="w-3 h-3 text-gray-400" />
                        <span className="text-xs text-gray-400">
                          {formatDate(email.scheduled_at)}
                        </span>
                        {email.policy_id && (
                          <>
                            <span className="text-gray-300">•</span>
                            <span className="text-xs text-primary-600">
                              Policy: {email.policy_id}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge className={STATUS_COLORS[email.status]}>
                        {STATUS_ICONS[email.status]}
                        <span className="ml-1 capitalize">{email.status}</span>
                      </Badge>
                      {email.status === 'pending' && (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleSendNow(email.id)}
                            title="Send Now"
                          >
                            <Send className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleCancel(email.id)}
                            title="Cancel"
                            className="text-red-500 hover:text-red-600"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </>
                      )}
                      <ChevronRight className="w-4 h-4 text-gray-400" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Templates Section */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <h2 className="text-lg font-semibold">Email Templates</h2>
            <Button variant="secondary" size="sm">
              <Plus className="w-4 h-4 mr-2" />
              Create Template
            </Button>
          </CardHeader>
          <CardContent>
            {templates.length === 0 ? (
              <p className="text-center text-gray-500 py-8">No templates available</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {templates.map((template) => (
                  <div
                    key={template.id}
                    className="border border-gray-200 rounded-lg p-4 hover:border-primary-300 hover:shadow-sm transition-all cursor-pointer"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="font-medium text-gray-900">{template.name}</h3>
                      {template.is_system && (
                        <Badge variant="info" className="text-xs">System</Badge>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 mb-3 line-clamp-2">
                      {template.description || 'No description'}
                    </p>
                    <div className="flex items-center justify-between">
                      <Badge variant="default" className="text-xs capitalize">
                        {template.category}
                      </Badge>
                      <Button variant="ghost" size="sm">
                        <Eye className="w-4 h-4 mr-1" />
                        Preview
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Schedule Email Modal */}
      {showScheduleModal && (
        <ScheduleEmailModal
          templates={templates}
          userId={userId}
          onClose={() => setShowScheduleModal(false)}
          onSuccess={() => {
            setShowScheduleModal(false);
            fetchData();
          }}
        />
      )}
    </Layout>
  );
}
