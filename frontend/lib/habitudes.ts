const BASE = '/api/habitudes'

export type Habit = {
  id: number
  nom: string
  type: string
  unite: string | null
  cible: number
  frequence: string
  source_auto: string | null
  actif: boolean
  ordre: number
  couleur?: string | null
  icone?: string | null
  linked_ids?: string // JSON list[int]
}

export type Streak = { habit_id: number; nom: string; streak: number; best_streak: number }
export type Gamification = { habit_id: number; nom: string; xp: number; level: number; xp_to_next: number }

export const fetchHabits = (): Promise<Habit[]> => fetch(`${BASE}/habits`).then(r => r.json())
export const fetchToday = () => fetch(`${BASE}/today`).then(r => r.json())
export const fetchStreaks = (): Promise<Streak[]> => fetch(`${BASE}/streaks`).then(r => r.json())
export const fetchGamification = (): Promise<Gamification[]> =>
  fetch(`${BASE}/gamification`).then(r => r.json())
export const fetchHeatmap = (habit_id: number, year: number) =>
  fetch(`${BASE}/heatmap?habit_id=${habit_id}&year=${year}`).then(r => r.json())
export const fetchStats = () => fetch(`${BASE}/stats`).then(r => r.json())
export const checkEntry = (habit_id: number, date: string, valeur = 1) =>
  fetch(`${BASE}/entries`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ habit_id, date, valeur }) }).then(r => r.json())
export const deleteEntry = (id: number) =>
  fetch(`${BASE}/entries/${id}`, { method: 'DELETE' })

export const createHabit = (data: {
  nom: string; type?: string; frequence?: string; cible?: number; unite?: string
  couleur?: string | null; icone?: string | null
}) =>
  fetch(`${BASE}/habits`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data) }).then(r => r.json())

export const updateHabit = (id: number, patch: Partial<Habit>) =>
  fetch(`${BASE}/habits/${id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch) }).then(r => r.json())

export const archiveHabit = (id: number) =>
  fetch(`${BASE}/habits/${id}`, { method: 'DELETE' })
