const BASE = '/api/cuisine'

export const fetchRecipes = (search?: string) =>
  fetch(`${BASE}/recipes${search ? '?search=' + encodeURIComponent(search) : ''}`).then(r => r.json())

export const createRecipe = (data: any) =>
  fetch(`${BASE}/recipes`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }).then(r => r.json())

export const importFromUrl = (url: string) =>
  fetch(`${BASE}/recipes/from-url?url=${encodeURIComponent(url)}`, { method: 'POST' }).then(r => r.json())

export const fetchMealPlan = (week: string) =>
  fetch(`${BASE}/meal-plan?week=${week}`).then(r => r.json())

export const generateMealPlan = (semaine: string) =>
  fetch(`${BASE}/meal-plan/generate`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ semaine, cibles: { calories: 2500, proteines: 180, glucides: 300, lipides: 80 } }) }).then(r => r.json())

export const fetchShoppingList = (week: string) =>
  fetch(`${BASE}/shopping-list?week=${week}`).then(r => r.json())

export const markShoppingDone = (week: string) =>
  fetch(`${BASE}/shopping-list/done?week=${week}`, { method: 'POST' }).then(r => r.json())

export const toggleShoppingItem = (id: number, achete: boolean) =>
  fetch(`${BASE}/shopping-list/${id}?achete=${achete}`, { method: 'PATCH' }).then(r => r.json())
