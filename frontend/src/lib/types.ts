/**
 * API Types for Broker Copilot
 */

// ============================================================================
// Renewal / Policy Types
// ============================================================================

export interface Policy {
  id: string;
  policy_number: string;
  client_name: string;
  premium_at_risk: number;
  expiry_date: string;
  days_to_expiry: number;
  claims_frequency: number;
  policy_type: string;
  assignee: string;
  link?: string;
  score?: number;
  score_breakdown?: ScoreBreakdown;
  priority_explanation?: string;
}

export interface ScoreBreakdown {
  premium_score: number;
  urgency_score: number;
  claims_score: number;
  weights: {
    premium: number;
    urgency: number;
    claims: number;
  };
}

export interface RenewalFilter {
  days_window: number;
  policy_type?: string;
  assignee?: string;
  sort_by: 'score' | 'expiry' | 'premium';
}

export interface RenewalsResponse {
  renewals: Policy[];
  total: number;
  filters_applied: RenewalFilter;
}

// ============================================================================
// Brief Types
// ============================================================================

export interface BriefData {
  policy_id: string;
  summary: string;
  key_facts: string[];
  risk_factors: string[];
  recommendations: string[];
  citations: Citation[];
  confidence: number;
}

export interface Citation {
  source: string;
  text: string;
  link?: string;
  timestamp?: string;
}

// ============================================================================
// Chat Types
// ============================================================================

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  citations?: Citation[];
  confidence?: number;
  function_calls?: FunctionCall[];
}

export interface FunctionCall {
  name: string;
  arguments: Record<string, unknown>;
  result?: unknown;
}

export interface ChatPayload {
  user_id: string;
  message: string;
  stream?: boolean;
}

export interface ChatResponse {
  response: string;
  citations: Citation[];
  confidence: number;
  function_calls_made: FunctionCall[];
}

// ============================================================================
// OAuth Types
// ============================================================================

export interface OAuthStartResponse {
  auth_url: string;
  state: string;
  provider: string;
}

export interface OAuthStatusResponse {
  authenticated: boolean;
  user_id?: string;
  user?: {
    id: string;
    display_name?: string;
    email?: string;
    job_title?: string;
  };
  token_info?: {
    expires_at: number;
    is_expired: boolean;
    scopes: string[];
  };
  needs_refresh?: boolean;
}

// ============================================================================
// Aggregate Types
// ============================================================================

export interface AggregateQuery {
  query: string;
  limit?: number;
}

export interface AggregateResponse {
  results: Record<string, Snippet[]>;
  failures: { source: string; error: string }[];
}

export interface Snippet {
  id: string;
  content: string;
  source: string;
  timestamp?: string;
  link?: string;
  metadata?: Record<string, unknown>;
}

// ============================================================================
// Template Types
// ============================================================================

export interface TemplatePayload {
  template: string;
  context: Record<string, unknown>;
}

export interface TemplateResponse {
  markdown: string;
  html: string;
}

// ============================================================================
// Score Types
// ============================================================================

export interface ScoreResponse {
  policy: Policy;
  score: number;
  breakdown: ScoreBreakdown;
  interpretation: string;
}

// ============================================================================
// Email Scheduling Types
// ============================================================================

export type EmailStatus = 'pending' | 'queued' | 'sending' | 'sent' | 'failed' | 'cancelled';
export type EmailPriority = 'low' | 'normal' | 'high' | 'urgent';
export type RecurrenceType = 'none' | 'daily' | 'weekly' | 'monthly' | 'custom';

export interface EmailRecipient {
  email: string;
  name?: string;
  type: 'to' | 'cc' | 'bcc';
  variables?: Record<string, unknown>;
}

export interface EmailAttachment {
  filename: string;
  content_type: string;
  size_bytes: number;
  storage_key?: string;
  inline: boolean;
}

export interface ScheduledEmail {
  id: string;
  subject: string;
  body_html?: string;
  body_text?: string;
  template_id?: string;
  template_variables?: Record<string, unknown>;
  from_email: string;
  from_name?: string;
  recipients: EmailRecipient[];
  reply_to?: string;
  attachments: EmailAttachment[];
  scheduled_at: string;
  timezone: string;
  recurrence: RecurrenceType;
  recurrence_end?: string;
  recurrence_count?: number;
  priority: EmailPriority;
  status: EmailStatus;
  policy_id?: string;
  user_id: string;
  campaign_id?: string;
  tags: string[];
  created_at: string;
  updated_at: string;
  sent_at?: string;
  error_message?: string;
  retry_count: number;
  max_retries: number;
  message_id?: string;
  open_count: number;
  click_count: number;
}

export interface EmailTemplate {
  id: string;
  name: string;
  description?: string;
  subject_template: string;
  body_html_template: string;
  body_text_template?: string;
  category: string;
  variables: string[];
  user_id?: string;
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

export interface ScheduleEmailRequest {
  subject: string;
  body_html?: string;
  body_text?: string;
  template_id?: string;
  template_variables?: Record<string, unknown>;
  recipients: EmailRecipient[];
  from_name?: string;
  reply_to?: string;
  scheduled_at: string;
  timezone?: string;
  recurrence?: RecurrenceType;
  recurrence_end?: string;
  priority?: EmailPriority;
  policy_id?: string;
  campaign_id?: string;
  tags?: string[];
}

export interface ScheduleEmailResponse {
  id: string;
  status: EmailStatus;
  scheduled_at: string;
  message: string;
}

export interface EmailListResponse {
  emails: ScheduledEmail[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface EmailStatsResponse {
  total_scheduled: number;
  total_sent: number;
  total_failed: number;
  total_pending: number;
  total_cancelled: number;
  open_rate: number;
  click_rate: number;
  period_start: string;
  period_end: string;
}
