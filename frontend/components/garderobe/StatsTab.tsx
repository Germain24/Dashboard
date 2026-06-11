"use client";

import { useState } from "react";
import type { StatsResponse, WearFrequency, Vetement } from "@/lib/garderobe";
import { emojiForCategorie, assetUrl } from "@/lib/garderobe";
import { useWearFrequence } from "@/lib/queries/garderobe";

export function StatsTab({ stats }: { stats: StatsResponse }) {
  const freq: WearFrequency | null = useWearFrequence(5).data ?? null;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <StatCard label="Pièces" value={String(stats.total)} />
        <StatCard
          label="Valeur estimée"
          value={`${stats.valeur_estimee.toLocaleString("fr-CA", { maximumFractionDigits: 0 })} $`}
          hint={stats.valeur_count < stats.total ? `${stats.valeur_count}/${stats.total} avec prix` : undefined}
        />
        <StatCard label="À laver" value={String(stats.a_laver.length)} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Section title="Par catégorie" entries={stats.par_categorie} />
        <Section title="Par couleur" entries={stats.par_couleur} />
      </div>
      <Section title="Par style" entries={stats.par_style} />
      <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="text-xs font-medium uppercase mb-2 text-[var(--muted-foreground)]">
          Ratio couleurs (cible 60 / 30 / 10)
        </div>
        <div className="text-sm">
          <span>Neutres : {(stats.color_ratio.Neutre * 100).toFixed(0)}%</span>
          {" · "}
          <span className="text-[var(--ring)]">Secondaires : {(stats.color_ratio.Secondaire * 100).toFixed(0)}%</span>
          {" · "}
          <span className="text-[var(--warning)]">Accents : {(stats.color_ratio.Accent * 100).toFixed(0)}%</span>
        </div>
      </div>
      <div>
        <h3 className="text-sm font-semibold mb-2">🧺 À laver maintenant ({stats.a_laver.length})</h3>
        {stats.a_laver.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">Rien à laver, bien joué.</p>
        ) : (
          <div className="space-y-2">
            {stats.a_laver.map((v) => <LavanderieRow key={v.id} v={v} />)}
          </div>
        )}
      </div>
      {stats.hs.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-2">💀 Hors-service ({stats.hs.length})</h3>
          <div className="space-y-2">
            {stats.hs.map((v) => <LavanderieRow key={v.id} v={v} />)}
          </div>
        </div>
      )}

      {/* Fréquence de port (#77) */}
      {freq && (
        <div className="space-y-4">
          {freq.never_worn.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold mb-2">
                🗑️ Jamais portées — à recycler ? ({freq.never_worn_count})
              </h3>
              <div className="flex flex-wrap gap-2">
                {freq.never_worn.map((v) => <WearChip key={v.id} v={v} />)}
              </div>
            </div>
          )}
          {freq.most_worn.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold mb-2">❤️ Les plus portées</h3>
              <div className="flex flex-wrap gap-2">
                {freq.most_worn.map((v) => <WearChip key={v.id} v={v} showCount />)}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function WearChip({ v, showCount }: { v: Vetement; showCount?: boolean }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--card)] px-2.5 py-1 text-xs"
      title={v.nom}
    >
      <span>{emojiForCategorie(v.categorie)}</span>
      <span className="max-w-[10rem] truncate">{v.nom}</span>
      {showCount && <span className="text-[var(--muted-foreground)] tabular-nums">{v.portes}×</span>}
    </span>
  );
}

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3">
      <div className="text-[11px] uppercase tracking-wide text-[var(--muted-foreground)]">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
      {hint && <div className="text-[10px] text-[var(--muted-foreground)]">{hint}</div>}
    </div>
  );
}

function Section({ title, entries }: { title: string; entries: { label: string; count: number }[] }) {
  const total = entries.reduce((a, b) => a + b.count, 0) || 1;
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="text-xs font-medium uppercase mb-3 text-[var(--muted-foreground)]">{title}</div>
      <div className="space-y-1">
        {entries.slice(0, 10).map((e) => (
          <div key={e.label} className="flex items-center gap-2 text-sm">
            <div className="w-24 truncate" title={e.label}>{e.label}</div>
            <div className="flex-1 h-2 bg-[var(--muted)] rounded overflow-hidden">
              <div className="h-full bg-[var(--ring)]" style={{ width: `${(e.count / total) * 100}%` }} />
            </div>
            <div className="w-8 text-right text-xs text-[var(--muted-foreground)]">{e.count}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function LavanderieRow({ v }: { v: any }) {
  const [failed, setFailed] = useState(false);
  return (
    <div className="flex items-center gap-3 p-2 rounded border border-[var(--destructive)]/50 bg-[var(--destructive)]/10">
      <div className="w-10 flex justify-center">
        {!failed ? (
          <img src={assetUrl(v.id)} alt={v.nom} onError={() => setFailed(true)} style={{ imageRendering: "pixelated", height: "28px" }} />
        ) : (
          <span className="text-lg">{emojiForCategorie(v.categorie)}</span>
        )}
      </div>
      <div className="flex-1 text-sm">
        <div className="font-medium">{v.nom}</div>
        <div className="text-[11px] text-[var(--muted-foreground)]">
          {v.marque ? v.marque + " · " : ""}{v.portes} ports · lavage / {v.etat_propre}
        </div>
      </div>
    </div>
  );
}
