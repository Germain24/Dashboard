'use client'

/**
 * Onglet Recettes — liste + filtres + favoris (#520 : migré TanStack Query,
 * formulaire et fiche détail extraits dans RecipeForm / RecipeDetailModal).
 */

import { useState } from 'react'
import { toast } from 'sonner'
import { Clock, Users, Carrot, Plus, Star } from 'lucide-react'
import { useAliments, useCuisineFavorites, useRecipes, useToggleFavorite } from '@/lib/queries/cuisine'
import RecipeForm from './RecipeForm'
import RecipeDetailModal from './RecipeDetailModal'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'

export default function RecettesTab() {
  const [search, setSearch] = useState('')
  const [ingredient, setIngredient] = useState('')
  const [favOnly, setFavOnly] = useState(false)
  const [open, setOpen] = useState(false)
  const [detailId, setDetailId] = useState<number | null>(null)

  const recipesQ = useRecipes(undefined, ingredient.trim() || undefined)
  const recipes = recipesQ.isError ? [] : recipesQ.data ?? null
  const error = recipesQ.isError
  const aliments = useAliments().data ?? []
  const favorites = useCuisineFavorites().data?.favorites ?? []
  const toggleFavMutation = useToggleFavorite()

  const handleToggleFav = (e: React.MouseEvent, id: number) => {
    e.stopPropagation()
    toggleFavMutation.mutate(id, {
      onError: () => toast.error('Impossible de modifier les favoris.'),
    })
  }

  const filtered = (recipes ?? [])
    .filter((r) => r.titre.toLowerCase().includes(search.toLowerCase()))
    .filter((r) => !favOnly || favorites.includes(r.id))

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-1 flex-wrap items-center gap-2">
          <input
            type="text"
            placeholder="Rechercher une recette…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="min-w-[12rem] flex-1 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          />
          <input
            type="text"
            placeholder="Filtrer par ingrédient…"
            value={ingredient}
            onChange={(e) => setIngredient(e.target.value)}
            list="aliments-catalog"
            className="min-w-[12rem] flex-1 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
          />
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={() => setFavOnly((v) => !v)}
            title={favOnly ? 'Toutes les recettes' : 'Favoris seulement'}
            className={`flex items-center gap-1.5 rounded-md border px-3 py-2 text-sm font-medium transition-colors ${
              favOnly
                ? 'border-amber-400 bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400'
                : 'border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]'
            }`}
          >
            <Star className={`h-4 w-4 ${favOnly ? 'fill-amber-400 text-amber-400' : ''}`} aria-hidden="true" />
            Favoris
          </button>
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Nouvelle recette
          </button>
        </div>
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
          {filtered.map((r) => {
            const isFav = favorites.includes(r.id)
            return (
              <button
                key={r.id}
                type="button"
                onClick={() => setDetailId(r.id)}
                className="relative w-full rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-left transition-colors hover:border-[color-mix(in_srgb,var(--ring)_30%,var(--border))]"
              >
                <button
                  type="button"
                  onClick={(e) => handleToggleFav(e, r.id)}
                  aria-label={isFav ? 'Retirer des favoris' : 'Ajouter aux favoris'}
                  className="absolute right-3 top-3 rounded p-0.5 text-[var(--muted-foreground)] transition-colors hover:text-amber-400"
                >
                  <Star className={`h-4 w-4 ${isFav ? 'fill-amber-400 text-amber-400' : ''}`} aria-hidden="true" />
                </button>
                <h3 className="pr-6 font-display text-sm font-semibold">{r.titre}</h3>
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
              </button>
            )
          })}
        </div>
      )}

      {detailId !== null && (
        <RecipeDetailModal id={detailId} onClose={() => setDetailId(null)} />
      )}

      {open && <RecipeForm aliments={aliments} onClose={() => setOpen(false)} />}
    </div>
  )
}
