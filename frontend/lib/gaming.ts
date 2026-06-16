// Types + client API pour le module Gaming (proxy Next -> backend)
const BASE = "/api/gaming";

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

export interface Game {
  id: number;
  titre: string;
  plateforme: string;
  statut: "backlog" | "en_cours" | "termine" | "abandonne";
  note?: number | null;
  heures: number;
  nb_goals?: number;
}

export interface GameGoal {
  id: number;
  game_id: number;
  titre: string;
  type: "objectif" | "build" | "filtre";
  contenu?: string | null;
  fait: boolean;
}

export const gamingApi = {
  games: (): Promise<Game[]> => fetch(`${BASE}/games`).then((r) => json<Game[]>(r)),
  goals: (gameId: number): Promise<GameGoal[]> =>
    fetch(`${BASE}/games/${gameId}/goals`).then((r) => json<GameGoal[]>(r)),
  createGame: (data: Partial<Game>): Promise<Game> =>
    fetch(`${BASE}/games`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => json<Game>(r)),
  updateGame: (id: number, data: Partial<Game>): Promise<Game> =>
    fetch(`${BASE}/games/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => json<Game>(r)),
  removeGame: (id: number): Promise<Response> => fetch(`${BASE}/games/${id}`, { method: "DELETE" }),
  createGoal: (gameId: number, data: Partial<GameGoal>): Promise<GameGoal> =>
    fetch(`${BASE}/games/${gameId}/goals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => json<GameGoal>(r)),
  updateGoal: (id: number, data: Partial<GameGoal>): Promise<GameGoal> =>
    fetch(`${BASE}/goals/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    }).then((r) => json<GameGoal>(r)),
  removeGoal: (id: number): Promise<Response> => fetch(`${BASE}/goals/${id}`, { method: "DELETE" }),
};
