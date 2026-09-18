"use client";

import { useState, type MouseEvent } from "react";
import { toast } from "sonner";
import { Carrot, Clock, Plus, Star, Users } from "lucide-react";
import type { Recipe } from "@/lib/cuisine";
import { useAliments, useCuisineFavorites, useRecipes, useToggleFavorite } from "@/lib/queries/cuisine";
import RecipeForm from "./RecipeForm";
import RecipeDetailModal from "./RecipeDetailModal";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";

function recipeList(data: Recipe[] | undefined, isError: boolean): Recipe[] | null {
  return isError ? [] : data ?? null;
}

function ingredientQuery(value: string) {
  const trimmed = value.trim();
  return trimmed || undefined;
}

function listOrEmpty<T>(value: T[] | undefined): T[] {
  return value ?? [];
}

function favoriteIds(value: { favorites?: number[] } | undefined) {
  return value?.favorites ?? [];
}

function filteredRecipes(recipes: Recipe[] | null, search: string, favoriteOnly: boolean, favorites: number[]) {
  const query = search.toLowerCase();
  return (recipes ?? [])
    .filter((recipe) => recipe.titre.toLowerCase().includes(query))
    .filter((recipe) => !favoriteOnly || favorites.includes(recipe.id));
}

function RecipeToolbar({
  search,
  ingredient,
  favoriteOnly,
  onSearch,
  onIngredient,
  onToggleFavoriteOnly,
  onCreate,
}: {
  search: string;
  ingredient: string;
  favoriteOnly: boolean;
  onSearch: (value: string) => void;
  onIngredient: (value: string) => void;
  onToggleFavoriteOnly: () => void;
  onCreate: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-1 flex-wrap items-center gap-2">
        <input type="text" placeholder="Rechercher une recette…" value={search} onChange={(event) => onSearch(event.target.value)} className="min-w-[12rem] flex-1 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]" />
        <input type="text" placeholder="Filtrer par ingrédient…" value={ingredient} onChange={(event) => onIngredient(event.target.value)} list="aliments-catalog" className="min-w-[12rem] flex-1 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]" />
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <button type="button" onClick={onToggleFavoriteOnly} title={favoriteOnly ? "Toutes les recettes" : "Favoris seulement"} className={`flex items-center gap-1.5 rounded-md border px-3 py-2 text-sm font-medium transition-colors ${favoriteOnly ? "border-amber-400 bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400" : "border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]"}`}>
          <Star className={`h-4 w-4 ${favoriteOnly ? "fill-amber-400 text-amber-400" : ""}`} aria-hidden="true" /> Favoris
        </button>
        <button type="button" onClick={onCreate} className="flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90">
          <Plus className="h-4 w-4" aria-hidden="true" /> Nouvelle recette
        </button>
      </div>
    </div>
  );
}

function RecipeEmpty({ error, search, onCreate }: { error: boolean; search: string; onCreate: () => void }) {
  return <EmptyState icon={<Carrot className="h-6 w-6" aria-hidden="true" />} title={emptyTitle(error, search)} description={emptyDescription(error)} action={emptyAction(error, search, onCreate)} />;
}

function emptyTitle(error: boolean, search: string) {
  if (error) return "Recettes indisponibles";
  if (search) return "Aucune recette trouvée";
  return "Aucune recette";
}

function emptyDescription(error: boolean) {
  return error ? "Le backend Cuisine ne répond pas." : "Ajoute ta première recette avec ses ingrédients ; elle alimentera le plan et la liste de courses.";
}

function emptyAction(error: boolean, search: string, onCreate: () => void) {
  if (error || search) return undefined;
  return <button type="button" onClick={onCreate} className="inline-flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-1.5 text-xs font-medium text-[var(--primary-foreground)] hover:opacity-90"><Plus className="h-3.5 w-3.5" aria-hidden="true" /> Nouvelle recette</button>;
}

function RecipeCard({ recipe, favorite, onOpen, onToggleFavorite }: { recipe: Recipe; favorite: boolean; onOpen: () => void; onToggleFavorite: (event: MouseEvent) => void }) {
  return (
    <div role="button" tabIndex={0} onClick={onOpen} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onOpen(); }} className="relative w-full cursor-pointer rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 text-left transition-colors hover:border-[color-mix(in_srgb,var(--ring)_30%,var(--border))]">
      <button type="button" onClick={onToggleFavorite} aria-label={favorite ? "Retirer des favoris" : "Ajouter aux favoris"} className="absolute right-3 top-3 rounded p-0.5 text-[var(--muted-foreground)] transition-colors hover:text-amber-400">
        <Star className={`h-4 w-4 ${favorite ? "fill-amber-400 text-amber-400" : ""}`} aria-hidden="true" />
      </button>
      <h3 className="pr-6 font-display text-sm font-semibold">{recipe.titre}</h3>
      <div className="mt-2 flex flex-wrap gap-3 text-xs text-[var(--muted-foreground)]">
        <span className="flex items-center gap-1"><Users size={12} /> {recipe.portions} pers.</span>
        <span className="flex items-center gap-1"><Clock size={12} /> {recipe.temps_prep + recipe.temps_cuisson} min</span>
        <span className="flex items-center gap-1"><Carrot size={12} /> {recipe.ingredient_count ?? 0} ingr.</span>
      </div>
      <RecipeWarning recipe={recipe} />
    </div>
  );
}

function RecipeWarning({ recipe }: { recipe: Recipe }) {
  if ((recipe.ingredient_count ?? 0) !== 0) return null;
  return <p className="mt-2 text-xs text-[var(--warning-foreground)]">Sans ingrédient : invisible pour la liste de courses.</p>;
}

function RecipeResults({ recipes, filtered, favorites, onOpen, onToggleFavorite }: { recipes: Recipe[] | null; filtered: Recipe[]; favorites: number[]; onOpen: (id: number) => void; onToggleFavorite: (event: MouseEvent, id: number) => void }) {
  if (recipes === null) return <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">{[0, 1, 2, 3].map((index) => <Skeleton key={index} className="h-24" />)}</div>;
  if (filtered.length === 0) return null;
  return <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">{filtered.map((recipe) => <RecipeCard key={recipe.id} recipe={recipe} favorite={favorites.includes(recipe.id)} onOpen={() => onOpen(recipe.id)} onToggleFavorite={(event) => onToggleFavorite(event, recipe.id)} />)}</div>;
}

function RecipeContent({ recipes, filtered, error, search, favorites, onCreate, onOpen, onToggleFavorite }: { recipes: Recipe[] | null; filtered: Recipe[]; error: boolean; search: string; favorites: number[]; onCreate: () => void; onOpen: (id: number) => void; onToggleFavorite: (event: MouseEvent, id: number) => void }) {
  return <>{recipes !== null && filtered.length === 0 && <RecipeEmpty error={error} search={search} onCreate={onCreate} />}<RecipeResults recipes={recipes} filtered={filtered} favorites={favorites} onOpen={onOpen} onToggleFavorite={onToggleFavorite} /></>;
}

function RecipeOverlays({ detailId, open, aliments, onCloseDetail, onCloseForm }: { detailId: number | null; open: boolean; aliments: ReturnType<typeof useAliments>["data"] extends infer T ? T : never; onCloseDetail: () => void; onCloseForm: () => void }) {
  return <>{detailId !== null && <RecipeDetailModal key={detailId} id={detailId} onClose={onCloseDetail} />}{open && <RecipeForm aliments={aliments ?? []} onClose={onCloseForm} />}</>;
}

export default function RecettesTab() {
  const [search, setSearch] = useState("");
  const [ingredient, setIngredient] = useState("");
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [open, setOpen] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(null);
  const recipesQ = useRecipes(undefined, ingredientQuery(ingredient));
  const recipes = recipeList(recipesQ.data, recipesQ.isError);
  const favorites = favoriteIds(useCuisineFavorites().data);
  const aliments = listOrEmpty(useAliments().data);
  const toggleFavorite = useToggleFavorite();
  const filtered = filteredRecipes(recipes, search, favoriteOnly, favorites);
  const handleToggleFavorite = (event: MouseEvent, id: number) => {
    event.stopPropagation();
    toggleFavorite.mutate(id, { onError: () => toast.error("Impossible de modifier les favoris.") });
  };
  return (
    <div className="space-y-4">
      <RecipeToolbar search={search} ingredient={ingredient} favoriteOnly={favoriteOnly} onSearch={setSearch} onIngredient={setIngredient} onToggleFavoriteOnly={() => setFavoriteOnly((current) => !current)} onCreate={() => setOpen(true)} />
      <RecipeContent recipes={recipes} filtered={filtered} error={recipesQ.isError} search={search} favorites={favorites} onCreate={() => setOpen(true)} onOpen={setDetailId} onToggleFavorite={handleToggleFavorite} />
      <RecipeOverlays detailId={detailId} open={open} aliments={aliments} onCloseDetail={() => setDetailId(null)} onCloseForm={() => setOpen(false)} />
    </div>
  );
}
