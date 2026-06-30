/**
 * Client API + types pour le module Garde-robe.
 *
 * Endpoints sous /garderobe/* (cf. backend/app/api/routes_garderobe.py).
 */

import { api } from "./api";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export type Vetement = {
  id: string;
  nom: string;
  marque: string | null;
  categorie: string;
  sous_categorie: string | null;
  matiere: string | null;
  couleur: string | null;
  type_objectif: string | null;
  temp_min: number | null;
  temp_max: number | null;
  etat_propre: number | null;
  usure_max: number | null;
  portes: number;
  impermeable: boolean;
  style: string[] | null;
  extra: Record<string, unknown> | null;
  // Champs derives
  proprete_pct: number;
  vie_pct: number;
  needs_wash: boolean;
  is_worn_out: boolean;
  ports_avant_lavage: number;
  thermal_score: number;
  saison: string;
  entretien: CareLabel | null;
};

export type CareLabel = {
  matiere: string | null;
  lavage: string;
  temperature: number;
  sechage: string;
  icones: string;
  delicat: boolean;
  resume: string;
};

export type VetementUpdate = Partial<Omit<Vetement, "id" | "proprete_pct" | "vie_pct" | "needs_wash" | "is_worn_out" | "ports_avant_lavage" | "thermal_score" | "saison" | "entretien">>;

export type HourlyTemp = { hour: number; temp: number; apparent_temp: number };

export type Weather = {
  temp: number;
  feels: number;
  temp_min: number;
  temp_max: number;
  humidity: number;
  wind: number;
  precip: number;
  desc: string;
  icon: string;
  source: string;
  pluie: boolean;
  snow: boolean;
  mean_window_temp: number;
  hour_window: [number, number];
  hourly: HourlyTemp[];
};

export type SlotInfo = {
  id: string;
  emoji: string;
  categories: string[];
  need: "ALWAYS" | "METEO" | "OPTIONAL";
  trigger?: string | null;
};

export type OutfitSlot = { slot_id: string; vetement: Vetement | null };

export type SuggestResponse = {
  slots: OutfitSlot[];
  use_body: boolean;
  target_thermal: number;
  total_thermal: number;
  style_score: number;
  mean_temp: number;
  weather: Weather;
};

export type ValiderItemUpdate = {
  id: string;
  nom: string;
  portes: number;
  needs_wash: boolean;
  ports_avant_lavage: number;
  vie_pct: number;
};

export type ValiderResponse = {
  history_id: number;
  updates: ValiderItemUpdate[];
};

export type TenueHistory = {
  id: number;
  date: string;
  tenue: Record<string, string | null>;
  ids: Record<string, string | null>;
  note: string | null;
};

export type CountEntry = { label: string; count: number };

export type StatsResponse = {
  total: number;
  par_categorie: CountEntry[];
  par_couleur: CountEntry[];
  par_style: CountEntry[];
  a_laver: Vetement[];
  hs: Vetement[];
  color_ratio: { Neutre: number; Secondaire: number; Accent: number };
  valeur_estimee: number;
  valeur_count: number;
};

export type Recommendation = {
  nom: string;
  raison: string;
  potentiel: number;
  type: string;
};

export type PlannerEvent = { titre: string; categorie: string | null; heure: string };
export type PlannerDay = {
  date: string;
  weekday: number;
  tenue: Record<string, Vetement | null>;
  events: PlannerEvent[];
};
export type WeekPlan = { start: string; days: PlannerDay[] };

export type WearFrequency = {
  total: number;
  never_worn_count: number;
  never_worn: Vetement[];
  least_worn: Vetement[];
  most_worn: Vetement[];
};

export type Emplacement = {
  statut: "rempli" | "vide";
  vetement_id: string | null;
  vetement_nom: string | null;
  marque: string | null;
  position: number | null; // 0..100, null si vide ou hors échelle
  hors_echelle: boolean;
};

export type ObjectifTypeOut = {
  nom: string;
  ordre: number;
  quantite_objectif: number;
  echelle: string[];
  rempli: number;
  emplacements: Emplacement[];
  excedent: Emplacement[];
};

export type ObjectifResponse = {
  total_emplacements: number;
  total_remplis: number;
  types: ObjectifTypeOut[];
};

// ─────────────────────────────────────────────────────────────────────────────
// Endpoints
// ─────────────────────────────────────────────────────────────────────────────

export const garderobeApi = {
  listVetements: (params?: { categorie?: string; style?: string; etat?: string; couleur?: string; saison?: string; occasion?: string }) => {
    const q = new URLSearchParams();
    if (params?.categorie) q.set("categorie", params.categorie);
    if (params?.style) q.set("style", params.style);
    if (params?.etat) q.set("etat", params.etat);
    if (params?.couleur) q.set("couleur", params.couleur);
    if (params?.saison) q.set("saison", params.saison);
    if (params?.occasion) q.set("occasion", params.occasion);
    const qs = q.toString();
    return api<Vetement[]>(`/garderobe/vetements${qs ? "?" + qs : ""}`);
  },

  getVetement: (id: string) => api<Vetement>(`/garderobe/vetements/${encodeURIComponent(id)}`),

  createVetement: (payload: Omit<Vetement, "proprete_pct" | "vie_pct" | "needs_wash" | "is_worn_out" | "ports_avant_lavage" | "thermal_score" | "saison" | "entretien">) =>
    api<Vetement>(`/garderobe/vetements`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateVetement: (id: string, payload: VetementUpdate) =>
    api<Vetement>(`/garderobe/vetements/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  deleteVetement: (id: string) =>
    fetch(
      `${process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000"}/garderobe/vetements/${encodeURIComponent(id)}`,
      { method: "DELETE" },
    ).then((r) => {
      if (!r.ok) throw new Error(`Delete failed: ${r.status}`);
    }),

  getMeteo: (forceRefresh = false) =>
    api<Weather>(`/garderobe/meteo${forceRefresh ? "?force_refresh=true" : ""}`),

  getSlots: () => api<{ slots: SlotInfo[] }>(`/garderobe/slots`),

  suggest: (opts: { mean_temp?: number; rain?: boolean } = {}) =>
    api<SuggestResponse>(`/garderobe/suggest`, {
      method: "POST",
      body: JSON.stringify(opts),
    }),

  valider: (payload: { tenue: Record<string, string | null>; use_body?: boolean; note?: string }) =>
    api<ValiderResponse>(`/garderobe/valider`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  history: (limit = 20) => api<TenueHistory[]>(`/garderobe/history?limit=${limit}`),

  stats: () => api<StatsResponse>(`/garderobe/stats`),

  recommendations: () => api<Recommendation[]>(`/garderobe/recommendations`),

  getObjectif: () => api<ObjectifResponse>(`/garderobe/objectif`),

  syncObjectif: () =>
    api<{ types: number }>(`/garderobe/objectif/sync`, { method: "POST" }),

  frequence: (topN = 5) => api<WearFrequency>(`/garderobe/frequence?top_n=${topN}`),

  // Planificateur de tenues hebdomadaire (#79)
  getPlanner: (start?: string) => api<WeekPlan>(`/garderobe/planner${start ? `?start=${start}` : ""}`),
  setPlannerDay: (date: string, tenue: Record<string, string | null>) =>
    api<{ date: string; tenue: Record<string, Vetement | null> }>(`/garderobe/planner/${date}`, {
      method: "PUT",
      body: JSON.stringify({ tenue }),
    }),

  // Photo d'un vêtement + couleur dominante détectée (#75)
  uploadPhoto: (id: string, file: File, couleurDominante?: string) => {
    const fd = new FormData();
    fd.append("file", file);
    const base = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";
    const q = couleurDominante ? `?couleur_dominante=${encodeURIComponent(couleurDominante)}` : "";
    return fetch(`${base}/garderobe/vetements/${encodeURIComponent(id)}/photo${q}`, {
      method: "POST",
      body: fd,
    }).then((r) => {
      if (!r.ok) throw new Error(`Upload failed: ${r.status}`);
      return r.json() as Promise<Vetement>;
    });
  },
};

/** Préfixe une URL media relative (/media/garderobe/...) avec la base backend. */
export function mediaUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  const base = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";
  return `${base}${path}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers UI
// ─────────────────────────────────────────────────────────────────────────────

const EMO_BY_CAT: Record<string, string> = {
  Manteau: "🧥", Veste: "🧥",
  Haut: "👕", "T-shirt": "👕", Chemise: "👔", Shirt: "👔", Pull: "🧶",
  Pantalon: "👖", Short: "🩳", Jean: "👖",
  Chaussures: "👟", Bottes: "🥾", Sneakers: "👟",
  "Accessoire Cou": "🧣",
  "Tête": "🧢",
  Yeux: "🕶️",
  Bijoux: "💍",
  Poignet: "⌚",
  Cou: "📿",
};

export function emojiForCategorie(cat: string | null | undefined): string {
  if (!cat) return "👔";
  return EMO_BY_CAT[cat] || "👔";
}

export function assetUrl(itemId: string): string {
  return `/garderobe/assets/${itemId}.png`;
}
