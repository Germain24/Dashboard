"use client";

import { useEffect, useState } from "react";
import { fetchHealth, type HealthResponse } from "@/lib/api";

type State =
  | { kind: "loading" }
  | { kind: "ok"; data: HealthResponse }
  | { kind: "error"; message: string };

export function HealthBadge() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    fetchHealth()
      .then((data) => active && setState({ kind: "ok", data }))
      .catch((e) => active && setState({ kind: "error", message: String(e) }));
    return () => {
      active = false;
    };
  }, []);

  if (state.kind === "loading") {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] px-3 py-1 text-xs text-[var(--muted-foreground)]">
        <span className="h-2 w-2 rounded-full bg-yellow-400 animate-pulse" />
        Backend : vérification…
      </span>
    );
  }
  if (state.kind === "error") {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-red-300 bg-red-50 dark:bg-red-950 px-3 py-1 text-xs text-red-700 dark:text-red-300">
        <span className="h-2 w-2 rounded-full bg-red-500" />
        Backend KO — {state.message}
      </span>
    );
  }
  const { data } = state;
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-green-300 bg-green-50 dark:bg-green-950 px-3 py-1 text-xs text-green-700 dark:text-green-300">
      <span className="h-2 w-2 rounded-full bg-green-500" />
      Backend OK · v{data.version} · env={data.env} · db={data.db}
    </span>
  );
}
