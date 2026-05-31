const BASE = '/api/habitudes'
export const fetchHabits = () => fetch(`${BASE}/habits`).then(r => r.json())
export const fetchToday = () => fetch(`${BASE}/today`).then(r => r.json())
export const fetchStreaks = () => fetch(`${BASE}/streaks`).then(r => r.json())
export const fetchHeatmap = (habit_id: number, year: number) =>
  fetch(`${BASE}/heatmap?habit_id=${habit_id}&year=${year}`).then(r => r.json())
export const fetchStats = () => fetch(`${BASE}/stats`).then(r => r.json())
export const checkEntry = (habit_id: number, date: string, valeur = 1) =>
  fetch(`${BASE}/entries`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ habit_id, date, valeur }) }).then(r => r.json())
export const deleteEntry = (id: number) =>
  fetch(`${BASE}/entries/${id}`, { method: 'DELETE' })
