/**
 * Client API + types pour le module Entraînement.
 *
 * Endpoints sous /entrainement/* (cf. backend/app/api/routes_entrainement.py).
 */

import { api } from "./api";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export type Exercice = {
  id: number;
  nom: string;
  categorie: string;
  muscles: string[];
  type_mouvement: string;
  unilateral: boolean;
  source: string;
  note: string | null;
};

export type ExerciceCreate = {
  nom: string;
  categorie: string;
  muscles?: string[];
  type_mouvement?: string;
  unilateral?: boolean;
  source?: string;
  note?: string | null;
};

export type ProgrammeJour = {
  id: number;
  weekday: number;
  label: string;
  slots: Record<string, unknown>[];
};

export type Programme = {
  id: number;
  nom: string;
  description: string | null;
  actif: boolean;
  jours: ProgrammeJour[];
};

export type SetSerie = {
  id: number;
  seance_id: number;
  exercice_id: number;
  ordre: number;
  reps: number;
  poids_kg: number;
  rpe: number | null;
  echec: boolean;
};

export type SetSerieCreate = {
  exercice_id: number;
  reps: number;
  poids_kg: number;
  rpe?: number | null;
  echec?: boolean;
  ordre?: number | null;
};

export type Seance = {
  id: number;
  date: string; // ISO datetime
  type: string | null;
  duree_min: number | null;
  note: string | null;
  programme_jour_id: number | null;
  intensite: string | null;
  source: string;
  sets: SetSerie[];
  tonnage_kg: number;
};

export type SeanceCreate = {
  date?: string;
  type?: string | null;
  duree_min?: number | null;
  note?: string | null;
  programme_jour_id?: number | null;
  intensite?: string | null;
  source?: string;
  sets?: SetSerieCreate[];
};

export type ProgressionPoint = {
  date: string;
  best_1rm_kg: number;
  volume_kg: number;
  top_set_kg: number;
  nb_sets: number;
};

export type ProgressionResponse = {
  exercice_id: number;
  nom: string;
  points: ProgressionPoint[];
  current_1rm_kg: number;
  best_1rm_kg: number;
  delta_4w_pct: number | null;
};

export type MuscleVolume = {
  muscle: string;
  sets: number;
  tonnage_kg: number;
  status: "sous" | "optimal" | "sur";
};

export type WeekPoint = {
  semaine: string;
  tonnage_kg: number;
  seances: number;
  poids_kg: number | null;
};

export type TrainingCorrelation = {
  weeks: WeekPoint[];
  correlation: number | null;
  n: number;
};

export type CourseCardio = {
  id: number;
  date: string;
  distance_km: number;
  duree_sec: number;
  pace_sec_per_km: number | null;
  pace_str: string | null;
  note: string | null;
  source: string;
};

export type CourseCardioCreate = {
  date: string;
  distance_km: number;
  duree_sec: number;
  note?: string | null;
  source?: string;
};

export type IntensityResponse = {
  date: string;
  intensity: "none" | "low" | "medium" | "high";
};

export type SlotToday = {
  label: string;
  note: string | null;
  sets_target: number | null;
  reps_target: number | string | null;
  charge_indicative_kg: number | null;
  exercice_id: number | null;
  categorie: string | null;
  poids_suggere_kg: number | null;
  derniere_fois: { date: string; resume: string } | null;
};

export type TodayResponse = {
  date: string;
  weekday: number;
  jour_label: string;
  programme_jour_id: number | null;
  slots: SlotToday[];
  seance_en_cours: Seance | null;
  kcal_estimees: number;
  poids_corps_kg: number;
};

export type CaloriesDayResponse = {
  date: string;
  kcal_muscu: number;
  kcal_cardio: number;
  total_kcal: number;
  poids_corps_kg: number;
};

// ─────────────────────────────────────────────────────────────────────────────
// Endpoints
// ─────────────────────────────────────────────────────────────────────────────

export const entrainementApi = {
  // Exercices
  listExercices: (categorie?: string) =>
    api<Exercice[]>(
      `/entrainement/exercises${categorie ? `?categorie=${encodeURIComponent(categorie)}` : ""}`,
    ),
  createExercice: (payload: ExerciceCreate) =>
    api<Exercice>(`/entrainement/exercises`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  patchExercice: (id: number, payload: Partial<ExerciceCreate>) =>
    api<Exercice>(`/entrainement/exercises/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  // Programme
  getProgram: () => api<Programme>(`/entrainement/program`),
  patchProgram: (payload: { nom?: string; description?: string }) =>
    api<Programme>(`/entrainement/program`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  patchProgramJour: (
    weekday: number,
    payload: { label?: string; slots?: Record<string, unknown>[] },
  ) =>
    api<ProgrammeJour>(`/entrainement/program/jours/${weekday}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  // Séances
  listSessions: (params?: { from?: string; to?: string }) => {
    const q = new URLSearchParams();
    if (params?.from) q.set("from", params.from);
    if (params?.to) q.set("to", params.to);
    const qs = q.toString();
    return api<Seance[]>(`/entrainement/sessions${qs ? "?" + qs : ""}`);
  },
  createSession: (payload: SeanceCreate) =>
    api<Seance>(`/entrainement/sessions`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getSession: (id: number) => api<Seance>(`/entrainement/sessions/${id}`),
  patchSession: (id: number, payload: Partial<SeanceCreate>) =>
    api<Seance>(`/entrainement/sessions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteSession: (id: number) =>
    fetch(
      `${process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000"}/entrainement/sessions/${id}`,
      { method: "DELETE" },
    ).then((r) => {
      if (!r.ok) throw new Error(`Delete failed: ${r.status}`);
    }),
  addSet: (seance_id: number, payload: SetSerieCreate) =>
    api<SetSerie>(`/entrainement/sessions/${seance_id}/sets`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteSet: (seance_id: number, set_id: number) =>
    fetch(
      `${process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000"}/entrainement/sessions/${seance_id}/sets/${set_id}`,
      { method: "DELETE" },
    ).then((r) => {
      if (!r.ok) throw new Error(`Delete failed: ${r.status}`);
    }),

  // Progression / 1RM
  getProgression: (exercice_id: number, days = 90) =>
    api<ProgressionResponse>(
      `/entrainement/progression/${exercice_id}?days=${days}`,
    ),
  getOneRM: (exercice_id: number) =>
    api<{ exercice_id: number; nom: string; current_1rm_kg: number; formula: string }>(
      `/entrainement/1rm/${exercice_id}`,
    ),
  getMuscleVolume: (days = 7) =>
    api<MuscleVolume[]>(`/entrainement/volume/muscles?days=${days}`),
  getCorrelation: (weeks = 12) =>
    api<TrainingCorrelation>(`/entrainement/correlation?weeks=${weeks}`),

  // Cardio
  listCardio: (params?: { from?: string; to?: string }) => {
    const q = new URLSearchParams();
    if (params?.from) q.set("from", params.from);
    if (params?.to) q.set("to", params.to);
    const qs = q.toString();
    return api<CourseCardio[]>(`/entrainement/cardio${qs ? "?" + qs : ""}`);
  },
  createCardio: (payload: CourseCardioCreate) =>
    api<CourseCardio>(`/entrainement/cardio`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteCardio: (id: number) =>
    fetch(
      `${process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000"}/entrainement/cardio/${id}`,
      { method: "DELETE" },
    ).then((r) => {
      if (!r.ok) throw new Error(`Delete failed: ${r.status}`);
    }),

  // Intensité (consommé par Santé en interne, exposé ici pour debug UI)
  getIntensityForDate: (date: string) =>
    api<IntensityResponse>(`/entrainement/intensity/${date}`),
  getIntensityToday: () =>
    api<IntensityResponse>(`/entrainement/intensity/today`),

  // Vue "Aujourd'hui" — séance opérationnelle du jour
  getToday: () => api<TodayResponse>(`/entrainement/today`),

  // Calories par date (consommé par CONV nutrition future)
  getCaloriesForDate: (date: string) =>
    api<CaloriesDayResponse>(`/entrainement/calories/${date}`),
};

// ─────────────────────────────────────────────────────────────────────────────
// Helpers UI
// ─────────────────────────────────────────────────────────────────────────────

export const INTENSITY_LABELS: Record<string, string> = {
  none: "Repos",
  low: "Léger",
  medium: "Modéré",
  high: "Intense",
};

export const WEEKDAY_LABELS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];
export const WEEKDAY_LABELS_FULL = [
  "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche",
];

export const CATEGORIE_LABELS: Record<string, string> = {
  push: "Push",
  pull: "Pull",
  legs: "Jambes",
  upper: "Upper",
  lower: "Lower",
  core: "Gainage",
  cardio: "Cardio",
};

export function formatPaceFromSeconds(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.round(sec - m * 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function todayKey(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
