/**
 * Client API + types pour le module Agenda (CONV 5).
 * Endpoints sous /agenda/* (cf. backend/app/api/routes_agenda.py).
 */

import { api } from "./api";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export type Evenement = {
  id: number | null;        // null = occurrence virtuelle (récurrence ou entraînement)
  titre: string;
  debut: string;            // ISO datetime
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
  weekdays: number[];       // 0=Lun…6=Dim
  start_time: string;       // "HH:MM"
  end_time: string;
  lieu: string | null;
  description: string | null;
  categorie: string | null;
  couleur: string | null;
  until: string | null;     // YYYY-MM-DD
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
  deadline: string | null;  // YYYY-MM-DD
  priorite: number;         // 1=haute…5=basse
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

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

export const CATEGORIE_COLORS: Record<string, string> = {
  cours:   "#3B82F6", // bleu
  travail: "#8B5CF6", // violet
  sport:   "#F59E0B", // amber
  rdv:     "#10B981", // vert
  autre:   "#6B7280", // gris
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
    weekday: "long", day: "numeric", month: "long",
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

/** Événements en conflit avec [debut, fin) côté serveur (#87). */
export async function checkConflicts(debut: string, fin?: string, ignoreId?: number): Promise<Evenement[]> {
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
  const keyOf = (e: Evenement) => (e.id != null ? String(e.id) : e.debut + "|" + e.titre);
  const spans = events.map((e) => {
    const start = new Date(e.debut).getTime();
    const end = e.fin ? new Date(e.fin).getTime() : start + 3600_000;
    return { key: keyOf(e), start, end };
  });
  const out = new Set<string>();
  for (let i = 0; i < spans.length; i++) {
    for (let j = i + 1; j < spans.length; j++) {
      if (spans[i].start < spans[j].end && spans[j].start < spans[i].end) {
        out.add(spans[i].key);
        out.add(spans[j].key);
      }
    }
  }
  return out;
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

export async function fetchSlots(
  date: string,
  minDuration = 60,
): Promise<SlotLibre[]> {
  return api<SlotLibre[]>(`/agenda/slots?date=${date}&min_duration=${minDuration}`);
}
