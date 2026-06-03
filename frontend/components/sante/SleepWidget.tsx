"use client";

/** Widget de sommeil : saisie durée/qualité du jour + corrélation poids (#68). */

import { useEffect, useState } from "react";
import { santeApi } from "@/lib/sante";

export function SleepWidget() {
  const [heures, setHeures] = useState<string>("");
  const [qualite, setQualite] = useState<number | null>(null);
  const [saved, setSaved] = useState<{ sommeil_h: number; sommeil_q?: number } | null>(null);
  const [summary, setSummary] = useState<{ n: number; correlation: number | null; sommeil_moyen_h: number | null } | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    santeApi.sleepSummary().then(setSummary).catch(() => {});
  }, []);

  const save = async () => {
    const h = parseFloat(heures);
    if (!Number.isFinite(h) || h <= 0) return;
    setSaving(true);
    try {
      const res = await santeApi.logSleep(h, qualite ?? undefined);
      setSaved({ sommeil_h: res.sommeil_h, sommeil_q: res.sommeil_q });
      santeApi.sleepSummary().then(setSummary).catch(() => {});
    } catch {
      /* toast global */
    } finally {
      setSaving(false);
    }
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
        {saved && (
          <span className="text-xs text-[var(--success)] tabular-nums">
            Enregistré : {saved.sommeil_h} h{saved.sommeil_q ? ` · qualité ${saved.sommeil_q}/5` : ""}
          </span>
        )}
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
        <div className="text-xs flex flex-col">
          Qualité
          <div className="mt-1 flex gap-1">
            {[1, 2, 3, 4, 5].map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => setQualite(q === qualite ? null : q)}
                aria-pressed={q === qualite}
                aria-label={`Qualité ${q} sur 5`}
                className={`text-base leading-none ${q <= (qualite ?? 0) ? "opacity-100" : "opacity-30"} hover:opacity-100`}
              >
                ★
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={save}
          disabled={saving || !heures}
          className="rounded-md border border-[var(--border)] px-2.5 py-1 text-xs hover:bg-[var(--muted)] disabled:opacity-50"
        >
          {saving ? "…" : "Enregistrer"}
        </button>
      </div>

      {summary && summary.n >= 3 && (
        <p className="text-xs text-[var(--muted-foreground)]">
          Moyenne {summary.sommeil_moyen_h} h sur {summary.n} jours · {corrLabel(summary.correlation)}
        </p>
      )}
    </div>
  );
}
