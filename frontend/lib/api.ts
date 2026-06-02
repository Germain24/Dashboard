/**
 * Client HTTP minimal vers le backend FastAPI.
 * En CONV 1, sert juste à appeler /health et /<module>/ping.
 */

const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

// Préfixe de version de l'API. Aligné sur `settings.api_v1_prefix` côté backend.
// Surchargeable via NEXT_PUBLIC_API_PREFIX (mettre "" pour cibler la racine).
const API_PREFIX = (
  process.env.NEXT_PUBLIC_API_PREFIX ?? "/api/v1"
).replace(/\/$/, "");

export async function api<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${API_PREFIX}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
    ...init,
  });
  if (!res.ok) {
    // Extrait le message d'erreur du backend (FastAPI met le détail dans `detail`)
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body);
    } catch {
      try {
        detail = await res.text();
      } catch {
        // ignore
      }
    }
    const suffix = detail ? ` — ${detail}` : "";
    throw new Error(`API ${path} ${res.status} ${res.statusText}${suffix}`);
  }
  return res.json() as Promise<T>;
}

export type HealthResponse = {
  status: string;
  app: string;
  version: string;
  env: string;
  timezone: string;
  db: string;
  timestamp: string;
};

export async function fetchHealth(): Promise<HealthResponse> {
  return api<HealthResponse>("/health");
}
