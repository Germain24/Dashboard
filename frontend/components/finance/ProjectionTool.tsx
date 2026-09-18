"use client";

/** Calculateur d'objectif d'épargne / investissement à intérêts composés. */

import { useState } from "react";
import { financeApi } from "@/lib/finance";

type Result = {
  valeur_finale: number; total_verse: number; total_interets: number;
  mois_pour_objectif?: number | null;
};

const money = (v: number) =>
  v.toLocaleString("fr-CA", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

export function ProjectionTool() {
  const [open, setOpen] = useState(false);
  const [initial, setInitial] = useState(1000);
  const [mensuel, setMensuel] = useState(200);
  const [taux, setTaux] = useState(5);
  const [annees, setAnnees] = useState(10);
  const [objectif, setObjectif] = useState(50000);
  const [res, setRes] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);

  const compute = async () => {
    setLoading(true);
    try {
      setRes(await financeApi.projection({ initial, mensuel, taux, mois: annees * 12, objectif }));
    } catch { /* géré par le toast global */ }
    finally { setLoading(false); }
  };

  const field = (label: string, value: number, set: (n: number) => void, suffix = "") => (
    <label className="flex flex-col gap-0.5">
      <span className="text-xs text-[var(--muted-foreground)]">{label}</span>
      <input
        type="number" value={value}
        onChange={(e) => set(parseFloat(e.target.value) || 0)}
        className="w-28 px-2 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--background)]"
      />
      {suffix && <span className="text-[10px] text-[var(--muted-foreground)]">{suffix}</span>}
    </label>
  );

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border)] p-4">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between text-sm font-semibold"
      >
        🎯 Objectif d&apos;épargne — projection
        <span className="text-[var(--muted-foreground)]">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            {field("Capital initial", initial, setInitial, "€")}
            {field("Versement / mois", mensuel, setMensuel, "€")}
            {field("Rendement annuel", taux, setTaux, "%")}
            {field("Durée", annees, setAnnees, "ans")}
            {field("Objectif", objectif, setObjectif, "€")}
            <button
              onClick={compute} disabled={loading}
              className="rounded-md bg-[var(--primary)] text-[var(--primary-foreground)] px-3 py-2 text-sm font-medium disabled:opacity-50"
            >
              {loading ? "…" : "Calculer"}
            </button>
          </div>

          {res && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              <div>
                <p className="text-xs text-[var(--muted-foreground)]">Valeur finale</p>
                <p className="font-mono font-semibold">{money(res.valeur_finale)}</p>
              </div>
              <div>
                <p className="text-xs text-[var(--muted-foreground)]">Total versé</p>
                <p className="font-mono">{money(res.total_verse)}</p>
              </div>
              <div>
                <p className="text-xs text-[var(--muted-foreground)]">Intérêts gagnés</p>
                <p className="font-mono text-[var(--success)]">{money(res.total_interets)}</p>
              </div>
              <div>
                <p className="text-xs text-[var(--muted-foreground)]">Objectif atteint en</p>
                <p className="font-mono">
                  {res.mois_pour_objectif == null
                    ? "hors d'atteinte"
                    : `${Math.floor(res.mois_pour_objectif / 12)} an${res.mois_pour_objectif >= 24 ? "s" : ""} ${res.mois_pour_objectif % 12} mois`}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
