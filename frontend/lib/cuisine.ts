const BASE = '/api/cuisine'

// ── Types ────────────────────────────────────────────────────────────────────

export type Ingredient = {
  nom_libre: string
  quantite: number
  unite: string
  aliment_id?: number | null // lien catalogue Santé (macros) ; null = texte libre
}

/** Aliment du catalogue Santé (source des macros). */
export type Aliment = { id: number; nom: string; proprietes: Record<string, number> }

export type Recipe = {
  id: number
  titre: string
  portions: number
  temps_prep: number
  temps_cuisson: number
  instructions?: string
  image_url?: string | null
  source_url?: string | null
  ingredient_count?: number
}

export type RecipeInput = {
  titre: string
  portions: number
  temps_prep: number
  temps_cuisson: number
  instructions: string
  ingredients: Ingredient[]
}

// ── Recettes ─────────────────────────────────────────────────────────────────

export async function fetchRecipes(search?: string): Promise<Recipe[]> {
  const r = await fetch(`${BASE}/recipes${search ? '?search=' + encodeURIComponent(search) : ''}`)
  if (!r.ok) throw new Error('Échec du chargement des recettes')
  return r.json()
}

export async function createRecipe(data: RecipeInput): Promise<Recipe> {
  const r = await fetch(`${BASE}/recipes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!r.ok) throw new Error('Échec de la création de la recette')
  return r.json()
}

export async function importFromUrl(url: string): Promise<Recipe> {
  const r = await fetch(`${BASE}/recipes/from-url?url=${encodeURIComponent(url)}`, { method: 'POST' })
  if (!r.ok) throw new Error('Impossible de parser cette URL')
  return r.json()
}

// ── Catalogue Santé + cibles (pour lier les ingrédients et optimiser le plan) ──

export async function fetchAliments(): Promise<Aliment[]> {
  const r = await fetch('/api/sante/aliments')
  if (!r.ok) throw new Error('Échec du chargement du catalogue d’aliments')
  return r.json()
}

/** Cibles macros du jour calculées par l'optimiseur Santé (clés capitalisées). */
export async function fetchDailyTargets(): Promise<Record<string, number>> {
  const r = await fetch('/api/sante/targets/today')
  if (!r.ok) throw new Error('Cibles nutrition indisponibles')
  const d = await r.json()
  return (d?.targets as Record<string, number>) ?? {}
}

// ── Plan repas + courses (branchés plus tard) ────────────────────────────────

export const fetchMealPlan = (week: string) =>
  fetch(`${BASE}/meal-plan?week=${week}`).then((r) => r.json())

export const generateMealPlan = (semaine: string, cibles: Record<string, number>) =>
  fetch(`${BASE}/meal-plan/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ semaine, cibles }),
  }).then((r) => r.json())

export const fetchShoppingList = (week: string) =>
  fetch(`${BASE}/shopping-list?week=${week}`).then((r) => r.json())

export const toggleShoppingItem = (id: number, achete: boolean) =>
  fetch(`${BASE}/shopping-list/${id}?achete=${achete}`, { method: 'PATCH' }).then((r) => r.json())
