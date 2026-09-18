// Types + client API pour le module Langues & International (proxy Next -> backend)
import { json } from "./fetch-json";

const BASE = "/api/langues";

export interface VocabEntry {
  id: number;
  terme: string;
  lecture?: string | null;
  traduction: string;
  type: "vocab" | "kanji";
  tags?: string | null;
  maitrise: number;
  cree_le: string;
}

export interface VocabStats {
  vocab: { total: number; par_maitrise: Record<string, number> };
  kanji: { total: number; par_maitrise: Record<string, number> };
}

export interface ProjetInternational {
  id: number;
  titre: string;
  type: "semestre" | "visa" | "voyage" | "autre";
  statut: "idee" | "planifie" | "en_cours" | "fait";
  echeance?: string | null;
  budget_estime?: number | null;
  notes?: string | null;
}

export const languesApi = {
  vocab: (type?: string): Promise<VocabEntry[]> =>
    fetch(`${BASE}/vocab${type ? `?type=${type}` : ""}`).then((r) => json<VocabEntry[]>(r)),
  stats: (): Promise<VocabStats> => fetch(`${BASE}/vocab/stats`).then((r) => json<VocabStats>(r)),
  createVocab: (data: Partial<VocabEntry>): Promise<VocabEntry> =>
    fetch(`${BASE}/vocab`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => json<VocabEntry>(r)),
  updateVocab: (id: number, data: Partial<VocabEntry>): Promise<VocabEntry> =>
    fetch(`${BASE}/vocab/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => json<VocabEntry>(r)),
  removeVocab: (id: number): Promise<Response> => fetch(`${BASE}/vocab/${id}`, { method: "DELETE" }),
  projets: (): Promise<ProjetInternational[]> => fetch(`${BASE}/projets`).then((r) => json<ProjetInternational[]>(r)),
  createProjet: (data: Partial<ProjetInternational>): Promise<ProjetInternational> =>
    fetch(`${BASE}/projets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => json<ProjetInternational>(r)),
  updateProjet: (id: number, data: Partial<ProjetInternational>): Promise<ProjetInternational> =>
    fetch(`${BASE}/projets/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => json<ProjetInternational>(r)),
  removeProjet: (id: number): Promise<Response> => fetch(`${BASE}/projets/${id}`, { method: "DELETE" }),
};
