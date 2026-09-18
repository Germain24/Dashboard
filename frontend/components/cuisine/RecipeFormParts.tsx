'use client'

import { Plus, Trash2, X } from 'lucide-react'
import type { Aliment } from '@/lib/cuisine'

export type RecipeFormRow = {
  nom_libre: string
  quantite: string
  unite: string
  aliment_id: number | null
}

export const RECIPE_UNITS = ['g', 'kg', 'ml', 'cl', 'l', 'unité', 'c. à soupe', 'c. à café', 'pincée', 'gousse', 'tranche']
export const recipeInputCls =
  'w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]'

export function RecipeField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">{label}</span>
      {children}
    </label>
  )
}

export function RecipeFormHeader({ onClose }: { onClose: () => void }) {
  return (
    <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
      <h2 id="recipe-form-title" className="font-display text-base font-semibold">Nouvelle recette</h2>
      <button type="button" onClick={onClose} aria-label="Fermer" className="rounded-[var(--radius-sm)] p-1 text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]">
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  )
}

function CatalogInput({ row, index, aliments, setRow }: {
  row: RecipeFormRow
  index: number
  aliments: Aliment[]
  setRow: (index: number, patch: Partial<RecipeFormRow>) => void
}) {
  function update(value: string) {
    const match = aliments.find((aliment) => aliment.nom === value)
    setRow(index, { nom_libre: value, aliment_id: match?.id ?? null, ...(match ? { unite: 'g' } : {}) })
  }

  return <input value={row.nom_libre} list="aliments-catalog" onChange={(event) => update(event.target.value)} placeholder="Choisir un aliment ou texte libre" className={`${recipeInputCls} flex-1`} />
}

function IngredientRow({ row, index, aliments, setRow, removeRow }: {
  row: RecipeFormRow
  index: number
  aliments: Aliment[]
  setRow: (index: number, patch: Partial<RecipeFormRow>) => void
  removeRow: (index: number) => void
}) {
  const linked = Boolean(row.aliment_id)
  return (
    <div className="flex items-center gap-2">
      <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: linked ? 'var(--success)' : 'var(--border)' }} title={linked ? 'Lié au catalogue : macros prises en compte' : 'Texte libre : courses seulement (pas de macros)'} aria-hidden="true" />
      <CatalogInput row={row} index={index} aliments={aliments} setRow={setRow} />
      <input value={row.quantite} onChange={(event) => setRow(index, { quantite: event.target.value })} placeholder="200" inputMode="decimal" className={`${recipeInputCls} w-16 tabular-nums`} />
      <input value={row.unite} onChange={(event) => setRow(index, { unite: event.target.value })} list="unites" className={`${recipeInputCls} w-20`} />
      <button type="button" onClick={() => removeRow(index)} aria-label="Retirer l'ingrédient" className="shrink-0 rounded p-1.5 text-[var(--muted-foreground)] transition-colors hover:text-[var(--destructive)]">
        <Trash2 className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  )
}

export function IngredientEditor({ rows, aliments, setRow, addRow, removeRow }: {
  rows: RecipeFormRow[]
  aliments: Aliment[]
  setRow: (index: number, patch: Partial<RecipeFormRow>) => void
  addRow: () => void
  removeRow: (index: number) => void
}) {
  return (
    <div>
      <p className="mb-1.5 text-xs font-medium text-[var(--muted-foreground)]">Ingrédients</p>
      <div className="space-y-2">{rows.map((row, index) => <IngredientRow key={index} row={row} index={index} aliments={aliments} setRow={setRow} removeRow={removeRow} />)}</div>
      <datalist id="unites">{RECIPE_UNITS.map((unit) => <option key={unit} value={unit} />)}</datalist>
      <datalist id="aliments-catalog">{aliments.map((aliment) => <option key={aliment.id} value={aliment.nom} />)}</datalist>
      <p className="mt-1.5 text-[11px] text-[var(--muted-foreground)]">Pastille verte = aliment du catalogue (macros comptées pour le plan) ; grise = texte libre (courses seulement).</p>
      <button type="button" onClick={addRow} className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-[var(--nav-active-fg)] hover:underline">
        <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Ajouter un ingrédient
      </button>
    </div>
  )
}

export function RecipeFormFields({ form, aliments }: { form: RecipeFormModel; aliments: Aliment[] }) {
  const { values, errors, update, clearErrors } = form
  return (
    <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
      <RecipeBasics values={values} errors={errors} update={update} clearErrors={clearErrors} />
      <IngredientEditor rows={form.rows} aliments={aliments} setRow={form.setRow} addRow={form.addRow} removeRow={form.removeRow} />
      <RecipeField label="Instructions (optionnel)"><textarea value={values.instructions} onChange={(event) => update('instructions', event.target.value)} rows={3} className={`${recipeInputCls} resize-none`} /></RecipeField>
    </div>
  )
}

function RecipeBasics({ values, errors, update, clearErrors }: { values: RecipeFormModel['values']; errors: RecipeFormModel['errors']; update: RecipeFormModel['update']; clearErrors: () => void }) {
  return <><RecipeField label="Titre"><input value={values.titre} onChange={(event) => { update('titre', event.target.value); clearErrors() }} placeholder="Poulet rôti aux herbes" className={recipeInputCls} aria-invalid={hasError(errors.titre)} /><ErrorText message={errors.titre} /></RecipeField><div className="grid grid-cols-3 gap-3"><RecipeField label="Portions"><input type="number" min={1} value={values.portions} onChange={(event) => { update('portions', event.target.value); clearErrors() }} className={recipeInputCls} aria-invalid={hasError(errors.portions)} /><ErrorText message={errors.portions} /></RecipeField><RecipeField label="Prép. (min)"><input type="number" min={0} value={values.prep} onChange={(event) => update('prep', event.target.value)} className={recipeInputCls} /></RecipeField><RecipeField label="Cuisson (min)"><input type="number" min={0} value={values.cuisson} onChange={(event) => update('cuisson', event.target.value)} className={recipeInputCls} /></RecipeField></div></>
}

const hasError = (message?: string) => Boolean(message)

function ErrorText({ message }: { message?: string }) {
  if (!message) return null
  return <p className="mt-1 text-xs text-[var(--destructive)]">{message}</p>
}

export function RecipeFormFooter({ saving, onClose, onSubmit }: { saving: boolean; onClose: () => void; onSubmit: () => void }) {
  return <div className="flex items-center justify-end gap-2 border-t border-[var(--border)] px-4 py-3"><button type="button" onClick={onClose} className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm font-medium transition-colors hover:bg-[var(--muted)]">Annuler</button><button type="button" onClick={onSubmit} disabled={saving} className="rounded-md bg-[var(--primary)] px-4 py-1.5 text-sm font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90 disabled:opacity-60">{saving ? 'Enregistrement…' : 'Enregistrer'}</button></div>
}

export type RecipeFormModel = {
  values: { titre: string; portions: string; prep: string; cuisson: string; instructions: string }
  errors: Record<string, string | undefined>
  rows: RecipeFormRow[]
  update: (name: 'titre' | 'portions' | 'prep' | 'cuisson' | 'instructions', value: string) => void
  clearErrors: () => void
  setRow: (index: number, patch: Partial<RecipeFormRow>) => void
  addRow: () => void
  removeRow: (index: number) => void
}
