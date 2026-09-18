'use client'

import { LockKeyhole, RefreshCw } from 'lucide-react'
import type { LieuVoyage, SyncVoyageResult } from '@/lib/voyage'

function LieuDetails({ lieu }: { lieu: LieuVoyage }) {
  return <><span className="flex-1">{lieu.nom}</span><span className="text-[var(--muted-foreground)]">{lieu.ville ?? lieu.pays ?? ''}</span><LieuProgress lieu={lieu} /><LieuLock lieu={lieu} /><LieuStatus lieu={lieu} /></>
}

function LieuProgress({ lieu }: { lieu: LieuVoyage }) {
  if (!lieu.ordre) return null
  return <span className="rounded-full border border-[var(--border)] px-2 py-0.5 text-xs">{lieu.progression ?? 'progression'} · palier {lieu.ordre}</span>
}

function LieuLock({ lieu }: { lieu: LieuVoyage }) {
  if (!lieu.verrouille) return null
  return <span className="flex items-center gap-1 text-xs text-[var(--muted-foreground)]" title={lieu.raison_verrouillage ?? 'Verrouillé'}><LockKeyhole className="h-3.5 w-3.5" /> verrouillé</span>
}

function LieuStatus({ lieu }: { lieu: LieuVoyage }) {
  return <>{lieu.statut === 'impossible' && <span className="text-xs text-[var(--destructive)]">impossible</span>}{!lieu.complet && <span className="text-xs text-[var(--destructive)]">incomplet</span>}</>
}

function LieuRow({ lieu, selected, onToggle }: { lieu: LieuVoyage; selected: boolean; onToggle: (id: number) => void }) {
  const enabled = lieu.complet && !lieu.verrouille
  return <label className={`flex items-center gap-3 rounded-lg border border-[var(--border)] p-2 text-sm ${enabled ? 'cursor-pointer transition-colors hover:bg-[var(--muted)]' : 'opacity-50'}`}><input type="checkbox" disabled={!enabled} checked={selected} onChange={() => onToggle(lieu.id)} /><LieuDetails lieu={lieu} /></label>
}

export function LieuxHeader({ count, selected, pending, onSync }: { count: number; selected: number; pending: boolean; onSync: () => void }) {
  return <div className="flex items-center justify-between"><div className="text-sm text-[var(--muted-foreground)]">{count} lieux à visiter · {selected} sélectionné(s) pour la planification</div><button onClick={onSync} disabled={pending} className="flex items-center gap-2 rounded border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--muted)] disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${pending ? 'animate-spin' : ''}`} />Re-synchroniser l&apos;Excel</button></div>
}

export function SyncWarning({ result }: { result?: SyncVoyageResult }) {
  if (!result || result.incomplets.length === 0) return null
  return <div className="rounded-lg border border-[var(--destructive)] bg-[var(--destructive)]/10 px-3 py-2 text-sm text-[var(--destructive)]">⚠ {result.incomplets.length} lieu(x) incomplet(s) (aéroport ou jours manquants) : {result.incomplets.join(', ')}</div>
}

export function LieuxList({ lieux, selected, onToggle }: { lieux: LieuVoyage[]; selected: Set<number>; onToggle: (id: number) => void }) {
  return <div className="space-y-1">{lieux.map((lieu) => <LieuRow key={lieu.id} lieu={lieu} selected={selected.has(lieu.id)} onToggle={onToggle} />)}</div>
}
