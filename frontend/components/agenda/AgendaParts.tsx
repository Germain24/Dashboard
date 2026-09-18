'use client'

import type { AgendaJour } from '@/lib/agenda'
import { EmptyState } from '@/components/ui/empty-state'

export function AgendaIndicators({ data }: { data: AgendaJour | null }) {
  if (!data) return null
  const urgent = data.taches_urgentes.length
  const slots = data.slots_libres.length
  return <div className="flex gap-2 text-xs"><CountBadge count={urgent} tone="urgent" /><CountBadge count={slots} tone="slot" /></div>
}

function CountBadge({ count, tone }: { count: number; tone: 'urgent' | 'slot' }) {
  if (count === 0) return null
  return tone === 'urgent' ? <UrgentBadge count={count} /> : <SlotBadge count={count} />
}

function UrgentBadge({ count }: { count: number }) {
  return <span className="rounded-[var(--radius-full)] bg-[color-mix(in_srgb,var(--destructive)_12%,transparent)] px-2.5 py-1 font-medium text-[var(--destructive)]">⚠ {count} urgente{count > 1 ? 's' : ''}</span>
}

function SlotBadge({ count }: { count: number }) {
  return <span className="rounded-[var(--radius-full)] bg-[color-mix(in_srgb,var(--success)_12%,transparent)] px-2.5 py-1 text-[var(--success)]">{count} slot{count > 1 ? 's' : ''} libre{count > 1 ? 's' : ''}</span>
}

export function AgendaError({ message }: { message: string | null }) {
  if (!message) return null
  return <div className="mb-4 rounded-xl border border-[var(--destructive)]/30 bg-[color-mix(in_srgb,var(--destructive)_8%,transparent)] px-4 py-3 text-sm text-[var(--destructive)]">Erreur : {message}</div>
}

export function AgendaLoading() {
  return <div className="space-y-3">{[1, 2, 3].map((id) => <div key={id} className="h-16 rounded-xl border border-[var(--border)] bg-[var(--card)] skeleton-shimmer" />)}</div>
}

export function AgendaTabContent({ tab, loading, data, onRender }: { tab: string; loading: boolean; data: AgendaJour | null; onRender: (tab: string) => React.ReactNode }) {
  if (tab === 'jour') {
    if (loading) return <AgendaLoading />
    if (data) return onRender(tab)
    return null
  }
  return onRender(tab)
}

export function AgendaUnavailable() {
  return <EmptyState title="Agenda indisponible" description="Les données du jour ne sont pas encore disponibles." />
}
