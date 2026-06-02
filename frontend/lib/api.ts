/**
 * Client HTTP minimal vers le backend FastAPI.
 * En CONV 1, sert juste à appeler /health et /<module>/ping.
 */

import { env } from "@/lib/env";

const BASE_URL = env.NEXT_PUBLIC_API_BASE_URL.replace(/\/$/, "");

// Préfixe de version de l'API. Aligné sur `settings.api_v1_prefix` côté backend.
// Surchargeable via NEXT_PUBLIC_API_PREFIX (mettre "" pour cibler la racine).
const API_PREFIX = env.NEXT_PUBLIC_API_PREFIX.replace(/\/$/, "");

/** Timeout par défaut (ms) avant annulation automatique d'une requête. */
const DEFAULT_TIMEOUT_MS = 15_000;

export type ApiInit = RequestInit & {
  /** Timeout en ms (défaut 15 s). Passe 0 pour désactiver. */
  timeoutMs?: number;
};

export async function api<T = unknown>(path: string, init?: ApiInit): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, signal: callerSignal, ...rest } = init ?? {};

  // AbortController interne pour le timeout, combiné au signal éventuel de l'appelant
  // (ex. annulation par TanStack Query quand la requête devient obsolète).
  const controller = new AbortController();
  const timer = timeoutMs > 0 ? setTimeout(() => controller.abort(new DOMException("Timeout", "TimeoutError")), timeoutMs) : null;
  if (callerSignal) {
    if (callerSignal.aborted) controller.abort(callerSignal.reason);
    else callerSignal.addEventListener("abort", () => controller.abort(callerSignal.reason), { once: true });
  }

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${API_PREFIX}${path}`, {
      headers: { "Content-Type": "application/json", ...(rest.headers ?? {}) },
      cache: "no-store",
      signal: controller.signal,
      ...rest,
    });
  } catch (err) {
    if (controller.signal.aborted && (err as Error)?.name !== "AbortError") {
      throw new Error(`API ${path} annulée (timeout ${timeoutMs}ms)`);
    }
    throw err;
  } finally {
    if (timer) clearTimeout(timer);
  }
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
