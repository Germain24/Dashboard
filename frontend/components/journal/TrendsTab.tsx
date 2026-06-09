"use client";

import { useEffect, useState } from "react";
import { journalApi, type MoodTrends } from "@/lib/journal";

export function TrendsTab() {
  const [t, setT] = useState<MoodTrends | null>(null);
  useEffect(() => { journalApi.trends(30).then(setT).catch(() => {}); }, []);
  if (!t) return <p className="text-sm text-[var(--muted-foreground)]">Chargement…</p>;
  if (t.n === 0) return <p className="text-sm text-[var(--muted-foreground)]">Aucune entrée sur 30 jours.</p>;

  const maxTag = t.tags_freq[0]?.count || 1;
  // Sparkline 1-5 : convertit une série MA7 en polyline SVG (viewBox 100x40).
  const line = (pts: { value: number }[]) => {
    if (pts.length < 2) return "";
    return pts.map((p, i) => {
      const x = (i / (pts.length - 1)) * 100;
      const y = 40 - ((p.value - 1) / 4) * 40; // humeur 1..5 -> y 40..0
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
  };
  return (
    <div className="space-y-5">
      <div className="flex gap-6 text-sm">
        <span>Humeur moyenne : <strong>{t.moyenne_humeur}</strong>/5</span>
        <span>Énergie moyenne : <strong>{t.moyenne_energie}</strong>/5</span>
        <span className="text-[var(--muted-foreground)]">{t.n} jours</span>
      </div>
      <div>
        <h3 className="text-sm font-medium mb-1">Humeur (—) &amp; énergie (·) — moyenne mobile 7 j</h3>
        <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="w-full h-24 rounded border border-[var(--border)]">
          <polyline points={line(t.humeur_ma7)} fill="none" stroke="var(--ring)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
          <polyline points={line(t.energie_ma7)} fill="none" stroke="var(--muted-foreground)" strokeWidth="1" strokeDasharray="3 2" vectorEffect="non-scaling-stroke" />
        </svg>
      </div>
      <div>
        <h3 className="text-sm font-medium mb-1">Distribution de l&apos;humeur</h3>
        <div className="flex items-end gap-2 h-24">
          {[1, 2, 3, 4, 5].map((n) => {
            const c = t.distribution_humeur[String(n)] || 0;
            const max = Math.max(...Object.values(t.distribution_humeur), 1);
            return (
              <div key={n} className="flex flex-col items-center gap-1">
                <div className="w-8 rounded-t bg-[var(--ring)]" style={{ height: `${(c / max) * 100}%` }} />
                <span className="text-xs text-[var(--muted-foreground)]">{n}</span>
              </div>
            );
          })}
        </div>
      </div>
      <div>
        <h3 className="text-sm font-medium mb-1">Émotions fréquentes</h3>
        <div className="space-y-1">
          {t.tags_freq.map((f) => (
            <div key={f.tag} className="flex items-center gap-2 text-xs">
              <span className="w-24">{f.tag}</span>
              <div className="h-2 rounded-full bg-[var(--ring)]" style={{ width: `${(f.count / maxTag) * 160}px` }} />
              <span className="text-[var(--muted-foreground)]">{f.count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
