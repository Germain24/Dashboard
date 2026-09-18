/**
 * Client API + types pour le module Agenda (CONV 5).
 * Endpoints sous /agenda/* (cf. backend/app/api/routes_agenda.py).
 */

import { api } from "./api";
import { proxyApiUrl } from "./env";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export type Evenement = {
  id: number | null; // null = occurrence virtuelle (récurrence ou entraînement)
  titre: string;
  debut: string; // ISO datetime
  fin: string | null;
  lieu: string | null;
  description: string | null;
  source: string | null;
  source_id: string | null;
  categorie: string | null; // "cours" | "travail" | "sport" | "rdv" | "autre"
  couleur: string | null;
  recurrence_id: number | null;
  is_virtual: boolean;
};

export type EvenementCreate = {
  titre: string;
  debut: string;
  fin?: string | null;
  lieu?: string | null;
  description?: string | null;
  source?: string;
  categorie?: string | null;
  couleur?: string | null;
  recurrence_id?: number | null;
};

export type EvenementUpdate = Partial<EvenementCreate>;

export type RegleRecurrence = {
  id: number;
  titre: string;
  weekdays: number[]; // 0=Lun…6=Dim
  start_time: string; // "HH:MM"
  end_time: string;
  lieu: string | null;
  description: string | null;
  categorie: string | null;
  couleur: string | null;
  until: string | null; // YYYY-MM-DD
  created_at: string;
};

export type RegleRecurrenceCreate = {
  titre: string;
  weekdays: number[];
  start_time: string;
  end_time: string;
  lieu?: string | null;
  description?: string | null;
  categorie?: string | null;
  couleur?: string | null;
  until?: string | null;
};

export type Tache = {
  id: number;
  titre: string;
  deadline: string | null; // YYYY-MM-DD
  priorite: number; // 1=haute…5=basse
  statut: "todo" | "done";
  duree_estimee_min: number | null;
  note: string | null;
  categorie: string | null;
  source: string | null;
  created_at: string;
};

export type TacheCreate = {
  titre: string;
  deadline?: string | null;
  priorite?: number;
  duree_estimee_min?: number | null;
  note?: string | null;
  categorie?: string | null;
};

export type SlotLibre = {
  debut: string;
  fin: string;
  duree_min: number;
};

export type AgendaJour = {
  date: string;
  evenements: Evenement[];
  seance_entrainement: Evenement | null;
  slots_libres: SlotLibre[];
  taches_urgentes: Tache[];
};

export type IcalSourceStatus = {
  configured: boolean;
  enabled: boolean;
  label: string;
  last_sync_at: string | null;
  last_error: string | null;
  created_events: number;
  updated_events: number;
  skipped_duplicates: number;
};

export type IcalImportCounts = {
  created_events: number;
  updated_events: number;
  deleted_events: number;
  skipped_duplicates: number;
  created_rules: number;
};

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

export const CATEGORIE_COLORS: Record<string, string> = {
  cours: "#3B82F6", // bleu
  travail: "#8B5CF6", // violet
  sport: "#F59E0B", // amber
  rdv: "#10B981", // vert
  autre: "#6B7280", // gris
};

export function couleurFor(ev: Evenement): string {
  if (ev.couleur) return ev.couleur;
  if (ev.categorie && CATEGORIE_COLORS[ev.categorie]) return CATEGORIE_COLORS[ev.categorie];
  return "#6B7280";
}

export function formatHeure(iso: string): string {
  return new Date(iso).toLocaleTimeString("fr-CA", { hour: "2-digit", minute: "2-digit" });
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-CA", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// API calls
// ─────────────────────────────────────────────────────────────────────────────

export async function fetchToday(): Promise<AgendaJour> {
  return api<AgendaJour>("/agenda/today");
}

export async function fetchEvents(from?: string, to?: string): Promise<Evenement[]> {
  const params = new URLSearchParams();
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  params.set("include_training", "true");
  return api<Evenement[]>(`/agenda/events?${params}`);
}

/** Statut de l'intégration Google Calendar OAuth (#83). */
export async function gcalStatus(): Promise<{ configured: boolean; calendar_id: string }> {
  return api(`/agenda/gcal/status`);
}

/** Import des événements Google Calendar via OAuth (Google → app, #83). */
export async function gcalPull(from?: string, to?: string): Promise<IcalImportCounts> {
  const q = new URLSearchParams();
  if (from) q.set("from", from);
  if (to) q.set("to", to);
  return api(`/agenda/gcal/pull?${q}`, { method: "POST" });
}

/** Pousse un événement local vers Google Calendar (app → Google, #83). */
export async function gcalPush(eventId: number): Promise<Evenement> {
  return api<Evenement>(`/agenda/gcal/push/${eventId}`, { method: "POST" });
}

/** Sync entrante via URL .ics distante (Google Calendar, #83). */
export async function syncIcalUrl(url: string): Promise<IcalImportCounts> {
  return api("/agenda/sync-ical-url", { method: "POST", body: JSON.stringify({ url }) });
}

export async function fetchIcalSource(): Promise<IcalSourceStatus> {
  return api<IcalSourceStatus>("/agenda/ical-source");
}

export async function saveIcalSource(url: string, label = "7shifts"): Promise<IcalSourceStatus> {
  return api<IcalSourceStatus>("/agenda/ical-source", {
    method: "PUT",
    body: JSON.stringify({ url, label }),
  });
}

export async function removeIcalSource(): Promise<IcalSourceStatus> {
  return api<IcalSourceStatus>("/agenda/ical-source", { method: "DELETE" });
}

export async function syncIcalSource(): Promise<IcalImportCounts> {
  return api<IcalImportCounts>("/agenda/ical-source/sync", { method: "POST" });
}

export async function replanWeeklyRevisions(date?: string): Promise<{ message: string }> {
  const query = date ? `?date=${encodeURIComponent(date)}` : "";
  return api<{ message: string }>(`/agenda/revisions/replan${query}`, { method: "POST" });
}

function addOptionalParam(
  params: URLSearchParams,
  key: string,
  value: string | number | null | undefined,
) {
  if (value) params.set(key, String(value));
}

/** Planifie un bloc focus Études dans un créneau libre (#89). */
export async function planFocus(params: {
  duree_min?: number;
  date?: string;
  titre?: string;
  cours?: string;
}): Promise<Evenement> {
  const q = new URLSearchParams();
  addOptionalParam(q, "duree_min", params.duree_min);
  addOptionalParam(q, "date", params.date);
  addOptionalParam(q, "titre", params.titre);
  addOptionalParam(q, "cours", params.cours);
  return api<Evenement>(`/agenda/focus?${q}`, { method: "POST" });
}

/** URL de téléchargement .ics de la fenêtre donnée (#91). */
export function exportIcsUrl(from?: string, to?: string): string {
  const params = new URLSearchParams();
  addOptionalParam(params, "from", from);
  addOptionalParam(params, "to", to);
  const qs = params.toString();
  return proxyApiUrl(`/agenda/export-ical${qs ? "?" + qs : ""}`);
}

/** Événements en conflit avec [debut, fin) côté serveur (#87). */
export async function checkConflicts(
  debut: string,
  fin?: string,
  ignoreId?: number,
): Promise<Evenement[]> {
  const params = new URLSearchParams({ debut });
  if (fin) params.set("fin", fin);
  if (ignoreId != null) params.set("ignore_id", String(ignoreId));
  return api<Evenement[]>(`/agenda/events/conflicts?${params}`);
}

/**
 * Repère les chevauchements parmi une liste d'événements (logique locale #87).
 * Retourne l'ensemble des ids (ou clés début) qui chevauchent un autre événement.
 */
export function overlappingKeys(events: Evenement[]): Set<string> {
  const spans = events.map((event) => eventSpan(event, eventKey));
  const out = new Set<string>();
  for (let i = 0; i < spans.length; i++) {
    for (let j = i + 1; j < spans.length; j++) {
      if (overlaps(spans[i], spans[j])) {
        out.add(spans[i].key);
        out.add(spans[j].key);
      }
    }
  }
  return out;
}

const eventKey = (event: Evenement) =>
  event.id != null ? String(event.id) : event.debut + "|" + event.titre;

const overlaps = (left: { start: number; end: number }, right: { start: number; end: number }) =>
  left.start < right.end && right.start < left.end;

function eventSpan(event: Evenement, keyOf: (event: Evenement) => string) {
  const start = new Date(event.debut).getTime();
  const end = event.fin ? new Date(event.fin).getTime() : start + 3600_000;
  return { key: keyOf(event), start, end };
}

export async function createEvent(data: EvenementCreate): Promise<Evenement> {
  return api<Evenement>("/agenda/events", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateEvent(id: number, data: EvenementUpdate): Promise<Evenement> {
  return api<Evenement>(`/agenda/events/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteEvent(id: number): Promise<void> {
  await api(`/agenda/events/${id}`, { method: "DELETE" });
}

export async function fetchRecurrences(): Promise<RegleRecurrence[]> {
  return api<RegleRecurrence[]>("/agenda/recurrences");
}

export async function createRecurrence(data: RegleRecurrenceCreate): Promise<RegleRecurrence> {
  return api<RegleRecurrence>("/agenda/recurrences", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteRecurrence(id: number): Promise<void> {
  await api(`/agenda/recurrences/${id}`, { method: "DELETE" });
}

export async function fetchTasks(statut?: string): Promise<Tache[]> {
  const params = statut ? `?statut=${statut}` : "";
  return api<Tache[]>(`/agenda/tasks${params}`);
}

export async function createTask(data: TacheCreate): Promise<Tache> {
  return api<Tache>("/agenda/tasks", { method: "POST", body: JSON.stringify(data) });
}

export async function markTaskDone(id: number): Promise<Tache> {
  return api<Tache>(`/agenda/tasks/${id}/done`, { method: "POST" });
}

export async function deleteTask(id: number): Promise<void> {
  await api(`/agenda/tasks/${id}`, { method: "DELETE" });
}

export async function fetchSlots(date: string, minDuration = 60): Promise<SlotLibre[]> {
  return api<SlotLibre[]>(`/agenda/slots?date=${date}&min_duration=${minDuration}`);
}

// ─────────────────────────────────────────────────────────────────────────────
// Planificateur automatique (#planner — cf. spec 2026-06-04)
// ─────────────────────────────────────────────────────────────────────────────

export type PlanBloc = {
  date: string; // YYYY-MM-DD
  debut: string; // ISO datetime
  fin: string;
  type: string; // sommeil | repas | cuisine | revision | sport
  titre: string;
};

export type PlanProposition = {
  fenetre: { debut: string; fin: string };
  blocs: PlanBloc[];
  non_places: string[];
};

/** Calcule le planning du cycle (lecture seule). `date` = jour de lancement. */
export async function planPreview(date?: string): Promise<PlanProposition> {
  return api<PlanProposition>(`/agenda/plan/preview${date ? `?date=${date}` : ""}`);
}

/** Valide : écrit les blocs planner du cycle dans l'agenda (idempotent). */
export async function planCommit(date?: string): Promise<PlanProposition & { created: number }> {
  return api(`/agenda/plan/commit${date ? `?date=${date}` : ""}`, { method: "POST" });
}

/** Pousse les blocs planner du cycle vers Google Calendar (#83). */
export async function planPush(date?: string): Promise<{ pushed: number }> {
  return api(`/agenda/plan/push${date ? `?date=${date}` : ""}`, { method: "POST" });
}

/** Couleur d'un type de bloc (aligné sur TYPE_META côté backend). */
export const PLAN_TYPE_COLOR: Record<string, string> = {
  sommeil: "#6366F1",
  repas: "#14B8A6",
  cuisine: "#16A34A",
  revision: "#2563EB",
  sport: "#F59E0B",
};
