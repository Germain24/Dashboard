"use client";
import { useMemo, useState } from "react";
import type { GpaResult } from "@/lib/etudes";
import { useCours, useGpa } from "@/lib/queries/etudes";
import { Skeleton } from "@/components/ui/skeleton";

const GPA_COLOR = (gpa: number) => {
  if (gpa >= 3.7) return "var(--success)";
  if (gpa >= 3.0) return "var(--info)";
  if (gpa >= 2.0) return "var(--warning)";
  return "var(--destructive)";
};

export function GpaTab() {
  const [semestre, setSemestre] = useState("");

  const coursQ = useCours();
  const semestres = useMemo(
    () => [...new Set((coursQ.data ?? []).map((c) => c.semestre))].sort(),
    [coursQ.data],
  );
  const gpaQ = useGpa(semestre || undefined);
  const result: GpaResult | null = gpaQ.data ?? null;
  const status: "loading" | "error" | "ready" =
    gpaQ.isLoading ? "loading" : gpaQ.isError ? "error" : "ready";

  const gpaVal = result?.gpa;
  const radius = 54;
  const circ = 2 * Math.PI * radius;
  const filled = gpaVal != null ? (gpaVal / 4.3) * circ : 0;

  return (
    <div className="space-y-6">
      <div className="flex gap-2 items-center">
        <label htmlFor="gpa-semestre" className="text-sm text-[var(--muted-foreground)]">Semestre</label>
        <select id="gpa-semestre" className="border rounded px-2 py-1 text-sm bg-[var(--card)]"
          value={semestre} onChange={e => setSemestre(e.target.value)}>
          <option value="">Cumulatif</option>
          {semestres.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {status === "loading" && <Skeleton lines={5} />}

      {status === "error" && (
        <div className="flex flex-col items-start gap-2 py-2">
          <p className="text-sm text-[var(--muted-foreground)]">GPA indisponible pour le moment.</p>
          <button onClick={() => void gpaQ.refetch()}
            className="rounded border border-[var(--border)] px-2.5 py-1 text-xs font-medium hover:bg-[var(--accent)]">
            Réessayer
          </button>
        </div>
      )}

      {status === "ready" && result && (
        <>
          {/* Jauge circulaire SVG */}
          <div className="flex justify-center">
            <svg width="140" height="140" viewBox="0 0 140 140">
              <circle cx="70" cy="70" r={radius} fill="none" stroke="var(--border)" strokeWidth="12" />
              <circle cx="70" cy="70" r={radius} fill="none"
                stroke={gpaVal != null ? GPA_COLOR(gpaVal) : "var(--muted-foreground)"}
                strokeWidth="12"
                strokeDasharray={`${filled} ${circ - filled}`}
                strokeLinecap="round"
                transform="rotate(-90 70 70)" />
              <text x="70" y="66" textAnchor="middle" fontSize="24" fontWeight="700"
                fill={gpaVal != null ? GPA_COLOR(gpaVal) : "var(--muted-foreground)"}>
                {gpaVal != null ? gpaVal.toFixed(2) : "—"}
              </text>
              <text x="70" y="84" textAnchor="middle" fontSize="11" fill="var(--muted-foreground)">/ 4.3</text>
            </svg>
          </div>

          <p className="text-center text-xs text-[var(--muted-foreground)]">
            {result.nb_cours_notes} cours notés sur {result.nb_cours}
            {semestre ? ` — ${semestre}` : " (cumulatif)"}
          </p>

          {/* Détail par cours */}
          <div className="space-y-1">
            {result.detail.map(cg => (
              <div key={cg.cours_id} className="flex items-center gap-2 text-sm py-1 border-b border-[var(--border)] last:border-0">
                <span className="font-mono text-xs w-20 shrink-0 text-[var(--muted-foreground)]">{cg.code}</span>
                <span className="flex-1 text-xs truncate">{cg.nom}</span>
                {cg.note_finale != null ? (
                  <>
                    <span className="text-xs text-[var(--muted-foreground)]">{cg.note_finale}/100</span>
                    <span className="font-bold text-sm" style={{ color: GPA_COLOR(cg.points_gpa ?? 0) }}>
                      {cg.lettre}
                    </span>
                    <span className="text-xs w-8 text-right text-[var(--muted-foreground)]">{cg.points_gpa?.toFixed(1)}</span>
                  </>
                ) : (
                  <span className="text-xs text-[var(--muted-foreground)] italic">non noté</span>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
