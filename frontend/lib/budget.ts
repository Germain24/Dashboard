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
export type TagSpend = { tag: string; montant: number; pct: number }
export type MonthTrend = { mois: string; revenus: number; depenses: number }

export async function fetchByCategory(month: string): Promise<CategorySpend[]> {
  const d = await (await fetch(`${BASE}/by-category?month=${month}`)).json()
  return Array.isArray(d) ? d : []
}

export async function fetchByTag(days = 365): Promise<TagSpend[]> {
  const d = await (await fetch(`${BASE}/by-tag?days=${days}`)).json()
  return Array.isArray(d) ? d : []
}

export async function fetchTrend(months = 6): Promise<MonthTrend[]> {
  const d = await (await fetch(`${BASE}/trend?months=${months}`)).json()
  return Array.isArray(d) ? d : []
}

// Fenêtre glissante (30 derniers jours) — revenus/dépenses/solde
export type RollingSummary = {
  revenus: number; depenses: number; solde: number; debut: string; fin: string; jours: number
}
export async function fetchRollingSummary(days = 30): Promise<RollingSummary> {
  return (await fetch(`${BASE}/rolling-summary?days=${days}`)).json()
}

// Part (%) des catégories de dépenses au fil du temps (fenêtre glissante)
export type CategoryShare = {
  categories: { nom: string; couleur: string }[]
  points: { date: string; shares: Record<string, number> }[]
}
export async function fetchCategoryShare(days = 180, window = 30): Promise<CategoryShare> {
  return (await fetch(`${BASE}/category-share?days=${days}&window=${window}`)).json()
}

// Prévision de trésorerie (#259)
export type CashFlowForecast = {
  moyenne_revenus: number
  moyenne_depenses: number
  solde_mensuel_moyen: number
  points: { mois: string; solde_mensuel: number; cumul: number }[]
}
export async function fetchForecast(
  monthsAhead = 6, historyMonths = 6,
  scenario?: { revenusDeltaPct?: number; depensesDeltaPct?: number },
): Promise<CashFlowForecast> {
  const params = new URLSearchParams({
    months_ahead: String(monthsAhead),
    history_months: String(historyMonths),
    revenus_delta_pct: String(scenario?.revenusDeltaPct ?? 0),
    depenses_delta_pct: String(scenario?.depensesDeltaPct ?? 0),
  })
  return (await fetch(`${BASE}/forecast?${params}`)).json()
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

// Alertes sur abonnements : hausses de prix + doublons (#260)
export type SubscriptionHausse = {
  marchand: string; montant_precedent: number; montant_actuel: number
  delta: number; delta_pct: number; date: string; occurrences: number
  category_id: number | null
}
export type SubscriptionDoublon = {
  type: 'meme_service' | 'double_prelevement'
  service: string; marchands: string[]; mois: string
  occurrences: number; montant_redondant: number
}
export type SubscriptionAlerts = {
  hausses: SubscriptionHausse[]
  doublons: SubscriptionDoublon[]
  nb_alertes: number
  surcout_mensuel: number
}
const EMPTY_ALERTS: SubscriptionAlerts = { hausses: [], doublons: [], nb_alertes: 0, surcout_mensuel: 0 }

export async function fetchSubscriptionAlerts(): Promise<SubscriptionAlerts> {
  const d = await (await fetch(`${BASE}/recurring/alerts`)).json()
  return d && Array.isArray(d.hausses) ? d : EMPTY_ALERTS
}

// Rapport d'indépendance financière (#268)
export type FireReport = {
  patrimoine_net: number
  revenus_annuels: number
  epargne_annuelle: number
  depenses_annuelles: number
  objectif_fi: number
  taux_epargne_pct: number
  taux_retrait_pct: number
  rendement_reel_pct: number
  progression_pct: number
  annees_restantes: number | null
  annee_cible: number | null
  atteint: boolean
  horizon_max: number
  mois_analyses: number
  devise: string
}

export async function fetchFire(
  months = 12, tauxRetrait = 0.04, rendementReel = 0.05,
): Promise<FireReport> {
  const params = new URLSearchParams({
    months: String(months),
    taux_retrait: String(tauxRetrait),
    rendement_reel: String(rendementReel),
  })
  return (await fetch(`${BASE}/fire?${params}`)).json()
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

// Suivi manuel des abonnements/contrats (#362) — distinct de la détection auto (#116/#266)
export type Contract = {
  id: number
  nom: string
  categorie: string
  montant: number
  periodicite: 'mensuel' | 'annuel'
  date_echeance: string | null
  statut: 'actif' | 'resilie'
  date_resiliation: string | null
  notes: string
  statut_echeance: 'no_date' | 'depassee' | 'proche' | 'ok'
}
export type ContractsSummary = {
  cout_mensuel: number
  prochaines_echeances: Contract[]
}

export async function fetchContracts(statut?: string): Promise<Contract[]> {
  const q = statut ? `?statut=${encodeURIComponent(statut)}` : ''
  const d = await (await fetch(`${BASE}/contracts${q}`)).json()
  return Array.isArray(d) ? d : []
}

export async function fetchContractsSummary(): Promise<ContractsSummary> {
  const d = await (await fetch(`${BASE}/contracts/summary`)).json()
  return d && typeof d.cout_mensuel === 'number' ? d : { cout_mensuel: 0, prochaines_echeances: [] }
}

export async function createContract(data: {
  nom: string; categorie: string; montant: number; periodicite: string
  date_echeance?: string | null; notes?: string
}) {
  const res = await fetch(`${BASE}/contracts`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
  })
  return res.json()
}

export async function updateContract(id: number, patch: Partial<Contract>) {
  const res = await fetch(`${BASE}/contracts/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(patch),
  })
  return res.json()
}

export async function deleteContract(id: number) {
  await fetch(`${BASE}/contracts/${id}`, { method: 'DELETE' })
}
