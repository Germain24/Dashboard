// Types + client API pour le module Objectifs long terme (proxy Next -> backend)
const BASE = "/api/objectifs";

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
