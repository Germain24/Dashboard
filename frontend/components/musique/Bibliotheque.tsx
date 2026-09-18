"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { useQueryClient } from "@tanstack/react-query";
import { mediaUrl, musiqueApi, type Track, type WalkmanSyncProgress } from "@/lib/musique";
import { useRealtimeEvent } from "@/components/RealtimeProvider";
import {
  musiqueKeys,
  useClassify,
  useResetClassify,
  useScanLibrary,
  useStartWalkmanSync,
  useTracks,
  useWalkmanSyncStatus,
} from "@/lib/queries/musique";

export function Bibliotheque() {
  const [q, setQ] = useState("");
  const [progress, setProgress] = useState<{ n_done: number; n_total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const tracksQ = useTracks(q);
  const tracks: Track[] = tracksQ.data ?? [];
  const scanMutation = useScanLibrary();
  const walkmanStatusQ = useWalkmanSyncStatus();
  const walkmanSyncMutation = useStartWalkmanSync();
  const classifyMutation = useClassify();
  const resetMutation = useResetClassify();
  const busy = scanMutation.isPending ? "Scan…" : "";
  const queryClient = useQueryClient();

  useRealtimeEvent<WalkmanSyncProgress>("music.walkman.sync.progress", ({ data }) => {
    if (!data) return;
    queryClient.setQueryData(musiqueKeys.walkmanSyncStatus(), data);
  });

  useRealtimeEvent<{ n_done: number; n_total: number; active: boolean; error?: string | null }>(
    "music.classification.progress",
    ({ data }) => {
      if (!data) return;
      setError(data.error ?? null);
      setProgress(data.active ? { n_done: data.n_done, n_total: data.n_total } : null);
    },
  );

  useEffect(() => {
    let cancelled = false;
    void musiqueApi
      .progress()
      .then((data) => {
        if (!cancelled && data.active) {
          setProgress({ n_done: data.n_done, n_total: data.n_total });
          setError(data.error ?? null);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const doScan = () => {
    scanMutation.mutate(undefined, {
      onSuccess: (r) => alert(`Scan : ${r.ajoutes} ajoutés, ${r.total} au total`),
    });
  };
  const doWalkmanSync = () => walkmanSyncMutation.mutate();
  const doClassify = () => {
    setError(null);
    classifyMutation.mutate(undefined, {
      onSuccess: () => undefined,
    });
  };

  const walkmanStatus = walkmanStatusQ.data;
  const walkmanActive = walkmanStatus?.active ?? false;
  const walkmanVisible = !!walkmanStatus && walkmanStatus.status !== "idle";
  const walkmanError =
    walkmanSyncMutation.error instanceof Error
      ? walkmanSyncMutation.error.message
      : (walkmanStatus?.error ??
        (walkmanStatusQ.error instanceof Error ? walkmanStatusQ.error.message : null));
  const walkmanPercent = walkmanStatus?.n_total
    ? Math.min(100, Math.round((walkmanStatus.n_done / walkmanStatus.n_total) * 100))
    : 0;
  const walkmanPhase =
    walkmanStatus?.status === "completed"
      ? "Synchronisation terminée"
      : walkmanStatus?.status === "failed"
        ? "Synchronisation interrompue"
        : walkmanStatus?.phase === "preparing"
          ? "Préparation"
          : walkmanStatus?.phase === "converting"
            ? "Conversion AAC"
            : walkmanStatus?.phase === "copying"
              ? "Copie vers le Walkman"
              : "Synchronisation en cours";

  const walkmanCounts =
    walkmanStatus &&
    ([
      ["Copiés", walkmanStatus.copied],
      ["Convertis", walkmanStatus.converted],
      ["Identiques", walkmanStatus.identical],
      ["Remplacés", walkmanStatus.replaced],
      ["Doublons ignorés", walkmanStatus.skipped_priority],
      ["Hors capacité", walkmanStatus.skipped_capacity],
      ["Échecs", walkmanStatus.failed],
    ] as const);
  const doReset = () => {
    if (
      !confirm(
        "Tout reclasser ?\n\nEfface les ambiances attribuées automatiquement " +
          "(les ambiances ajoutées à la main sont conservées), puis relance « Classer ».",
      )
    )
      return;
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
        <button
          onClick={doScan}
          disabled={!!busy}
          className="rounded-md bg-[var(--primary)] text-[var(--primary-foreground)] px-3 py-1.5 text-sm"
        >
          {busy || "Scanner"}
        </button>
        <button
          onClick={doWalkmanSync}
          disabled={walkmanActive || walkmanSyncMutation.isPending}
          className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm disabled:opacity-50"
          title="Copie et convertit les morceaux vers le Walkman"
        >
          {walkmanActive
            ? "Synchronisation…"
            : walkmanSyncMutation.isPending
              ? "Démarrage…"
              : "Synchroniser le Walkman"}
        </button>
        <button
          onClick={() => doClassify()}
          className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm"
          title="Classe les nouveaux morceaux avec DeepSeek"
        >
          Classer (DeepSeek)
        </button>
        <button
          onClick={() => doReset()}
          className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--muted-foreground)]"
          title="Efface les ambiances attribuées automatiquement et remet tout à classer (les ambiances manuelles sont conservées)"
        >
          Réinitialiser
        </button>
        {progress && (
          <span className="text-xs text-[var(--muted-foreground)]">
            Classement {progress.n_done}/{progress.n_total}
          </span>
        )}
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Rechercher…"
          className="ml-auto px-2 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--background)]"
        />
      </div>
      {error && (
        <div
          role="alert"
          className="rounded-md border border-[var(--warning-muted)] bg-[color-mix(in_srgb,var(--warning)_8%,transparent)] px-3 py-2 text-xs text-[var(--warning-foreground)]"
        >
          Attention : {error}
        </div>
      )}
      {(walkmanVisible || walkmanSyncMutation.isError || walkmanStatusQ.isError) && (
        <section
          className="space-y-3 rounded-lg border border-[var(--border)] p-3 sm:p-4"
          aria-live="polite"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="min-w-0">
              <h2 className="text-sm font-semibold">{walkmanPhase}</h2>
              {walkmanStatus?.active && (
                <p className="text-xs text-[var(--muted-foreground)]">
                  {walkmanStatus.n_done} / {walkmanStatus.n_total} morceaux
                </p>
              )}
            </div>
            {walkmanStatus?.active && (
              <span className="text-xs tabular-nums text-[var(--muted-foreground)]">
                {walkmanPercent}%
              </span>
            )}
          </div>
          {walkmanStatus?.active && (
            <div
              role="progressbar"
              aria-label="Progression de la synchronisation du Walkman"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={walkmanPercent}
              className="h-2 overflow-hidden rounded-full bg-[var(--muted)]"
            >
              <div
                className="h-full rounded-full bg-[var(--ring)] transition-[width]"
                style={{ width: `${walkmanPercent}%` }}
              />
            </div>
          )}
          {walkmanStatus?.active && walkmanStatus.current_file && (
            <p className="break-all text-xs text-[var(--muted-foreground)]">
              {walkmanStatus.current_file}
            </p>
          )}
          {walkmanCounts && (
            <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
              {walkmanCounts.map(([label, count]) => (
                <div key={label} className="rounded-md bg-[var(--muted)]/40 px-2 py-1.5">
                  <dt className="text-[11px] leading-tight text-[var(--muted-foreground)]">
                    {label}
                  </dt>
                  <dd className="text-sm font-medium tabular-nums">{count}</dd>
                </div>
              ))}
            </dl>
          )}
          {walkmanError && (
            <p
              role="alert"
              className="rounded-md border border-[var(--warning-muted)] bg-[color-mix(in_srgb,var(--warning)_8%,transparent)] px-3 py-2 text-xs text-[var(--warning-foreground)]"
            >
              Attention : {walkmanError}
            </p>
          )}
        </section>
      )}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {tracks.map((t) => (
          <div
            key={t.id}
            className="flex items-center gap-3 rounded-lg border border-[var(--border)] p-2"
          >
            {t.cover ? (
              <Image
                src={mediaUrl(t.cover)}
                alt=""
                width={48}
                height={48}
                className="h-12 w-12 rounded object-cover"
              />
            ) : (
              <div className="h-12 w-12 rounded bg-[var(--muted)]" />
            )}
            <div className="min-w-0">
              <div className="truncate text-sm font-medium">{t.title}</div>
              <div className="truncate text-xs text-[var(--muted-foreground)]">
                {t.artist} · {t.album}
              </div>
              <div className="text-xs text-[var(--ring)]">{t.ambiances.join(", ")}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
