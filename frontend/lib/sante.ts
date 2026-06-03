/**
 * Client API + types pour le module Sante / Nutrition.
 *
 * Endpoints sous /sante/* (cf. backend/app/api/routes_sante.py).
 */

import { api } from "./api";

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

export type NutritionGoalUpdate = Partial<
  Omit<NutritionGoal, "id" | "date_set" | "actif">
>;

export type TargetsResponse = {
  date: string;
  poids: number;
  intensity: string;
  intensity_was_default: boolean;
  base_targets: Record<string, number>;
  targets: Record<string, number>;
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

/** Préfixe une URL media relative (/media/sante/...) avec la base backend. */
export function mediaUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";
  return `${base}${path}`;
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

export const santeApi = {
  listMesures: (days = 180) =>
    api<MesureSante[]>(`/sante/mesures?days=${days}`),

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
    fetch(
      `${process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000"}/sante/mesures/${date}`,
      { method: "DELETE" },
    ).then((r) => {
      if (!r.ok) throw new Error(`Delete failed: ${r.status}`);
    }),

  listAliments: () => api<Aliment[]>(`/sante/aliments`),

  // Favoris d'aliments — saisie rapide (#64)
  listFavorites: () => api<{ favorites: string[] }>(`/sante/favorites`).then((r) => r.favorites),
  addFavorite: (nom: string) =>
    api<{ favorites: string[] }>(`/sante/favorites?nom=${encodeURIComponent(nom)}`, { method: "POST" }).then((r) => r.favorites),
  removeFavorite: (nom: string) =>
    api<{ favorites: string[] }>(`/sante/favorites?nom=${encodeURIComponent(nom)}`, { method: "DELETE" }).then((r) => r.favorites),

  // Hydratation (#66)
  waterToday: () => api<{ date: string; eau_ml: number; cible_ml: number; pct: number }>(`/sante/water/today`),
  addWater: (ml: number) =>
    api<{ date: string; eau_ml: number; cible_ml: number; pct: number }>(`/sante/water?ml=${ml}`, { method: "POST" }),

  // Sommeil (#68)
  logSleep: (heures: number, qualite?: number) =>
    api<{ date: string; sommeil_h: number; sommeil_q?: number }>(
      `/sante/sleep?heures=${heures}${qualite != null ? `&qualite=${qualite}` : ""}`, { method: "POST" }),
  sleepSummary: (days = 30) =>
    api<{ n: number; correlation: number | null; sommeil_moyen_h: number | null }>(`/sante/sleep/summary?days=${days}`),

  // Qualité nutritionnelle hebdo (#65)
  weeklyQuality: (days = 7) =>
    api<WeeklyQuality>(`/sante/quality/weekly?days=${days}`),

  // Bilan énergétique + alerte déficit/surplus agressif (#70)
  energyBalance: (days = 7) =>
    api<EnergyBalance>(`/sante/energy/balance?days=${days}`),

  // Calories dépensées en séance — intégration Entraînement (#67)
  workoutBurn: (date?: string) =>
    api<WorkoutBurn>(`/sante/workout-burn${date ? `?date=${date}` : ""}`),

  // Photos de progression avant/après (#69)
  listPhotos: () => api<ProgressPhoto[]>(`/sante/photos`),
  uploadPhoto: (file: File, date?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    const base = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";
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
};

// ─────────────────────────────────────────────────────────────────────────────
// Helpers UI
// ─────────────────────────────────────────────────────────────────────────────

export const MACRO_KEYS = ["Calories", "Protéines", "Lipides", "Glucides", "Fibres"] as const;
export type MacroKey = typeof MACRO_KEYS[number];

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
