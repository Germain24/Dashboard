const BASE = '/api/budget'

export async function fetchTransactions(params?: { from?: string; to?: string; category_id?: number }) {
  const q = new URLSearchParams(params as any).toString()
  const res = await fetch(`${BASE}/transactions${q ? '?' + q : ''}`)
  return res.json()
}

export async function createTransaction(data: { date: string; montant: number; marchand: string; description?: string; compte?: string }) {
  const res = await fetch(`${BASE}/transactions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
  return res.json()
}

export async function fetchCategories() {
  return (await fetch(`${BASE}/categories`)).json()
}

export async function fetchSummary(month: string) {
  return (await fetch(`${BASE}/summary?month=${month}`)).json()
}

// Comparaison mois vs mois précédent (#229)
export type Comparison = {
  current: number; previous: number; delta: number
  delta_pct: number | null; direction: 'up' | 'down' | 'flat'
}
export type MonthlyComparison = {
  mois: string; mois_precedent: string
  revenus: Comparison; depenses: Comparison; solde: Comparison
}
export async function fetchSummaryComparison(month: string): Promise<MonthlyComparison> {
  return (await fetch(`${BASE}/summary/compare?month=${month}`)).json()
}

export async function fetchEnvelopes(month: string) {
  return (await fetch(`${BASE}/envelopes?month=${month}`)).json()
}

export async function fetchDisposable(month: string) {
  return (await fetch(`${BASE}/disposable?month=${month}`)).json()
}

export async function fetchCashflow(from: string, to: string) {
  return (await fetch(`${BASE}/cashflow?from_date=${from}&to_date=${to}`)).json()
}

export type CategorySpend = { category_id: number | null; nom: string; couleur: string; montant: number; pct: number }
export type MonthTrend = { mois: string; revenus: number; depenses: number }

export async function fetchByCategory(month: string): Promise<CategorySpend[]> {
  const d = await (await fetch(`${BASE}/by-category?month=${month}`)).json()
  return Array.isArray(d) ? d : []
}

export async function fetchTrend(months = 6): Promise<MonthTrend[]> {
  const d = await (await fetch(`${BASE}/trend?months=${months}`)).json()
  return Array.isArray(d) ? d : []
}

export type Recurring = {
  marchand: string; montant_moyen: number; occurrences: number
  periodicite: string; derniere_date: string; category_id: number | null
}

export async function fetchRecurring(): Promise<Recurring[]> {
  const d = await (await fetch(`${BASE}/recurring`)).json()
  return Array.isArray(d) ? d : []
}

// Récurrent vs ponctuel + projection annuelle (#266)
export type RecurringProjection = {
  recurrents: Recurring[]
  nb_recurrents: number
  recurrent_mensuel_total: number
  projection_annuelle_recurrents: number
  ponctuel_total: number
}
export async function fetchRecurringProjection(): Promise<RecurringProjection> {
  return (await fetch(`${BASE}/recurring/projection`)).json()
}

export type SavingsGoal = { objectif: number; epargne: number; progress_pct: number }

export async function fetchSavingsGoal(): Promise<SavingsGoal> {
  const d = await (await fetch(`${BASE}/savings-goal`)).json()
  return d && typeof d.objectif === 'number' ? d : { objectif: 0, epargne: 0, progress_pct: 0 }
}

export async function setSavingsGoal(montant: number) {
  return (await fetch(`${BASE}/savings-goal?montant=${montant}`, { method: 'POST' })).json()
}

export async function setTransactionTags(id: number, tags: string[]) {
  return (await fetch(`${BASE}/transactions/${id}/tags`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tags }),
  })).json()
}

export async function importCsv(file: File, compte = 'principal') {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(`${BASE}/import?compte=${encodeURIComponent(compte)}`, { method: 'POST', body: fd })
  return res.json()
}

export async function fetchRules() {
  return (await fetch(`${BASE}/rules`)).json()
}

export async function applyRules() {
  return (await fetch(`${BASE}/rules/apply`, { method: 'POST' })).json()
}

// Règles apprenables depuis l'historique catégorisé à la main (#258)
export interface LearnedRule {
  pattern: string
  category_id: number
  category_nom: string
  occurrences: number
}
export interface LearnRulesResult {
  suggestions: LearnedRule[]
  created: number
  recategorised: number
}

export async function fetchRuleSuggestions(): Promise<LearnRulesResult> {
  return (await fetch(`${BASE}/rules/suggestions`)).json()
}

export async function learnRules(): Promise<LearnRulesResult> {
  return (await fetch(`${BASE}/rules/learn`, { method: 'POST' })).json()
}
