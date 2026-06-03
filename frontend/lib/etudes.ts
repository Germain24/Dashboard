// Types + client API typé pour le module Études

export interface Cours {
  id: number;
  code: string;
  nom: string;
  semestre: string;
  credits: number;
  prof?: string;
  local?: string;
  note_finale?: number;
  lettre?: string;
  points_gpa?: number;
  total_minutes_etude?: number;
  actif: boolean;
  note?: string;
  created_at: string;
  updated_at: string;
}

export interface CoursCreate {
  code: string;
  nom: string;
  semestre: string;
  credits?: number;
  prof?: string;
  local?: string;
  note?: string;
}

export interface Evaluation {
  id: number;
  cours_id: number;
  titre: string;
  type_eval: string;
  date_limite?: string;
  note_obtenue?: number;
  note_max?: number;
  jours_restants?: number;
  note?: string;
  created_at: string;
  updated_at: string;
}

export interface EvaluationCreate {
  cours_id: number;
  titre: string;
  type_eval?: string;
  date_limite?: string;
  note_obtenue?: number;
  note_max?: number;
  note?: string;
}

export interface SessionEtude {
  id: number;
  cours_id?: number;
  date: string;
  duree_min: number;
  sujet?: string;
  note?: string;
  created_at: string;
}

export interface CoursGrade {
  cours_id: number;
  code: string;
  nom: string;
  semestre: string;
  note_finale?: number;
  lettre?: string;
  points_gpa?: number;
}

export interface GpaResult {
  semestre?: string;
  nb_cours: number;
  nb_cours_notes: number;
  gpa?: number;
  detail: CoursGrade[];
}

const BASE = "/api/etudes";

// ── Cours ────────────────────────────────────────────────────────

export async function fetchCours(params?: { semestre?: string; actif?: boolean }): Promise<Cours[]> {
  const q = new URLSearchParams();
  if (params?.semestre) q.set("semestre", params.semestre);
  if (params?.actif !== undefined) q.set("actif", String(params.actif));
  const r = await fetch(`${BASE}/cours?${q}`);
  if (!r.ok) throw new Error("Erreur chargement cours");
  return r.json();
}

export async function createCours(data: CoursCreate): Promise<Cours> {
  const r = await fetch(`${BASE}/cours`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!r.ok) throw new Error("Erreur création cours");
  return r.json();
}

export async function patchCours(id: number, data: Partial<Cours>): Promise<Cours> {
  const r = await fetch(`${BASE}/cours/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!r.ok) throw new Error("Erreur mise à jour cours");
  return r.json();
}

export async function deleteCours(id: number): Promise<void> {
  await fetch(`${BASE}/cours/${id}`, { method: "DELETE" });
}

// ── Évaluations ──────────────────────────────────────────────────

export async function fetchEvaluations(coursId: number, upcomingOnly = false): Promise<Evaluation[]> {
  const q = upcomingOnly ? "?upcoming_only=true" : "";
  const r = await fetch(`${BASE}/cours/${coursId}/evaluations${q}`);
  if (!r.ok) throw new Error("Erreur chargement évaluations");
  return r.json();
}

export async function fetchDeadlines(days = 30): Promise<Evaluation[]> {
  const r = await fetch(`${BASE}/deadlines?days=${days}`);
  if (!r.ok) throw new Error("Erreur chargement deadlines");
  return r.json();
}

export async function createEvaluation(data: EvaluationCreate): Promise<Evaluation> {
  const r = await fetch(`${BASE}/evaluations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!r.ok) throw new Error("Erreur création évaluation");
  return r.json();
}

export async function patchEvaluation(id: number, data: Partial<Evaluation>): Promise<Evaluation> {
  const r = await fetch(`${BASE}/evaluations/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!r.ok) throw new Error("Erreur mise à jour évaluation");
  return r.json();
}

export async function deleteEvaluation(id: number): Promise<void> {
  await fetch(`${BASE}/evaluations/${id}`, { method: "DELETE" });
}

// ── GPA ──────────────────────────────────────────────────────────

export async function fetchGpa(semestre?: string): Promise<GpaResult> {
  const q = semestre ? `?semestre=${semestre}` : "";
  const r = await fetch(`${BASE}/gpa${q}`);
  if (!r.ok) throw new Error("Erreur chargement GPA");
  return r.json();
}

// ── Sessions d'étude ─────────────────────────────────────────────

export async function fetchSessions(coursId?: number): Promise<SessionEtude[]> {
  const q = coursId ? `?cours_id=${coursId}` : "";
  const r = await fetch(`${BASE}/sessions${q}`);
  if (!r.ok) throw new Error("Erreur chargement sessions");
  return r.json();
}

export async function createSession(data: { cours_id?: number; duree_min: number; sujet?: string; note?: string }): Promise<SessionEtude> {
  const r = await fetch(`${BASE}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!r.ok) throw new Error("Erreur création session");
  return r.json();
}

export async function deleteSession(id: number): Promise<void> {
  await fetch(`${BASE}/sessions/${id}`, { method: "DELETE" });
}

// ── Statistiques & objectif (#94/#95/#97/#101/#102) ─────────────────

export interface EtudesStats {
  days: number;
  by_course: { cours_id: number | null; label: string; minutes: number }[];
  daily: Record<string, number>;
  streak: { current: number; best: number };
  weekly: {
    week_start: string;
    week_end: string;
    total_minutes: number;
    sessions: number;
    by_course: { cours_id: number | null; label: string; minutes: number }[];
  };
  goal: { weekly_hours: number; done_hours: number; progress_pct: number };
}

export async function fetchEtudesStats(days = 120): Promise<EtudesStats> {
  const r = await fetch(`${BASE}/stats?days=${days}`);
  if (!r.ok) throw new Error("Erreur chargement stats");
  return r.json();
}

export async function setEtudesGoal(weeklyHours: number): Promise<{ weekly_hours: number }> {
  const r = await fetch(`${BASE}/goal?weekly_hours=${weeklyHours}`, { method: "PUT" });
  if (!r.ok) throw new Error("Erreur enregistrement objectif");
  return r.json();
}
