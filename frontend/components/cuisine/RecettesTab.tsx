'use client'

/**
 * Onglet Recettes — liste réelle + éditeur de saisie manuelle.
 *
 * Branché sur le backend (lib/cuisine). La création capture des ingrédients
 * structurés (nom / quantité / unité), base de la future liste de courses.
 */

import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Clock, Users, Carrot, Plus, X, Trash2 } from 'lucide-react'
import {
  fetchRecipes,
  createRecipe,
  fetchAliments,
  type Recipe,
  type Ingredient,
  type Aliment,
} from '@/lib/cuisine'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'

const UNITES = ['g', 'kg', 'ml', 'cl', 'l', 'unité', 'c. à soupe', 'c. à café', 'pincée', 'gousse', 'tranche']

type Row = { nom_libre: string; quantite: string; unite: string; aliment_id: number | null }
const emptyRow = (): Row => ({ nom_libre: '', quantite: '', unite: 'g', aliment_id: null })

export default function RecettesTab() {
  const [recipes, setRecipes] = useState<Recipe[] | null>(null)
  const [error, setError] = useState(false)
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)
  const [aliments, setAliments] = useState<Aliment[]>([])

  async function load() {
    setError(false)
    try {
      setRecipes(await fetchRecipes())
    } catch {
      setError(true)
      setRecipes([])
    }
  }

  useEffect(() => {
    void load()
    fetchAliments()
      .then(setAliments)
      .catch(() => setAliments([]))
  }, [])

  const filtered = (recipes ?? []).filter((r) =>
    r.titre.toLowerCase().includes(search.toLowerCase()),
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <input
          type="text"
          placeholder="Rechercher une recette…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-sm rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
        />
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="flex shrink-0 items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          Nouvelle recette
        </button>
      </div>

      {recipes === null && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      )}

      {recipes !== null && filtered.length === 0 && (
        <EmptyState
          icon={<Carrot className="h-6 w-6" aria-hidden="true" />}
          title={error ? 'Recettes indisponibles' : search ? 'Aucune recette trouvée' : 'Aucune recette'}
          description={
            error
              ? 'Le backend Cuisine ne répond pas.'
              : 'Ajoute ta première recette avec ses ingrédients ; elle alimentera le plan et la liste de courses.'
          }
          action={
            !error && !search ? (
              <button
                type="button"
                onClick={() => setOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-[var(--primary-foreground)] hover:opacity-90"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                Nouvelle recette
              </button>
            ) : undefined
          }
        />
      )}

      {filtered.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {filtered.map((r) => (
            <div
              key={r.id}
              className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 transition-colors hover:border-[color-mix(in_srgb,var(--ring)_30%,var(--border))]"
            >
              <h3 className="font-display text-sm font-semibold">{r.titre}</h3>
              <div className="mt-2 flex flex-wrap gap-3 text-xs text-[var(--muted-foreground)]">
                <span className="flex items-center gap-1">
                  <Users size={12} /> {r.portions} pers.
                </span>
                <span className="flex items-center gap-1">
                  <Clock size={12} /> {r.temps_prep + r.temps_cuisson} min
                </span>
                <span className="flex items-center gap-1">
                  <Carrot size={12} /> {r.ingredient_count ?? 0} ingr.
                </span>
              </div>
              {(r.ingredient_count ?? 0) === 0 && (
                <p className="mt-2 text-xs text-[var(--warning-foreground)]">
                  Sans ingrédient : invisible pour la liste de courses.
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {open && (
        <RecipeForm
          aliments={aliments}
          onClose={() => setOpen(false)}
          onCreated={() => void load()}
        />
      )}
    </div>
  )
}

function RecipeForm({
  aliments,
  onClose,
  onCreated,
}: {
  aliments: Aliment[]
  onClose: () => void
  onCreated: () => void
}) {
  const [titre, setTitre] = useState('')
  const [portions, setPortions] = useState('4')
  const [prep, setPrep] = useState('')
  const [cuisson, setCuisson] = useState('')
  const [instructions, setInstructions] = useState('')
  const [rows, setRows] = useState<Row[]>([emptyRow(), emptyRow(), emptyRow()])
  const [saving, setSaving] = useState(false)
  const dialogRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  function setRow(i: number, patch: Partial<Row>) {
    setRows((prev) => prev.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  }

  async function submit() {
    if (!titre.trim()) {
      toast.error('Donne un titre à la recette.')
      return
    }
    const ingredients: Ingredient[] = rows
      .filter((r) => r.nom_libre.trim())
      .map((r) => ({
        nom_libre: r.nom_libre.trim(),
        quantite: Number(r.quantite.replace(',', '.')) || 0,
        unite: r.unite.trim(),
        aliment_id: r.aliment_id,
      }))
    setSaving(true)
    try {
      await createRecipe({
        titre: titre.trim(),
        portions: Number(portions) || 1,
        temps_prep: Number(prep) || 0,
        temps_cuisson: Number(cuisson) || 0,
        instructions: instructions.trim(),
        ingredients,
      })
      toast.success('Recette ajoutée.')
      onCreated()
      onClose()
    } catch {
      toast.error("Échec de l'enregistrement.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 pt-[6vh]">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="recipe-form-title"
        className="flex max-h-[88vh] w-full max-w-lg flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-[var(--shadow-lg)]"
      >
        <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
          <h2 id="recipe-form-title" className="font-display text-base font-semibold">
            Nouvelle recette
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fermer"
            className="rounded-[var(--radius-sm)] p-1 text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
          <Field label="Titre">
            <input
              value={titre}
              onChange={(e) => setTitre(e.target.value)}
              placeholder="Poulet rôti aux herbes"
              className={inputCls}
            />
          </Field>

          <div className="grid grid-cols-3 gap-3">
            <Field label="Portions">
              <input type="number" min={1} value={portions} onChange={(e) => setPortions(e.target.value)} className={inputCls} />
            </Field>
            <Field label="Prép. (min)">
              <input type="number" min={0} value={prep} onChange={(e) => setPrep(e.target.value)} className={inputCls} />
            </Field>
            <Field label="Cuisson (min)">
              <input type="number" min={0} value={cuisson} onChange={(e) => setCuisson(e.target.value)} className={inputCls} />
            </Field>
          </div>

          <div>
            <p className="mb-1.5 text-xs font-medium text-[var(--muted-foreground)]">Ingrédients</p>
            <div className="space-y-2">
              {rows.map((row, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span
                    className="h-2 w-2 shrink-0 rounded-full"
                    style={{ backgroundColor: row.aliment_id ? 'var(--success)' : 'var(--border)' }}
                    title={row.aliment_id ? 'Lié au catalogue : macros prises en compte' : 'Texte libre : courses seulement (pas de macros)'}
                    aria-hidden="true"
                  />
                  <input
                    value={row.nom_libre}
                    list="aliments-catalog"
                    onChange={(e) => {
                      const v = e.target.value
                      const match = aliments.find((a) => a.nom === v)
                      setRow(i, {
                        nom_libre: v,
                        aliment_id: match ? match.id : null,
                        ...(match ? { unite: 'g' } : {}),
                      })
                    }}
                    placeholder="Choisir un aliment ou texte libre"
                    className={`${inputCls} flex-1`}
                  />
                  <input
                    value={row.quantite}
                    onChange={(e) => setRow(i, { quantite: e.target.value })}
                    placeholder="200"
                    inputMode="decimal"
                    className={`${inputCls} w-16 tabular-nums`}
                  />
                  <input
                    value={row.unite}
                    onChange={(e) => setRow(i, { unite: e.target.value })}
                    list="unites"
                    className={`${inputCls} w-20`}
                  />
                  <button
                    type="button"
                    onClick={() => setRows((prev) => (prev.length > 1 ? prev.filter((_, j) => j !== i) : prev))}
                    aria-label="Retirer l'ingrédient"
                    className="shrink-0 rounded p-1.5 text-[var(--muted-foreground)] transition-colors hover:text-[var(--destructive)]"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              ))}
            </div>
            <datalist id="unites">
              {UNITES.map((u) => (
                <option key={u} value={u} />
              ))}
            </datalist>
            <datalist id="aliments-catalog">
              {aliments.map((a) => (
                <option key={a.id} value={a.nom} />
              ))}
            </datalist>
            <p className="mt-1.5 text-[11px] text-[var(--muted-foreground)]">
              Pastille verte = aliment du catalogue (macros comptées pour le plan) ; grise = texte libre (courses seulement).
            </p>
            <button
              type="button"
              onClick={() => setRows((prev) => [...prev, emptyRow()])}
              className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-[var(--nav-active-fg)] hover:underline"
            >
              <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Ajouter un ingrédient
            </button>
          </div>

          <Field label="Instructions (optionnel)">
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              rows={3}
              className={`${inputCls} resize-none`}
            />
          </Field>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[var(--border)] px-4 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm font-medium transition-colors hover:bg-[var(--muted)]"
          >
            Annuler
          </button>
          <button
            type="button"
            onClick={() => void submit()}
            disabled={saving}
            className="rounded-md bg-[var(--primary)] px-4 py-1.5 text-sm font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90 disabled:opacity-60"
          >
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </div>
      </div>
    </div>
  )
}

const inputCls =
  'w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]'

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">{label}</span>
      {children}
    </label>
  )
}
