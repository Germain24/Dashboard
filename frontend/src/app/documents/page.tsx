'use client'

import { useState } from 'react'
import { Calendar, FileText } from 'lucide-react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ModuleHeader } from '@/components/layout'
import DocumentsTab from '@/components/documents/DocumentsTab'
import EcheancesTab from '@/components/documents/EcheancesTab'

const TABS = [
  { id: 'documents', label: 'Documents', icon: FileText },
  { id: 'echeances', label: 'Échéances',  icon: Calendar },
] as const

type Tab = (typeof TABS)[number]['id']

export default function DocumentsPage() {
  const [tab, setTab] = useState<Tab>('documents')

  return (
    <div className="space-y-0 animate-fade-in">
      <ModuleHeader
        title="Documents"
        subtitle="Coffre-fort administratif"
        tabs={TABS.map((t) => ({ id: t.id, label: t.label, icon: t.icon }))}
        active={tab}
        onChange={(id) => setTab(id as Tab)}
      />

      <div className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Documents">
          {tab === 'documents' ? <DocumentsTab /> : <EcheancesTab />}
        </ErrorBoundary>
      </div>
    </div>
  )
}
