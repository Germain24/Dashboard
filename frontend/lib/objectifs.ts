// Types + client API pour le module Objectifs long terme (proxy Next -> backend)
import { json } from "./fetch-json";

const BASE = "/api/objectifs";

export interface LongTermGoal {
  id: number;
  titre: string;
  categorie: "master" | "concours" | "carriere" | "autre";
  statut: "veille" | "preparation" | "candidature" | "obtenu" | "abandonne";
  echeance?: string | null;
  progression: number;
  description?: string | null;
  lien?: string | null;
  cree_le: string;
}

export const objectifsApi = {
  list: (): Promise<LongTermGoal[]> => fetch(`${BASE}/goals`).then((r) => json<LongTermGoal[]>(r)),
  create: (data: Partial<LongTermGoal>): Promise<LongTermGoal> =>
    fetch(`${BASE}/goals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => json<LongTermGoal>(r)),
  update: (id: number, data: Partial<LongTermGoal>): Promise<LongTermGoal> =>
    fetch(`${BASE}/goals/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => json<LongTermGoal>(r)),
  remove: (id: number): Promise<Response> => fetch(`${BASE}/goals/${id}`, { method: "DELETE" }),
};
