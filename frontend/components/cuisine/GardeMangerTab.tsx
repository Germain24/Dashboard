'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Package, Plus, Trash2, X, AlertTriangle, CheckCircle, Clock } from 'lucide-react'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import type { PantryItem } from '@/lib/cuisine'
import { useAddPantryItem, useDeletePantryItem, usePantry } from '@/lib/queries/cuisine'
import { useSanteAliments } from '@/lib/queries/sante'

const RAYONS = [
  'Fruits & légumes', 'Produits laitiers', 'Viandes & poissons', 'Épicerie sèche',
  'Conserves', 'Surgelés', 'Boissons', 'Boulangerie', 'Autre',
]

const STATUT_CONFIG = {
  expired: { label: 'Périmé', color: 'var(--destructive)', Icon: AlertTriangle },
  warning: { label: 'À consommer vite', color: 'var(--warning)', Icon: Clock },
  ok: { label: 'OK', color: 'var(--success)', Icon: CheckCircle },
  no_date: { label: '', color: 'var(--muted-foreground)', Icon: Package },
}

export default function GardeMangerTab() {
  const [open, setOpen] = useState(false)

  const pantryQ = usePantry()
  const items: PantryItem[] | null = pantryQ.isError ? [] : pantryQ.data ?? null
  const error = pantryQ.isError
  const deleteMutation = useDeletePantryItem()

  const handleDelete = (id: number) => {
    deleteMutation.mutate(id, {
      onSuccess: () => toast.success('Article retiré.'),
      onError: () => toast.error('Impossible de retirer cet article.'),
    })
  }

  const expired = (items ?? []).filter((i) => i.statut === 'expired')
  const warning = (items ?? []).filter((i) => i.statut === 'warning')
  const rest = (items ?? []).filter((i) => i.statut !== 'expired' && i.statut !== 'warning')
  const sorted = [...expired, ...warning, ...rest]

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-[var(--muted-foreground)]">
            {items === null ? '…' : `${items.length} article${items.length !== 1 ? 's' : ''}`}
            {expired.length > 0 && (
              <span className="ml-2 rounded-full bg-[color-mix(in_srgb,var(--destructive)_15%,transparent)] px-2 py-0.5 text-xs font-medium text-[var(--destructive)]">
                {expired.length} périmé{expired.length > 1 ? 's' : ''}
              </span>
            )}
            {warning.length > 0 && (
              <span className="ml-1 rounded-full bg-[color-mix(in_srgb,var(--warning)_15%,transparent)] px-2 py-0.5 text-xs font-medium text-[var(--warning-foreground)]">
                {warning.length} à consommer
              </span>
            )}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="flex shrink-0 items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          Ajouter
        </button>
      </div>

      {items === null && (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-14" />)}
        </div>
      )}

      {items !== null && sorted.length === 0 && (
        <EmptyState
          icon={<Package className="h-6 w-6" aria-hidden="true" />}
          title={error ? 'Garde-manger indisponible' : 'Garde-manger vide'}
          description={
            error
              ? 'Le backend Cuisine ne répond pas.'
              : 'Ajoute des ingrédients avec leur date de péremption pour suivre tes stocks.'
          }
          action={
            !error ? (
              <button
                type="button"
                onClick={() => setOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-[var(--primary-foreground)] hover:opacity-90"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                Ajouter un article
              </button>
            ) : undefined
          }
        />
      )}

      {sorted.length > 0 && (
        <div className="divide-y divide-[var(--border)] rounded-xl border border-[var(--border)] bg-[var(--card)]">
          {sorted.map((item) => {
            const cfg = STATUT_CONFIG[item.statut] ?? STATUT_CONFIG.no_date
            const Icon = cfg.Icon
            return (
              <div key={item.id} className="flex items-center gap-3 px-4 py-3">
                <Icon
                  className="h-4 w-4 shrink-0"
                  style={{ color: cfg.color }}
                  aria-hidden="true"
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{item.ingredient}</p>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {item.quantite} {item.unite}
                    {item.rayon && item.rayon !== 'Autre' && ` · ${item.rayon}`}
                    {item.date_peremption && (
                      <span style={{ color: cfg.color }} className="ml-1">
                        · exp. {item.date_peremption}
                        {cfg.label && ` (${cfg.label})`}
                      </span>
                    )}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void handleDelete(item.id)}
                  aria-label={`Retirer ${item.ingredient}`}
                  className="shrink-0 rounded p-1.5 text-[var(--muted-foreground)] transition-colors hover:text-[var(--destructive)]"
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            )
          })}
        </div>
      )}

      {open && (
        <AddPantryItemModal
          onClose={() => setOpen(false)}
          onAdded={() => setOpen(false)}
        />
      )}
    </div>
  )
}

function AddPantryItemModal({ onClose, onAdded }: { onClose: () => void; onAdded: () => void }) {
  const [ingredient, setIngredient] = useState('')
  const [quantite, setQuantite] = useState('')
  const [unite, setUnite] = useState('g')
  const [dateExp, setDateExp] = useState('')
  const [rayon, setRayon] = useState('Autre')
  const addMutation = useAddPantryItem()
  const saving = addMutation.isPending
  // Aliments du catalogue CIQUAL : choisir un nom connu permet de déduire
  // automatiquement le stock de la liste de courses (noms qui correspondent).
  const alimentsQ = useSanteAliments()
  const alimentNames = (alimentsQ.data ?? [])
    .map((a) => a.nom)
    .sort((a, b) => a.localeCompare(b, 'fr'))

  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const submit = () => {
    if (!ingredient.trim()) { toast.error("Nom d'ingredient requis."); return }
    addMutation.mutate(
      {
        ingredient: ingredient.trim(),
        quantite: Number(quantite.replace(',', '.')) || 1,
        unite: unite.trim(),
        date_peremption: dateExp || null,
        rayon,
      },
      {
        onSuccess: () => {
          toast.success(`${ingredient} ajouté au garde-manger.`)
          onAdded()
        },
        onError: () => toast.error("Échec de l'ajout."),
      },
    )
  }

  const inputCls = 'w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]'

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 pt-[10vh]">
      <div
        role="dialog" aria-modal="true" aria-labelledby="pantry-modal-title"
        className="w-full max-w-sm rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-[var(--shadow-lg)]"
      >
        <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
          <h2 id="pantry-modal-title" className="font-display text-base font-semibold">Ajouter au garde-manger</h2>
          <button type="button" onClick={onClose} aria-label="Fermer"
            className="rounded p-1 text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="space-y-3 px-4 py-4">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Ingrédient</span>
            <input value={ingredient} onChange={(e) => setIngredient(e.target.value)}
              list="pantry-aliments" placeholder="Choisir un aliment (CIQUAL)…" className={inputCls} />
            <datalist id="pantry-aliments">
              {alimentNames.map((n) => <option key={n} value={n} />)}
            </datalist>
            <span className="mt-1 block text-[10px] text-[var(--muted-foreground)]">
              Choisis un aliment du catalogue pour qu'il soit déduit de ta liste de courses.
            </span>
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Quantité</span>
              <input value={quantite} onChange={(e) => setQuantite(e.target.value)}
                inputMode="decimal" placeholder="1" className={inputCls} />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Unité</span>
              <input value={unite} onChange={(e) => setUnite(e.target.value)}
                list="pantry-unites" placeholder="g" className={inputCls} />
              <datalist id="pantry-unites">
                {['g', 'kg', 'ml', 'L', 'unité', 'boîte', 'sachet', 'bouteille'].map((u) => (
                  <option key={u} value={u} />
                ))}
              </datalist>
            </label>
          </div>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Date de péremption (optionnel)</span>
            <input type="date" value={dateExp} onChange={(e) => setDateExp(e.target.value)} className={inputCls} />
          </label>

          <label className="block">
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Rayon</span>
            <select value={rayon} onChange={(e) => setRayon(e.target.value)} className={inputCls}>
              {RAYONS.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </label>
        </div>

        <div className="flex justify-end gap-2 border-t border-[var(--border)] px-4 py-3">
          <button type="button" onClick={onClose}
            className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-[var(--muted)]">
            Annuler
          </button>
          <button type="button" onClick={() => void submit()} disabled={saving}
            className="rounded-md bg-[var(--primary)] px-4 py-1.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-60">
            {saving ? 'Ajout…' : 'Ajouter'}
          </button>
        </div>
      </div>
    </div>
  )
}
