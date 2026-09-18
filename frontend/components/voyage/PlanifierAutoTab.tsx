"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { useConfirmerVoyage, usePlanifierAuto } from "@/lib/queries/voyage";
import { buildConfirmerRequest, type Itineraire } from "@/lib/voyage";
import { notifySuccess } from "@/lib/toast";
import { AutoPlanningView, todayPlus } from "@/components/voyage/PlanifierAutoParts";

const CAD_EUR_APPROX = 0.65;

function mutationError(error: unknown): Error | null {
  return error instanceof Error ? error : null;
}

function useAutoPlanning(onConfirmed?: () => void) {
  const params = useSearchParams();
  const budgetCad = params.get("budget");
  const joursParam = params.get("jours");
  const [departIata, setDepartIata] = useState("YUL");
  const [arriveeIata, setArriveeIata] = useState("");
  const [dateDebut, setDateDebut] = useState(joursParam ? todayPlus(30) : "");
  const [dateFin, setDateFin] = useState(joursParam ? todayPlus(30 + Number(joursParam)) : "");
  const [budget, setBudget] = useState(budgetCad ? Math.round(Number(budgetCad) * CAD_EUR_APPROX) : 3000);
  const [itineraires, setItineraires] = useState<Itineraire[] | null>(null);
  const [prixLive, setPrixLive] = useState(true);
  const planifier = usePlanifierAuto();
  const confirmer = useConfirmerVoyage();

  const soumettre = () => {
    if (!dateDebut || !dateFin) return;
    setItineraires(null);
    planifier.mutate({ depart_iata: departIata, arrivee_iata: arriveeIata || undefined, date_debut: dateDebut, date_fin: dateFin, budget_total: budget, k: 5, prix_live: prixLive }, { onSuccess: (result) => setItineraires(result.itineraires) });
  };

  const confirmerItineraire = (itinerary: Itineraire) => {
    confirmer.mutate(buildConfirmerRequest(itinerary, { dateDebut, dateFin, departIata, arriveeIata }), {
      onSuccess: () => {
        setItineraires(null);
        notifySuccess("Voyage confirmé — checklist et budget disponibles plus bas.");
        onConfirmed?.();
      },
    });
  };

  return {
    budgetCad,
    departIata,
    arriveeIata,
    dateDebut,
    dateFin,
    budget,
    prixLive,
    itineraires,
    planifierPending: planifier.isPending,
    planifierError: mutationError(planifier.error),
    confirmerPending: confirmer.isPending,
    onDepartChange: setDepartIata,
    onArriveeChange: setArriveeIata,
    onDateDebutChange: setDateDebut,
    onDateFinChange: setDateFin,
    onBudgetChange: setBudget,
    onPrixLiveChange: setPrixLive,
    onSubmit: soumettre,
    onConfirm: confirmerItineraire,
  };
}

export function PlanifierAutoTab({ onConfirmed }: { onConfirmed?: () => void }) {
  return <AutoPlanningView {...useAutoPlanning(onConfirmed)} />;
}
