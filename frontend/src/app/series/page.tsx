'use client'

import { Tv } from 'lucide-react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import WatchlistSection from '@/components/films/WatchlistSection'

export default function SeriesPage() {
  return (
    <div className="space-y-0 animate-fade-in">
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <div className="flex items-center gap-2 mb-1">
          <Tv size={20} className="text-[var(--muted-foreground)]" />
          <h1 className="text-xl font-semibold tracking-tight">Séries</h1>
        </div>
        <p className="text-sm text-[var(--muted-foreground)]">Watchlist personnelle</p>
      </div>
      <div className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Séries">
          <WatchlistSection mediaType="serie" />
        </ErrorBoundary>
      </div>
    </div>
  )
}
