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
};

export type VetementUpdate = Partial<Omit<Vetement, "id" | "proprete_pct" | "vie_pct" | "needs_wash" | "is_worn_out" | "ports_avant_lavage" | "thermal_score">>;

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
};

export type Recommendation = {
  nom: string;
  raison: string;
  potentiel: number;
  type: string;
};

// ─────────────────────────────────────────────────────────────────────────────
// Endpoints
// ─────────────────────────────────────────────────────────────────────────────

export const garderobeApi = {
  listVetements: (params?: { categorie?: string; style?: string; etat?: string }) => {
    const q = new URLSearchParams();
    if (params?.categorie) q.set("categorie", params.categorie);
    if (params?.style) q.set("style", params.style);
    if (params?.etat) q.set("etat", params.etat);
    const qs = q.toString();
    return api<Vetement[]>(`/garderobe/vetements${qs ? "?" + qs : ""}`);
  },

  getVetement: (id: string) => api<Vetement>(`/garderobe/vetements/${encodeURIComponent(id)}`),

  createVetement: (payload: Omit<Vetement, "proprete_pct" | "vie_pct" | "needs_wash" | "is_worn_out" | "ports_avant_lavage" | "thermal_score">) =>
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
};

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
