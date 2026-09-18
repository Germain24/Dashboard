'use client'

/** Formulaire de création de recette (extrait de RecettesTab.tsx, #520). */

import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { z } from 'zod'
import type { Aliment, Ingredient, RecipeInput } from '@/lib/cuisine'
import { useCreateRecipe } from '@/lib/queries/cuisine'
import { useZodForm } from '@/lib/useZodForm'
import {
  RecipeFormFields,
  RecipeFormFooter,
  RecipeFormHeader,
  type RecipeFormModel,
  type RecipeFormRow,
} from './RecipeFormParts'

const recipeSchema = z.object({
  titre: z.string().min(1, 'Le titre est requis.').max(120),
  portions: z.number().int().min(1, 'Au moins 1 portion.'),
  temps_prep: z.number().int().min(0),
  temps_cuisson: z.number().int().min(0),
})

const emptyRow = (): RecipeFormRow => ({ nom_libre: '', quantite: '', unite: 'g', aliment_id: null })
type FormValues = RecipeFormModel['values']

const numberOr = (value: string, fallback: number) => Number(value) || fallback

function buildIngredients(rows: RecipeFormRow[]): Ingredient[] {
  return rows.filter((row) => row.nom_libre.trim()).map((row) => ({
    nom_libre: row.nom_libre.trim(),
    quantite: numberOr(row.quantite.replace(',', '.'), 0),
    unite: row.unite.trim(),
    aliment_id: row.aliment_id,
  }))
}

function parseRecipe(values: FormValues, rows: RecipeFormRow[], validate: (data: unknown) => unknown): RecipeInput | null {
  const parsed = validate({
    titre: values.titre.trim(),
    portions: numberOr(values.portions, 1),
    temps_prep: numberOr(values.prep, 0),
    temps_cuisson: numberOr(values.cuisson, 0),
  }) as { titre: string; portions: number; temps_prep: number; temps_cuisson: number } | null
  if (!parsed) return null
  return { ...parsed, instructions: values.instructions.trim(), ingredients: buildIngredients(rows) }
}

function useRecipeForm(onClose: () => void): RecipeFormModel & { submit: () => void; saving: boolean } {
  const [values, setValues] = useState<FormValues>({ titre: '', portions: '4', prep: '', cuisson: '', instructions: '' })
  const [rows, setRows] = useState<RecipeFormRow[]>([emptyRow(), emptyRow(), emptyRow()])
  const createMutation = useCreateRecipe()
  const { validate, fieldError, clearErrors } = useZodForm(recipeSchema)

  const update = useCallback((name: keyof FormValues, value: string) => {
    setValues((current) => ({ ...current, [name]: value }))
  }, [])
  const setRow = useCallback((index: number, patch: Partial<RecipeFormRow>) => {
    setRows((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, ...patch } : row))
  }, [])
  const addRow = useCallback(() => setRows((current) => [...current, emptyRow()]), [])
  const removeRow = useCallback((index: number) => setRows((current) => current.length > 1 ? current.filter((_, rowIndex) => rowIndex !== index) : current), [])
  const submit = useCallback(() => {
    const payload = parseRecipe(values, rows, validate)
    if (!payload) return
    createMutation.mutate(payload, {
      onSuccess: () => { toast.success('Recette ajoutée.'); onClose() },
      onError: () => toast.error("Échec de l'enregistrement."),
    })
  }, [createMutation, onClose, rows, validate, values])

  return { values, errors: { titre: fieldError('titre'), portions: fieldError('portions') }, rows, update, clearErrors, setRow, addRow, removeRow, submit, saving: createMutation.isPending }
}

export default function RecipeForm({ aliments, onClose }: { aliments: Aliment[]; onClose: () => void }) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const form = useRecipeForm(onClose)

  useEffect(() => {
    function onKey(event: KeyboardEvent) { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 pt-[6vh]">
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="recipe-form-title" className="flex max-h-[88vh] w-full max-w-lg flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-[var(--shadow-lg)]">
        <RecipeFormHeader onClose={onClose} />
        <RecipeFormFields form={form} aliments={aliments} />
        <RecipeFormFooter saving={form.saving} onClose={onClose} onSubmit={form.submit} />
      </div>
    </div>
  )
}
