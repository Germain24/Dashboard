// Notifications — appels directs au backend proxifié (/api/* -> backend),
// comme les autres modules (lib/jobs.ts, etc.).

const BASE = '/api/notifications'

// Le backend renvoie les champs du modèle : titre / message / lu / source.
export type Notification = {
  id: number
  source: string
  level: string
  titre: string
  message: string
  lu: boolean
  created_at: string
}

export type NotifPref = { source: string; enabled: boolean }

export async function fetchNotifications(limit = 10): Promise<Notification[]> {
  const r = await fetch(`${BASE}?limit=${limit}`)
  const d = await r.json()
  return Array.isArray(d) ? d : []
}

export const markRead = (id: number) =>
  fetch(`${BASE}/${id}/read`, { method: 'PATCH' }).then((r) => r.json())

export const markAllRead = () =>
  fetch(`${BASE}/read-all`, { method: 'POST' }).then((r) => r.json())

export const clearAll = () =>
  fetch(`${BASE}/clear`, { method: 'DELETE' }).then((r) => r.json())

export const fetchPrefs = (): Promise<NotifPref[]> =>
  fetch(`${BASE}/prefs`).then((r) => r.json())

export const setPref = (source: string, enabled: boolean) =>
  fetch(`${BASE}/prefs`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source, enabled }),
  }).then((r) => r.json())
