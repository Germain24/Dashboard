"use client";

/** Préférences de planification (remplace l'onglet Tâches).
 *  Moment préféré par activité (matin / après-midi / soir) → pris en compte par
 *  le planificateur au prochain plan. Extensible (jours préférés, ordre). */

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Moon, Dumbbell, ChefHat, GraduationCap } from "lucide-react";

type Moments = Record<string, string>;

const ACTIVITIES = [
  { key: "sport", label: "Sport", Icon: Dumbbell },
  { key: "etudes", label: "Études", Icon: GraduationCap },
  { key: "cuisine", label: "Batch cooking", Icon: ChefHat },
] as const;

const MOMENTS = [
  { value: "", label: "Auto (créneau libre)" },
  { value: "matin", label: "Matin" },
  { value: "aprem", label: "Après-midi" },
  { value: "soir", label: "Soir" },
];

export default function PreferencesTab() {
  const [moments, setMoments] = useState<Moments>({});
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch("/api/agenda/preferences")
      .then((r) => (r.ok ? r.json() : { moments: {} }))
      .then((d) => setMoments(d.moments ?? {}))
      .catch(() => setMoments({}))
      .finally(() => setLoaded(true));
  }, []);

  const update = (key: string, value: string) => {
    const next = { ...moments };
    if (value) next[key] = value;
    else delete next[key];
    setMoments(next);
    fetch("/api/agenda/preferences", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ moments: { [key]: value } }),
    })
      .then((r) => {
        if (!r.ok) throw new Error();
        toast.success("Préférence enregistrée — appliquée au prochain plan.");
      })
      .catch(() => toast.error("Échec de l'enregistrement."));
  };

  return (
    <div className="max-w-xl space-y-4">
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <Moon className="h-4 w-4 text-[var(--muted-foreground)]" aria-hidden="true" />
          Moment préféré par activité
        </h2>
        <p className="mt-1 text-xs text-[var(--muted-foreground)]">
          Le planificateur place ces blocs au moment choisi s'il y a un créneau libre,
          sinon il prend le premier créneau disponible.
        </p>

        <div className="mt-4 space-y-3">
          {ACTIVITIES.map(({ key, label, Icon }) => (
            <div key={key} className="flex items-center gap-3">
              <Icon className="h-4 w-4 shrink-0 text-[var(--muted-foreground)]" aria-hidden="true" />
              <span className="w-32 text-sm">{label}</span>
              <select
                value={moments[key] ?? ""}
                disabled={!loaded}
                onChange={(e) => update(key, e.target.value)}
                aria-label={`Moment préféré pour ${label}`}
                className="flex-1 rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm"
              >
                {MOMENTS.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>
          ))}
        </div>
      </div>

      <p className="text-xs text-[var(--muted-foreground)]">
        Les changements s'appliquent à la prochaine génération du plan (Agenda → Planifier,
        ou la replanification hebdomadaire automatique).
      </p>
    </div>
  );
}
