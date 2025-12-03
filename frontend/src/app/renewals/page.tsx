'use client';

import React, { useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { RenewalsDashboard } from '@/components/renewals/RenewalsDashboard';
import { BriefModal } from '@/components/brief/BriefModal';

export default function RenewalsPage() {
  const [selectedPolicy, setSelectedPolicy] = useState<string | null>(null);

  return (
    <Layout>
      <RenewalsDashboard onViewBrief={(id) => setSelectedPolicy(id)} />
      
      {selectedPolicy && (
        <BriefModal
          policyId={selectedPolicy}
          onClose={() => setSelectedPolicy(null)}
        />
      )}
    </Layout>
  );
}
