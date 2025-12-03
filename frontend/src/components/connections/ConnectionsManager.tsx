'use client';

import React, { useState, useEffect } from 'react';
import {
  Shield,
  Check,
  X,
  ExternalLink,
  Loader2,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';
import { Card, CardHeader, CardContent, Button, Badge } from '@/components/ui';
import {
  startOAuth,
  getOAuthStatus,
  startSalesforceOAuth,
  getSalesforceStatus,
  startHubSpotOAuth,
  getHubSpotStatus,
} from '@/lib/api';
import { cn } from '@/lib/utils';

interface Connection {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  checkStatus: (userId: string) => Promise<{ authenticated: boolean }>;
  startAuth: () => Promise<{ auth_url: string }>;
}

const connections: Connection[] = [
  {
    id: 'microsoft',
    name: 'Microsoft 365',
    description: 'Access emails, calendar, and Teams messages',
    icon: (
      <svg className="w-6 h-6" viewBox="0 0 23 23">
        <path fill="#f35325" d="M1 1h10v10H1z" />
        <path fill="#81bc06" d="M12 1h10v10H12z" />
        <path fill="#05a6f0" d="M1 12h10v10H1z" />
        <path fill="#ffba08" d="M12 12h10v10H12z" />
      </svg>
    ),
    color: 'bg-blue-50 border-blue-200',
    checkStatus: getOAuthStatus,
    startAuth: () => startOAuth('microsoft'),
  },
  {
    id: 'salesforce',
    name: 'Salesforce',
    description: 'Sync policies and client data from Salesforce CRM',
    icon: (
      <svg className="w-6 h-6" viewBox="0 0 24 24">
        <path
          fill="#00A1E0"
          d="M10.006 5.415a4.195 4.195 0 0 1 3.045-1.306c1.56 0 2.954.9 3.69 2.205a4.99 4.99 0 0 1 2.064-.444c2.724 0 4.932 2.263 4.932 5.056s-2.208 5.055-4.932 5.055a4.93 4.93 0 0 1-.885-.08 3.772 3.772 0 0 1-3.373 2.1c-.628 0-1.22-.157-1.74-.434a4.455 4.455 0 0 1-4.091 2.705c-2.159 0-3.97-1.545-4.38-3.597a4.077 4.077 0 0 1-.63.049c-2.27 0-4.11-1.89-4.11-4.223 0-1.6.875-2.994 2.163-3.716a4.584 4.584 0 0 1-.36-1.79c0-2.478 1.964-4.487 4.387-4.487 1.236 0 2.355.52 3.15 1.357z"
        />
      </svg>
    ),
    color: 'bg-cyan-50 border-cyan-200',
    checkStatus: getSalesforceStatus,
    startAuth: startSalesforceOAuth,
  },
  {
    id: 'hubspot',
    name: 'HubSpot',
    description: 'Sync contacts and deals from HubSpot CRM',
    icon: (
      <svg className="w-6 h-6" viewBox="0 0 24 24">
        <path
          fill="#FF7A59"
          d="M18.164 7.93V5.084a2.198 2.198 0 0 0 1.267-1.984v-.066A2.198 2.198 0 0 0 17.233.836h-.066a2.198 2.198 0 0 0-2.198 2.198v.066c0 .867.503 1.617 1.232 1.974v2.862a5.085 5.085 0 0 0-2.348 1.178l-6.234-4.853a2.521 2.521 0 0 0 .073-.546 2.52 2.52 0 1 0-2.52 2.52c.387 0 .752-.091 1.08-.248l6.132 4.772a5.085 5.085 0 0 0-.426 2.034 5.1 5.1 0 0 0 5.1 5.1 5.08 5.08 0 0 0 2.832-.86l2.156 2.156a1.622 1.622 0 0 0-.122.614 1.63 1.63 0 1 0 1.63-1.63c-.218 0-.424.044-.615.122l-2.15-2.15a5.07 5.07 0 0 0 .869-2.852 5.1 5.1 0 0 0-3.552-4.863zM17.2 15.5a2.7 2.7 0 1 1 0-5.4 2.7 2.7 0 0 1 0 5.4z"
        />
      </svg>
    ),
    color: 'bg-orange-50 border-orange-200',
    checkStatus: getHubSpotStatus,
    startAuth: startHubSpotOAuth,
  },
];

interface ConnectionsManagerProps {
  userId?: string;
}

export function ConnectionsManager({ userId = 'demo-user' }: ConnectionsManagerProps) {
  const [statuses, setStatuses] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  const checkAllStatuses = async () => {
    for (const conn of connections) {
      setLoading((prev) => ({ ...prev, [conn.id]: true }));
      try {
        const status = await conn.checkStatus(userId);
        setStatuses((prev) => ({ ...prev, [conn.id]: status.authenticated }));
        setErrors((prev) => ({ ...prev, [conn.id]: '' }));
      } catch (err) {
        setErrors((prev) => ({
          ...prev,
          [conn.id]: err instanceof Error ? err.message : 'Failed to check status',
        }));
      } finally {
        setLoading((prev) => ({ ...prev, [conn.id]: false }));
      }
    }
  };

  useEffect(() => {
    checkAllStatuses();
  }, [userId]);

  const handleConnect = async (connection: Connection) => {
    setLoading((prev) => ({ ...prev, [connection.id]: true }));
    setErrors((prev) => ({ ...prev, [connection.id]: '' }));

    try {
      const { auth_url } = await connection.startAuth();
      // Open OAuth flow in new window
      window.open(auth_url, '_blank', 'width=600,height=700');
    } catch (err) {
      setErrors((prev) => ({
        ...prev,
        [connection.id]: err instanceof Error ? err.message : 'Failed to start authentication',
      }));
    } finally {
      setLoading((prev) => ({ ...prev, [connection.id]: false }));
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Connections</h1>
          <p className="text-gray-500">
            Connect your data sources to enable AI-powered insights
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={checkAllStatuses}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh Status
        </Button>
      </div>

      {/* Connection cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {connections.map((conn) => (
          <Card
            key={conn.id}
            className={cn(
              'border-2 transition-all',
              statuses[conn.id] ? conn.color : 'border-gray-200'
            )}
          >
            <CardContent className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div className="p-3 bg-white rounded-lg shadow-sm border">
                  {conn.icon}
                </div>
                {statuses[conn.id] ? (
                  <Badge variant="success">
                    <Check className="w-3 h-3 mr-1" />
                    Connected
                  </Badge>
                ) : (
                  <Badge>
                    <X className="w-3 h-3 mr-1" />
                    Not Connected
                  </Badge>
                )}
              </div>

              <h3 className="font-semibold text-gray-900 mb-1">{conn.name}</h3>
              <p className="text-sm text-gray-500 mb-4">{conn.description}</p>

              {errors[conn.id] && (
                <div className="mb-4 p-2 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-sm text-red-600 flex items-center gap-1">
                    <AlertCircle className="w-4 h-4" />
                    {errors[conn.id]}
                  </p>
                </div>
              )}

              {statuses[conn.id] ? (
                <Button variant="secondary" size="sm" className="w-full">
                  <Shield className="w-4 h-4 mr-2" />
                  Manage Connection
                </Button>
              ) : (
                <Button
                  variant="primary"
                  size="sm"
                  className="w-full"
                  onClick={() => handleConnect(conn)}
                  disabled={loading[conn.id]}
                >
                  {loading[conn.id] ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <ExternalLink className="w-4 h-4 mr-2" />
                  )}
                  Connect
                </Button>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Info section */}
      <Card className="bg-blue-50 border-blue-200">
        <CardContent className="p-6">
          <div className="flex gap-4">
            <div className="flex-shrink-0">
              <Shield className="w-8 h-8 text-blue-600" />
            </div>
            <div>
              <h3 className="font-semibold text-blue-900 mb-1">
                Zero-Storage Architecture
              </h3>
              <p className="text-sm text-blue-700">
                Broker Copilot uses a connector-driven architecture that fetches data
                in real-time from your connected sources. We never store your business
                data - it's retrieved live and processed in memory only. All OAuth
                tokens are encrypted and stored securely.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
