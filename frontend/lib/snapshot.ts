const BASE = '/api/automatisations'

export type WellbeingScore = {
  score: number
  components: {
    habitudes: number
    humeur: number
    nutrition: number
    entrainement: number
  }
  label: string
  date: string
}

export type SnapshotData = {
  date: string
  habitudes?: { done: number; total: number; pct: number }
  budget?: { nb_transactions: number; depenses_total: number; revenus_total: number }
  sante?: { poids?: number; calories?: number }
  humeur?: { valeur: number; energie: number }
  entrainement?: { nb_seances: number; tonnage_kg: number }
  agenda?: { nb_evenements: number }
}

export type Snapshot = { date: string; data: SnapshotData; cached?: boolean }

export type RoutineTemplate = {
  id: string
  name: string
  description: string
  trigger_type: string
  trigger_value: string
  actions: object[]
}

const json = (r: Response) => r.json()

export const fetchSnapshots = (days = 30): Promise<Snapshot[]> =>
  fetch(`${BASE}/snapshot?days=${days}`).then(json)

export const fetchSnapshot = (date: string): Promise<Snapshot> =>
  fetch(`${BASE}/snapshot/${date}`).then(json)

export type EnergyBudget = {
  date: string;
  energie_ressentie: number | null;
  n_activites: number;
  capacite: number;
  cout_prevu: number;
  restant: number;
  statut: "ok" | "serré" | "dépassé";
};
export const fetchEnergyBudget = (): Promise<EnergyBudget> =>
  fetch(`${BASE}/energy`).then(json);

export const fetchWellbeing = (date?: string): Promise<WellbeingScore> => {
  const qs = date ? `?date=${date}` : ''
  return fetch(`${BASE}/wellbeing${qs}`).then(json)
}

export const fetchTemplates = (): Promise<RoutineTemplate[]> =>
  fetch(`${BASE}/templates`).then(json)

export const activateTemplate = (id: string) =>
  fetch(`${BASE}/templates/${id}/activate`, { method: 'POST' }).then(json)

export const fetchVacationMode = (): Promise<{ mode_vacances: boolean }> =>
  fetch(`${BASE}/vacances`).then(json)

export const setVacationMode = (enabled: boolean): Promise<{ mode_vacances: boolean }> =>
  fetch(`${BASE}/vacances?enabled=${enabled}`, { method: 'POST' }).then(json)
