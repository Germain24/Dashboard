/**
 * Client HTTP minimal vers le backend FastAPI.
 * En CONV 1, sert juste à appeler /health et /<module>/ping.
 */

const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

export async function api<T = unknown>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
    ...init,
  });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status} ${res.statusText}`);
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
