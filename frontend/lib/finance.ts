// Types + client API pour le module Finance

const BASE = "/api/finance";

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
  valeur: number;        // valeur dans la devise native
  valeur_eur?: number;   // convertie en EUR (calculée côté serveur)
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
  volatilite_annuelle_pct?: number;
  sharpe_ratio?: number;
  hhi?: number;
  hhi_label: string;
  n_positions: number;
}

export interface TreemapNode {
  id: string; parent: string; valeur: number; label: string;
}

export type TransactionType = "achat" | "vente" | "dividende" | "depot" | "retrait" | "frais";

export interface TransactionOut {
  id: number; ticker: string; type: string;
  date: string; quantite: number; prix_unitaire: number;
  frais: number; devise: string; broker?: string; note?: string; created_at: string;
}

export interface TransactionCreate {
  ticker: string; type_transaction: TransactionType;
  date_transaction: string; quantite: number; prix_unitaire: number;
  frais?: number; devise?: string; broker?: string; note?: string;
}

export interface PortfolioStateOut {
  positions: { ticker: string; broker: string; quantite: number; acb: number; prix: number; valeur: number; pl_latent: number; pl_pct: number; poids_pct: number }[];
  cash_par_broker: Record<string, number>;
  cash_total: number;
  investi_net: number;
  valeur_totale: number;
  pl_realise: number;
  pl_latent_total: number;
  dividendes_total: number;
  allocation: { label: string; valeur: number; poids_pct: number }[];
  taxes: { base_pv: number; impot_pv: number; base_div: number; impot_div: number; total: number; taux_plus_value_pct: number; taux_dividende_pct: number };
}

export interface FinanceSettingsOut {
  taux_plus_value_pct: number; taux_dividende_pct: number; devise_affichage: string;
}

export interface ImportResult { imported: number; skipped: number; errors: string[] }

export interface BuffettRunOut {
  id: number; run_date: string; statut: string;
  n_tickers_total?: number; n_tickers_analyzed?: number;
  progress_pct?: number; duree_sec?: number;
  resume?: string; erreur?: string; created_at: string;
}

export interface BuffettResultOut {
  id: number; run_id?: number; ticker: string; nom?: string;
  score?: number; secteur?: string; pays?: string;
  allocation_pct?: number; broker_cible?: string;
}

export interface BuffettRunDetail {
  run: BuffettRunOut;
  top_results: BuffettResultOut[];
  allocation_cible: BuffettResultOut[];
}

export interface BuffettProgress {
  run_id?: number; statut: string; progress_pct: number;
  n_done?: number; n_total?: number;
  active: boolean;   // true = une analyse tourne reellement (sinon en_cours = interrompu)
  paused_until?: number | null;  // epoch (s) de reprise estimee si en pause (plafond API)
}

export interface RebalancingLine {
  ticker: string; nom: string; broker: string;
  quantite_actuelle: number;
  valeur_actuelle_eur: number; allocation_actuelle_pct: number;
  cible_type: "pie" | "shares";
  cible_shares: number | null;
  prix_unitaire: number;
  valeur_cible_eur: number; allocation_cible_pct: number;
  delta_eur: number; delta_shares: number | null;
  action: "ACHETER" | "VENDRE" | "CONSERVER";
  ecart_pct: number; alerte: boolean;
}

export interface RebalancingDiff {
  run_id: number; run_date: string;
  valeur_totale_eur: number; budget_total_eur: number;
  lignes: RebalancingLine[];
  n_acheter: number; n_vendre: number; n_conserver: number;
  seuil_alerte_pct: number; n_alertes: number;
}

// ---- API client ----

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
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
  /** Recharge l'historique depuis Historique_portefeuille.xlsx (source editable) */
  historySyncExcel: () => post<{ synced: number; file: string }>("/history/sync-excel"),

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
    get<TransactionOut[]>(ticker ? `/transactions?ticker=${ticker}` : "/transactions"),
  createTransaction: (tx: TransactionCreate) => post<TransactionOut>("/transactions", tx),
  importCsv: async (file: File, broker = "auto"): Promise<ImportResult> => {
    const fd = new FormData(); fd.append("file", file);
    const r = await fetch(`${BASE}/transactions/import?broker=${broker}`,
      { method: "POST", body: fd });
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
    get<{ dates: string[]; equity: number[]; rendement_pct: number; n_points: number; tickers: string[] }>(
      `/backtest?periode=${periode}`,
    ),
  dividendes: () =>
    get<{
      total_recu: number; n_versements: number;
      par_ticker: Record<string, number>; par_mois: Record<string, number>;
      lignes: { date: string; ticker: string; montant: number; devise: string }[];
    }>("/dividendes"),
  projection: (p: { initial: number; mensuel: number; taux: number; mois: number; objectif?: number }) =>
    get<{
      courbe: { mois: number; valeur: number; verse: number; interets: number }[];
      valeur_finale: number; total_verse: number; total_interets: number;
      objectif?: number; mois_pour_objectif?: number | null;
    }>(`/projection?initial=${p.initial}&mensuel=${p.mensuel}&taux=${p.taux}&mois=${p.mois}&objectif=${p.objectif ?? 0}`),
  state: () => get<PortfolioStateOut>("/state"),
  cash: () => get<{ cash_par_broker: Record<string, number>; cash_total: number }>("/cash"),
  taxInfo: () => get<PortfolioStateOut["taxes"]>("/tax"),
  settings: () => get<FinanceSettingsOut>("/settings"),
  patchSettings: (s: Partial<FinanceSettingsOut>) => patch<FinanceSettingsOut>("/settings", s),
  diversification: () =>
    get<{
      secteurs: { secteur: string; valeur: number; poids_pct: number; surpondere: boolean }[];
      hhi_secteur: number; n_secteurs: number; seuil_pct: number; n_surponderes: number;
    }>("/diversification"),
  fx: (base = "EUR", quotes = "USD,CAD") =>
    get<{ base: string; rates: Record<string, number> }>(`/fx?base=${base}&quotes=${quotes}`),
  buffettBreakdown: (ticker: string) =>
    get<{
      ticker: string; score: number; secteur: string | null;
      criteres: {
        cle: string; label: string; categorie: string; valeur: number;
        seuil: number; sens: "min" | "max"; ok: boolean; sous_score: number; explication: string;
      }[];
    }>(`/buffett/breakdown/${encodeURIComponent(ticker)}`),
  /** Bouton 1 — Analyser tous les tickers */
  buffettStart: (csvPath?: string) =>
    post<{ message: string; status: string }>(
      csvPath ? `/buffett/run?csv_path=${encodeURIComponent(csvPath)}` : "/buffett/run"),
  /** Bouton 2 — Analyser un ticker precis */
  buffettAnalyzeTicker: (ticker: string) =>
    post<{ ticker: string; score: number; metrics: Record<string, unknown> }>(
      `/buffett/analyze-ticker?ticker=${encodeURIComponent(ticker)}`),
  /** Bouton 3 — Creer le portefeuille optimal (DE) */
  portfolioCreate: (minScore = 80) =>
    post<{ message: string; status: string; run_id: number }>(
      `/portfolio/create?min_score=${minScore}`),

  // Rebalancing
  rebalancing: () => get<RebalancingDiff | null>("/rebalancing/diff"),

  // Objectif patrimoine
  objectifPatrimoine: () =>
    get<{
      objectif_eur: number;
      valeur_eur: number;
      valeur_cad: number;
      taux_cad_eur: number;
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
};
