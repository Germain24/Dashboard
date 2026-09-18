/**
 * Client HTTP minimal vers le backend FastAPI (timeout + gestion d'erreurs),
 * utilisé par toutes les couches `lib/<module>.ts`.
 */

import { env, getApiBaseUrl, proxyApiUrl } from "@/lib/env";

// Préfixe de version de l'API. Aligné sur `settings.api_v1_prefix` côté backend.
// Surchargeable via NEXT_PUBLIC_API_PREFIX (mettre "" pour cibler la racine).
const API_PREFIX = env.NEXT_PUBLIC_API_PREFIX.replace(/\/$/, "");

/** Timeout par défaut (ms) avant annulation automatique d'une requête. */
const DEFAULT_TIMEOUT_MS = 15_000;

export type ApiInit = RequestInit & {
  /** Timeout en ms (défaut 15 s). Passe 0 pour désactiver. */
  timeoutMs?: number;
};

function createTimeout(controller: AbortController, timeoutMs: number) {
  if (timeoutMs <= 0) return null;
  return setTimeout(() => controller.abort(new DOMException("Timeout", "TimeoutError")), timeoutMs);
}

function connectCallerSignal(controller: AbortController, signal?: AbortSignal | null) {
  if (!signal) return;
  if (signal.aborted) {
    controller.abort(signal.reason);
    return;
  }
  signal.addEventListener("abort", () => controller.abort(signal.reason), { once: true });
}

function isTimeoutAbort(controller: AbortController, error: unknown) {
  return controller.signal.aborted && (error as Error)?.name !== "AbortError";
}

async function fetchResponse(
  url: string,
  init: RequestInit,
  controller: AbortController,
  path: string,
  timeoutMs: number,
) {
  try {
    return await fetch(url, init);
  } catch (error) {
    if (isTimeoutAbort(controller, error)) {
      throw new Error(`API ${path} annulée (timeout ${timeoutMs}ms)`, { cause: error });
    }
    throw error;
  }
}

function detailFromBody(body: unknown) {
  const detail = (Object(body) as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  return JSON.stringify(body);
}

function clearRequestTimeout(timer: ReturnType<typeof setTimeout> | null) {
  if (timer) clearTimeout(timer);
}

async function readTextFallback(res: Response) {
  try {
    return await res.text();
  } catch {
    return "";
  }
}

async function readErrorDetail(res: Response) {
  try {
    return detailFromBody(await res.json());
  } catch {
    return readTextFallback(res);
  }
}

async function assertResponseOk(res: Response, path: string) {
  if (res.ok) return;
  const detail = await readErrorDetail(res);
  const suffix = detail ? ` — ${detail}` : "";
  throw new Error(`API ${path} ${res.status} ${res.statusText}${suffix}`);
}

async function parseResponse<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export async function api<T = unknown>(path: string, init?: ApiInit): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, signal: callerSignal, ...rest } = init ?? {};

  // AbortController interne pour le timeout, combiné au signal éventuel de l'appelant
  // (ex. annulation par TanStack Query quand la requête devient obsolète).
  const controller = new AbortController();
  const timer = createTimeout(controller, timeoutMs);
  connectCallerSignal(controller, callerSignal);
  try {
    const apiUrl =
      typeof window === "undefined"
        ? `${getApiBaseUrl()}${API_PREFIX}${path}`
        : proxyApiUrl(`${API_PREFIX}${path}`);
    const res = await fetchResponse(
      apiUrl,
      {
        headers: { "Content-Type": "application/json", ...(rest.headers ?? {}) },
        cache: "no-store",
        signal: controller.signal,
        ...rest,
      },
      controller,
      path,
      timeoutMs,
    );
    await assertResponseOk(res, path);
    return await parseResponse<T>(res);
  } finally {
    clearRequestTimeout(timer);
  }
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
