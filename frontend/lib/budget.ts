import { json } from "@/lib/fetch-json";

const BASE = "/api/budget";

async function requestJson<T = unknown>(url: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const upstreamSignal = init?.signal;
  const forwardAbort = () => controller.abort(upstreamSignal?.reason);
  if (upstreamSignal?.aborted) forwardAbort();
  else upstreamSignal?.addEventListener("abort", forwardAbort, { once: true });
  const timeout = setTimeout(
    () => controller.abort(new DOMException("Délai API dépassé", "TimeoutError")),
    30_000,
  );
  try {
    return await json<T>(await fetch(url, { ...init, signal: controller.signal }));
  } finally {
    clearTimeout(timeout);
    upstreamSignal?.removeEventListener("abort", forwardAbort);
  }
}

export type BudgetCategory = {
  id: number;
  nom: string;
  parent_id: number | null;
  couleur: string;
};

export type InvestmentFlowPlatform = {
  plateforme: string;
  classe: string;
  devise: string;
  versements: number;
  retraits: number;
  net: number;
  mouvements: number;
  source: "platform" | "bank" | "category" | "mixed";
};

export type InvestmentFlowTotal = {
  devise: string;
  versements: number;
  retraits: number;
  net: number;
  mouvements: number;
};

export type InvestmentFlowSummary = {
  from_date: string | null;
  to_date: string | null;
  plateformes: InvestmentFlowPlatform[];
  totaux_par_devise: InvestmentFlowTotal[];
  plateformes_sans_historique: string[];
  mouvements_bancaires_comptes: number;
  mouvements_plateformes_comptes: number;
  mouvements_bancaires_ecartes: number;
  mouvements_bancaires_associes_plateforme: number;
  doublons_bancaires_ecartes: number;
  doublons_bancaires_intercomptes_ecartes: number;
  doublons_plateformes_ecartes: number;
  regle_dedoublonnage: string;
};

export async function fetchInvestmentFlows(
  params?: { from?: string; to?: string },
  signal?: AbortSignal,
) {
  const query = new URLSearchParams();
  if (params?.from) query.set("from_date", params.from);
  if (params?.to) query.set("to_date", params.to);
  const queryString = query.toString();
  const suffix = queryString ? `?${queryString}` : "";
  return requestJson<InvestmentFlowSummary>(`${BASE}/investment-flows${suffix}`, { signal });
}

export type EnvelopeStatus = {
  category_id: number;
  budget: number;
  depense: number;
  reste: number;
  pct: number;
  status: "ok" | "warning" | "over";
};

export async function fetchTransactions(
  params?: {
    from?: string;
    to?: string;
    category_id?: number;
  },
  signal?: AbortSignal,
) {
  const query = new URLSearchParams();
  if (params?.from) query.set("from_date", params.from);
  if (params?.to) query.set("to_date", params.to);
  if (params?.category_id != null) query.set("category_id", String(params.category_id));
  const q = query.toString();
  return requestJson(`${BASE}/transactions${q ? "?" + q : ""}`, { signal });
}

export async function createTransaction(data: {
  date: string;
  montant: number;
  marchand: string;
  description?: string;
  compte?: string;
}) {
  return requestJson(`${BASE}/transactions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function fetchCategories(signal?: AbortSignal): Promise<BudgetCategory[]> {
  const data = await requestJson(`${BASE}/categories`, { signal });
  return Array.isArray(data) ? data : [];
}

export async function createBudgetCategory(data: {
  nom: string;
  parent_id: number | null;
  couleur?: string;
}) {
  return requestJson(`${BASE}/categories`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateBudgetCategory(
  id: number,
  data: { nom: string; parent_id: number | null; couleur?: string },
) {
  return requestJson(`${BASE}/categories/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function setTransactionCategory(id: number, category_id: number | null) {
  return requestJson(`${BASE}/transactions/${id}/category`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category_id }),
  });
}

export async function fetchSummary(month: string, signal?: AbortSignal) {
  return requestJson(`${BASE}/summary?month=${month}`, { signal });
}

// Comparaison mois vs mois précédent (#229)
export type Comparison = {
  current: number;
  previous: number;
  delta: number;
  delta_pct: number | null;
  direction: "up" | "down" | "flat";
};
export type MonthlyComparison = {
  mois: string;
  mois_precedent: string;
  revenus: Comparison;
  depenses: Comparison;
  solde: Comparison;
};
export async function fetchSummaryComparison(month: string): Promise<MonthlyComparison> {
  return requestJson<MonthlyComparison>(`${BASE}/summary/compare?month=${month}`);
}

export async function fetchEnvelopes(month: string): Promise<EnvelopeStatus[]> {
  const data = await requestJson(`${BASE}/envelopes?month=${month}`);
  return Array.isArray(data) ? data : [];
}

export async function fetchDisposable(month: string) {
  return requestJson(`${BASE}/disposable?month=${month}`);
}

export async function fetchCashflow(from: string, to: string) {
  return requestJson(`${BASE}/cashflow?from_date=${from}&to_date=${to}`);
}

export type CategorySpend = {
  category_id: number | null;
  nom: string;
  couleur: string;
  montant: number;
  pct: number;
};
export type TagSpend = { tag: string; montant: number; pct: number };
export type MonthTrend = { mois: string; revenus: number; depenses: number };

export async function fetchByCategory(month: string): Promise<CategorySpend[]> {
  const d = await requestJson(`${BASE}/by-category?month=${month}`);
  return Array.isArray(d) ? d : [];
}

export async function fetchByTag(days = 365): Promise<TagSpend[]> {
  const d = await requestJson(`${BASE}/by-tag?days=${days}`);
  return Array.isArray(d) ? d : [];
}

export async function fetchTrend(months = 6): Promise<MonthTrend[]> {
  const d = await requestJson(`${BASE}/trend?months=${months}`);
  return Array.isArray(d) ? d : [];
}

// Fenêtre glissante (30 derniers jours) — revenus/dépenses/solde
export type RollingSummary = {
  revenus: number;
  depenses: number;
  solde: number;
  debut: string;
  fin: string;
  jours: number;
};
export async function fetchRollingSummary(days = 30): Promise<RollingSummary> {
  return requestJson<RollingSummary>(`${BASE}/rolling-summary?days=${days}`);
}

// Part (%) des catégories de dépenses au fil du temps (fenêtre glissante)
export type CategoryShare = {
  categories: { nom: string; couleur: string }[];
  points: { date: string; shares: Record<string, number> }[];
};
export async function fetchCategoryShare(days = 180, window = 30): Promise<CategoryShare> {
  return requestJson<CategoryShare>(`${BASE}/category-share?days=${days}&window=${window}`);
}

// Prévision de trésorerie (#259)
export type CashFlowForecast = {
  moyenne_revenus: number;
  moyenne_depenses: number;
  solde_mensuel_moyen: number;
  points: { mois: string; solde_mensuel: number; cumul: number }[];
};
export async function fetchForecast(
  monthsAhead = 6,
  historyMonths = 6,
  scenario?: { revenusDeltaPct?: number; depensesDeltaPct?: number },
): Promise<CashFlowForecast> {
  const params = new URLSearchParams({
    months_ahead: String(monthsAhead),
    history_months: String(historyMonths),
    revenus_delta_pct: String(scenario?.revenusDeltaPct ?? 0),
    depenses_delta_pct: String(scenario?.depensesDeltaPct ?? 0),
  });
  return requestJson<CashFlowForecast>(`${BASE}/forecast?${params}`);
}

export type Recurring = {
  marchand: string;
  montant_moyen: number;
  occurrences: number;
  periodicite: string;
  derniere_date: string;
  category_id: number | null;
};

export async function fetchRecurring(): Promise<Recurring[]> {
  const d = await requestJson(`${BASE}/recurring`);
  return Array.isArray(d) ? d : [];
}

// Récurrent vs ponctuel + projection annuelle (#266)
export type RecurringProjection = {
  recurrents: Recurring[];
  nb_recurrents: number;
  recurrent_mensuel_total: number;
  projection_annuelle_recurrents: number;
  ponctuel_total: number;
};
export async function fetchRecurringProjection(): Promise<RecurringProjection> {
  return requestJson<RecurringProjection>(`${BASE}/recurring/projection`);
}

// Alertes sur abonnements : hausses de prix + doublons (#260)
export type SubscriptionHausse = {
  marchand: string;
  montant_precedent: number;
  montant_actuel: number;
  delta: number;
  delta_pct: number;
  date: string;
  occurrences: number;
  category_id: number | null;
};
export type SubscriptionDoublon = {
  type: "meme_service" | "double_prelevement";
  service: string;
  marchands: string[];
  mois: string;
  occurrences: number;
  montant_redondant: number;
};
export type SubscriptionAlerts = {
  hausses: SubscriptionHausse[];
  doublons: SubscriptionDoublon[];
  nb_alertes: number;
  surcout_mensuel: number;
};
const EMPTY_ALERTS: SubscriptionAlerts = {
  hausses: [],
  doublons: [],
  nb_alertes: 0,
  surcout_mensuel: 0,
};

export async function fetchSubscriptionAlerts(): Promise<SubscriptionAlerts> {
  const d = await requestJson<SubscriptionAlerts>(`${BASE}/recurring/alerts`);
  return d && Array.isArray(d.hausses) ? d : EMPTY_ALERTS;
}

// Rapport d'indépendance financière (#268)
export type FireReport = {
  patrimoine_net: number;
  revenus_annuels: number;
  epargne_annuelle: number;
  depenses_annuelles: number;
  objectif_fi: number;
  taux_epargne_pct: number;
  taux_retrait_pct: number;
  rendement_reel_pct: number;
  progression_pct: number;
  annees_restantes: number | null;
  annee_cible: number | null;
  atteint: boolean;
  horizon_max: number;
  mois_analyses: number;
  devise: string;
};

export async function fetchFire(
  months = 12,
  tauxRetrait = 0.04,
  rendementReel = 0.05,
): Promise<FireReport> {
  const params = new URLSearchParams({
    months: String(months),
    taux_retrait: String(tauxRetrait),
    rendement_reel: String(rendementReel),
  });
  return requestJson<FireReport>(`${BASE}/fire?${params}`);
}

export type SavingsGoal = { objectif: number; epargne: number; progress_pct: number };

export async function fetchSavingsGoal(): Promise<SavingsGoal> {
  const d = await requestJson<SavingsGoal>(`${BASE}/savings-goal`);
  return d && typeof d.objectif === "number" ? d : { objectif: 0, epargne: 0, progress_pct: 0 };
}

export async function setSavingsGoal(montant: number) {
  return requestJson(`${BASE}/savings-goal?montant=${montant}`, { method: "POST" });
}

export async function setTransactionTags(id: number, tags: string[]) {
  return requestJson(`${BASE}/transactions/${id}/tags`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tags }),
  });
}

export type BudgetImportResult = {
  imported: number;
  errors: number;
  categorised: number;
  skipped?: number;
  parsed?: number;
  format?: string;
};

export async function importCsv(file: File, compte = "principal"): Promise<BudgetImportResult> {
  const fd = new FormData();
  fd.append("file", file);
  return requestJson<BudgetImportResult>(`${BASE}/import?compte=${encodeURIComponent(compte)}`, {
    method: "POST",
    body: fd,
  });
}

export async function fetchRules() {
  return requestJson(`${BASE}/rules`);
}

export async function applyRules() {
  return requestJson(`${BASE}/rules/apply`, { method: "POST" });
}

// Règles apprenables depuis l'historique catégorisé à la main (#258)
export interface LearnedRule {
  pattern: string;
  category_id: number;
  category_nom: string;
  occurrences: number;
}
export interface LearnRulesResult {
  suggestions: LearnedRule[];
  created: number;
  recategorised: number;
}

export async function fetchRuleSuggestions(): Promise<LearnRulesResult> {
  return requestJson<LearnRulesResult>(`${BASE}/rules/suggestions`);
}

export async function learnRules(): Promise<LearnRulesResult> {
  return requestJson<LearnRulesResult>(`${BASE}/rules/learn`, { method: "POST" });
}

// Suivi manuel des abonnements/contrats (#362) — distinct de la détection auto (#116/#266)
export type Contract = {
  id: number;
  nom: string;
  categorie: string;
  montant: number;
  periodicite: "mensuel" | "annuel";
  date_echeance: string | null;
  statut: "actif" | "resilie";
  date_resiliation: string | null;
  notes: string;
  statut_echeance: "no_date" | "depassee" | "proche" | "ok";
};
export type ContractsSummary = {
  cout_mensuel: number;
  prochaines_echeances: Contract[];
};

export async function fetchContracts(statut?: string): Promise<Contract[]> {
  const q = statut ? `?statut=${encodeURIComponent(statut)}` : "";
  const d = await requestJson(`${BASE}/contracts${q}`);
  return Array.isArray(d) ? d : [];
}

export async function fetchContractsSummary(): Promise<ContractsSummary> {
  const d = await requestJson<ContractsSummary>(`${BASE}/contracts/summary`);
  return d && typeof d.cout_mensuel === "number"
    ? d
    : { cout_mensuel: 0, prochaines_echeances: [] };
}

export async function createContract(data: {
  nom: string;
  categorie: string;
  montant: number;
  periodicite: string;
  date_echeance?: string | null;
  notes?: string;
}) {
  return requestJson(`${BASE}/contracts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateContract(id: number, patch: Partial<Contract>) {
  return requestJson(`${BASE}/contracts/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}

export async function deleteContract(id: number) {
  const response = await fetch(`${BASE}/contracts/${id}`, { method: "DELETE" });
  if (!response.ok) throw new Error(`Suppression impossible (API ${response.status}).`);
}
