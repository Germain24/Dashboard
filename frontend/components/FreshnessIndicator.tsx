"use client";

/**
 * Indicateur de fraîcheur des données — point vert + timestamp du dernier
 * fetch réussi. Utilise TanStack Query useIsFetching pour savoir si des
 * requêtes sont en cours, et affiche "À jour" ou "Actualisation…".
 */

import { useIsFetching } from "@tanstack/react-query";
import { useEffect, useState, useSyncExternalStore } from "react";
import { useRealtimeStatus } from "@/components/RealtimeProvider";

const subscribeToMount = () => () => undefined;

export function FreshnessIndicator() {
  const mounted = useSyncExternalStore(subscribeToMount, () => true, () => false);

  if (!mounted) {
    return (
      <span
        className="invisible inline-flex min-w-20 items-center gap-1.5 text-xs"
        aria-hidden="true"
      >
        <span className="h-2 w-2 rounded-full" />
        À jour
      </span>
    );
  }
  return <MountedFreshnessIndicator />;
}

function MountedFreshnessIndicator() {
  const fetching = useIsFetching();
  const realtimeStatus = useRealtimeStatus();
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const [now, setNow] = useState(0);

  // Date.now() et le formatage localisé ne sont évalués que dans le navigateur.
  useEffect(() => {
    const update = () => {
      const value = Date.now();
      setNow(value);
      if (fetching === 0) setLastUpdated(value);
    };
    const initial = setTimeout(update, 0);
    return () => clearTimeout(initial);
  }, [fetching]);

  // Tick toutes les 30s pour rafraîchir "Il y a X min".
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);

  if (fetching > 0) {
    return <FetchingFreshness />;
  }

  if (realtimeStatus !== "connected") {
    return <DisconnectedFreshness status={realtimeStatus} />;
  }

  return <ConnectedFreshness lastUpdated={lastUpdated} now={now} />;
}

function FetchingFreshness() {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]">
      <span className="h-2 w-2 rounded-full bg-[var(--warning)] animate-pulse" aria-hidden="true" />
      Actualisation…
    </span>
  );
}

function DisconnectedFreshness({ status }: { status: string }) {
  const offline = status === "offline";
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]"
      title={offline ? "Canal temps réel hors ligne" : "Reconnexion au canal temps réel"}
    >
      <span
        className={`h-2 w-2 rounded-full ${offline ? "bg-[var(--destructive)]" : "bg-[var(--warning)] animate-pulse"}`}
        aria-hidden="true"
      />
      {offline ? "Hors ligne" : "Reconnexion…"}
    </span>
  );
}

function ConnectedFreshness({ lastUpdated, now }: { lastUpdated: number | null; now: number }) {
  if (!lastUpdated) return null;
  const minutes = Math.round((now - lastUpdated) / 60_000);
  const label = minutes < 1 ? "À jour" : `Il y a ${minutes} min`;
  return (
    <span
      className="inline-flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]"
      title={`Temps réel connecté · Dernière mise à jour : ${new Date(lastUpdated).toLocaleTimeString("fr-CA")}`}
    >
      <span className="h-2 w-2 rounded-full bg-[var(--success)]" aria-hidden="true" />
      {label}
    </span>
  );
}
