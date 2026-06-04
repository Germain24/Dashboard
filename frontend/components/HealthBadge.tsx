"use client";

import { useEffect, useState } from "react";
import { Server } from "lucide-react";
import { fetchHealth, type HealthResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

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
    return () => { active = false; };
  }, []);

  const base =
    "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors";

  if (state.kind === "loading") {
    return (
      <span
        className={cn(base, "border-[var(--border)] text-[var(--muted-foreground)]")}
        aria-live="polite"
        aria-label="Verification du backend en cours"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-[var(--warning)] animate-pulse" aria-hidden="true" />
        Verification...
      </span>
    );
  }

  if (state.kind === "error") {
    return (
      <span
        className={cn(
          base,
          "border-[var(--destructive)]/30 bg-[var(--destructive-muted)] text-[var(--destructive-foreground)]",
        )}
        aria-live="polite"
        aria-label="Backend hors ligne"
        title={state.message}
      >
        <Server className="h-3 w-3" aria-hidden="true" />
        <span className="h-1.5 w-1.5 rounded-full bg-[var(--destructive)]" aria-hidden="true" />
        Backend hors ligne
      </span>
    );
  }

  const { data } = state;
  return (
    <span
      className={cn(
        base,
        "border-[var(--success)]/30 bg-[var(--success-muted)] text-[var(--success-foreground)]",
      )}
      aria-live="polite"
      aria-label={"Backend en ligne, version " + data.version}
      title={"v" + data.version + " · env=" + data.env + " · db=" + data.db}
    >
      <Server className="h-3 w-3" aria-hidden="true" />
      <span className="h-1.5 w-1.5 rounded-full bg-[var(--success)]" aria-hidden="true" />
      OK
    </span>
  );
}
