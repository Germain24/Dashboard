import { api } from "./api";
import { proxyApiUrl } from "./env";

export const MEDIA_BASE = proxyApiUrl("/media/music");

export interface Track {
  id: number;
  path: string;
  artist: string;
  album: string;
  title: string;
  genre: string;
  duree_sec: number | null;
  cover: string | null;
  ambiances: string[];
}
export interface AmbianceCount {
  ambiance: string;
  label: string;
  count: number;
}
export interface ClassifyProgress {
  n_done: number;
  n_total: number;
  active: boolean;
  error?: string | null;
}
export type WalkmanSyncStatus = "idle" | "running" | "completed" | "failed";
export type WalkmanSyncPhase = "preparing" | "copying" | "converting" | null;
export interface WalkmanSyncProgress {
  active: boolean;
  status: WalkmanSyncStatus;
  phase: WalkmanSyncPhase;
  n_done: number;
  n_total: number;
  current_file: string | null;
  copied: number;
  converted: number;
  identical: number;
  replaced: number;
  skipped_priority: number;
  skipped_capacity: number;
  failed: number;
  error: string | null;
}
export interface QualityRow {
  id: number;
  title: string;
  artist: string;
  format: string;
  quality_label: string;
  tier: string;
  qobuz_available: boolean | null;
  status: "owned" | "to_buy" | "unavailable" | "unknown";
}

export const mediaUrl = (rel: string) =>
  `${MEDIA_BASE}/${rel.split("/").map(encodeURIComponent).join("/")}`;

export const musiqueApi = {
  scan: () =>
    api<{ ajoutes: number; majs: number; total: number }>("/musique/scan", { method: "POST" }),
  classify: () => api<{ message: string }>("/musique/classify", { method: "POST" }),
  resetClassify: (tout = false) =>
    api<{ reinitialises: number }>(`/musique/classify/reset?tout=${tout}`, { method: "POST" }),
  progress: () => api<ClassifyProgress>("/musique/classify/progress"),
  startWalkmanSync: () => api<{ message: string }>("/musique/walkman/sync", { method: "POST" }),
  walkmanSyncStatus: () => api<WalkmanSyncProgress>("/musique/walkman/sync/status"),
  tracks: (q = "", ambiance = "") => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (ambiance) p.set("ambiance", ambiance);
    return api<Track[]>(`/musique/tracks?${p}`);
  },
  ambiances: () => api<AmbianceCount[]>("/musique/ambiances"),
  playlist: (a: string) => api<Track[]>(`/musique/playlists/${encodeURIComponent(a)}`),
  reco: (a: string) => api<Track[]>(`/musique/playlists/${encodeURIComponent(a)}/reco`),
  discovery: (a: string) =>
    api<{ ambiance: string; suggestions: string[] }>(
      `/musique/playlists/${encodeURIComponent(a)}/discovery`,
    ),
  addAmbiance: (id: number, a: string) =>
    api<void>(`/musique/tracks/${id}/ambiances/${encodeURIComponent(a)}`, { method: "PUT" }),
  removeAmbiance: (id: number, a: string) =>
    api<void>(`/musique/tracks/${id}/ambiances/${encodeURIComponent(a)}`, { method: "DELETE" }),
  exportAllUrl: () => proxyApiUrl("/musique/playlists/export.zip"),
  quality: () => api<QualityRow[]>("/musique/quality"),
  setQobuzAvailable: (id: number, available: boolean | null) =>
    api<void>(`/musique/tracks/${id}/qobuz-available`, {
      method: "PUT",
      body: JSON.stringify({ available }),
    }),
};
