"use client";

/** Planification simple : départ + dates + budget -> jusqu'à 5 itinéraires
 *  proposés automatiquement (aucune sélection manuelle de lieux). */

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { usePlanifierAuto, useConfirmerVoyage } from "@/lib/queries/voyage";
import { buildConfirmerRequest, type Itineraire } from "@/lib/voyage";
import { notifySuccess } from "@/lib/toast";
import { DatePicker } from "@/components/ui/date-picker";

const eur = (n: number) =>
  new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(n);

type GroupeDestination = { destination: string; pays: string; jours: number; lieux: string[] };

// Le nombre de jours affiché par pays ne compte que le temps SUR PLACE : le
// transport entre étapes (dates d'arrivée/départ) peut représenter plusieurs
// jours supplémentaires non visibles dans ce total -- on l'affiche à part
// pour éviter l'impression que des jours de vacances "disparaissent".
function dureeVoyage(etapes: Itineraire["etapes"]): { totalJours: number; joursTransport: number } {
  if (etapes.length === 0) return { totalJours: 0, joursTransport: 0 };
  const debut = new Date(etapes[0].date_arrivee);
  const fin = new Date(etapes[etapes.length - 1].date_depart);
  const totalJours = Math.round((fin.getTime() - debut.getTime()) / 86_400_000);
  const joursSejour = etapes.reduce((somme, e) => somme + e.jours, 0);
  return { totalJours, joursTransport: Math.max(0, totalJours - joursSejour) };
}

// Les prix/durées de vol sont des ESTIMATIONS (formule par distance) : afficher
// une date d'arrivée/départ précise par lieu donnerait une fausse précision.
// On regroupe donc par pays -- nombre de jours + lieux prévus -- plutôt qu'un
// itinéraire jour par jour.
function grouperParDestination(etapes: Itineraire["etapes"]): GroupeDestination[] {
  const groupes: GroupeDestination[] = [];
  const indexParDestination = new Map<string, number>();
  for (const e of etapes) {
    const pays = e.pays ?? "Pays inconnu";
    const key = e.aeroport_iata ?? e.ville ?? pays;
    if (!indexParDestination.has(key)) {
      indexParDestination.set(key, groupes.length);
      groupes.push({ destination: e.ville ?? key, pays, jours: 0, lieux: [] });
    }
    const g = groupes[indexParDestination.get(key)!];
    g.jours += e.jours;
    g.lieux.push(e.nom);
  }
  return groupes;
}

// Taux CAD->EUR approximatif, seulement pour pré-remplir depuis le budget
// voyage de l'onglet Crédit (en CAD) -- l'utilisateur doit vérifier/ajuster,
// ce n'est pas un taux de change live.
const CAD_EUR_APPROX = 0.65;

function todayPlus(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export function PlanifierAutoTab({ onConfirmed }: { onConfirmed?: () => void }) {
  const params = useSearchParams();
  const budgetCad = params.get("budget");
  const joursParam = params.get("jours");

  const [departIata, setDepartIata] = useState("YUL");
  const [arriveeIata, setArriveeIata] = useState("");
  const [dateDebut, setDateDebut] = useState(joursParam ? todayPlus(30) : "");
  const [dateFin, setDateFin] = useState(
    joursParam ? todayPlus(30 + Number(joursParam)) : "",
  );
  const [budget, setBudget] = useState(
    budgetCad ? Math.round(Number(budgetCad) * CAD_EUR_APPROX) : 3000,
  );
  const [itineraires, setItineraires] = useState<Itineraire[] | null>(null);
  const [prixLive, setPrixLive] = useState(true);

  const planifierMut = usePlanifierAuto();
  const confirmerMut = useConfirmerVoyage();

  const soumettre = () => {
    if (!dateDebut || !dateFin) return;
    setItineraires(null);
    planifierMut.mutate(
      {
        depart_iata: departIata,
        arrivee_iata: arriveeIata || undefined,
        date_debut: dateDebut, date_fin: dateFin, budget_total: budget, k: 5,
        prix_live: prixLive,
      },
      { onSuccess: (res) => setItineraires(res.itineraires) },
    );
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--muted-foreground)]">
        Dis où tu pars, entre quelles dates et avec quel budget — les lieux sont choisis automatiquement
        Le calcul tient compte des paliers, de la saison, des activités et des transports locaux.
        Les vols sont vérifiés aux dates choisies quand Duffel est configuré.
      </p>
      {budgetCad && (
        <p className="text-xs text-[var(--muted-foreground)]">
          Budget pré-rempli depuis le budget voyage carte de crédit ({budgetCad} CAD, converti approximativement
          en EUR à ~{CAD_EUR_APPROX} — vérifie/ajuste avant de lancer).
        </p>
      )}
      <details className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm">
        <summary className="cursor-pointer font-medium">Comment améliorer la précision</summary>
        <p className="mt-2 text-[var(--muted-foreground)]">
          Dans Voyage.xlsx, complète « Coût activité », « Transport local » et « Mois disponibles »
          (par exemple 06-09). « Ordre » gère les prérequis, « Progression » sépare les filières
          course/montagne, et « Priorité » note ton envie de 1 à 5. La clé DUFFEL_API_KEY active
          les tarifs aériens datés.
        </p>
      </details>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <label className="text-sm">
          Départ (IATA)
          <input value={departIata} onChange={(e) => setDepartIata(e.target.value.toUpperCase())}
                 className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-1.5 text-sm" />
        </label>
        <label className="text-sm">
          Retour (IATA, optionnel)
          <input value={arriveeIata} onChange={(e) => setArriveeIata(e.target.value.toUpperCase())}
                 placeholder={departIata}
                 className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-1.5 text-sm" />
        </label>
        <DatePicker
          id="voyage-date-debut" label="Date de début"
          value={dateDebut} min={todayPlus(0)} onChange={setDateDebut}
        />
        <DatePicker
          id="voyage-date-fin" label="Date de fin"
          value={dateFin} min={dateDebut || todayPlus(0)} onChange={setDateFin}
        />
        <label className="text-sm sm:col-span-2">
          Budget total (€)
          <input type="number" value={budget} onChange={(e) => setBudget(Number(e.target.value))}
                 className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-1.5 text-sm" />
        </label>
        <label className="flex cursor-pointer items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" checked={prixLive} onChange={(e) => setPrixLive(e.target.checked)} />
          Vérifier les prix de vols aux dates exactes
        </label>
      </div>
      <button
        onClick={soumettre}
        disabled={planifierMut.isPending || !dateDebut || !dateFin}
        className="rounded bg-[var(--primary)] px-4 py-2 text-sm text-[var(--primary-foreground)] disabled:opacity-50"
      >
        {planifierMut.isPending ? "Recherche des itinéraires…" : "Trouver des itinéraires"}
      </button>
      {planifierMut.isError && (
        <div className="text-sm text-[var(--destructive)]">
          {planifierMut.error?.message ?? "Erreur de planification"}
        </div>
      )}

      {itineraires && (
        <div className="space-y-3">
          <p className="text-sm font-semibold">{itineraires.length} itinéraire(s) trouvé(s)</p>
          {itineraires.map((itin, i) => {
            const groupes = grouperParDestination(itin.etapes);
            const { totalJours, joursTransport } = dureeVoyage(itin.etapes);
            return (
            <div key={i} className="space-y-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold">
                  #{i + 1} — {groupes.length} destination(s) · {totalJours} jours · {eur(itin.cout_total)}
                </span>
                <span className={`rounded-full px-2 py-1 text-xs ${itin.fiabilite_prix === "élevée" ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" : "bg-amber-500/15 text-amber-700 dark:text-amber-300"}`}>
                  {itin.source_prix_vol === "live" ? "Vols vérifiés" : itin.source_prix_vol === "cache_live" ? "Prix live en cache" : "Prix estimés"}
                </span>
              </div>
              <p className="text-xs text-[var(--muted-foreground)]">
                vols et transit {eur(itin.cout_transport)} · hébergement {eur(itin.cout_hebergement ?? 0)} · nourriture {eur(itin.cout_nourriture ?? 0)} · activités {eur(itin.cout_activites ?? 0)} · local {eur(itin.cout_transport_local ?? 0)}
                {itin.transporteur ? ` · ${itin.transporteur}` : ""}
              </p>
              {joursTransport > 0 && (
                <p className="text-xs text-[var(--muted-foreground)]">
                  dont {joursTransport} jour(s) de transport entre étapes
                </p>
              )}
              <ul className="space-y-1.5 text-sm">
                {groupes.map((g) => (
                  <li key={`${g.pays}-${g.destination}`}>
                    <span className="font-medium">{g.destination}, {g.pays}</span> — {g.jours} jour(s) :{" "}
                    <span className="text-[var(--muted-foreground)]">{g.lieux.join(", ")}</span>
                  </li>
                ))}
              </ul>
              {(itin.avertissements?.length ?? 0) > 0 && (
                <ul className="space-y-1 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2 text-xs text-amber-800 dark:text-amber-200">
                  {itin.avertissements?.map((warning) => <li key={warning}>{warning}</li>)}
                </ul>
              )}
              <button
                onClick={() =>
                  confirmerMut.mutate(
                    buildConfirmerRequest(itin, {
                      dateDebut, dateFin, departIata, arriveeIata,
                    }),
                    {
                      onSuccess: () => {
                        setItineraires(null);
                        notifySuccess("Voyage confirmé — checklist et budget disponibles plus bas.");
                        onConfirmed?.();
                      },
                    },
                  )
                }
                disabled={confirmerMut.isPending}
                className="rounded border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--muted)] disabled:opacity-50"
              >
                {confirmerMut.isPending ? "Confirmation…" : "Confirmer ce voyage"}
              </button>
            </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
