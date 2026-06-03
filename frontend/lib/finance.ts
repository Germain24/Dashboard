// Types + client API pour le module Finance

const BASE = "/api/finance";

// ---- Types (alignes avec les schemas FastAPI) ----

export interface SnapshotOut {
  id: number;
  date: string;
  valeur: number;
  investit: number;
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

export interface TransactionOut {
  id: number; ticker: string; type_transaction: string;
  date_transaction: string; quantite: number; prix_unitaire: number;
  frais: number; devise: string; broker?: string; note?: string; created_at: string;
}

export interface TransactionCreate {
  ticker: string; type_transaction: "ACHAT" | "VENTE" | "DIVIDENDE";
  date_transaction: string; quantite: number; prix_unitaire: number;
  frais?: number; devise?: string; broker?: string; note?: string;
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
  buffettLatest: () => get<BuffettRunOut | null>("/buffett/latest"),
  buffettProgress: () => get<BuffettProgress>("/buffett/progress"),
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
};
