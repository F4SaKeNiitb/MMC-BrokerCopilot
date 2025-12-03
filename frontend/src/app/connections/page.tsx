'use client';

import React from 'react';
import { Layout } from '@/components/layout/Layout';
import { ConnectionsManager } from '@/components/connections/ConnectionsManager';

export default function ConnectionsPage() {
  return (
    <Layout>
      <ConnectionsManager />
    </Layout>
  );
}
