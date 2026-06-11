"use client";

import { useState } from "react";
import {
  WEEKDAY_LABELS_FULL,
  type Exercice,
  type Programme,
  type ProgrammeJour,
} from "@/lib/entrainement";
import { usePatchProgramJour } from "@/lib/queries/entrainement";

type Props = {
  program: Programme;
  exercices: Exercice[];
};

const LABEL_OPTIONS = [
  "Push", "Pull", "Legs", "Upper", "Lower", "Repos", "Cardio", "Custom",
];

export function ProgrammeTab({ program, exercices }: Props) {
  const [editing, setEditing] = useState<number | null>(null);
  const [draftLabel, setDraftLabel] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);
  const patchMutation = usePatchProgramJour();
  const busy = patchMutation.isPending;

  const handleEdit = (j: ProgrammeJour) => {
    setEditing(j.weekday);
    setDraftLabel(j.label);
  };

  const handleSave = (weekday: number) => {
    setErr(null);
    patchMutation.mutate(
      { weekday, payload: { label: draftLabel } },
      {
        onSuccess: () => setEditing(null),
        onError: (e) => setErr(e instanceof Error ? e.message : "Erreur"),
      },
    );
  };

  return (
    <div className="space-y-4">
      <div className="rounded border border-[var(--border)] p-3 text-sm">
        <p className="font-medium">{program.nom}</p>
        {program.description && (
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">
            {program.description}
          </p>
        )}
      </div>

      <div className="rounded border border-[var(--border)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--muted)]/50 text-xs uppercase text-[var(--muted-foreground)]">
            <tr>
              <th className="text-left px-3 py-2 w-32">Jour</th>
              <th className="text-left px-3 py-2">Label</th>
              <th className="text-right px-3 py-2 w-32">Action</th>
            </tr>
          </thead>
          <tbody>
            {program.jours.map((j) => (
              <tr key={j.id} className="border-t border-[var(--border)]">
                <td className="px-3 py-1.5">{WEEKDAY_LABELS_FULL[j.weekday]}</td>
                <td className="px-3 py-1.5">
                  {editing === j.weekday ? (
                    <select
                      value={draftLabel}
                      onChange={(e) => setDraftLabel(e.target.value)}
                      className="rounded border border-[var(--border)] bg-transparent px-2 py-1 text-xs"
                    >
                      {LABEL_OPTIONS.map((l) => (
                        <option key={l} value={l}>{l}</option>
                      ))}
                    </select>
                  ) : (
                    <span className={j.label === "Repos" ? "opacity-60" : "font-medium"}>
                      {j.label}
                    </span>
                  )}
                </td>
                <td className="px-3 py-1.5 text-right">
                  {editing === j.weekday ? (
                    <div className="flex justify-end gap-1">
                      <button
                        onClick={() => handleSave(j.weekday)}
                        disabled={busy}
                        className="rounded bg-[var(--primary)] text-[var(--primary-foreground)] px-2 py-0.5 text-xs"
                      >✓</button>
                      <button
                        onClick={() => setEditing(null)}
                        className="rounded border border-[var(--border)] px-2 py-0.5 text-xs"
                      >✗</button>
                    </div>
                  ) : (
                    <button
                      onClick={() => handleEdit(j)}
                      className="rounded border border-[var(--border)] px-2 py-0.5 text-xs hover:bg-[var(--accent)]"
                    >Modifier</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {err && <div className="text-sm text-[var(--destructive)]">⚠ {err}</div>}

      <p className="text-xs text-[var(--muted-foreground)]">
        Le programme PPL/UL est créé automatiquement. Tu peux changer le label
        de chaque jour. L&apos;édition des exercices par jour (slots) est
        prévue pour une itération suivante — pour l&apos;instant, log tes
        séries en direct dans l&apos;onglet Aujourd&apos;hui.
      </p>

      <details className="rounded border border-[var(--border)] p-3 text-sm">
        <summary className="cursor-pointer font-medium">
          Catalogue exercices ({exercices.length})
        </summary>
        <div className="mt-2 max-h-64 overflow-auto">
          <ul className="text-xs space-y-0.5">
            {exercices.map((e) => (
              <li key={e.id}>
                <span className="opacity-60">[{e.categorie}]</span> {e.nom}
                {e.unilateral && <span className="opacity-50"> · unilat.</span>}
              </li>
            ))}
          </ul>
        </div>
      </details>
    </div>
  );
}
