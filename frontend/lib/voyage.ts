/**
 * Client API + types pour le module Voyage (planificateur d'itinéraire).
 * Endpoints sous /voyage/* (cf. backend/app/api/voyage/routes.py).
 */
import { api } from "./api";

export type LieuVoyage = {
  id: number;
  nom: string;
  ville: string | null;
  pays: string | null;
  visite: boolean;
  aeroport_iata: string | null;
  jours_min: number | null;
  jours_max: number | null;
  cout_jour_estime: number | null;
  complet: boolean;
};

export type LieuProche = LieuVoyage & { distance_km: number };

export type SyncVoyageResult = { lieux: number; incomplets: string[] };

export type PlanifierRequest = {
  candidats: number[];
  depart_iata: string;
  arrivee_iata: string;
  date_debut: string; // "YYYY-MM-DD"
  date_fin: string;
  budget_total: number;
};

export type PointItineraire = {
  iata: string;
  lat: number | null;
  lon: number | null;
};

export type EtapeItineraire = {
  lieu_id: number;
  nom: string;
  pays: string | null;
  jours: number;
  date_arrivee: string;
  date_depart: string;
  lat: number | null;
  lon: number | null;
};

export type Itineraire = {
  etapes: EtapeItineraire[];
  cout_total: number;
  cout_transport: number;
  cout_sejour: number;
  depart: PointItineraire;
  arrivee: PointItineraire;
};

export type PlanifierAutoRequest = {
  depart_iata: string;
  arrivee_iata?: string;
  date_debut: string;
  date_fin: string;
  budget_total: number;
  k?: number;
};

export const voyageApi = {
  listLieux: () => api<LieuVoyage[]>(`/voyage/lieux`),

  suggerer: (departIata: string, limit = 25) =>
    api<LieuProche[]>(`/voyage/suggerer?depart_iata=${encodeURIComponent(departIata)}&limit=${limit}`),

  sync: () => api<SyncVoyageResult>(`/voyage/sync`, { method: "POST" }),

  // Solveur CP-SAT capé à 10 s côté backend ; prix estimés localement (pas
  // d'appel réseau) -- marge confortable au-delà du pire cas.
  planifier: (req: PlanifierRequest) =>
    api<Itineraire>(`/voyage/planifier`, {
      method: "POST", body: JSON.stringify(req), timeoutMs: 30_000,
    }),

  // Jusqu'à k résolutions CP-SAT successives (8 s/résolution, k<=20) ->
  // 160 s pire cas, marge incluse.
  planifierAuto: (req: PlanifierAutoRequest) =>
    api<{ itineraires: Itineraire[] }>(`/voyage/planifier-auto`, {
      method: "POST", body: JSON.stringify(req), timeoutMs: 180_000,
    }),

  confirmer: (lieuIds: number[]) =>
    api<{ visites: number }>(`/voyage/confirmer`, {
      method: "POST",
      body: JSON.stringify({ lieu_ids: lieuIds }),
    }),
};
