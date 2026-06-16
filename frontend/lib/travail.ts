// Types + client API pour le module Travail (proxy Next -> backend)
const BASE = "/api/travail";

async function json<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const body = await r.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(`API ${r.status} ${detail}`);
  }
  return r.json() as Promise<T>;
}

export interface WorkShift {
  id: number;
  date_jour: string;
  heure_debut: string;
  heure_fin: string;
  pause_min: number;
  taux_horaire?: number | null;
  role: string;
  statut: "prevu" | "fait" | "annule";
  note?: string | null;
  heures?: number;
}

export interface TravailSummary {
  mois: string;
  taux_horaire_defaut: number;
  nb_shifts: number;
  heures_faites: number;
  heures_prevues: number;
  revenu_realise: number;
  revenu_prevu: number;
}

export const travailApi = {
  shifts: (mois?: string): Promise<WorkShift[]> =>
    fetch(`${BASE}/shifts${mois ? `?mois=${mois}` : ""}`).then((r) => json<WorkShift[]>(r)),
  summary: (mois: string): Promise<TravailSummary> =>
    fetch(`${BASE}/summary?mois=${mois}`).then((r) => json<TravailSummary>(r)),
  settings: (): Promise<{ taux_horaire: number }> =>
    fetch(`${BASE}/settings`).then((r) => json<{ taux_horaire: number }>(r)),
  setTauxHoraire: (taux_horaire: number): Promise<{ taux_horaire: number }> =>
    fetch(`${BASE}/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ taux_horaire }),
    }).then((r) => json<{ taux_horaire: number }>(r)),
  create: (data: Partial<WorkShift>): Promise<WorkShift> =>
    fetch(`${BASE}/shifts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => json<WorkShift>(r)),
  update: (id: number, data: Partial<WorkShift>): Promise<WorkShift> =>
    fetch(`${BASE}/shifts/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => json<WorkShift>(r)),
  remove: (id: number): Promise<Response> => fetch(`${BASE}/shifts/${id}`, { method: "DELETE" }),
};
