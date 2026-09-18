import { api } from "./api";

export interface MoodEntry {
  id?: number; date: string; humeur: number; energie: number; tags: string[]; note: string;
}
export interface MoodTrends {
  n: number; moyenne_humeur: number; moyenne_energie: number;
  humeur_ma7: { date: string; value: number }[];
  energie_ma7: { date: string; value: number }[];
  distribution_humeur: Record<string, number>;
  tags_freq: { tag: string; count: number }[];
}
export interface Correlation {
  source: string; cible: string; r: number | null; force: string; signe: string; n: number;
}
export interface CorrelationsOut { caveat: string; jours: number; correlations: Correlation[]; }

export const TAGS_EMOTIONS = [
  "calme", "heureux", "motivé", "fatigué", "anxieux",
  "irrité", "triste", "serein", "stressé", "reconnaissant",
];

export const journalApi = {
  entries: (from?: string, to?: string) => {
    const q = new URLSearchParams();
    if (from) q.set("from", from);
    if (to) q.set("to", to);
    return api<MoodEntry[]>(`/journal/entries?${q}`);
  },
  getEntry: (date: string) => api<MoodEntry>(`/journal/entries/${date}`),
  putEntry: (date: string, body: Omit<MoodEntry, "id" | "date">) =>
    api<MoodEntry>(`/journal/entries/${date}`, { method: "PUT", body: JSON.stringify(body) }),
  trends: (days = 30) => api<MoodTrends>(`/journal/trends?days=${days}`),
  correlations: (days = 90) => api<CorrelationsOut>(`/journal/correlations?days=${days}`),
};
