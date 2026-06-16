'use client'

import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ModuleHeader } from '@/components/layout'
import WatchlistSection from '@/components/films/WatchlistSection'

export default function FilmPage() {
  return (
    <div className="space-y-0 animate-fade-in">
      <ModuleHeader title="Films" subtitle="Watchlist personnelle" />
      <div className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Films">
          <WatchlistSection mediaType="film" />
        </ErrorBoundary>
      </div>
    </div>
  )
}
