/**
 * Client API + types pour le module Sante / Nutrition.
 *
 * Endpoints sous /sante/* (cf. backend/app/api/routes_sante.py).
 */

import { api } from "./api";
import { getApiBaseUrl, proxyApiUrl } from "./env";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export type MesureSante = {
  id: number;
  date: string; // YYYY-MM-DD
  poids: number | null;
  photo_url: string | null;
  note: string | null;
  extra: Record<string, unknown> | null;
};

export type MesureSanteCreate = {
  date: string;
  poids?: number | null;
  photo_url?: string | null;
  note?: string | null;
  extra?: Record<string, unknown> | null;
};

export type Aliment = {
  id: number;
  nom: string;
  proprietes: Record<string, number>;
};

export type ScoreDay = {
  date: string;
  score: number | null;
  composantes: { sommeil: number | null; sport: number | null; nutrition: number | null };
  details: {
    sommeil_h: number | null;
    sessions_7j: number;
    kcal_consommees: number | null;
    kcal_cible: number | null;
  };
};
export type ScorePoint = { date: string; score: number | null };

/** `exclus` = composantes du score (sommeil/sport/nutrition), volontairement
 *  hors corrélations : les corréler au score qu'elles calculent serait circulaire. */
export type ScoreCorrelation = {
  source: "score";
  cible: string;
  r: number | null;
  n: number;
  force: string;
  signe: string;
};
export type ScoreCorrelations = {
  caveat: string;
  jours: number;
  exclus: string[];
  correlations: ScoreCorrelation[];
};

export type NutritionGoal = {
  id: number;
  date_set: string;
  poids_cible: number | null;
  body_fat_target_pct: number | null;
  date_cible: string | null;
  type: string;
  surplus_kcal_sport: number;
  rest_factor: number;
  sport_days: number[];
  actif: boolean;
  note: string | null;
};

export type NutritionGoalUpdate = Partial<Omit<NutritionGoal, "id" | "date_set" | "actif">>;

export type TargetsResponse = {
  date: string;
  poids: number;
  intensity: string;
  intensity_was_default: boolean;
  base_targets: Record<string, number>;
  targets: Record<string, number>;
  day_context?: DayContext | null;
};

export type DayContext = {
  source: string;
  workout_intensity?: string;
  agenda_intensity?: string;
  scheduled_minutes?: number;
  weighted_minutes?: number;
  categories_minutes?: Record<string, number>;
};

export type PlanItem = {
  aliment: string;
  quantite_g: number;
  quantite_str: string;
  calories: number;
  proteines: number;
  lipides: number;
  glucides: number;
  prix: number;
};

export type PlanResponse = {
  date: string;
  poids_used: number;
  intensite: string;
  intensity_was_default: boolean;
  base_targets: Record<string, number>;
  targets: Record<string, number>;
  items: PlanItem[];
  totals: Record<string, number>;
  consumed: Record<string, number> | null;
  warning: string | null;
  budget_max_daily: number;
  day_context?: DayContext | null;
  pricing_context?: {
    store: string;
    includes_flyer: boolean;
    matched_foods: number;
    fallback?: string | null;
  } | null;
};

export type PlanGenerateRequest = {
  date?: string;
  poids?: number;
  intensity?: string;
  budget_max_daily?: number;
  force?: boolean;
};

export type WeightTrend = {
  days: number;
  slope_kg_per_day: number;
  slope_kg_per_week: number;
  last_weight: number;
  samples: number;
};

export type ProjectionResponse = {
  target_weight: number;
  current_weight: number;
  delta_kg: number;
  days_to_target: number | null;
  target_date: string | null;
  slope_kg_per_week: number;
  confidence: string;
  note: string;
  trend_7d: WeightTrend | null;
  trend_30d: WeightTrend | null;
};

export type WeeklyQuality = {
  days: number;
  score: number | null;
  daily: { date: string; score: number; criteria: Record<string, number> }[];
  criteria_avg?: Record<string, number>;
  worst: string | null;
  best: string | null;
};

export type EnergyBalance = {
  days: number;
  avg_balance: number | null;
  avg_consumed?: number;
  avg_maintenance?: number;
  level: "ok" | "warning" | "alert";
  direction: "déficit" | "surplus" | null;
  message: string | null;
};

export type ProgressPhoto = {
  date: string;
  photo_url: string;
  poids: number | null;
};

/** Préfixe une URL media relative avec le proxy de même origine. */
export function mediaUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  return proxyApiUrl(path);
}

export type WorkoutBurn = {
  date: string;
  total_kcal: number;
  kcal_muscu: number;
  kcal_cardio: number;
  available: boolean;
};

// ─────────────────────────────────────────────────────────────────────────────
// Endpoints
// ─────────────────────────────────────────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────────
// Fenêtre batch-cook (poids lun/jeu → plan fenêtre + liste de courses Super C)
// ─────────────────────────────────────────────────────────────────────────────

export type ShoppingItem = {
  aliment: string;
  quantite_g: number;
  prix: number | null;
  promo: boolean;
  dispo_g?: number | null;
  a_acheter_g?: number | null;
  product_id?: string | null;
  product_name?: string | null;
  href?: string | null;
  format?: string | null;
  qty?: number;
  prix_unitaire?: number | null;
  prix_verifie?: boolean;
};
export type FenetrePlanItem = {
  aliment: string;
  quantite_g: number;
  quantite_str: string;
  calories: number;
  proteines: number;
  lipides: number;
  glucides: number;
  prix: number;
};
export type FenetreDayPlan = {
  date: string;
  intensite: string;
  items: FenetrePlanItem[];
  totals: Record<string, number>;
  targets?: Record<string, number>;
  repas_travail?: { name: string; price: number; credit_couvert: number; reste_a_payer: number; items: { name: string; price: number }[]; calories: number; proteines: number; glucides: number; lipides: number; micros?: Record<string, number>; micros_estimes?: boolean; description: string }[];
};
export type FenetreScore = {
  couverture_moyenne: number;
  pct_micros_atteints: number;
  equilibre_macros?: number;
  equilibre_moyen?: number;
  cout_total: number;
  cout_optimise?: number;
  cout_a_payer: number;
  ratio: number;
  sous_couverts: string[];
};
// `shopping_date` : jour des courses/cuisine — lundi pour la fenêtre lun-mer,
// mercredi (veille) pour la fenêtre jeu-dim, afin de capter le rabais étudiant
// Super C (lun→mer). Optionnel : les réponses d'avant ce champ restent valides.
export type WindowPlanResponse = {
  anchor_date: string;
  shopping_date?: string | null;
  length: number;
  poids_used: number;
  jours: FenetreDayPlan[];
  shopping_list: ShoppingItem[];
  score: FenetreScore;
  warning: string | null;
};
export type FenetreGenerateJob = {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  message: string;
  anchor_date: string | null;
  error: string | null;
  created?: boolean;
  stop_requested?: boolean;
  stopped?: boolean;
  attempt?: number;
  max_attempts?: number | null;
  solutions_found?: number;
  pareto_solutions?: number;
  stagnation?: number;
  patience?: number;
  convergence?: number;
  temperature?: number | null;
  best_ratio?: number | null;
  best_coverage?: number | null;
  best_cost?: number | null;
  best_items?: { aliment: string; quantite_g: number }[];
  phase?: "search" | "simplification";
  prune_attempt?: number;
  prune_total?: number;
  removed_foods?: string[];
};
export type CartPlanItem = {
  aliment: string;
  product_id: string | null;
  product_name: string | null;
  href: string | null;
  format: string | null;
  qty: number;
  prix_estime: number | null;
  a_verifier: boolean;
  promo?: boolean;
};
export type CartPlanResponse = { anchor_date: string; items: CartPlanItem[]; total_estime: number };
export type CartFillResult = {
  aliment: string;
  product_name: string | null;
  requested_qty: number;
  added_qty: number;
  a_verifier: boolean;
  status: "added" | "already_present" | "not_found" | "failed";
  message: string;
};
export type CartFillJob = {
  job_id: string;
  anchor_date: string;
  status: "queued" | "running" | "awaiting_user" | "completed" | "failed";
  message: string;
  current: number;
  total: number;
  results: CartFillResult[];
  error: string | null;
  created?: boolean;
};

export const santeApi = {
  refreshStorePricingIfStale: () =>
    api<{ started: boolean }>(`/sante/store-pricing/refresh-if-stale`, { method: "POST" }),

  listMesures: (days = 180) => api<MesureSante[]>(`/sante/mesures?days=${days}`),

  upsertMesure: (payload: MesureSanteCreate) =>
    api<MesureSante>(`/sante/mesures`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateMesure: (date: string, payload: Partial<MesureSanteCreate>) =>
    api<MesureSante>(`/sante/mesures/${date}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  deleteMesure: (date: string) =>
    fetch(`${getApiBaseUrl()}/sante/mesures/${date}`, { method: "DELETE" }).then((r) => {
      if (!r.ok) throw new Error(`Delete failed: ${r.status}`);
    }),

  listAliments: () => api<Aliment[]>(`/sante/aliments`),

  // Score de forme (sommeil + sport + nutrition)
  score: () => api<ScoreDay>(`/sante/score`),
  scoreHistory: (days = 90) =>
    api<{ days: number; points: ScorePoint[] }>(`/sante/score/history?days=${days}`),
  scoreCorrelations: (jours = 90) =>
    api<ScoreCorrelations>(`/sante/score/correlations?jours=${jours}`),

  // Favoris d'aliments — saisie rapide (#64)
  listFavorites: () => api<{ favorites: string[] }>(`/sante/favorites`).then((r) => r.favorites),
  addFavorite: (nom: string) =>
    api<{ favorites: string[] }>(`/sante/favorites?nom=${encodeURIComponent(nom)}`, {
      method: "POST",
    }).then((r) => r.favorites),
  removeFavorite: (nom: string) =>
    api<{ favorites: string[] }>(`/sante/favorites?nom=${encodeURIComponent(nom)}`, {
      method: "DELETE",
    }).then((r) => r.favorites),

  // Hydratation (#66)
  waterToday: () =>
    api<{ date: string; eau_ml: number; cible_ml: number; pct: number }>(`/sante/water/today`),
  addWater: (ml: number) =>
    api<{ date: string; eau_ml: number; cible_ml: number; pct: number }>(`/sante/water?ml=${ml}`, {
      method: "POST",
    }),

  // Sommeil (#68)
  logSleep: (heures: number, qualite?: number) =>
    api<{ date: string; sommeil_h: number; sommeil_q?: number }>(
      `/sante/sleep?heures=${heures}${qualite != null ? `&qualite=${qualite}` : ""}`,
      { method: "POST" },
    ),
  sleepSummary: (days = 30) =>
    api<{ n: number; correlation: number | null; sommeil_moyen_h: number | null }>(
      `/sante/sleep/summary?days=${days}`,
    ),

  // Qualité nutritionnelle hebdo (#65)
  weeklyQuality: (days = 7) => api<WeeklyQuality>(`/sante/quality/weekly?days=${days}`),

  // Bilan énergétique + alerte déficit/surplus agressif (#70)
  energyBalance: (days = 7) => api<EnergyBalance>(`/sante/energy/balance?days=${days}`),

  // Calories dépensées en séance — intégration Entraînement (#67)
  workoutBurn: (date?: string) =>
    api<WorkoutBurn>(`/sante/workout-burn${date ? `?date=${date}` : ""}`),

  // Photos de progression avant/après (#69)
  listPhotos: () => api<ProgressPhoto[]>(`/sante/photos`),
  uploadPhoto: (file: File, date?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    const base = getApiBaseUrl();
    return fetch(`${base}/sante/photo${date ? `?date=${date}` : ""}`, {
      method: "POST",
      body: fd,
    }).then((r) => {
      if (!r.ok) throw new Error(`Upload failed: ${r.status}`);
      return r.json() as Promise<MesureSante>;
    });
  },

  getGoal: () => api<NutritionGoal>(`/sante/goal`),
  updateGoal: (payload: NutritionGoalUpdate) =>
    api<NutritionGoal>(`/sante/goal`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  getTargets: (params?: { date?: string; poids?: number; intensity?: string }) => {
    const q = new URLSearchParams();
    if (params?.date) q.set("date", params.date);
    if (params?.poids !== undefined) q.set("poids", String(params.poids));
    if (params?.intensity) q.set("intensity", params.intensity);
    const qs = q.toString();
    return api<TargetsResponse>(`/sante/targets/today${qs ? "?" + qs : ""}`);
  },

  generatePlan: (payload: PlanGenerateRequest = {}) =>
    api<PlanResponse>(`/sante/plan/generate`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getPlanToday: () => api<PlanResponse>(`/sante/plan/today`),
  getPlan: (date: string) => api<PlanResponse>(`/sante/plan/${date}`),

  patchPlan: (
    date: string,
    payload: {
      quantites?: Record<string, number>;
      consumed?: Record<string, number>;
      consumed_grams?: Record<string, number>;
      warning?: string;
    },
  ) =>
    api<PlanResponse>(`/sante/plan/${date}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  getProjection: (target_weight?: number) => {
    const qs = target_weight !== undefined ? `?target_weight=${target_weight}` : "";
    return api<ProjectionResponse>(`/sante/projection${qs}`);
  },

  // Fenêtre batch-cook
  fenetreCurrent: (date?: string) =>
    api<WindowPlanResponse>(
      `/sante/fenetre/current${date ? `?date=${encodeURIComponent(date)}` : ""}`,
      {
        timeoutMs: 60_000,
      },
    ),
  generateFenetre: (body: {
    date?: string;
    poids?: number;
    force?: boolean;
    refresh_prices?: boolean;
  }) =>
    api<WindowPlanResponse>(`/sante/fenetre/generate`, {
      method: "POST",
      body: JSON.stringify(body),
      // L'optimisation SLSQP (6 balayages prix sur le vrai catalogue) dure ~15-25 s,
      // davantage si un scrape Super C tourne encore. L'ancien plafond de 60 s était
      // trop juste : la requête était annulée alors que le serveur répondait ~60,1 s.
      timeoutMs: 180000,
    }),
  // Génération en tâche de fond : depuis l'élargissement du catalogue aux
  // produits Super C, une optimisation dure ~2 min (mesuré 127 s sur 400
  // aliments présélectionnés). Le mode synchrone ci-dessus tient encore sous
  // les 180 s, mais la marge est trop mince pour en dépendre.
  startGenerateFenetre: (body: {
    date?: string;
    poids?: number;
    force?: boolean;
    refresh_prices?: boolean;
  }) =>
    api<FenetreGenerateJob>(`/sante/fenetre/generate-async`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  generateFenetreStatus: (jobId: string) =>
    api<FenetreGenerateJob>(`/sante/fenetre/generate/${encodeURIComponent(jobId)}`),
  activeGenerateFenetre: () => api<FenetreGenerateJob | null>(`/sante/fenetre/generate-active`),
  stopGenerateFenetre: (jobId: string) =>
    api<FenetreGenerateJob>(`/sante/fenetre/generate/${encodeURIComponent(jobId)}/stop`, {
      method: "POST",
    }),
  cartPlan: (date?: string) =>
    api<CartPlanResponse>(
      `/sante/fenetre/cart-plan${date ? `?date=${encodeURIComponent(date)}` : ""}`,
      {
        timeoutMs: 60_000,
      },
    ),
  startCartFill: (date?: string) =>
    api<CartFillJob>(`/sante/fenetre/cart-fill${date ? `?date=${encodeURIComponent(date)}` : ""}`, {
      method: "POST",
    }),
  cartFillStatus: (jobId: string) =>
    api<CartFillJob>(`/sante/fenetre/cart-fill/${encodeURIComponent(jobId)}`),
};

// ─────────────────────────────────────────────────────────────────────────────
// Helpers UI
// ─────────────────────────────────────────────────────────────────────────────

export const MACRO_KEYS = ["Calories", "Protéines", "Lipides", "Glucides", "Fibres"] as const;
export type MacroKey = (typeof MACRO_KEYS)[number];

export const MACRO_UNITS: Record<string, string> = {
  Calories: "kcal",
  Protéines: "g",
  Lipides: "g",
  Glucides: "g",
  Fibres: "g",
  Sodium_Max: "mg",
  Cholesterol_Max: "mg",
  Sucres_Max: "g",
  Prix_Max: "CAD",
  Magnésium: "mg",
  Omega3: "g",
  Calcium: "mg",
  Fer: "mg",
  Zinc: "mg",
  Potassium: "mg",
  Phosphore: "mg",
  Chlorure: "mg",
  Cuivre: "mg",
  Iode: "µg",
  Manganèse: "mg",
  Sélénium: "µg",
  VitA: "µg",
  VitB1: "mg",
  VitB2: "mg",
  VitB3: "mg",
  VitB5: "mg",
  VitB6: "mg",
  VitB9: "µg",
  VitB12: "µg",
  VitC: "mg",
  VitD: "µg",
  VitE: "mg",
  VitK: "µg",
};

export const INTENSITY_LABELS: Record<string, string> = {
  none: "Repos",
  low: "Léger",
  medium: "Modéré",
  high: "Intense",
};

export function todayKey(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
