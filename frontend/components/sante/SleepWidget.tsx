"use client";

/** Widget de sommeil : saisie durée/qualité du jour + corrélation poids (#68). */

import { useState } from "react";
import { useLogSleep, useSleepSummary } from "@/lib/queries/sante";

type SavedSleep = { sommeil_h: number; sommeil_q?: number };
type SleepSummary = { n: number; correlation: number | null; sommeil_moyen_h: number | null };

function SavedLabel({ saved }: { saved: SavedSleep | null }) {
  if (!saved) return null;
  return <span className="text-xs tabular-nums text-[var(--success)]">Enregistré : {saved.sommeil_h} h{saved.sommeil_q ? ` · qualité ${saved.sommeil_q}/5` : ""}</span>;
}

function QualityButtons({ value, onChange }: { value: number | null; onChange: (quality: number | null) => void }) {
  return <div className="mt-1 flex gap-1">{[1, 2, 3, 4, 5].map((quality) => <button key={quality} type="button" onClick={() => onChange(quality === value ? null : quality)} aria-pressed={quality === value} aria-label={`Qualité ${quality} sur 5`} className={`text-base leading-none ${quality <= (value ?? 0) ? "opacity-100" : "opacity-30"} hover:opacity-100`}>★</button>)}</div>;
}

function SleepSummary({ summary, label }: { summary: SleepSummary | null; label: (correlation: number | null) => string }) {
  if (!summary || summary.n < 3) return null;
  return <p className="text-xs text-[var(--muted-foreground)]">Moyenne {summary.sommeil_moyen_h} h sur {summary.n} jours · {label(summary.correlation)}</p>;
}

export function SleepWidget() {
  const [heures, setHeures] = useState<string>("");
  const [qualite, setQualite] = useState<number | null>(null);
  const [saved, setSaved] = useState<{ sommeil_h: number; sommeil_q?: number } | null>(null);

  const summary = useSleepSummary().data as SleepSummary | null;
  const logMutation = useLogSleep();
  const saving = logMutation.isPending;

  const save = () => {
    const h = parseFloat(heures);
    if (!Number.isFinite(h) || h <= 0) return;
    logMutation.mutate({ heures: h, qualite: qualite ?? undefined }, {
      onSuccess: (res) => setSaved({ sommeil_h: res.sommeil_h, sommeil_q: res.sommeil_q }),
    });
  };

  const corrLabel = (c: number | null): string => {
    if (c === null) return "données insuffisantes";
    if (c <= -0.3) return "plus tu dors, plus ton poids baisse";
    if (c >= 0.3) return "plus tu dors, plus ton poids monte";
    return "pas de lien net";
  };

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">😴 Sommeil</h3>
        <SavedLabel saved={saved} />
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <label className="text-xs flex flex-col">
          Durée (h)
          <input
            type="number"
            step="0.25"
            min="0"
            max="24"
            value={heures}
            onChange={(e) => setHeures(e.target.value)}
            placeholder="7.5"
            className="mt-1 w-20 rounded border border-[var(--border)] bg-transparent px-2 py-1 text-sm"
          />
        </label>
        <div className="flex flex-col text-xs">Qualité<QualityButtons value={qualite} onChange={setQualite} /></div>
        <button
          onClick={() => void save()}
          disabled={saving || !heures}
          className="rounded-md border border-[var(--border)] px-2.5 py-1 text-xs hover:bg-[var(--muted)] disabled:opacity-50"
        >
          {saving ? "…" : "Enregistrer"}
        </button>
      </div>

      <SleepSummary summary={summary} label={corrLabel} />
    </div>
  );
}
