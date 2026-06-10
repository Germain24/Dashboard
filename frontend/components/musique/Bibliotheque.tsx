"use client";

import { useEffect, useState } from "react";
import { mediaUrl, musiqueApi, type Track } from "@/lib/musique";

export function Bibliotheque() {
  const [tracks, setTracks] = useState<Track[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState("");
  const [progress, setProgress] = useState<{ n_done: number; n_total: number } | null>(null);

  const load = () => musiqueApi.tracks(q).then(setTracks).catch(() => {});
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [q]);

  const doScan = async () => {
    setBusy("Scan…");
    try { const r = await musiqueApi.scan(); alert(`Scan : ${r.ajoutes} ajoutés, ${r.total} au total`); await load(); }
    finally { setBusy(""); }
  };
  const doClassify = async () => {
    await musiqueApi.classify();
    const poll = setInterval(async () => {
      const p = await musiqueApi.progress().catch(() => null);
      if (!p) return;
      setProgress({ n_done: p.n_done, n_total: p.n_total });
      if (!p.active) { clearInterval(poll); setProgress(null); await load(); }
    }, 1500);
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 items-center">
        <button onClick={() => void doScan()} disabled={!!busy}
          className="rounded-md bg-[var(--primary)] text-[var(--primary-foreground)] px-3 py-1.5 text-sm">{busy || "Scanner"}</button>
        <button onClick={() => void doClassify()}
          className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm">Classer (Ollama)</button>
        {progress && <span className="text-xs text-[var(--muted-foreground)]">Classement {progress.n_done}/{progress.n_total}</span>}
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher…"
          className="ml-auto px-2 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--background)]" />
      </div>
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
