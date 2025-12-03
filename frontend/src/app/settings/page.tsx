'use client';

import React from 'react';
import {
  User,
  Bell,
  Shield,
  Palette,
  Globe,
  Key,
  Save,
} from 'lucide-react';
import { Layout } from '@/components/layout/Layout';
import { Card, CardHeader, CardContent, Button, Input, Select } from '@/components/ui';

export default function SettingsPage() {
  return (
    <Layout>
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <p className="text-gray-500">Manage your account and application preferences</p>
        </div>

        {/* Profile section */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <User className="w-5 h-5 text-gray-500" />
              <h2 className="text-lg font-semibold text-gray-900">Profile</h2>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input label="Full Name" placeholder="John Doe" defaultValue="Demo User" />
              <Input label="Email" type="email" placeholder="john@company.com" defaultValue="demo@broker.com" />
              <Input label="Job Title" placeholder="Senior Broker" />
              <Input label="Company" placeholder="Insurance Co." />
            </div>
            <Button variant="primary" size="sm">
              <Save className="w-4 h-4 mr-2" />
              Save Changes
            </Button>
          </CardContent>
        </Card>

        {/* Notifications */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <Bell className="w-5 h-5 text-gray-500" />
              <h2 className="text-lg font-semibold text-gray-900">Notifications</h2>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between py-3 border-b border-gray-100">
              <div>
                <p className="font-medium text-gray-900">Email Notifications</p>
                <p className="text-sm text-gray-500">Receive email alerts for critical renewals</p>
              </div>
              <input type="checkbox" defaultChecked className="w-5 h-5 text-primary-600 rounded" />
            </div>
            <div className="flex items-center justify-between py-3 border-b border-gray-100">
              <div>
                <p className="font-medium text-gray-900">Daily Digest</p>
                <p className="text-sm text-gray-500">Get a daily summary of your pipeline</p>
              </div>
              <input type="checkbox" className="w-5 h-5 text-primary-600 rounded" />
            </div>
            <div className="flex items-center justify-between py-3">
              <div>
                <p className="font-medium text-gray-900">Browser Notifications</p>
                <p className="text-sm text-gray-500">Show desktop notifications</p>
              </div>
              <input type="checkbox" className="w-5 h-5 text-primary-600 rounded" />
            </div>
          </CardContent>
        </Card>

        {/* Appearance */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <Palette className="w-5 h-5 text-gray-500" />
              <h2 className="text-lg font-semibold text-gray-900">Appearance</h2>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <Select
              label="Theme"
              options={[
                { value: 'light', label: 'Light' },
                { value: 'dark', label: 'Dark' },
                { value: 'system', label: 'System' },
              ]}
              defaultValue="light"
            />
            <Select
              label="Default View"
              options={[
                { value: 'kanban', label: 'Kanban Board' },
                { value: 'list', label: 'List View' },
              ]}
              defaultValue="kanban"
            />
          </CardContent>
        </Card>

        {/* API Keys */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <Key className="w-5 h-5 text-gray-500" />
              <h2 className="text-lg font-semibold text-gray-900">API Configuration</h2>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              label="Gemini API Key"
              type="password"
              placeholder="Enter your Gemini API key"
            />
            <p className="text-sm text-gray-500">
              API keys are stored securely and never exposed in the frontend.
              Get your API key from{' '}
              <a
                href="https://aistudio.google.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary-600 hover:underline"
              >
                Google AI Studio
              </a>
              .
            </p>
          </CardContent>
        </Card>

        {/* Security */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <Shield className="w-5 h-5 text-gray-500" />
              <h2 className="text-lg font-semibold text-gray-900">Security</h2>
            </div>
          </CardHeader>
          <CardContent>
            <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
              <div className="flex items-start gap-3">
                <Shield className="w-5 h-5 text-green-600 mt-0.5" />
                <div>
                  <p className="font-medium text-green-800">Zero-Storage Architecture</p>
                  <p className="text-sm text-green-700 mt-1">
                    Broker Copilot never stores your business data. All information is fetched
                    in real-time from your connected sources and processed in memory only.
                    OAuth tokens are encrypted using industry-standard AES-256 encryption.
                  </p>
                </div>
              </div>
            </div>
            <div className="mt-4 space-y-3">
              <Button variant="secondary" size="sm">
                View Active Sessions
              </Button>
              <Button variant="danger" size="sm">
                Revoke All Connections
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
}
