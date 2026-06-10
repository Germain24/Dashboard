"use client";

import { useEffect, useState } from "react";
import { mediaUrl, musiqueApi, type Track } from "@/lib/musique";

export function Bibliotheque() {
  const [tracks, setTracks] = useState<Track[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState("");
  const [progress, setProgress] = useState<{ n_done: number; n_total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => { void musiqueApi.tracks(q).then(setTracks).catch(() => {}); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [q]);

  const doScan = async () => {
    setBusy("Scan…");
    try { const r = await musiqueApi.scan(); alert(`Scan : ${r.ajoutes} ajoutés, ${r.total} au total`); load(); }
    finally { setBusy(""); }
  };
  const doClassify = () => {
    setError(null);
    void musiqueApi.classify().then(() => {
      const poll = setInterval(() => {
        void musiqueApi.progress().catch(() => null).then((p) => {
          if (!p) return;
          setProgress({ n_done: p.n_done, n_total: p.n_total });
          setError(p.error ?? null);
          if (!p.active) { clearInterval(poll); setProgress(null); load(); }
        });
      }, 1500);
    });
  };
  const doReset = () => {
    void musiqueApi.resetClassify().then((r) => {
      alert(`${r.reinitialises} morceau(x) à reclasser. Relance « Classer ».`);
      setError(null);
    });
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 items-center">
        <button onClick={() => void doScan()} disabled={!!busy}
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
