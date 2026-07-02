"use client";

import { useState } from "react";
import { usePlanifier, useConfirmerVoyage } from "@/lib/queries/voyage";
import type { Itineraire } from "@/lib/voyage";
import { notifySuccess } from "@/lib/toast";

export function PlanifierTab({
  candidats,
  onConfirmed,
}: {
  candidats: number[];
  onConfirmed?: () => void;
}) {
  const [departIata, setDepartIata] = useState("YUL");
  const [arriveeIata, setArriveeIata] = useState("YUL");
  const [dateDebut, setDateDebut] = useState("");
  const [dateFin, setDateFin] = useState("");
  const [budget, setBudget] = useState(3000);
  const [resultat, setResultat] = useState<Itineraire | null>(null);

  const planifierMut = usePlanifier();
  const confirmerMut = useConfirmerVoyage();

  const soumettre = () => {
    if (candidats.length === 0 || !dateDebut || !dateFin) return;
    planifierMut.mutate(
      {
        candidats, depart_iata: departIata, arrivee_iata: arriveeIata,
        date_debut: dateDebut, date_fin: dateFin, budget_total: budget,
      },
      { onSuccess: setResultat },
    );
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <label className="text-sm">
          Départ (IATA)
          <input value={departIata} onChange={(e) => setDepartIata(e.target.value.toUpperCase())}
                 className="mt-1 w-full rounded border border-[var(--border)] p-1.5" />
        </label>
        <label className="text-sm">
          Arrivée (IATA)
          <input value={arriveeIata} onChange={(e) => setArriveeIata(e.target.value.toUpperCase())}
                 className="mt-1 w-full rounded border border-[var(--border)] p-1.5" />
        </label>
        <label className="text-sm">
          Budget total (€)
          <input type="number" value={budget} onChange={(e) => setBudget(Number(e.target.value))}
                 className="mt-1 w-full rounded border border-[var(--border)] p-1.5" />
        </label>
        <label className="text-sm">
          Date de début
          <input type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)}
                 className="mt-1 w-full rounded border border-[var(--border)] p-1.5" />
        </label>
        <label className="text-sm">
          Date de fin
          <input type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)}
                 className="mt-1 w-full rounded border border-[var(--border)] p-1.5" />
        </label>
      </div>
      <button
        onClick={soumettre}
        disabled={planifierMut.isPending || candidats.length === 0}
        className="rounded bg-[var(--primary)] px-4 py-2 text-sm text-[var(--primary-foreground)] disabled:opacity-50"
      >
        {planifierMut.isPending ? "Calcul en cours…" : "Planifier"}
      </button>
      {planifierMut.isError && (
        <div className="text-sm text-[var(--destructive)]">
          {(planifierMut.error as Error)?.message ?? "Erreur de planification"}
        </div>
      )}
      {resultat && (
        <div className="space-y-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <div className="text-sm font-semibold">
            {resultat.etapes.length} lieu(x) retenu(s) · {resultat.cout_total.toFixed(0)} €
            (transport {resultat.cout_transport.toFixed(0)} € + séjour {resultat.cout_sejour.toFixed(0)} €)
          </div>
          <ol className="list-decimal space-y-1 pl-5 text-sm">
            {resultat.etapes.map((e) => (
              <li key={e.lieu_id}>
                {e.nom} — {e.jours} jour(s), du {e.date_arrivee} au {e.date_depart}
              </li>
            ))}
          </ol>
          <button
            onClick={() =>
              confirmerMut.mutate(resultat.etapes.map((e) => e.lieu_id), {
                onSuccess: () => {
                  setResultat(null);
                  notifySuccess("Voyage confirmé !");
                  onConfirmed?.();
                },
              })
            }
            disabled={confirmerMut.isPending}
            className="rounded border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
          >
            {confirmerMut.isPending ? "Confirmation…" : "Confirmer ce voyage"}
          </button>
          {confirmerMut.isError && (
            <div className="text-sm text-[var(--destructive)]">
              {(confirmerMut.error as Error)?.message ?? "Erreur de confirmation"}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
