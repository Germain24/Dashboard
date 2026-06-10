"use client";

import { useEffect, useState } from "react";
import { mediaUrl, musiqueApi, type AmbianceCount, type Track } from "@/lib/musique";

export function Ambiances() {
  const [ambiances, setAmbiances] = useState<AmbianceCount[]>([]);
  const [sel, setSel] = useState<string>("café");
  const [tracks, setTracks] = useState<Track[]>([]);
  const [reco, setReco] = useState<Track[]>([]);

  useEffect(() => { void musiqueApi.ambiances().then(setAmbiances).catch(() => {}); }, []);
  const load = (a: string) => {
    void musiqueApi.playlist(a).then(setTracks).catch(() => {});
    void musiqueApi.reco(a).then(setReco).catch(() => {});
  };
  useEffect(() => {
    void musiqueApi.playlist(sel).then(setTracks).catch(() => {});
    void musiqueApi.reco(sel).then(setReco).catch(() => {});
  }, [sel]);

  const add = async (id: number) => { await musiqueApi.addAmbiance(id, sel); load(sel); };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1.5">
        {ambiances.map((a) => (
          <button key={a.ambiance} onClick={() => setSel(a.ambiance)}
            className={`text-xs px-2.5 py-1 rounded-full border ${sel === a.ambiance
              ? "bg-[var(--ring)] text-white border-[var(--ring)]"
              : "border-[var(--border)] text-[var(--muted-foreground)]"}`}>
            {a.ambiance} ({a.count})
          </button>
        ))}
        <a href={musiqueApi.exportUrl(sel)} className="ml-auto text-xs px-2.5 py-1 rounded-full border border-[var(--border)]">⬇ .m3u</a>
      </div>

      <div className="space-y-1">
        {tracks.map((t) => (
          <div key={t.id} className="flex items-center gap-3 rounded-lg border border-[var(--border)] p-2">
            {t.cover && <img src={mediaUrl(t.cover)} alt="" className="h-10 w-10 rounded object-cover" />}
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm">{t.title} — <span className="text-[var(--muted-foreground)]">{t.artist}</span></div>
              {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
              <audio controls preload="none" src={mediaUrl(t.path)} className="h-8 w-full mt-1" />
            </div>
          </div>
        ))}
        {tracks.length === 0 && <p className="text-sm text-[var(--muted-foreground)]">Playlist vide — lance un classement ou ajoute depuis la reco.</p>}
      </div>

      {reco.length > 0 && (
        <div>
          <h3 className="text-sm font-medium mb-1">Suggestions de ta bibliothèque</h3>
          <div className="space-y-1">
            {reco.slice(0, 15).map((t) => (
              <div key={t.id} className="flex items-center gap-2 text-sm">
                <span className="flex-1 truncate">{t.title} — <span className="text-[var(--muted-foreground)]">{t.artist}</span></span>
                <button onClick={() => void add(t.id)} className="text-xs px-2 py-0.5 rounded border border-[var(--border)]">+ ajouter</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
