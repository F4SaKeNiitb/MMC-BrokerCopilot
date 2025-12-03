'use client';

import React, { useState } from 'react';
import {
  X,
  Mail,
  Calendar,
  Clock,
  User,
  FileText,
  Send,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { Card, CardHeader, CardContent, Button, Badge } from '@/components/ui';
import { scheduleEmail, previewEmailTemplate } from '@/lib/api';
import type { EmailTemplate, ScheduleEmailRequest, EmailRecipient, EmailPriority, RecurrenceType } from '@/lib/types';

interface ScheduleEmailModalProps {
  templates: EmailTemplate[];
  userId: string;
  policyId?: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function ScheduleEmailModal({
  templates,
  userId,
  policyId,
  onClose,
  onSuccess,
}: ScheduleEmailModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);

  // Form state
  const [useTemplate, setUseTemplate] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const [templateVars, setTemplateVars] = useState<Record<string, string>>({});
  const [subject, setSubject] = useState('');
  const [bodyHtml, setBodyHtml] = useState('');
  const [recipients, setRecipients] = useState<string>('');
  const [fromName, setFromName] = useState('');
  const [fromEmail, setFromEmail] = useState('broker@company.com');
  const [scheduledDate, setScheduledDate] = useState('');
  const [scheduledTime, setScheduledTime] = useState('09:00');
  const [priority, setPriority] = useState<EmailPriority>('normal');
  const [recurrence, setRecurrence] = useState<RecurrenceType>('none');

  const selectedTemplateData = templates.find((t) => t.id === selectedTemplate);

  const handleTemplateChange = async (templateId: string) => {
    setSelectedTemplate(templateId);
    setPreviewHtml(null);
    setError(null);

    if (templateId) {
      const template = templates.find((t) => t.id === templateId);
      if (template) {
        // Initialize template variables
        const vars: Record<string, string> = {};
        template.variables.forEach((v) => {
          vars[v] = '';
        });
        setTemplateVars(vars);
      }
    }
  };

  const handlePreview = async () => {
    if (!selectedTemplate) return;

    try {
      const result = await previewEmailTemplate(selectedTemplate, templateVars);
      setPreviewHtml(result.body_html);
      setSubject(result.subject);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to preview template');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Parse recipients
      const recipientList: EmailRecipient[] = recipients
        .split(',')
        .map((email) => email.trim())
        .filter((email) => email)
        .map((email) => ({
          email,
          type: 'to' as const,
        }));

      if (recipientList.length === 0) {
        throw new Error('At least one recipient is required');
      }

      // Combine date and time
      const scheduledAt = new Date(`${scheduledDate}T${scheduledTime}:00`);
      if (scheduledAt <= new Date()) {
        throw new Error('Scheduled time must be in the future');
      }

      const request: ScheduleEmailRequest = {
        subject: useTemplate ? '' : subject,
        body_html: useTemplate ? undefined : bodyHtml,
        template_id: useTemplate ? selectedTemplate : undefined,
        template_variables: useTemplate ? templateVars : undefined,
        recipients: recipientList,
        from_name: fromName || undefined,
        scheduled_at: scheduledAt.toISOString(),
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        priority,
        recurrence,
        policy_id: policyId,
      };

      await scheduleEmail(request, userId, fromEmail);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to schedule email');
    } finally {
      setLoading(false);
    }
  };

  // Set default date to tomorrow
  React.useEffect(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    setScheduledDate(tomorrow.toISOString().split('T')[0]);
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <Card className="relative w-full max-w-2xl max-h-[90vh] flex flex-col animate-slide-up overflow-hidden">
        <CardHeader className="flex flex-row items-center justify-between sticky top-0 bg-white z-10 border-b">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary-100 rounded-lg">
              <Mail className="w-5 h-5 text-primary-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Schedule Email</h2>
              <p className="text-sm text-gray-500">Set up an automated email</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </CardHeader>

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto">
          <CardContent className="space-y-6 py-6">
            {/* Error Alert */}
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-500" />
                <p className="text-sm text-red-700">{error}</p>
              </div>
            )}

            {/* Template vs Custom Toggle */}
            <div className="flex gap-2">
              <Button
                type="button"
                variant={useTemplate ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => setUseTemplate(true)}
              >
                <FileText className="w-4 h-4 mr-2" />
                Use Template
              </Button>
              <Button
                type="button"
                variant={!useTemplate ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => setUseTemplate(false)}
              >
                <Mail className="w-4 h-4 mr-2" />
                Custom Email
              </Button>
            </div>

            {useTemplate ? (
              <>
                {/* Template Selection */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Email Template
                  </label>
                  <select
                    value={selectedTemplate}
                    onChange={(e) => handleTemplateChange(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    required
                  >
                    <option value="">Select a template...</option>
                    {templates.map((template) => (
                      <option key={template.id} value={template.id}>
                        {template.name} ({template.category})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Template Variables */}
                {selectedTemplateData && selectedTemplateData.variables.length > 0 && (
                  <div className="space-y-3">
                    <label className="block text-sm font-medium text-gray-700">
                      Template Variables
                    </label>
                    <div className="grid grid-cols-2 gap-3">
                      {selectedTemplateData.variables.map((variable) => (
                        <div key={variable}>
                          <label className="block text-xs text-gray-500 mb-1">
                            {variable.replace(/_/g, ' ')}
                          </label>
                          <input
                            type="text"
                            value={templateVars[variable] || ''}
                            onChange={(e) =>
                              setTemplateVars((prev) => ({
                                ...prev,
                                [variable]: e.target.value,
                              }))
                            }
                            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                            placeholder={`Enter ${variable.replace(/_/g, ' ')}`}
                          />
                        </div>
                      ))}
                    </div>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={handlePreview}
                    >
                      Preview Template
                    </Button>
                  </div>
                )}

                {/* Template Preview */}
                {previewHtml && (
                  <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                    <p className="text-sm font-medium text-gray-700 mb-2">Preview:</p>
                    <div
                      className="prose prose-sm max-w-none bg-white p-4 rounded border"
                      dangerouslySetInnerHTML={{ __html: previewHtml }}
                    />
                  </div>
                )}
              </>
            ) : (
              <>
                {/* Custom Subject */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Subject
                  </label>
                  <input
                    type="text"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    placeholder="Enter email subject"
                    required={!useTemplate}
                  />
                </div>

                {/* Custom Body */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Email Body (HTML)
                  </label>
                  <textarea
                    value={bodyHtml}
                    onChange={(e) => setBodyHtml(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 h-32 font-mono text-sm"
                    placeholder="Enter email body (HTML supported)"
                    required={!useTemplate}
                  />
                </div>
              </>
            )}

            {/* Recipients */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                <User className="w-4 h-4 inline mr-1" />
                Recipients
              </label>
              <input
                type="text"
                value={recipients}
                onChange={(e) => setRecipients(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                placeholder="Enter email addresses (comma-separated)"
                required
              />
              <p className="text-xs text-gray-500 mt-1">
                Separate multiple emails with commas
              </p>
            </div>

            {/* From Name */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  From Name
                </label>
                <input
                  type="text"
                  value={fromName}
                  onChange={(e) => setFromName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="Your Name"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  From Email
                </label>
                <input
                  type="email"
                  value={fromEmail}
                  onChange={(e) => setFromEmail(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="your@email.com"
                  required
                />
              </div>
            </div>

            {/* Schedule Date/Time */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <Calendar className="w-4 h-4 inline mr-1" />
                  Send Date
                </label>
                <input
                  type="date"
                  value={scheduledDate}
                  onChange={(e) => setScheduledDate(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <Clock className="w-4 h-4 inline mr-1" />
                  Send Time
                </label>
                <input
                  type="time"
                  value={scheduledTime}
                  onChange={(e) => setScheduledTime(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  required
                />
              </div>
            </div>

            {/* Priority & Recurrence */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Priority
                </label>
                <select
                  value={priority}
                  onChange={(e) => setPriority(e.target.value as EmailPriority)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                >
                  <option value="low">Low</option>
                  <option value="normal">Normal</option>
                  <option value="high">High</option>
                  <option value="urgent">Urgent</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Recurrence
                </label>
                <select
                  value={recurrence}
                  onChange={(e) => setRecurrence(e.target.value as RecurrenceType)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                >
                  <option value="none">One-time</option>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>
            </div>

            {/* Policy Link */}
            {policyId && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                <p className="text-sm text-blue-700">
                  This email will be linked to policy: <strong>{policyId}</strong>
                </p>
              </div>
            )}
          </CardContent>

          {/* Footer */}
          <div className="sticky bottom-0 bg-gray-50 border-t px-6 py-4 flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Scheduling...
                </>
              ) : (
                <>
                  <Send className="w-4 h-4 mr-2" />
                  Schedule Email
                </>
              )}
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
