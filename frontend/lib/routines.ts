const BASE = '/api/automatisations'

export type TriggerType = 'cron' | 'event'

export type RoutineAction =
  | { type: 'notify'; titre: string; message: string; level?: string }
  | { type: 'job'; job_id: string }
  | { type: string; [k: string]: unknown }

export type Routine = {
  id: number
  name: string
  description: string
  trigger_type: TriggerType
  trigger_value: string
  actions: RoutineAction[]
  enabled: boolean
  last_run_at: string | null
  created_at: string
}

const json = (r: Response) => r.json()
const jsonHeaders = { 'Content-Type': 'application/json' }

export const fetchRoutines = (): Promise<Routine[]> =>
  fetch(`${BASE}/routines`).then(json)

export const createRoutine = (data: Partial<Routine> & { name: string }): Promise<Routine> =>
  fetch(`${BASE}/routines`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(data),
  }).then(json)

export const updateRoutine = (id: number, patch: Partial<Routine>): Promise<Routine> =>
  fetch(`${BASE}/routines/${id}`, {
    method: 'PATCH',
    headers: jsonHeaders,
    body: JSON.stringify(patch),
  }).then(json)

export const deleteRoutine = (id: number): Promise<void> =>
  fetch(`${BASE}/routines/${id}`, { method: 'DELETE' }).then(() => undefined)

export const runRoutine = (id: number): Promise<{ result: string }> =>
  fetch(`${BASE}/routines/${id}/run`, { method: 'POST' }).then(json)
