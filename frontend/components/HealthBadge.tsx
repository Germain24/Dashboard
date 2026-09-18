"use client";

import { useEffect, useState } from "react";
import { Server } from "lucide-react";
import { fetchHealth, type HealthResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

type State =
  | { kind: "loading" }
  | { kind: "ok"; data: HealthResponse }
  | { kind: "error"; message: string };

export function HealthBadge({ compact = false }: { compact?: boolean }) {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    const check = () => {
      fetchHealth()
        .then((data) => {
          if (!active) return;
          setState({ kind: "ok", data });
          window.dispatchEvent(new CustomEvent("mc:backend-status", { detail: "online" }));
        })
        .catch((e) => {
          if (!active) return;
          setState({ kind: "error", message: String(e) });
          window.dispatchEvent(new CustomEvent("mc:backend-status", { detail: "offline" }));
        });
    };
    check();
    const interval = window.setInterval(check, 30_000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  const base =
    "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors";

  if (state.kind === "loading") {
    return (
      <span
        className={cn(base, "border-[var(--border)] text-[var(--muted-foreground)]")}
        aria-live="polite"
        aria-label="Vérification du backend en cours"
      >
        <span
          className="h-1.5 w-1.5 rounded-full bg-[var(--warning)] animate-pulse"
          aria-hidden="true"
        />
        {!compact && "Vérification…"}
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
        {!compact && "Backend hors ligne"}
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
      {!compact && "Backend OK"}
    </span>
  );
}
