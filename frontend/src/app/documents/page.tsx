'use client'

import { useState } from 'react'
import { FolderOpen, Calendar, FileText } from 'lucide-react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
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
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <div className="flex items-center gap-2 mb-1">
          <FolderOpen size={20} className="text-[var(--muted-foreground)]" />
          <h1 className="text-xl font-semibold tracking-tight">Documents</h1>
        </div>
        <p className="text-sm text-[var(--muted-foreground)]">Coffre-fort administratif</p>
      </div>

      <div className="px-6 pt-4 flex gap-1 border-b border-[var(--border)]">
        {TABS.map(t => {
          const Icon = t.icon
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
                tab === t.id
                  ? 'border-[var(--primary)] text-[var(--foreground)]'
                  : 'border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
              }`}
            >
              <Icon size={15} />
              {t.label}
            </button>
          )
        })}
      </div>

      <div className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Documents">
          {tab === 'documents' ? <DocumentsTab /> : <EcheancesTab />}
        </ErrorBoundary>
      </div>
    </div>
  )
}
