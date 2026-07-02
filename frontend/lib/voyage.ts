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

export type SyncVoyageResult = { lieux: number; incomplets: string[] };

export type PlanifierRequest = {
  candidats: number[];
  depart_iata: string;
  arrivee_iata: string;
  date_debut: string; // "YYYY-MM-DD"
  date_fin: string;
  budget_total: number;
};

export type EtapeItineraire = {
  lieu_id: number;
  nom: string;
  jours: number;
  date_arrivee: string;
  date_depart: string;
};

export type Itineraire = {
  etapes: EtapeItineraire[];
  cout_total: number;
  cout_transport: number;
  cout_sejour: number;
};

export const voyageApi = {
  listLieux: () => api<LieuVoyage[]>(`/voyage/lieux`),

  sync: () => api<SyncVoyageResult>(`/voyage/sync`, { method: "POST" }),

  // /planifier peut enchaîner de nombreux appels Duffel séquentiels (jusqu'à
  // (k+2)(k+1) paires pour k candidats) : le timeout par défaut (15 s) est
  // bien trop court, on l'étend à 2 min.
  planifier: (req: PlanifierRequest) =>
    api<Itineraire>(`/voyage/planifier`, {
      method: "POST", body: JSON.stringify(req), timeoutMs: 120_000,
    }),

  confirmer: (lieuIds: number[]) =>
    api<{ visites: number }>(`/voyage/confirmer`, {
      method: "POST",
      body: JSON.stringify({ lieu_ids: lieuIds }),
    }),
};
