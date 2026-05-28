// Types + client API pour le module Finance

const BASE = "/api/finance";

// ---- Types ----

export interface SnapshotOut {
  id: number; date: string; valeur_totale: number;
  montant_investi: number; plus_value_latente: number;
  nb_lignes: number; created_at: string;
}

export interface HistoryPoint {
  date: string; valeur_totale: number; montant_investi: number;
}

export interface PositionOut {
  id: number; ticker: string; nom?: string;
  quantite: number; prix_moyen?: number; prix_actuel?: number;
  valeur_actuelle?: number; plus_value?: number; plus_value_pct?: number;
  secteur?: string; pays?: string; devise?: string;
}

export interface PerfMetrics {
  valeur_totale: number; montant_investi: number;
  plus_value_latente: number; plus_value_pct: number;
  ytd_pct?: number; max_drawdown_pct?: number; volatilite_annuelle_pct?: number;
}

export interface BenchmarkOut {
  nom: string; ticker: string;
  perf_1m_pct?: number; perf_3m_pct?: number;
  perf_ytd_pct?: number; perf_1a_pct?: number;
  serie: { date: string; valeur: number }[];
}

export interface RiskMetrics {
  max_drawdown_pct?: number; volatilite_annuelle_pct?: number;
  sharpe_ratio?: number; hhi?: number; hhi_label: string; n_positions: number;
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
}

export interface RebalancingLine {
  ticker: string; nom: string;
  allocation_actuelle_pct: number; allocation_cible_pct: number;
  valeur_actuelle_eur: number; valeur_cible_eur: number;
  delta_eur: number; action: "ACHETER" | "VENDRE" | "CONSERVER";
}

export interface RebalancingDiff {
  run_id: number; run_date: string; valeur_totale_eur: number;
  lignes: RebalancingLine[];
  n_acheter: number; n_vendre: number; n_conserver: number;
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

export const financeApi = {
  snapshot: () => get<SnapshotOut | null>("/snapshot/latest"),
  snapshotCreate: () => post<SnapshotOut>("/snapshot"),
  history: (days = 365) => get<HistoryPoint[]>(`/history?days=${days}`),
  portfolio: () => get<PositionOut[]>("/portfolio"),
  perf: () => get<PerfMetrics>("/portfolio/perf"),
  benchmarks: () => get<BenchmarkOut[]>("/benchmarks"),
  risk: () => get<RiskMetrics>("/risk"),
  treemap: (groupBy = "secteur") => get<TreemapNode[]>(`/treemap?group_by=${groupBy}`),

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

  buffettRuns: () => get<BuffettRunOut[]>("/buffett/runs"),
  buffettRun: (id: number) => get<BuffettRunDetail>(`/buffett/runs/${id}`),
  buffettLatest: () => get<BuffettRunOut | null>("/buffett/latest"),
  buffettProgress: () => get<BuffettProgress>("/buffett/progress"),
  buffettStart: (csvPath?: string) =>
    post<{ message: string; status: string }>(
      csvPath ? `/buffett/run?csv_path=${encodeURIComponent(csvPath)}` : "/buffett/run"),

  rebalancing: () => get<RebalancingDiff | null>("/rebalancing/diff"),
};
