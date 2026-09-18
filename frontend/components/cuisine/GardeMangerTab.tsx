'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Package, Plus, Trash2, Pencil, X, AlertTriangle, CheckCircle, Clock } from 'lucide-react'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import type { PantryItem } from '@/lib/cuisine'
import { useAddPantryItem, useDeletePantryItem, usePantry, useUpdatePantryItem } from '@/lib/queries/cuisine'
import { useSanteAliments } from '@/lib/queries/sante'

const RAYONS = [
  'Fruits & légumes', 'Produits laitiers', 'Viandes & poissons', 'Épicerie sèche',
  'Conserves', 'Surgelés', 'Boissons', 'Boulangerie', 'Compléments', 'Autre',
]

const STATUT_CONFIG = {
  expired: { label: 'Périmé', color: 'var(--destructive)', Icon: AlertTriangle },
  warning: { label: 'À consommer vite', color: 'var(--warning)', Icon: Clock },
  ok: { label: 'OK', color: 'var(--success)', Icon: CheckCircle },
  no_date: { label: '', color: 'var(--muted-foreground)', Icon: Package },
  best_before_passed: { label: 'Meilleur avant dépassé', color: 'var(--muted-foreground)', Icon: Package },
  best_before_soon: { label: 'Meilleur avant bientôt', color: 'var(--muted-foreground)', Icon: Clock },
}

function pantryItems(data: PantryItem[] | undefined, isError: boolean): PantryItem[] | null {
  return isError ? [] : data ?? null;
}

function pantryGroups(items: PantryItem[]) {
  const expired = items.filter((item) => item.statut === 'expired');
  const warning = items.filter((item) => item.statut === 'warning');
  const rest = items.filter((item) => item.statut !== 'expired' && item.statut !== 'warning');
  return { expired, warning, sorted: [...expired, ...warning, ...rest] };
}

function PantryCounts({ items, expired, warning }: { items: PantryItem[] | null; expired: PantryItem[]; warning: PantryItem[] }) {
  return <p className="text-sm text-[var(--muted-foreground)]">{items === null ? '…' : `${items.length} article${items.length !== 1 ? 's' : ''}`}<ExpiredCount count={expired.length} /><WarningCount count={warning.length} /></p>;
}

function ExpiredCount({ count }: { count: number }) {
  if (count === 0) return null;
  return <span className="ml-2 rounded-full bg-[color-mix(in_srgb,var(--destructive)_15%,transparent)] px-2 py-0.5 text-xs font-medium text-[var(--destructive)]">{count} périmé{count > 1 ? 's' : ''}</span>;
}

function WarningCount({ count }: { count: number }) {
  if (count === 0) return null;
  return <span className="ml-1 rounded-full bg-[color-mix(in_srgb,var(--warning)_15%,transparent)] px-2 py-0.5 text-xs font-medium text-[var(--warning-foreground)]">{count} à consommer</span>;
}

function PantryEmpty({ error, onAdd }: { error: boolean; onAdd: () => void }) {
  return <EmptyState icon={<Package className="h-6 w-6" aria-hidden="true" />} title={error ? 'Garde-manger indisponible' : 'Garde-manger vide'} description={error ? 'Le backend Cuisine ne répond pas.' : 'Ajoute des ingrédients avec leur date de péremption pour suivre tes stocks.'} action={!error ? <button type="button" onClick={onAdd} className="inline-flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-[var(--primary-foreground)] hover:opacity-90"><Plus className="h-3.5 w-3.5" aria-hidden="true" /> Ajouter un article</button> : undefined} />;
}

function PantryRow({ item, onEdit, onDelete }: { item: PantryItem; onEdit: (item: PantryItem) => void; onDelete: (id: number) => void }) {
  const config = STATUT_CONFIG[item.statut] ?? STATUT_CONFIG.no_date;
  const Icon = config.Icon;
  return <div className="flex items-center gap-3 px-4 py-3"><Icon className="h-4 w-4 shrink-0" style={{ color: config.color }} aria-hidden="true" /><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{item.ingredient}</p><p className="text-xs text-[var(--muted-foreground)]">{item.quantite} {item.unite}<PantryAisle item={item} /><PantryExpiry item={item} config={config} /></p><PantrySource item={item} /><PantryNutrition item={item} /></div><button type="button" onClick={() => onEdit(item)} aria-label={`Modifier ${item.ingredient}`} className="shrink-0 rounded p-1.5 text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"><Pencil className="h-4 w-4" aria-hidden="true" /></button><button type="button" onClick={() => onDelete(item.id)} aria-label={`Retirer ${item.ingredient}`} className="shrink-0 rounded p-1.5 text-[var(--muted-foreground)] transition-colors hover:text-[var(--destructive)]"><Trash2 className="h-4 w-4" aria-hidden="true" /></button></div>;
}

function PantrySource({ item }: { item: PantryItem }) {
  const source = item.source_produit && item.source_produit !== item.ingredient ? item.source_produit : null;
  const ciqual = item.ciqual_nom ? `CIQUAL · ${item.ciqual_nom}` : null;
  const unmatched = item.type_aliment === 'non_mappe' ? 'Équivalent CIQUAL à confirmer' : null;
  const details = [source, item.marque, ciqual, unmatched].filter(Boolean).join(' · ');
  if (!details && !item.source_url) return null;
  return <p className="truncate text-xs text-[var(--muted-foreground)]">{details}{details && item.source_url ? ' · ' : ''}{item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer" className="underline underline-offset-2">Source produit</a>}</p>;
}

function PantryNutrition({ item }: { item: PantryItem }) {
  const label = item.nutrition_label;
  if (!label) return null;
  return <details className="mt-1 text-xs text-[var(--muted-foreground)]">
    <summary className="w-fit cursor-pointer underline underline-offset-2">Étiquette nutritionnelle · par {label.serving_size}</summary>
    <div className="mt-1 space-y-1 pl-2">
      <p>{label.values.map((entry) => `${entry.nutrient} ${entry.value} ${entry.unit}`).join(' · ')}</p>
      <p>{label.source_label}{label.source_updated ? ` · mise à jour ${label.source_updated}` : ''}</p>
      {label.note && <p>{label.note}</p>}
      <a href={label.source_url} target="_blank" rel="noreferrer" className="inline-block underline underline-offset-2">Voir la source</a>
    </div>
  </details>;
}

function PantryAisle({ item }: { item: PantryItem }) {
  return item.rayon && item.rayon !== 'Autre' ? <> · {item.rayon}</> : null;
}

function PantryExpiry({ item, config }: { item: PantryItem; config: (typeof STATUT_CONFIG)[keyof typeof STATUT_CONFIG] }) {
  if (!item.date_peremption) return null;
  const label = item.statut.startsWith('best_before_') ? 'meilleur avant' : 'date limite';
  return <span style={{ color: config.color }} className="ml-1">· {label} {item.date_peremption}{config.label && ` (${config.label})`}</span>;
}

function PantryContent({ items, sorted, error, onAdd, onEdit, onDelete }: { items: PantryItem[] | null; sorted: PantryItem[]; error: boolean; onAdd: () => void; onEdit: (item: PantryItem) => void; onDelete: (id: number) => void }) {
  if (items === null) return <div className="space-y-2">{[0, 1, 2].map((index) => <Skeleton key={index} className="h-14" />)}</div>;
  if (sorted.length === 0) return <PantryEmpty error={error} onAdd={onAdd} />;
  return <div className="divide-y divide-[var(--border)] rounded-xl border border-[var(--border)] bg-[var(--card)]">{sorted.map((item) => <PantryRow key={item.id} item={item} onEdit={onEdit} onDelete={onDelete} />)}</div>;
}

function PantryOverlay({ open, item, onClose }: { open: boolean; item: PantryItem | null; onClose: () => void }) {
  if (!open) return null;
  return <PantryItemModal key={item?.id ?? 'new'} item={item} onClose={onClose} onSaved={onClose} />;
}

export default function GardeMangerTab() {
  const [open, setOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<PantryItem | null>(null)
  const pantryQ = usePantry()
  const items = pantryItems(pantryQ.data, pantryQ.isError)
  const groups = pantryGroups(items ?? [])
  const deleteMutation = useDeletePantryItem()
  const handleDelete = (id: number) => deleteMutation.mutate(id, {
    onSuccess: () => toast.success('Article retiré.'),
    onError: () => toast.error('Impossible de retirer cet article.'),
  })
  const openModal = (item: PantryItem | null = null) => { setEditingItem(item); setOpen(true) }
  const closeModal = () => { setOpen(false); setEditingItem(null) }
  return <div className="space-y-4">
    <div className="flex items-center justify-between"><PantryCounts items={items} expired={groups.expired} warning={groups.warning} /><button type="button" onClick={() => openModal()} className="flex shrink-0 items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90"><Plus className="h-4 w-4" aria-hidden="true" /> Ajouter</button></div>
    <PantryContent items={items} sorted={groups.sorted} error={pantryQ.isError} onAdd={() => openModal()} onEdit={(item) => openModal(item)} onDelete={handleDelete} />
    <PantryOverlay open={open} item={editingItem} onClose={closeModal} />
  </div>
}

function PantryItemModal({ item, onClose, onSaved }: { item: PantryItem | null; onClose: () => void; onSaved: () => void }) {
  const [ingredient, setIngredient] = useState(item?.ingredient ?? '')
  const [quantite, setQuantite] = useState(item ? String(item.quantite) : '')
  const [unite, setUnite] = useState(item?.unite ?? 'g')
  const [dateExp, setDateExp] = useState(item?.date_peremption ?? '')
  const [rayon, setRayon] = useState(item?.rayon ?? 'Autre')
  const addMutation = useAddPantryItem()
  const updateMutation = useUpdatePantryItem()
  const saving = addMutation.isPending || updateMutation.isPending
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
    const amount = Number(quantite.replace(',', '.'))
    if (!Number.isFinite(amount) || amount <= 0) { toast.error('La quantité doit être supérieure à zéro.'); return }
    if (!unite.trim()) { toast.error('Unité requise.'); return }
    const payload = {
      ingredient: ingredient.trim(),
      quantite: amount,
      unite: unite.trim(),
      date_peremption: dateExp || null,
      rayon,
    }
    const callbacks = {
      onSuccess: () => {
        toast.success(item ? `${ingredient} modifié dans le garde-manger.` : `${ingredient} ajouté au garde-manger.`)
        onSaved()
      },
      onError: () => toast.error(item ? 'Échec de la modification.' : "Échec de l'ajout."),
    }
    if (item) updateMutation.mutate({ id: item.id, patch: payload }, callbacks)
    else addMutation.mutate(payload, callbacks)
  }

  const inputCls = 'w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]'

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 pt-[10vh]">
      <div
        role="dialog" aria-modal="true" aria-labelledby="pantry-modal-title"
        className="w-full max-w-sm rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-[var(--shadow-lg)]"
      >
        <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
          <h2 id="pantry-modal-title" className="font-display text-base font-semibold">{item ? 'Modifier un article' : 'Ajouter au garde-manger'}</h2>
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
            <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Date sur l’emballage (optionnel)</span>
            <input type="date" value={dateExp} onChange={(e) => setDateExp(e.target.value)} className={inputCls} />
            <span className="mt-1 block text-[10px] text-[var(--muted-foreground)]">Pour l’épicerie sèche et les conserves, la date est traitée comme « meilleur avant » (qualité).</span>
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
            {saving ? 'Enregistrement…' : item ? 'Enregistrer' : 'Ajouter'}
          </button>
        </div>
      </div>
    </div>
  )
}
