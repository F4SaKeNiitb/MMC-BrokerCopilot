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
