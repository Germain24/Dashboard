'use client'

import { Check } from 'lucide-react'
import type { MealEntry, ShoppingItem } from '@/lib/cuisine'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'

export type ShoppingGroups = Record<string, ShoppingItem[]>

export function RestaurantCreditSummary({ meals, loading }: { meals: MealEntry[] | null; loading: boolean }) {
  if (loading) return <div className="rounded-lg border border-[var(--border)] bg-[var(--muted)] px-3 py-2 text-xs text-[var(--muted-foreground)]">Chargement des repas prévus au travail…</div>
  const entries = meals ?? []
  const subtotal = entries.reduce((sum, entry) => sum + (entry.restaurant?.price ?? 0), 0)
  return <section className="rounded-lg border border-[var(--success)]/30 bg-[var(--success-muted)] px-3 py-3" aria-label="Crédits repas Crew">
    <div className="flex flex-wrap items-baseline justify-between gap-2"><h3 className="text-sm font-semibold text-[var(--success-foreground)]">Crédits repas au travail</h3><span className="text-xs font-semibold tabular-nums text-[var(--success-foreground)]">{entries.length} repas · {subtotal.toFixed(2)} $ couverts</span></div>
    {entries.length > 0 ? <ul className="mt-2 space-y-1">{entries.map((entry) => <li key={entry.id} className="text-xs text-[var(--success-foreground)]">{['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'][entry.jour]} · {entry.restaurant?.name} · {entry.restaurant?.price.toFixed(2)} $ · ~{entry.restaurant?.calories} kcal / {entry.restaurant?.proteines} g protéines</li>)}</ul> : <p className="mt-1 text-xs text-[var(--muted-foreground)]">Aucun repas Crew associé au plan de cette période. Actualise le plan après avoir synchronisé tes shifts de travail.</p>}
    <p className="mt-2 text-[11px] text-[var(--muted-foreground)]">Les repas choisis sont retirés du plan maison et leurs ingrédients ne sont pas ajoutés aux courses. Crédit maximum : 30 $ par shift, avant taxes; le crédit inutilisé n’est pas compté.</p>
  </section>
}

export function ShoppingHeader({ mode, setMode, total, done }: { mode: 'cycle' | 'semaine'; setMode: (mode: 'cycle' | 'semaine') => void; total: number; done: number }) {
  return <div className="flex flex-wrap items-center justify-between gap-3"><div className="inline-flex rounded-md border border-[var(--border)] p-0.5">{(['cycle', 'semaine'] as const).map((value) => <button key={value} type="button" onClick={() => setMode(value)} className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${mode === value ? 'bg-[var(--muted)] text-[var(--foreground)]' : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)]'}`}>{value === 'cycle' ? 'Cycle de cuisine' : 'Semaine entière'}</button>)}</div>{total > 0 && <span className="text-xs tabular-nums text-[var(--muted-foreground)]">{done}/{total} pris</span>}</div>
}

const quantity = (item: ShoppingItem) => item.unite ? `${item.quantite} ${item.unite}` : `${item.quantite}`
const itemKey = (item: ShoppingItem) => item.ingredient + item.unite

function ShoppingItemRow({ item, checked, toggle }: { item: ShoppingItem; checked: boolean; toggle: (key: string) => void }) {
  return <button type="button" onClick={() => toggle(itemKey(item))} className="flex w-full items-center gap-3 border-b border-[var(--border)] px-3 py-2 text-left transition-colors last:border-0 hover:bg-[var(--muted)]"><span className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${checked ? 'border-[var(--ring)] bg-[var(--ring)] text-white' : 'border-[var(--border)]'}`}>{checked && <Check className="h-3 w-3" aria-hidden="true" />}</span><span className={`flex-1 text-sm ${checked ? 'text-[var(--muted-foreground)] line-through' : ''}`}>{item.ingredient}</span><span className="shrink-0 text-xs tabular-nums text-[var(--muted-foreground)]">{quantity(item)}</span><StoreBadge item={item} /></button>
}

function StoreBadge({ item }: { item: ShoppingItem }) {
  if (!item.magasin_recommande) return null
  return <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${item.promo ? 'bg-[var(--warning-bg,#fef3c7)] text-[var(--warning-fg,#92400e)]' : 'bg-[var(--muted)] text-[var(--muted-foreground)]'}`}>{item.magasin_recommande}{item.prix_estime != null ? ` · ${item.prix_estime.toFixed(2)}$` : ''}</span>
}

function ShoppingGroup({ rayon, items, checked, toggle }: { rayon: string; items: ShoppingItem[]; checked: Set<string>; toggle: (key: string) => void }) {
  return <div><h3 className="mb-1.5 text-xs font-medium text-[var(--muted-foreground)]">{rayon}</h3><div className="overflow-hidden rounded-lg border border-[var(--border)]">{items.map((item) => <ShoppingItemRow key={itemKey(item)} item={item} checked={checked.has(itemKey(item))} toggle={toggle} />)}</div></div>
}

export function ShoppingContent({ items, groups, checked, toggle }: { items: ShoppingItem[] | null; groups: ShoppingGroups; checked: Set<string>; toggle: (key: string) => void }) {
  if (items === null) return <Skeleton lines={6} />
  if (items.length === 0) return <EmptyState title="Rien à acheter" description="Génère d'abord un plan dans l'onglet Plan ; la liste se remplit avec les ingrédients de tes recettes." />
  return <div className="space-y-4">{Object.keys(groups).sort().map((rayon) => <ShoppingGroup key={rayon} rayon={rayon} items={groups[rayon]} checked={checked} toggle={toggle} />)}</div>
}
