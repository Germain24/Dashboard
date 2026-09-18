"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { QueryClient } from "@tanstack/react-query";

export type RealtimeStatus = "connected" | "reconnecting" | "offline";

export type RealtimeEvent<T = unknown> = {
  id: number;
  topic: string;
  timestamp: string;
  data?: T;
  invalidate?: string[][];
};

type Listener = (event: RealtimeEvent) => void;
type RealtimeContextValue = {
  status: RealtimeStatus;
  subscribe: (topic: string, listener: Listener) => () => void;
};

const RealtimeContext = createContext<RealtimeContextValue>({
  status: "reconnecting",
  subscribe: () => () => undefined,
});

// Ces flux mettent déjà à jour leur état local. Invalider React Query à chaque
// ticker créerait des rafales de requêtes et peut affamer le thread UI.
const DIRECT_HIGH_FREQUENCY_TOPICS = new Set(["finance.buffett.progress"]);

function parseRealtimeEvent(data: string): RealtimeEvent | null {
  try {
    return JSON.parse(data) as RealtimeEvent;
  } catch {
    return null;
  }
}

function invalidateEvent(event: RealtimeEvent, queryClient: QueryClient): void {
  if (event.topic === "resync_required") {
    void queryClient.invalidateQueries();
    return;
  }
  if (DIRECT_HIGH_FREQUENCY_TOPICS.has(event.topic)) return;
  for (const key of event.invalidate ?? []) void queryClient.invalidateQueries({ queryKey: key });
}

function notifyListeners(event: RealtimeEvent, listenersRef: React.MutableRefObject<Map<string, Set<Listener>>>): void {
  for (const listener of listenersRef.current.get(event.topic) ?? []) listener(event);
  for (const listener of listenersRef.current.get("*") ?? []) listener(event);
}

function handleRealtimeMessage(
  message: MessageEvent<string>,
  closed: boolean,
  queryClient: QueryClient,
  listenersRef: React.MutableRefObject<Map<string, Set<Listener>>>,
): void {
  if (closed) return;
  const event = parseRealtimeEvent(message.data);
  if (!event) return;
  invalidateEvent(event, queryClient);
  notifyListeners(event, listenersRef);
}

export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();
  const listenersRef = useRef(new Map<string, Set<Listener>>());
  const [status, setStatus] = useState<RealtimeStatus>("reconnecting");

  const subscribe = useCallback((topic: string, listener: Listener) => {
    const listeners = listenersRef.current.get(topic) ?? new Set<Listener>();
    listeners.add(listener);
    listenersRef.current.set(topic, listeners);
    return () => {
      listeners.delete(listener);
      if (!listeners.size) listenersRef.current.delete(topic);
    };
  }, []);

  useEffect(() => {
    if (typeof EventSource === "undefined") {
      return;
    }
    let closed = false;
    const source = new EventSource("/api/events");
    const updateOffline = () => setStatus(navigator.onLine ? "reconnecting" : "offline");

    source.onopen = () => setStatus("connected");
    source.onerror = updateOffline;
    window.addEventListener("online", updateOffline);
    window.addEventListener("offline", updateOffline);
    source.onmessage = (message) => handleRealtimeMessage(message, closed, queryClient, listenersRef);

    return () => {
      closed = true;
      window.removeEventListener("online", updateOffline);
      window.removeEventListener("offline", updateOffline);
      source.close();
    };
  }, [queryClient]);

  const value = useMemo(() => ({ status, subscribe }), [status, subscribe]);
  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}

export function useRealtimeStatus() {
  return useContext(RealtimeContext).status;
}

export function useRealtimeEvent<T = unknown>(
  topic: string,
  handler: (event: RealtimeEvent<T>) => void,
) {
  const { subscribe } = useContext(RealtimeContext);
  const handlerRef = useRef(handler);
  useEffect(() => {
    handlerRef.current = handler;
  }, [handler]);
  useEffect(
    () => subscribe(topic, (event) => handlerRef.current(event as RealtimeEvent<T>)),
    [subscribe, topic],
  );
}
