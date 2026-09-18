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

export type PatrimoineGoalId = "liberte_financiere" | "japon";

export interface PatrimoineGoal {
  id: PatrimoineGoalId;
  label: string;
  objectif_eur: number;
  valeur_eur: number;
  progression_pct: number;
  restant_eur: number;
  atteint: boolean;
  echeance: string | null;
  jours_restants: number | null;
  epargne_journaliere_eur: number | null;
}

export interface ObjectifsPatrimoine {
  objectifs: PatrimoineGoal[];
}

export interface PatrimoineGoalPatch {
  id: PatrimoineGoalId;
  objectif_eur: number;
  echeance?: string;
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

export type TransactionType =
  | "achat"
  | "vente"
  | "dividende"
  | "interet"
  | "depot"
  | "retrait"
  | "frais";

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
  investi_total: number;
  valeur_totale: number;
  pl_realise: number;
  pl_latent_total: number;
  pl_total: number;
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
  display_name?: string;
  score?: number;
  buffett_rules_score?: number | null;
  buffett_quality_score?: number | null;
  score_confidence_pct?: number | null;
  durability_score?: number | null;
  financial_moat_proxy_score?: number | null;
  dilution_discipline_score?: number | null;
  resilience_score?: number | null;
  score_comparable_to_standard?: boolean | null;
  score_model_version?: number | null;
  score_business_model?: string | null;
  score_model_fit?: number | null;
  score_model_status?: string | null;
  score_model_complete?: boolean | null;
  score_comparison_group?: string | null;
  score_scoring_template?: string | null;
  score_confidence_breakdown?: {
    model_fit?: number;
    confidence_before_fit_pct?: number;
    confidence_final_pct?: number;
    families?: Record<string, {
      score?: number;
      coverage_pct?: number;
      historical_depth_pct?: number;
      model_fit?: number;
      confidence_before_fit_pct?: number;
      confidence_pct?: number;
      history_years?: number;
    }>;
  } | null;
  eligible_for_purchase?: boolean;
  purchase_ineligibility_reasons?: string[];
  score_versions?: {
    quality?: string | null;
    durability?: string | null;
    moat_proxy?: string | null;
  } | null;
  company_id?: string | null;
  company_listings?: string[];
  fundamental_mismatch?: boolean;
  secteur?: string;
  pays?: string;
  allocation_pct?: number;
  broker_cible?: string;
  allocations?: BuffettAllocationLine[] | null;
}

export interface BuffettWorldScenario {
  minimum_world_weight: number;
  world_tickers: string[];
  score: number;
  allocation: Array<Record<string, unknown>>;
  diagnostics: Record<string, unknown>;
}

export interface BuffettScoreCalibrationSummary {
  count: number;
  percentiles?: Record<"p50" | "p75" | "p90" | "p95" | "p99", number>;
  thresholds_pct?: Record<"gte_80" | "gte_85" | "gte_90" | "gte_95", number>;
}

export interface BuffettRunDetail {
  run: BuffettRunOut;
  top_results: BuffettResultOut[];
  allocation_cible: BuffettResultOut[];
  buy_signal?: {
    model_version: number;
    method: string;
    percentile: number;
    min_sector_size: number;
    accepted: number;
    excluded_missing_peg: number;
    missing_quality_total?: number;
    missing_quality_accepted?: number;
    missing_quality_excluded?: number;
    n_instruments: number;
    global: {
      per_max: number | null;
      peg_max: number | null;
      n_per: number;
      n_peg: number;
    };
    sectors: Record<
      string,
      {
        // per_max/peg_max gardent leur nom mais portent le seuil des DEUX axes du
        // profil du secteur (P/FFO, PER normalisé, PEG dividende, P/B÷ROE...).
        per_max: number | null;
        peg_max: number | null;
        source: "sector" | "global";
        n_per: number;
        n_peg: number;
        profile?: string;
        profile_fallback?: string | null;
        coverage?: number;
        value_metric?: string;
        quality_metric?: string;
        value_metric_label?: string;
        quality_metric_label?: string;
      }
    >;
  };
  optimization?: {
    schema_version: number;
    seed: number;
    n_sim: number;
    n_search: number;
    constraints_relaxed: boolean;
    world_scenarios?: {
      active: "free" | "world_25" | "world_40" | "world_55";
      unavailable_reason?: string;
      free?: BuffettWorldScenario;
      world_25?: BuffettWorldScenario;
      world_40?: BuffettWorldScenario;
      world_55?: BuffettWorldScenario;
    };
    best_action_candidate?: {
      found: boolean;
      unit: string;
      score?: number;
      score_gap_to_unrestricted?: number;
      action_weight?: number;
      action_count?: number;
      action_tickers?: string[];
      search_objective_score?: number;
      selection_is_constrained?: boolean;
    };
    benchmark_relative?: {
      ticker: string;
      annual_return_pct: number;
      cvar_pct: number;
      downside_deviation_pct: number;
      search_objective_score?: number;
      validation_objective_score?: number;
      validation_gap?: number;
      stability?: "stable" | "attention" | "instable";
      elite_count?: number;
      selected_rank?: number;
    };
    sector_constraints?: {
      max_sector_pct: number;
      exempt_diversified_etfs: boolean;
      exposures: Record<string, number>;
      cash_weight: number;
      compliant: boolean;
      downside_risk?: {
        method: string;
        max_risk_share: number;
        max_risk_share_overrides?: Record<string, number>;
        penalty_coefficient: number;
        penalty_coefficient_overrides?: Record<string, number>;
        objective_penalty_points: number;
        budget_exceeded: boolean;
        unclassified_assets_in_total_risk: boolean;
        sectors: Record<
          string,
          {
            weight: number;
            cvar_contribution: number;
            downside_deviation_contribution: number;
            composite_risk_contribution: number;
            risk_share: number;
            risk_budget?: number;
            risk_budget_excess: number;
          }
        >;
      };
      country_diversification?: {
        method: string;
        exposures: Record<string, Record<string, number>>;
        score: number;
        objective_bonus_points: number;
        bonus_cap_points?: number;
        bonus_sature?: boolean;
        applied_after_hard_caps: boolean;
        disabled_by_sector_risk?: boolean;
        disabled_sectors_by_risk?: string[];
        deficit_penalty_points?: number;
        effective_country_targets?: Record<string, number>;
      };
      post_discretization?: {
        exposures: Record<string, number>;
        cash_weight: number;
        compliant: boolean;
      };
    };
    /** Ventilation du score retenu : quel terme coûte combien de points. */
    score_breakdown?: {
      unit: string;
      terms: Record<string, number>;
      total_penalty: number;
      idle_cash_weight: number;
      dominant_term: string;
    };
    /** Axe géographique, symétrique de `sector_constraints`. */
    country_constraints?: {
      hard_cap_enabled?: boolean;
      max_country_pct: number | null;
      exposures: Record<string, number>;
      compliant: boolean;
      downside_risk?: {
        method: string;
        max_risk_share: number;
        penalty_coefficient: number;
        budget_exceeded: boolean;
        unclassified_assets_in_total_risk: boolean;
        countries: Record<
          string,
          {
            weight: number;
            cvar_contribution: number;
            downside_deviation_contribution: number;
            composite_risk_contribution: number;
            risk_share: number;
            risk_budget_excess: number;
          }
        >;
      };
    };
    region_constraints?: {
      hard_cap_enabled: boolean;
      max_region_pct?: number;
      exposures: Record<string, number>;
      compliant?: boolean;
      downside_risk: {
        method: string;
        max_risk_share: number;
        penalty_coefficient: number;
        budget_exceeded: boolean;
        unclassified_assets_in_total_risk: boolean;
        regions: Record<
          string,
          {
            weight: number;
            cvar_contribution: number;
            downside_deviation_contribution: number;
            composite_risk_contribution: number;
            risk_share: number;
            risk_budget_excess: number;
          }
        >;
      };
    };
    economic_action_concentration?: {
      descriptive_only?: boolean;
      coverage_weight: number;
      threshold: number;
      penalty_coefficient: number;
      objective_penalty_points: number;
      hhi: number;
      effective_actions: number;
      largest_action: string | null;
      largest_action_weight: number;
      actions: Record<string, number>;
    };
    unknown_equity_composition?: {
      method: "descriptive_weighted_residual";
      descriptive_only: boolean;
      actual_weight: number;
      by_ticker: Record<
        string,
        {
          portfolio_weight: number;
          unknown_fraction: number;
          unknown_contribution: number;
        }
      >;
    };
    selected_etf_exposures?: Record<string, {
      portfolio_weight: number;
      countries: Record<string, number>;
      source: string;
    }>;
    direct_action_policy?: {
      enabled: boolean;
      mandatory?: boolean;
      minimum_weight: number;
      minimum_lines: number;
      eligible_action_candidates: number;
      actual_weight: number;
      actual_lines: number;
      quality_bonus_max_points: number;
      quality_bonus_points: number;
    };
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
      next_rebalance_cost_eur?: number;
      next_rebalance_cost_pct?: number;
      first_year_cost_eur?: number;
      first_year_cost_pct?: number;
      annualized_cost_eur: number;
      annualized_cost_pct: number;
      rebalances_per_year: number;
      trade_cost_multiplier: number;
      current_positions_source?: string;
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
      search_sample?: {
        n_sim: number;
        counts: Record<string, number>;
        stratified: boolean;
        seed: number;
      };
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
      brokers: Record<
        string,
        {
          candidates_before: number;
          selected: number;
          removed: number;
          bucket_counts: Record<string, number>;
        }
      >;
    };
    classification_filter?: {
      score_calibration?: {
        score: string;
        global: BuffettScoreCalibrationSummary;
        by_business_model: Record<string, BuffettScoreCalibrationSummary>;
      };
      fundamental_mismatch?: { count: number; tickers: string[]; purchase_blocking: boolean };
      excluded_products?: { reason: string; count: number; tickers: string[] };
      replication_enrichment?: {
        total: number;
        known_before: number;
        unknown_before: number;
        resolved_now: number;
        unknown_after: number;
        broker_priority?: {
          available_unknown: number;
          available_resolved_now: number;
        };
        statuses: Record<string, number>;
        error?: string;
      };
    };
    economic_composition_filter?: {
      quality_reference_coverage: number;
      descriptive_only: boolean;
      excluded_for_economic_coverage: number;
      replaced_during_selection?: number;
      replaced_tickers: string[];
      coverage_by_ticker: Record<string, number>;
      quality_by_ticker: Record<
        string,
        {
          eligible: boolean;
          reason: string;
          coverage: number;
          joint_coverage: number;
          source: string;
          replication: string;
          provider?: string;
          index?: string;
          index_id?: string;
          provider_index_id?: string;
          index_source_url?: string;
          as_of?: string;
          index_status?: string;
          index_error?: string;
          enrichment_errors?: Array<{ stage: string; type: string; message: string }>;
          proxy_ticker?: string;
          proxy_isin?: string;
          proxy_source_url?: string;
          proxy_warning?: string;
        }
      >;
      index_resolution?: {
        checked_etfs: number;
        identified_indices: number;
        official_compositions: number;
        physical_tracker_proxies?: number;
        unresolved_count: number;
        status_counts: Record<string, number>;
        reason_counts: Record<string, number>;
        provider_counts: Record<string, number>;
        unresolved_reason_counts?: Record<string, number>;
        unresolved_status_counts?: Record<string, number>;
        unresolved: Array<{
          ticker: string;
          replication: string;
          index: string;
          index_id: string;
          provider: string;
          status: string;
          error: string;
          source_url: string;
          reason: string;
          pipeline_errors: Array<{ stage: string; type: string; message: string }>;
        }>;
      };
      replacement_search?: {
        rounds: number;
        max_rounds: number | null;
        truncated: boolean;
        unverified_count: number;
        unverified_tickers: string[];
      };
      broker_verification?: Record<
        string,
        {
          target: number;
          verified: number;
          shortage: number;
          rejected: number;
          rejected_tickers: string[];
          catalog_candidates?: number;
          rejected_by_reason?: Record<string, number>;
        }
      >;
    };
    termination: {
      reason: string;
      max_seeds: number | null;
      seeds_run: number;
      stagnation_streak: number;
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

export interface BuffettEquityLookthrough {
  version: number;
  run_id: number;
  generated_at: string;
  total_pct: number;
  known_pct: number;
  other_pct: number;
  coverage_pct: number;
  equity_coverage_pct: number;
  known_equities_pct: number;
  other_equities_pct: number;
  unknown_pct: number;
  non_equity_pct: number;
  known_bonds_pct: number;
  other_non_equity_pct: number;
  rows: Array<{
    ticker: string;
    name: string;
    weight_pct: number;
    sources: string[];
    is_other: boolean;
    asset_type: "action" | "obligation" | "other";
    country?: string;
    maturity_bucket?: string;
  }>;
  etfs: Array<{
    ticker: string;
    name: string;
    portfolio_weight_pct: number;
    holdings_coverage_pct: number;
    known_holdings: number;
    residual_pct: number;
    source: string;
    replication: string;
    index: string;
    status: "complete" | "partial" | "unavailable" | "non_equity";
  }>;
}

export interface BuffettProgress {
  run_id?: number;
  statut: string;
  progress_pct: number;
  n_done?: number;
  n_total?: number;
  active: boolean; // true = une analyse tourne reellement (sinon en_cours = interrompu)
  paused_until?: number | null; // epoch (s) de reprise estimee si en pause (plafond API)
  phase: string;
  throughput_per_min: number;
  eta_seconds?: number | null;
  cache_hits: number;
  error_counts: Record<string, number>;
  catalog_version?: string | null;
  already_completed: number;
  session_processed: number;
  unique_instruments?: number;
  secondary_quotes_skipped?: number;
  propagated_quotes?: number;
  http_requests?: number;
  http_requests_per_hour?: number;
  deferred_rate_limits?: number;
}

export interface OptimizationProgress {
  active: boolean;
  status: "idle" | "running" | "stopping" | "stopped" | "completed" | "error";
  termination_reason?: string | null;
  phase: "idle" | "preparation" | "initialisation" | "optimisation" | "finalisation";
  seed_num: number;
  completed_seeds?: number;
  iteration: number;
  total_iterations: number;
  initialization_attempt: number;
  initialization_max: number;
  convergence: number;
  progress_pct: number;
  message: string;
  run_id: number | null;
  optimization_id: string | null;
  optimization_started_at: number | null;
  stop_requested: boolean;
  best_score: number | null;
  seed_score?: number | null;
  temperature?: number | null;
  phase_done?: number;
  phase_total?: number;
  current_item?: string;
  last_activity_at?: number | null;
  seconds_since_activity?: number;
  stalled?: boolean;
  score_history?: Array<{
    iteration: number;
    seed_num: number;
    seed_iteration: number;
    score: number;
    global_best_score?: number;
    temperature?: number;
    forced_labels?: string[];
    forced_action_count?: number;
    forced_etf_count?: number;
  }>;
}

export interface BuffettLiveState {
  analysis: BuffettProgress;
  optimization: OptimizationProgress;
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

async function responseDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return typeof body?.detail === "string" ? body.detail : "";
  } catch {
    return "";
  }
}

async function responseError(response: Response): Promise<Error> {
  const detail = await responseDetail(response);
  return new Error(detail || `${response.status} ${response.statusText}`);
}

type GetOptions = {
  timeoutMs?: number;
  retries?: number;
  noStore?: boolean;
};

function isAbortError(error: unknown): boolean {
  return (error as { name?: string })?.name === "AbortError";
}

function timeoutError(cause: unknown): Error {
  return new Error("Le service Finance met trop de temps à répondre.", { cause });
}

function isRetryable(error: unknown, attempt: number, retries: number): boolean {
  return (
    attempt < retries &&
    (error as Error & { retryable?: boolean })?.retryable !== false
  );
}

function retryDelay(attempt: number): Promise<void> {
  return new Promise((resolve) => globalThis.setTimeout(resolve, 500 * 2 ** attempt));
}

async function fetchWithTimeout(path: string, options: GetOptions): Promise<Response> {
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? GET_TIMEOUT_MS,
  );
  try {
    return await fetch(`${BASE}${path}`, {
      signal: controller.signal,
      cache: options.noStore ? "no-store" : undefined,
    });
  } finally {
    globalThis.clearTimeout(timeout);
  }
}

function normalizeFetchError(error: unknown): unknown {
  return isAbortError(error) ? timeoutError(error) : error;
}

async function fetchGetResponse(path: string, options: GetOptions): Promise<Response> {
  try {
    return await fetchWithTimeout(path, options);
  } catch (error) {
    throw normalizeFetchError(error);
  }
}

async function fetchGetAttempt<T>(path: string, options: GetOptions): Promise<T> {
  const response = await fetchGetResponse(path, options);
  if (!response.ok) {
    const error = await responseError(response);
    (error as Error & { retryable?: boolean }).retryable = response.status >= 500;
    throw error;
  }
  return response.json();
}

async function getWithRetry<T>(
  path: string,
  options: GetOptions,
  attempt: number,
  retries: number,
): Promise<T> {
  try {
    return await fetchGetAttempt<T>(path, options);
  } catch (error) {
    if (!isRetryable(error, attempt, retries)) throw error;
    await retryDelay(attempt);
    return getWithRetry<T>(path, options, attempt + 1, retries);
  }
}

async function get<T>(path: string, options: GetOptions = {}): Promise<T> {
  const retries = Math.max(0, options.retries ?? 0);
  return getWithRetry<T>(path, options, 0, retries);
}

export interface PageResult<T> {
  items: T[];
  total: number;
}

async function fetchPage(path: string): Promise<Response> {
  const controller = new AbortController();
  const timeout = globalThis.setTimeout(() => controller.abort(), GET_TIMEOUT_MS);
  try {
    const response = await fetch(`${BASE}${path}`, { signal: controller.signal });
    if (!response.ok) throw await responseError(response);
    return response;
  } catch (error) {
    if (isAbortError(error)) throw timeoutError(error);
    throw error;
  } finally {
    globalThis.clearTimeout(timeout);
  }
}

async function getPage<T>(path: string): Promise<PageResult<T>> {
  const response = await fetchPage(path);
  const items = (await response.json()) as T[];
  const parsedTotal = Number(response.headers.get("X-Total-Count"));
  return { items, total: Number.isFinite(parsedTotal) ? parsedTotal : items.length };
}

function pagePath(path: string, params: { ticker?: string; limit: number; offset: number }): string {
  const query = new URLSearchParams({ limit: String(params.limit), offset: String(params.offset) });
  if (params.ticker) query.set("ticker", params.ticker);
  return `${path}?${query.toString()}`;
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
    return getPage<TransactionOut>(pagePath("/transactions", { ticker, limit, offset }));
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
  buffettEquityLookthrough: (id: number, refresh = false) =>
    get<BuffettEquityLookthrough>(
      `/buffett/runs/${id}/equity-lookthrough${refresh ? "?refresh=true" : ""}`,
      // Une première décomposition peut télécharger plusieurs milliers de
      // constituants (notamment pour TOPIX/MSCI World). Le délai HTTP général
      // de 30 s faisait échouer la demande côté navigateur alors que le
      // backend poursuivait correctement le calcul; le composant repassait
      // alors silencieusement sur l'onglet ETF.
      { timeoutMs: 120_000, retries: 1 },
    ),
  selectBuffettScenario: (id: number, scenario: "free" | "world_25" | "world_40" | "world_55") =>
    put<{ run_id: number; active_scenario: string }>(`/buffett/runs/${id}/active-scenario`, {
      scenario,
    }),
  buffettDeleteRun: (id: number) => del(`/buffett/runs/${id}`),
  buffettLatest: () => get<BuffettRunOut | null>("/buffett/latest"),
  buffettProgress: () => get<BuffettProgress>("/buffett/progress"),
  buffettLiveState: (historyAfter = 0) =>
    get<BuffettLiveState>(
      `/buffett/live-state?history_after=${Math.max(0, Math.trunc(historyAfter))}`,
      // Le polling suivant constitue déjà le retry. Retenter une même requête
      // expirée multipliait les appels encore actifs dans le proxy/backend et
      // pouvait saturer le pool de workers après un simple F5.
      { timeoutMs: 5_000, retries: 0, noStore: true },
    ),
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
      volatility_pct: number;
      semi_deviation_pct: number;
      omega: number | null;
      tickers: string[];
      comparisons: Record<
        string,
        {
          rendement_pct: number;
          cagr_pct: number;
          max_drawdown_pct: number;
          cvar_5_pct: number;
          turnover: number;
          costs_pct: number;
          n_points: number;
          volatility_pct: number;
          semi_deviation_pct: number;
          omega: number | null;
        }
      >;
      scenario_series: Record<string, { dates: string[]; equity: number[] }>;
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
      lignes: {
        date: string;
        ticker: string;
        montant: number;
        montant_brut: number;
        retenue_source: number;
        devise: string;
      }[];
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
  portfolioCreate: (minScore = 80, includeEtfs = true) =>
    post<{ message: string; status: string; run_id: number }>(
      `/portfolio/create?min_score=${minScore}&include_etfs=${includeEtfs}`,
    ),
  /** Progression de l'optimisation DE (barre de chargement du bouton 3) */
  portfolioProgress: (historyAfter?: number) =>
    get<OptimizationProgress>(
      historyAfter == null
        ? "/portfolio/progress"
        : `/portfolio/progress?history_after=${Math.max(0, Math.trunc(historyAfter))}`,
    ),
  /** Arrête l'optimisation DE en cours (run auto ou bouton manuel) */
  optimizationStop: () => post<{ message: string }>("/buffett/optimization/stop"),

  // Rebalancing
  rebalancing: () => get<RebalancingDiff | null>("/rebalancing/diff"),

  // Objectif patrimoine
  objectifPatrimoine: () => get<ObjectifsPatrimoine>("/objectif-patrimoine"),
  setObjectifPatrimoine: (goal: PatrimoineGoalPatch) =>
    post<ObjectifsPatrimoine>("/objectif-patrimoine", goal),

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
    Object.entries(params).forEach(([key, value]) => {
      if (value != null) q.set(key, String(value));
    });
    return get<CalculImpots>(`/impots/calcul?${q.toString()}`);
  },
  ventesImpots: (params: { annee?: number; broker?: string } = {}) => {
    const q = new URLSearchParams(
      Object.entries(params)
        .filter(([, value]) => value != null)
        .map(([key, value]) => [key, String(value)]),
    );
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
