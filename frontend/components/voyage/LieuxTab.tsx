'use client'

import { useLieuxVoyage, useSyncVoyage } from '@/lib/queries/voyage'
import { LieuxHeader, LieuxList, SyncWarning } from './LieuxParts'

export function LieuxTab({ selected, onToggle }: { selected: Set<number>; onToggle: (id: number) => void }) {
  const lieuxQ = useLieuxVoyage()
  const syncMut = useSyncVoyage()
  if (lieuxQ.isLoading) return <div className="p-2 text-[var(--muted-foreground)]">Chargement…</div>
  if (lieuxQ.isError || !lieuxQ.data) return <div className="p-2 text-[var(--destructive)]">⚠ Impossible de charger la liste.</div>
  const places = lieuxQ.data.filter((lieu) => !lieu.visite)
  return <div className="space-y-3"><LieuxHeader count={places.length} selected={selected.size} pending={syncMut.isPending} onSync={() => syncMut.mutate()} /><SyncWarning result={syncMut.data} /><LieuxList lieux={places} selected={selected} onToggle={onToggle} /></div>
}
