// Types + client API pour le module Finance

const BASE = "/api/finance";
const GET_TIMEOUT_MS = 30_000;

// ---- Types (alignes avec les schemas FastAPI) ----

export interface SnapshotOut {
  id: number;
  date: string;
  valeur: number;
  investit: number;
}

// Patrimoine net (actifs manuels RealT… + passifs emprunt)
export interface PatrimoineItem {
  id: number;
  type: "actif" | "passif";
  label: string;
  categorie: string;
  valeur: number; // valeur dans la devise native
  valeur_eur?: number; // convertie en EUR (calculée côté serveur)
  valeur_source?: "auto"; // "auto" = solde importé (relevé), non saisi à la main
  valeur_auto_date?: string | null; // date du solde auto (relevé)
  taux_pct: number | null;
  mensualite: number | null;
  devise: string;
}
export const PATRIMOINE_DEVISES = ["EUR", "USD", "CAD", "GBP", "CHF"] as const;
export interface PatrimoineItemCreate {
  type: "actif" | "passif";
  label: string;
  valeur: number;
  categorie?: string;
  taux_pct?: number | null;
  mensualite?: number | null;
  devise?: string;
}
export interface NetWorth {
  portefeuille: number;
  actifs_manuels: number;
  passifs: number;
  net: number;
  items: PatrimoineItem[];
}
export interface NetWorthPoint {
  date: string;
  net: number;
  actifs: number;
  passifs: number;
  portefeuille: number;
}
export interface NetWorthHistory {
  days: number;
  points: NetWorthPoint[];
}
export interface NetWorthBreakdown {
  days: number;
  dates: string[];
  comptes: string[];
  series: Record<string, number[]>;
  total: number[];
}

// Marge de crédit
export interface CreditProfile {
  id: number;
  date_cible: string;
  nom: string | null;
}
export interface CreditProfilePatch {
  date_cible?: string;
  nom?: string | null;
}
export interface CreditAccount {
  id: number;
  institution: string;
  produit: string;
  limite_actuelle: number;
  date_ouverture: string;
  derniere_augmentation: string | null;
  statut: "actif" | "ferme";
  notes: string | null;
}
export interface CreditAccountCreate {
  institution: string;
  produit: string;
  limite_actuelle: number;
  date_ouverture: string;
  derniere_augmentation?: string | null;
  statut?: "actif" | "ferme";
  notes?: string | null;
}
export interface CreditScoreEntry {
  id: number;
  date: string;
  score: number;
  source: string;
}
export interface CreditScoreEntryCreate {
  date: string;
  score: number;
  source?: string;
}
export interface CreditActionRule {
  id: number;
  seuil_score: number;
  type: "hausse" | "nouvelle_carte";
  montant_estime: number;
}
export interface CreditActionRuleCreate {
  seuil_score: number;
  type: "hausse" | "nouvelle_carte";
  montant_estime?: number;
}
export interface CreditScorePoint {
  date: string;
  score: number;
}
export interface CreditMarginPoint {
  date: string;
  marge_totale: number;
}
export interface CreditPlanAction {
  date: string;
  type: "hausse" | "nouvelle_carte";
  seuil_score: number;
  montant_estime: number;
}
export interface CreditPlan {
  marge_actuelle: number;
  historique_score: CreditScorePoint[];
  historique_marge: CreditMarginPoint[];
  projection_score: CreditScorePoint[];
  projection_marge: CreditMarginPoint[];
  actions: CreditPlanAction[];
  projection_possible: boolean;
}

export interface VoyageBudgetMois {
  mois: number;
  institution: string;
  produit: string;
  budget: number;
}
export interface VoyageBudget {
  mois: VoyageBudgetMois[];
  budget_total: number;
  mois_total: number;
}

export interface HistoryPoint {
  date: string;
  valeur: number;
  investit: number;
}

export interface PositionOut {
  ticker: string;
  broker?: string;
  quantite: number;
  pmu?: number;
  devise: string;
  prix_actuel: number;
  valeur_actuelle: number;
  pl_latent: number;
  pl_pct: number;
}

export interface TitreDetail {
  ticker: string;
  nom: string | null;
  secteur: string | null;
  pays: string | null;
  prix: number;
  per: number | null;
  score_buffett: number | null;
  quantite: number;
  pmu: number;
  valeur: number;
  poids_pct: number;
  pl_pct: number;
  detenu: boolean;
}

export interface PositionManuelle {
  id: number;
  ticker: string;
  broker?: string;
  quantite: number;
  pmu?: number;
  devise: string;
  updated_at?: string;
}

export interface PositionCreate {
  ticker: string;
  quantite: number;
  pmu?: number;
  devise?: string;
  broker?: string;
}

export interface PerfMetrics {
  valeur: number;
  investit: number;
  pl_total: number;
  pl_pct: number;
  max_drawdown_pct: number;
  ytd_pct: number;
  twr_pct?: number;
  twr_annualise_pct?: number;
  date_snapshot?: string;
}

export interface BenchmarkOut {
  nom: string;
  ticker: string;
  perf_1a_pct?: number;
  perf_6m_pct?: number;
  perf_mtd_pct?: number;
  serie: { date: string; valeur: number }[];
}

export interface RiskMetrics {
  max_drawdown_pct?: number;
  // `volatilite_annuelle_pct` et `hhi_label` n'ont jamais existé côté backend :
  // le schéma les déclarait, le service produisait ces noms-ci. Les deux champs
  // sortaient donc toujours vides.
  volatilite_annualisee_pct?: number;
  sharpe?: number | null;
  // null = aucun rendement baissier sur la période (ratio non défini), pas 0.
  sortino?: number | null;
  hhi?: number;
  concentration: string;
  n_positions: number;
}

export interface TreemapNode {
  id: string;
  parent: string;
  valeur: number;
  label: string;
}

export type TransactionType = "achat" | "vente" | "dividende" | "interet" | "depot" | "retrait" | "frais";

export interface TransactionOut {
  id: number;
  ticker: string;
  type: string;
  date: string;
  quantite: number;
  prix_unitaire: number;
  frais: number;
  montant_brut?: number | null;
  retenue_source?: number;
  devise: string;
  broker?: string;
  note?: string;
  created_at: string;
}

export interface TransactionCreate {
  ticker: string;
  type_transaction: TransactionType;
  date_transaction: string;
  quantite: number;
  prix_unitaire: number;
  frais?: number;
  montant_brut?: number | null;
  retenue_source?: number;
  devise?: string;
  broker?: string;
  note?: string;
}

export interface PortfolioStateOut {
  positions: {
    ticker: string;
    broker: string;
    quantite: number;
    acb: number;
    prix: number;
    valeur: number;
    pl_latent: number;
    pl_pct: number;
    poids_pct: number;
  }[];
  cash_par_broker: Record<string, number>;
  cash_total: number;
  investi_net: number;
  valeur_totale: number;
  pl_realise: number;
  pl_latent_total: number;
  dividendes_total: number;
  dividendes_bruts: number;
  retenues_source: number;
  interets_bruts: number;
  interets_total: number;
  revenus_mobiliers_total: number;
  allocation: { label: string; valeur: number; poids_pct: number }[];
  taxes: {
    base_pv: number;
    impot_pv: number;
    base_div: number;
    impot_div: number;
    total: number;
    taux_plus_value_pct: number;
    taux_dividende_pct: number;
  };
}

export interface FinanceSettingsOut {
  taux_plus_value_pct: number;
  taux_dividende_pct: number;
  devise_affichage: string;
}

export interface ImportResult {
  imported: number;
  updated: number;
  skipped: number;
  errors: string[];
}

export interface BuffettRunOut {
  id: number;
  run_date: string;
  statut: string;
  n_tickers_total?: number;
  n_tickers_analyzed?: number;
  progress_pct?: number;
  duree_sec?: number;
  resume?: string;
  erreur?: string;
  created_at: string;
}

export interface BuffettAllocationLine {
  broker?: string;
  type?: "pie" | "shares";
  pie_pct?: number | null; // Trading212 : % entier du pie (somme 100 dans le broker)
  shares?: number | null; // autres brokers : nombre d'actions entières
  eur?: number | null;
  prix?: number | null;
  pct?: number | null; // % du capital total
}

export interface BuffettResultOut {
  id: number;
  run_id?: number;
  ticker: string;
  nom?: string;
  score?: number;
  secteur?: string;
  pays?: string;
  allocation_pct?: number;
  broker_cible?: string;
  allocations?: BuffettAllocationLine[] | null;
}

export interface BuffettRunDetail {
  run: BuffettRunOut;
  top_results: BuffettResultOut[];
  allocation_cible: BuffettResultOut[];
  optimization?: {
    schema_version: number;
    seed: number;
    n_sim: number;
    n_search: number;
    constraints_relaxed: boolean;
    base_currency?: string;
    estimation?: {
      mean_window_observations: number;
      mean_signal_weight: number;
      mean_prior: string;
      correlation_shrinkage: number;
    };
    turnover?: {
      current_weights_available: boolean;
      penalty: number;
      rebalance_band: number;
      estimated_one_way: number;
    };
    transaction_costs?: {
      enabled: boolean;
      base_currency: string;
      trade_cost_eur: number;
      trade_cost_pct: number;
      annual_custody_eur: number;
      annualized_cost_eur: number;
      annualized_cost_pct: number;
      rebalances_per_year: number;
      trade_cost_multiplier: number;
      bourse_direct_tariff_effective: string;
      ttf_tickers_recognized: number;
      brokers: Array<{
        broker: string;
        trade_cost_eur: number;
        annual_custody_eur: number;
      }>;
      notes?: string[];
    };
    regimes?: {
      method: string;
      n_observations_available: number;
      mean_window_observations: number;
      windows: Array<{
        label: string;
        target_days: number;
        observations: number;
        weight: number;
        n_sim: number;
      }>;
      correlation_stability?: {
        available: boolean;
        n_pairs?: number;
        unstable_pairs?: number;
        major_shift_pairs?: number;
        p90_delta?: number;
        top_pairs?: Array<{
          ticker_a: string;
          ticker_b: string;
          max_delta: number;
          correlations: Record<string, number>;
        }>;
      };
    };
    etf_selection?: {
      enabled: boolean;
      max_per_broker: number;
      n_etf_before: number;
      n_etf_after: number;
      n_removed_from_union: number;
      brokers: Record<string, {
        candidates_before: number;
        selected: number;
        removed: number;
        bucket_counts: Record<string, number>;
      }>;
    };
    termination: {
      reason: string;
      max_seeds: number;
      seeds_run: number;
      stagnation_generations: number;
      min_improvement: number;
      runs: Array<{ seed: number; generations: number; reason: string }>;
    };
    benchmarks: {
      optimized: number;
      equal_weight: number;
      equal_weight_max_lines_per_broker: number;
      best_single_ticker?: string | null;
      best_single: number;
      best_single_candidates_tested: number;
      "CW8.PA"?: number;
      SGOV?: number;
    };
  } | null;
}

export interface BuffettProgress {
  run_id?: number;
  statut: string;
  progress_pct: number;
  n_done?: number;
  n_total?: number;
  active: boolean; // true = une analyse tourne reellement (sinon en_cours = interrompu)
  paused_until?: number | null; // epoch (s) de reprise estimee si en pause (plafond API)
}

export interface RebalancingLine {
  ticker: string;
  nom: string;
  broker: string;
  quantite_actuelle: number;
  valeur_actuelle_eur: number;
  allocation_actuelle_pct: number;
  cible_type: "pie" | "shares";
  cible_shares: number | null;
  prix_unitaire: number;
  valeur_cible_eur: number;
  allocation_cible_pct: number;
  delta_eur: number;
  delta_shares: number | null;
  action: "ACHETER" | "VENDRE" | "CONSERVER";
  ecart_pct: number;
  alerte: boolean;
}

export interface RebalancingDiff {
  run_id: number;
  run_date: string;
  valeur_totale_eur: number;
  budget_total_eur: number;
  lignes: RebalancingLine[];
  n_acheter: number;
  n_vendre: number;
  n_conserver: number;
  seuil_alerte_pct: number;
  n_alertes: number;
}

// Impôts — CTO français (plus-values au PMP + dividendes)
export interface RegimeTax {
  base: number;
  base_ir?: number;
  abattement_dividendes?: number;
  ir: number;
  social: number;
  total: number;
  taux_ir_pct?: number;
  taux_sociaux_pct: number;
  csg_deductible_annee_suivante?: number;
}
export interface AnneeImpots {
  gain_brut: number;
  gain_net_imposable: number;
  report_apres: number;
}
export interface CalculImpots {
  annee: number;
  methode_cout: "PMP";
  gain_brut: number;
  gain_net_imposable: number;
  report_moins_values_restant: number;
  dividendes_bruts: number;
  dividendes_eligibles_bruts: number;
  dividendes_nets: number;
  interets_bruts: number;
  interets_nets: number;
  revenus_mobiliers_bruts: number;
  revenus_mobiliers_nets: number;
  retenue_source_etrangere: number;
  taux_sociaux_pct: number;
  bareme_reference_revenus: number;
  bareme_provisoire: boolean;
  dividendes_eligibles_abattement: boolean;
  data_quality: {
    ventes_total: number;
    ventes_calculables: number;
    ventes_exclues: number;
    revenus_exclus: number;
  };
  avertissements: string[];
  historique_par_annee: Record<string, AnneeImpots>;
  pfu: RegimeTax;
  bareme: RegimeTax;
  recommande: "pfu" | "bareme" | "egalite";
}
// Alertes de marché — seuils de prix par ticker
export type PriceAlertDirection = "au_dessus" | "en_dessous";
export interface PriceAlert {
  id: number;
  ticker: string;
  seuil: number;
  direction: PriceAlertDirection;
  actif: boolean;
  cree_le: string;
}
export interface PriceAlertCreate {
  ticker: string;
  seuil: number;
  direction: PriceAlertDirection;
}
export interface PriceAlertPatch {
  ticker?: string;
  seuil?: number;
  direction?: PriceAlertDirection;
  actif?: boolean;
}
export interface PriceAlertStatus extends PriceAlert {
  prix_actuel: number | null;
  declenchee: boolean;
}

export interface VenteDetail {
  date: string;
  ticker: string;
  broker: string;
  quantite: number;
  prix_achat_moyen: number;
  prix_vente: number;
  produit_net: number | null;
  cout_acquisition: number | null;
  frais_vente: number;
  plus_value: number | null;
  calculable: boolean;
  raison: string | null;
}

// ---- API client ----

async function responseError(response: Response): Promise<Error> {
  let detail = "";
  try {
    const body = await response.json();
    detail = typeof body?.detail === "string" ? body.detail : "";
  } catch {
    /* réponse sans JSON */
  }
  return new Error(detail || `${response.status} ${response.statusText}`);
}

async function get<T>(path: string): Promise<T> {
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), GET_TIMEOUT_MS);
  try {
    const response = await fetch(`${BASE}${path}`, { signal: controller.signal });
    if (!response.ok) throw await responseError(response);
    return response.json();
  } catch (error) {
    if ((error as { name?: string })?.name === "AbortError") {
      throw new Error("Le service Finance met trop de temps à répondre.", {
        cause: error,
      });
    }
    throw error;
  } finally {
    globalThis.clearTimeout(timeout);
  }
}

export interface PageResult<T> {
  items: T[];
  total: number;
}

async function getPage<T>(path: string): Promise<PageResult<T>> {
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), GET_TIMEOUT_MS);
  try {
    const response = await fetch(`${BASE}${path}`, { signal: controller.signal });
    if (!response.ok) throw await responseError(response);
    const items = (await response.json()) as T[];
    const parsedTotal = Number(response.headers.get("X-Total-Count"));
    return {
      items,
      total: Number.isFinite(parsedTotal) ? parsedTotal : items.length,
    };
  } catch (error) {
    if ((error as { name?: string })?.name === "AbortError") {
      throw new Error("Le service Finance met trop de temps à répondre.", {
        cause: error,
      });
    }
    throw error;
  } finally {
    globalThis.clearTimeout(timeout);
  }
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function del(path: string): Promise<void> {
  const r = await fetch(`${BASE}${path}`, { method: "DELETE" });
  if (!r.ok && r.status !== 204) throw new Error(`${r.status} ${r.statusText}`);
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export const financeApi = {
  // Snapshots & historique
  snapshot: () => get<SnapshotOut | null>("/snapshot/latest"),
  snapshotCreate: () => post<SnapshotOut>("/snapshot"),
  snapshotAuto: () => post<{ status: string; date?: string; valeur?: number }>("/snapshot/auto"),
  history: (days = 365) => get<HistoryPoint[]>(`/history?days=${days}`),

  // Portfolio
  portfolio: () => get<PositionOut[]>("/portfolio"),
  perf: () => get<PerfMetrics>("/portfolio/perf"),
  titreDetail: (ticker: string) => get<TitreDetail>(`/titre/${encodeURIComponent(ticker)}`),

  // Positions manuelles
  positionsList: () => get<PositionManuelle[]>("/positions/list"),
  positionCreate: (p: PositionCreate) => post<PositionManuelle>("/positions", p),
  positionUpdate: (id: number, p: PositionCreate) => put<PositionManuelle>(`/positions/${id}`, p),
  positionDelete: (id: number) => del(`/positions/${id}`),

  // Benchmarks & risque
  benchmarks: () => get<BenchmarkOut[]>("/benchmarks"),
  risk: () => get<RiskMetrics>("/risk"),
  treemap: (groupBy = "secteur") => get<TreemapNode[]>(`/treemap?group_by=${groupBy}`),

  // Transactions
  transactions: (ticker?: string) =>
    get<TransactionOut[]>(
      ticker
        ? `/transactions?ticker=${encodeURIComponent(ticker)}&limit=1000`
        : "/transactions?limit=1000",
    ),
  transactionsPage: ({
    ticker,
    limit = 100,
    offset = 0,
  }: {
    ticker?: string;
    limit?: number;
    offset?: number;
  } = {}) => {
    const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (ticker) query.set("ticker", ticker);
    return getPage<TransactionOut>(`/transactions?${query.toString()}`);
  },
  createTransaction: (tx: TransactionCreate) => post<TransactionOut>("/transactions", tx),
  importCsv: async (file: File, broker = "auto"): Promise<ImportResult> => {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(`${BASE}/transactions/import?broker=${broker}`, {
      method: "POST",
      body: fd,
    });
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  },

  // Buffett
  buffettRuns: () => get<BuffettRunOut[]>("/buffett/runs"),
  buffettRun: (id: number) => get<BuffettRunDetail>(`/buffett/runs/${id}`),
  buffettDeleteRun: (id: number) => del(`/buffett/runs/${id}`),
  buffettLatest: () => get<BuffettRunOut | null>("/buffett/latest"),
  buffettProgress: () => get<BuffettProgress>("/buffett/progress"),
  backtest: (periode = "2y") =>
    get<{
      dates: string[];
      equity: number[];
      rendement_pct: number;
      n_points: number;
      tickers: string[];
    }>(`/backtest?periode=${periode}`),
  backtestWalkForward: (periode = "5y", costBps = 10) =>
    get<{
      mode: "walk_forward";
      dates: string[];
      equity: number[];
      rendement_pct: number;
      n_points: number;
      n_runs: number;
      n_rebalances: number;
      turnover: number;
      costs_pct: number;
      max_drawdown_pct: number;
      cvar_5_pct: number;
      cagr_pct: number;
      tickers: string[];
      comparisons: Record<string, {
        rendement_pct: number;
        cagr_pct: number;
        max_drawdown_pct: number;
        cvar_5_pct: number;
        turnover: number;
        costs_pct: number;
        n_points: number;
      }>;
    }>(`/backtest/walk-forward?periode=${periode}&cost_bps=${costBps}`),
  dividendes: () =>
    get<{
      total_recu: number;
      total_brut: number;
      total_retenue_source: number;
      n_versements: number;
      interets_recus: number;
      n_interets: number;
      revenus_nets: number;
      par_ticker: Record<string, number>;
      par_mois: Record<string, number>;
      lignes: { date: string; ticker: string; montant: number; montant_brut: number; retenue_source: number; devise: string }[];
    }>("/dividendes"),
  projection: (p: {
    initial: number;
    mensuel: number;
    taux: number;
    mois: number;
    objectif?: number;
  }) =>
    get<{
      courbe: { mois: number; valeur: number; verse: number; interets: number }[];
      valeur_finale: number;
      total_verse: number;
      total_interets: number;
      objectif?: number;
      mois_pour_objectif?: number | null;
    }>(
      `/projection?initial=${p.initial}&mensuel=${p.mensuel}&taux=${p.taux}&mois=${p.mois}&objectif=${p.objectif ?? 0}`,
    ),
  state: () => get<PortfolioStateOut>("/state"),
  cash: () => get<{ cash_par_broker: Record<string, number>; cash_total: number }>("/cash"),
  taxInfo: (annee?: number) => get<CalculImpots>(`/tax${annee ? `?annee=${annee}` : ""}`),
  settings: () => get<FinanceSettingsOut>("/settings"),
  patchSettings: (s: Partial<FinanceSettingsOut>) => patch<FinanceSettingsOut>("/settings", s),
  diversification: () =>
    get<{
      secteurs: { secteur: string; valeur: number; poids_pct: number; surpondere: boolean }[];
      hhi_secteur: number;
      n_secteurs: number;
      seuil_pct: number;
      n_surponderes: number;
    }>("/diversification"),
  fx: (base = "EUR", quotes = "USD,CAD") =>
    get<{ base: string; rates: Record<string, number> }>(`/fx?base=${base}&quotes=${quotes}`),
  buffettBreakdown: (ticker: string) =>
    get<{
      ticker: string;
      score: number;
      secteur: string | null;
      criteres: {
        cle: string;
        label: string;
        categorie: string;
        valeur: number;
        seuil: number;
        sens: "min" | "max";
        ok: boolean;
        sous_score: number;
        explication: string;
      }[];
    }>(`/buffett/breakdown/${encodeURIComponent(ticker)}`),
  /** Bouton 1 — Analyser tous les tickers */
  buffettStart: (csvPath?: string) =>
    post<{ message: string; status: string }>(
      csvPath ? `/buffett/run?csv_path=${encodeURIComponent(csvPath)}` : "/buffett/run",
    ),
  /** Bouton 2 — Analyser un ticker precis */
  buffettAnalyzeTicker: (ticker: string) =>
    post<{ ticker: string; score: number; metrics: Record<string, unknown> }>(
      `/buffett/analyze-ticker?ticker=${encodeURIComponent(ticker)}`,
    ),
  /** Bouton 3 — Creer le portefeuille optimal (DE) */
  portfolioCreate: (minScore = 80) =>
    post<{ message: string; status: string; run_id: number }>(
      `/portfolio/create?min_score=${minScore}`,
    ),
  /** Progression de l'optimisation DE (barre de chargement du bouton 3) */
  portfolioProgress: (historyAfter?: number) =>
    get<{
      active: boolean;
      phase: "idle" | "preparation" | "initialisation" | "optimisation" | "finalisation";
      seed_num: number;
      iteration: number;
      total_iterations: number;
      initialization_attempt: number;
      initialization_max: number;
      convergence: number;
      progress_pct: number;
      message: string;
      run_id: number | null;
      stop_requested: boolean;
      best_score: number | null;
      score_history?: Array<{
        iteration: number;
        seed_num: number;
        seed_iteration: number;
        score: number;
      }>;
    }>(historyAfter == null
      ? "/portfolio/progress"
      : `/portfolio/progress?history_after=${Math.max(0, Math.trunc(historyAfter))}`),
  /** Arrête l'optimisation DE en cours (run auto ou bouton manuel) */
  optimizationStop: () => post<{ message: string }>("/buffett/optimization/stop"),

  // Rebalancing
  rebalancing: () => get<RebalancingDiff | null>("/rebalancing/diff"),

  // Objectif patrimoine
  objectifPatrimoine: () =>
    get<{
      objectif_eur: number;
      valeur_eur: number;
      progression_pct: number;
      restant_eur: number;
      atteint: boolean;
    }>("/objectif-patrimoine"),
  setObjectifPatrimoine: (objectif_eur: number) =>
    post<{ objectif_eur: number }>("/objectif-patrimoine", { objectif_eur }),

  // Patrimoine net (RealT, emprunts…)
  patrimoine: () => get<NetWorth>("/patrimoine"),
  patrimoineHistory: (days = 365) => get<NetWorthHistory>(`/patrimoine/history?days=${days}`),
  patrimoineBreakdownHistory: (days = 365) =>
    get<NetWorthBreakdown>(`/patrimoine/breakdown-history?days=${days}`),
  patrimoineCreate: (item: PatrimoineItemCreate) => post<PatrimoineItem>("/patrimoine", item),
  patrimoineUpdate: (id: number, patch_: Partial<PatrimoineItemCreate>) =>
    patch<PatrimoineItem>(`/patrimoine/${id}`, patch_),
  patrimoineDelete: (id: number) => del(`/patrimoine/${id}`),

  // Marge de crédit
  creditProfile: () => get<CreditProfile>("/credit/profile"),
  creditProfileUpdate: (data: CreditProfilePatch) => patch<CreditProfile>("/credit/profile", data),
  creditAccounts: () => get<CreditAccount[]>("/credit/accounts"),
  creditAccountCreate: (data: CreditAccountCreate) => post<CreditAccount>("/credit/accounts", data),
  creditAccountUpdate: (id: number, data: Partial<CreditAccountCreate>) =>
    patch<CreditAccount>(`/credit/accounts/${id}`, data),
  creditAccountDelete: (id: number) => del(`/credit/accounts/${id}`),
  creditScores: () => get<CreditScoreEntry[]>("/credit/scores"),
  creditScoreCreate: (data: CreditScoreEntryCreate) =>
    post<CreditScoreEntry>("/credit/scores", data),
  creditScoreDelete: (id: number) => del(`/credit/scores/${id}`),
  creditRules: () => get<CreditActionRule[]>("/credit/rules"),
  creditRuleCreate: (data: CreditActionRuleCreate) => post<CreditActionRule>("/credit/rules", data),
  creditRuleDelete: (id: number) => del(`/credit/rules/${id}`),
  creditPlan: () => get<CreditPlan>("/credit/plan"),
  creditVoyageBudget: (ordre: "desc" | "asc" = "desc") =>
    get<VoyageBudget>(`/credit/voyage-budget?ordre=${ordre}`),

  // Impôts — plus-values de cession
  calculImpots: (params: {
    annee: number;
    autres_revenus?: number;
    parts?: number;
    moins_values_anterieures?: number;
    moins_values_anterieures_annee?: number;
    dividendes_eligibles_abattement?: boolean;
    broker?: string;
  }) => {
    const q = new URLSearchParams();
    q.set("annee", String(params.annee));
    if (params.autres_revenus != null) q.set("autres_revenus", String(params.autres_revenus));
    if (params.parts != null) q.set("parts", String(params.parts));
    if (params.moins_values_anterieures != null)
      q.set("moins_values_anterieures", String(params.moins_values_anterieures));
    if (params.moins_values_anterieures_annee != null)
      q.set("moins_values_anterieures_annee", String(params.moins_values_anterieures_annee));
    if (params.dividendes_eligibles_abattement != null)
      q.set("dividendes_eligibles_abattement", String(params.dividendes_eligibles_abattement));
    if (params.broker) q.set("broker", params.broker);
    return get<CalculImpots>(`/impots/calcul?${q.toString()}`);
  },
  ventesImpots: (params: { annee?: number; broker?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.annee != null) q.set("annee", String(params.annee));
    if (params.broker) q.set("broker", params.broker);
    const qs = q.toString();
    return get<{ ventes: VenteDetail[] }>(`/impots/ventes${qs ? `?${qs}` : ""}`);
  },

  // Alertes de marché (seuils de prix)
  alertsList: () => get<PriceAlert[]>("/alerts"),
  alertsCreate: (a: PriceAlertCreate) => post<PriceAlert>("/alerts", a),
  alertsUpdate: (id: number, patch_: PriceAlertPatch) => patch<PriceAlert>(`/alerts/${id}`, patch_),
  alertsDelete: (id: number) => del(`/alerts/${id}`),
  alertsStatus: () => get<PriceAlertStatus[]>("/alerts/status"),
};
