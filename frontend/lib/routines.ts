const BASE = '/api/automatisations'

export type TriggerType = 'cron' | 'event' | 'webhook'

export type RoutineAction =
  | { type: 'notify'; titre: string; message: string; level?: string }
  | { type: 'job'; job_id: string }
  | { type: 'webhook'; url: string }
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

// ── Kill switch global + journal d'audit (#217) ──────────────────────────────

export type RoutineRun = {
  id: number
  routine_id: number
  routine_name: string
  ran_at: string
  status: 'ok' | 'blocked' | 'error'
  detail: string
  created_ids?: string
  rolled_back?: boolean
}

export const fetchKillSwitch = (): Promise<{ enabled: boolean }> =>
  fetch(`${BASE}/routines/kill-switch`).then(json)

export const setKillSwitch = (enabled: boolean): Promise<{ enabled: boolean }> =>
  fetch(`${BASE}/routines/kill-switch`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ enabled }),
  }).then(json)

export const fetchRoutineRuns = (limit = 30): Promise<RoutineRun[]> =>
  fetch(`${BASE}/routines/runs?limit=${limit}`).then(json)

// Suggestions d'automatisation apprises des habitudes (#218)
export type AutomationSuggestion = {
  titre: string
  weekday: number
  jour: string
  heure: string
  occurrences: number
  message: string
}

export const fetchAutomationSuggestions = (): Promise<{ suggestions: AutomationSuggestion[]; count: number }> =>
  fetch(`${BASE}/suggestions`).then(json)

// Planificateur deep work (#220)
export const applyDeepWork = (nBlocks = 5): Promise<{ week_start: string; created: number }> =>
  fetch(`${BASE}/deep-work/apply?n_blocks=${nBlocks}`, { method: 'POST' }).then(json)

// Corrélations cross-modules (#221)
export type Correlation = { a: string; b: string; r: number; n: number; interpretation: string }

export const fetchCorrelations = (): Promise<{ days: number; correlations: Correlation[]; count: number }> =>
  fetch(`${BASE}/correlations`).then(json)

// File d'automatisations : ré-exécution + rollback (#216)
export const rerunRoutineRun = (runId: number): Promise<{ result: string }> =>
  fetch(`${BASE}/routines/runs/${runId}/rerun`, { method: 'POST' }).then(json)

export const rollbackRoutineRun = (runId: number): Promise<{ result: string }> =>
  fetch(`${BASE}/routines/runs/${runId}/rollback`, { method: 'POST' }).then(json)

// ── Constructeur no-code (#205) ──────────────────────────────────────────────

export type BuilderOptions = {
  events: { value: string; label: string }[]
  jobs: { id: string; label: string }[]
  action_types: { type: string; label: string }[]
}

export const fetchBuilderOptions = (): Promise<BuilderOptions> =>
  fetch(`${BASE}/routines/builder-options`).then(json)

// ── Recettes cross-module (#215) ─────────────────────────────────────────────

export type Recipe = {
  id: string; name: string; emoji: string; description: string; nb_actions: number
}

export const fetchRecipes = (): Promise<Recipe[]> =>
  fetch(`${BASE}/recipes`).then(json)

export const runRecipe = (id: string): Promise<{ result: string }> =>
  fetch(`${BASE}/recipes/${id}/run`, { method: 'POST' }).then(json)
