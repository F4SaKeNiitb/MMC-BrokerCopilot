/**
 * API Client for Broker Copilot Backend
 * 
 * All API calls go through the Next.js rewrite proxy (/api -> backend)
 * This keeps the backend URL configuration in one place.
 */

import type {
  RenewalFilter,
  RenewalsResponse,
  ChatPayload,
  ChatResponse,
  OAuthStartResponse,
  OAuthStatusResponse,
  AggregateQuery,
  AggregateResponse,
  TemplatePayload,
  TemplateResponse,
  ScoreResponse,
} from './types';

const API_BASE = '/api';

class APIError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'APIError';
  }
}

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new APIError(response.status, error.detail || error.message || 'Request failed');
  }

  return response.json();
}

// ============================================================================
// Health Check
// ============================================================================

export async function checkHealth(): Promise<{ status: string }> {
  return fetchJSON(`${API_BASE}/health`);
}

// ============================================================================
// Renewals API
// ============================================================================

export async function getRenewals(filters: RenewalFilter): Promise<RenewalsResponse> {
  return fetchJSON(`${API_BASE}/renewals`, {
    method: 'POST',
    body: JSON.stringify(filters),
  });
}

export async function getScore(policyId: string): Promise<ScoreResponse> {
  return fetchJSON(`${API_BASE}/score/${encodeURIComponent(policyId)}`);
}

// ============================================================================
// Brief API (with streaming support)
// ============================================================================

export async function getBrief(policyId: string): Promise<string> {
  const response = await fetch(`${API_BASE}/brief/${encodeURIComponent(policyId)}?stream=true`);
  
  if (!response.ok) {
    throw new APIError(response.status, 'Failed to fetch brief');
  }

  return response.text();
}

export async function* streamBrief(policyId: string): AsyncGenerator<string, void, unknown> {
  const response = await fetch(`${API_BASE}/brief/${encodeURIComponent(policyId)}?stream=true`);
  
  if (!response.ok) {
    throw new APIError(response.status, 'Failed to fetch brief');
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  const decoder = new TextDecoder();
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    yield decoder.decode(value, { stream: true });
  }
}

// ============================================================================
// Chat API (with streaming support)
// ============================================================================

export async function sendChat(payload: ChatPayload): Promise<ChatResponse> {
  return fetchJSON(`${API_BASE}/chat`, {
    method: 'POST',
    body: JSON.stringify({ ...payload, stream: false }),
  });
}

export async function* streamChat(payload: ChatPayload): AsyncGenerator<string, void, unknown> {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, stream: true }),
  });

  if (!response.ok) {
    throw new APIError(response.status, 'Failed to send message');
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  const decoder = new TextDecoder();
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    yield decoder.decode(value, { stream: true });
  }
}

// ============================================================================
// Aggregate API
// ============================================================================

export async function aggregate(query: AggregateQuery): Promise<AggregateResponse> {
  return fetchJSON(`${API_BASE}/aggregate`, {
    method: 'POST',
    body: JSON.stringify(query),
  });
}

// ============================================================================
// Template API
// ============================================================================

export async function renderTemplate(payload: TemplatePayload): Promise<TemplateResponse> {
  return fetchJSON(`${API_BASE}/render-template`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// ============================================================================
// OAuth API
// ============================================================================

export async function startOAuth(provider: string = 'microsoft'): Promise<OAuthStartResponse> {
  return fetchJSON(`${API_BASE}/oauth/start`, {
    method: 'POST',
    body: JSON.stringify({ provider }),
  });
}

export async function getOAuthStatus(userId: string): Promise<OAuthStatusResponse> {
  return fetchJSON(`${API_BASE}/oauth/status?user_id=${encodeURIComponent(userId)}`);
}

export async function refreshOAuth(userId: string): Promise<{ status: string }> {
  return fetchJSON(`${API_BASE}/oauth/refresh?user_id=${encodeURIComponent(userId)}`);
}

export async function logout(userId: string): Promise<{ status: string }> {
  return fetchJSON(`${API_BASE}/oauth/logout?user_id=${encodeURIComponent(userId)}`, {
    method: 'POST',
  });
}

// Salesforce OAuth
export async function startSalesforceOAuth(): Promise<OAuthStartResponse> {
  return fetchJSON(`${API_BASE}/oauth/salesforce/start`, { method: 'POST' });
}

export async function getSalesforceStatus(userId: string): Promise<OAuthStatusResponse> {
  return fetchJSON(`${API_BASE}/oauth/salesforce/status?user_id=${encodeURIComponent(userId)}`);
}

// HubSpot OAuth
export async function startHubSpotOAuth(): Promise<OAuthStartResponse> {
  return fetchJSON(`${API_BASE}/oauth/hubspot/start`, { method: 'POST' });
}

export async function getHubSpotStatus(userId: string): Promise<OAuthStatusResponse> {
  return fetchJSON(`${API_BASE}/oauth/hubspot/status?user_id=${encodeURIComponent(userId)}`);
}

// ============================================================================
// Export API Error class
// ============================================================================

export { APIError };
