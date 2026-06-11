"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { mediaUrl, musiqueApi, type Track } from "@/lib/musique";
import {
  musiqueKeys, useClassify, useResetClassify, useScanLibrary, useTracks,
} from "@/lib/queries/musique";

export function Bibliotheque() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [progress, setProgress] = useState<{ n_done: number; n_total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const tracksQ = useTracks(q);
  const tracks: Track[] = tracksQ.data ?? [];
  const scanMutation = useScanLibrary();
  const classifyMutation = useClassify();
  const resetMutation = useResetClassify();
  const busy = scanMutation.isPending ? "Scan…" : "";

  const doScan = () => {
    scanMutation.mutate(undefined, {
      onSuccess: (r) => alert(`Scan : ${r.ajoutes} ajoutés, ${r.total} au total`),
    });
  };
  const doClassify = () => {
    setError(null);
    classifyMutation.mutate(undefined, {
      onSuccess: () => {
        // Le classement tourne en arrière-plan côté backend : on garde le poll
        // imperatif (progress n'est pas une donnée cacheable).
        const poll = setInterval(() => {
          void musiqueApi.progress().catch(() => null).then((p) => {
            if (!p) return;
            setProgress({ n_done: p.n_done, n_total: p.n_total });
            setError(p.error ?? null);
            if (!p.active) {
              clearInterval(poll);
              setProgress(null);
              void qc.invalidateQueries({ queryKey: musiqueKeys.all });
            }
          });
        }, 1500);
      },
    });
  };
  const doReset = () => {
    if (!confirm(
      "Tout reclasser ?\n\nEfface les ambiances attribuées automatiquement "
      + "(les ambiances ajoutées à la main sont conservées), puis relance « Classer ».",
    )) return;
    resetMutation.mutate(true, {
      onSuccess: (r) => {
        alert(`${r.reinitialises} morceau(x) à reclasser. Relance « Classer ».`);
        setError(null);
      },
    });
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 items-center">
        <button onClick={doScan} disabled={!!busy}
          className="rounded-md bg-[var(--primary)] text-[var(--primary-foreground)] px-3 py-1.5 text-sm">{busy || "Scanner"}</button>
        <button onClick={() => doClassify()}
          className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm">Classer (Ollama)</button>
        <button onClick={() => doReset()}
          className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--muted-foreground)]"
          title="Remettre à classer les morceaux sans ambiance (après un échec Ollama)">Réinitialiser</button>
        {progress && <span className="text-xs text-[var(--muted-foreground)]">Classement {progress.n_done}/{progress.n_total}</span>}
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher…"
          className="ml-auto px-2 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--background)]" />
      </div>
      {error && (
        <div className="rounded-md border border-[var(--warning-muted,#d97706)] bg-[color-mix(in_srgb,#d97706_8%,transparent)] px-3 py-2 text-xs text-[var(--warning-foreground,#92400e)]">
          ⚠ {error}
        </div>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {tracks.map((t) => (
          <div key={t.id} className="flex items-center gap-3 rounded-lg border border-[var(--border)] p-2">
            {t.cover
              ? <img src={mediaUrl(t.cover)} alt="" className="h-12 w-12 rounded object-cover" />
              : <div className="h-12 w-12 rounded bg-[var(--muted)]" />}
            <div className="min-w-0">
              <div className="truncate text-sm font-medium">{t.title}</div>
              <div className="truncate text-xs text-[var(--muted-foreground)]">{t.artist} · {t.album}</div>
              <div className="text-xs text-[var(--ring)]">{t.ambiances.join(", ")}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
