'use client'

import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ModuleHeader } from '@/components/layout'
import { SnapshotContent } from '@/components/snapshot/SnapshotParts'

export default function SnapshotPage() {
  return (
    <div className="space-y-0">
      <ModuleHeader title="Journal de vie" subtitle="Snapshot quotidien multi-modules + score bien-être" />
      <div className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Journal de vie">
          <SnapshotContent />
        </ErrorBoundary>
      </div>
    </div>
  )
}
