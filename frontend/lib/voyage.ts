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
  ordre?: number | null;
  progression?: string | null;
  priorite?: number;
  cout_activite?: number | null;
  cout_transport_local?: number | null;
  mois_disponibles?: string | null;
  verrouille?: boolean;
  raison_verrouillage?: string | null;
  cout_hebergement_jour?: number | null;
  cout_nourriture_jour?: number | null;
  statut?: "possible" | "incertain" | "impossible";
  raison_indisponible?: string | null;
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
  ville?: string | null;
  aeroport_iata?: string | null;
  cout_activite?: number;
  cout_transport_local?: number;
  ordre?: number | null;
  progression?: string | null;
  cout_hebergement?: number;
  cout_nourriture?: number;
  source_cout_journalier?: string;
  source_cout_activite?: string;
  source_transport_local?: string;
};

export type Itineraire = {
  etapes: EtapeItineraire[];
  cout_total: number;
  cout_transport: number;
  cout_sejour: number;
  depart: PointItineraire;
  arrivee: PointItineraire;
  cout_activites?: number;
  cout_transport_local?: number;
  cout_hebergement?: number;
  cout_nourriture?: number;
  source_prix_vol?: "live" | "cache_live" | "estimation";
  transporteur?: string | null;
  fiabilite_prix?: "élevée" | "faible";
  avertissements?: string[];
};

export type PlanifierAutoRequest = {
  depart_iata: string;
  arrivee_iata?: string;
  date_debut: string;
  date_fin: string;
  budget_total: number;
  k?: number;
  prix_live?: boolean;
};

/** Étape retenue transmise à /confirmer — les coûts sont recalculés côté serveur. */
export type EtapeConfirmee = {
  lieu_id: number;
  jours: number;
  date_arrivee?: string | null;
  date_depart?: string | null;
};

export type ConfirmerRequest = {
  lieu_ids: number[];
  titre?: string;
  date_debut?: string;
  date_fin?: string;
  depart_iata?: string | null;
  arrivee_iata?: string | null;
  etapes?: EtapeConfirmee[];
};

export type VoyageEtape = {
  id: number;
  lieu_id: number | null;
  nom: string;
  ville: string | null;
  pays: string | null;
  ordre: number;
  jours: number;
  date_arrivee: string | null;
  date_depart: string | null;
  cout_estime: number;
  cout_reel: number | null;
};

export type ChecklistItem = {
  id: number;
  label: string;
  fait: boolean;
  ordre: number;
};

export type BudgetVoyage = {
  cout_estime_total: number;
  cout_reel_total: number;
  cout_projete_total: number;
  ecart: number;
  etapes_avec_cout_reel: number;
};

export type VoyageConfirme = {
  id: number;
  titre: string;
  date_debut: string;
  date_fin: string;
  depart_iata: string | null;
  arrivee_iata: string | null;
  etapes: VoyageEtape[];
  checklist: ChecklistItem[];
  budget: BudgetVoyage;
  checklist_total: number;
  checklist_faits: number;
};

const TITRE_MAX_PAYS = 3;

/** Requête /confirmer depuis un itinéraire calculé : lieux visités + étapes
 *  datées à persister. Aucun montant n'est transmis — le serveur recalcule les
 *  coûts depuis `lieu_voyage` (cf. services/voyage/costs.py). */
export function buildConfirmerRequest(
  itineraire: Itineraire,
  opts: { dateDebut: string; dateFin: string; departIata: string; arriveeIata?: string },
): ConfirmerRequest {
  const labels = [...new Set(itineraire.etapes.map((e) => e.pays ?? e.nom))];
  const visibles = labels.slice(0, TITRE_MAX_PAYS).join(" · ");
  const reste = labels.length - TITRE_MAX_PAYS;
  return {
    lieu_ids: itineraire.etapes.map((e) => e.lieu_id),
    titre: reste > 0 ? `${visibles} +${reste}` : visibles || "Voyage",
    date_debut: opts.dateDebut,
    date_fin: opts.dateFin,
    depart_iata: opts.departIata,
    arrivee_iata: opts.arriveeIata || opts.departIata,
    etapes: itineraire.etapes.map((e) => ({
      lieu_id: e.lieu_id,
      jours: e.jours,
      date_arrivee: e.date_arrivee,
      date_depart: e.date_depart,
    })),
  };
}

export const voyageApi = {
  listLieux: () => api<LieuVoyage[]>(`/voyage/lieux`),

  suggerer: (departIata: string, limit = 25) =>
    api<LieuProche[]>(`/voyage/suggerer?depart_iata=${encodeURIComponent(departIata)}&limit=${limit}`),

  sync: () => api<SyncVoyageResult>(`/voyage/sync`, { method: "POST" }),

  // Solveur CP-SAT capé à 3 s, puis vérification live optionnelle.
  planifier: (req: PlanifierRequest) =>
    api<Itineraire>(`/voyage/planifier`, {
      method: "POST", body: JSON.stringify(req), timeoutMs: 30_000,
    }),

  // Jusqu'à k résolutions CP-SAT successives (2 s/résolution, k<=20), puis
  // tarification Duffel des finalistes quand elle est configurée.
  planifierAuto: (req: PlanifierAutoRequest) =>
    api<{ itineraires: Itineraire[] }>(`/voyage/planifier-auto`, {
      method: "POST", body: JSON.stringify(req), timeoutMs: 180_000,
    }),

  // `etapes` omis = ancien contrat (marque seulement les lieux visités) ;
  // fourni, l'itinéraire est persisté et porte checklist + budget par étape.
  confirmer: (req: ConfirmerRequest) =>
    api<{ visites: number; voyage_id: number | null }>(`/voyage/confirmer`, {
      method: "POST",
      body: JSON.stringify(req),
    }),

  listVoyages: () => api<VoyageConfirme[]>(`/voyage/voyages`),

  deleteVoyage: (voyageId: number) =>
    api<void>(`/voyage/voyages/${voyageId}`, { method: "DELETE" }),

  setCoutReel: (voyageId: number, etapeId: number, coutReel: number | null) =>
    api<VoyageEtape>(`/voyage/voyages/${voyageId}/etapes/${etapeId}`, {
      method: "PATCH",
      body: JSON.stringify({ cout_reel: coutReel }),
    }),

  addChecklistItem: (voyageId: number, label: string) =>
    api<ChecklistItem>(`/voyage/voyages/${voyageId}/checklist`, {
      method: "POST",
      body: JSON.stringify({ label }),
    }),

  updateChecklistItem: (
    voyageId: number, itemId: number, patch: { label?: string; fait?: boolean; ordre?: number },
  ) =>
    api<ChecklistItem>(`/voyage/voyages/${voyageId}/checklist/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  deleteChecklistItem: (voyageId: number, itemId: number) =>
    api<void>(`/voyage/voyages/${voyageId}/checklist/${itemId}`, { method: "DELETE" }),
};
