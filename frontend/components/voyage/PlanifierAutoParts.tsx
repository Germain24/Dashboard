import { DatePicker } from "@/components/ui/date-picker";
import type { Itineraire } from "@/lib/voyage";

export type GroupeDestination = { destination: string; pays: string; jours: number; lieux: string[] };

export function eur(value: number): string {
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(value);
}

export function dureeVoyage(etapes: Itineraire["etapes"]): { totalJours: number; joursTransport: number } {
  if (etapes.length === 0) return { totalJours: 0, joursTransport: 0 };
  const debut = new Date(etapes[0].date_arrivee);
  const fin = new Date(etapes[etapes.length - 1].date_depart);
  const totalJours = Math.round((fin.getTime() - debut.getTime()) / 86_400_000);
  const joursSejour = etapes.reduce((sum, etape) => sum + etape.jours, 0);
  return { totalJours, joursTransport: Math.max(0, totalJours - joursSejour) };
}

function destinationKey(etape: Itineraire["etapes"][number]): string {
  return etape.aeroport_iata ?? etape.ville ?? etape.pays ?? "Pays inconnu";
}

function createDestination(etape: Itineraire["etapes"][number]): GroupeDestination {
  const pays = etape.pays ?? "Pays inconnu";
  const key = destinationKey(etape);
  return { destination: etape.ville ?? key, pays, jours: 0, lieux: [] };
}

function getDestination(
  etape: Itineraire["etapes"][number],
  groupes: GroupeDestination[],
  indexParDestination: Map<string, number>,
): GroupeDestination {
  const key = destinationKey(etape);
  const existing = indexParDestination.get(key);
  if (existing !== undefined) return groupes[existing];
  indexParDestination.set(key, groupes.length);
  const group = createDestination(etape);
  groupes.push(group);
  return group;
}

export function grouperParDestination(etapes: Itineraire["etapes"]): GroupeDestination[] {
  const groupes: GroupeDestination[] = [];
  const indexParDestination = new Map<string, number>();
  for (const etape of etapes) {
    const group = getDestination(etape, groupes, indexParDestination);
    group.jours += etape.jours;
    group.lieux.push(etape.nom);
  }
  return groupes;
}

export function AutoPlanningView({
  budgetCad,
  departIata,
  arriveeIata,
  dateDebut,
  dateFin,
  budget,
  prixLive,
  itineraires,
  planifierPending,
  planifierError,
  confirmerPending,
  onDepartChange,
  onArriveeChange,
  onDateDebutChange,
  onDateFinChange,
  onBudgetChange,
  onPrixLiveChange,
  onSubmit,
  onConfirm,
}: {
  budgetCad: string | null;
  departIata: string;
  arriveeIata: string;
  dateDebut: string;
  dateFin: string;
  budget: number;
  prixLive: boolean;
  itineraires: Itineraire[] | null;
  planifierPending: boolean;
  planifierError: Error | null;
  confirmerPending: boolean;
  onDepartChange: (value: string) => void;
  onArriveeChange: (value: string) => void;
  onDateDebutChange: (value: string) => void;
  onDateFinChange: (value: string) => void;
  onBudgetChange: (value: number) => void;
  onPrixLiveChange: (value: boolean) => void;
  onSubmit: () => void;
  onConfirm: (itinerary: Itineraire) => void;
}) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--muted-foreground)]">Dis où tu pars, entre quelles dates et avec quel budget — les lieux sont choisis automatiquement. Le calcul tient compte des paliers, de la saison, des activités et des transports locaux. Les vols sont vérifiés aux dates choisies quand Duffel est configuré.</p>
      <BudgetHint budgetCad={budgetCad} />
      <PrecisionHelp />
      <PlanningFields
        departIata={departIata}
        arriveeIata={arriveeIata}
        dateDebut={dateDebut}
        dateFin={dateFin}
        budget={budget}
        prixLive={prixLive}
        onDepartChange={onDepartChange}
        onArriveeChange={onArriveeChange}
        onDateDebutChange={onDateDebutChange}
        onDateFinChange={onDateFinChange}
        onBudgetChange={onBudgetChange}
        onPrixLiveChange={onPrixLiveChange}
      />
      <button onClick={onSubmit} disabled={planifierPending || !dateDebut || !dateFin} className="rounded bg-[var(--primary)] px-4 py-2 text-sm text-[var(--primary-foreground)] disabled:opacity-50">{planifierPending ? "Recherche des itinéraires…" : "Trouver des itinéraires"}</button>
      <PlanningError error={planifierError} />
      <PlanningResults itineraires={itineraires} confirmerPending={confirmerPending} onConfirm={onConfirm} />
    </div>
  );
}

function BudgetHint({ budgetCad }: { budgetCad: string | null }) {
  if (!budgetCad) return null;
  return <p className="text-xs text-[var(--muted-foreground)]">Budget pré-rempli depuis le budget voyage carte de crédit ({budgetCad} CAD, converti approximativement en EUR à ~0,65 — vérifie/ajuste avant de lancer).</p>;
}

function PrecisionHelp() {
  return <details className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-3 text-sm"><summary className="cursor-pointer font-medium">Comment améliorer la précision</summary><p className="mt-2 text-[var(--muted-foreground)]">Dans Voyage.xlsx, complète « Coût activité », « Transport local » et « Mois disponibles » (par exemple 06-09). « Ordre » gère les prérequis, « Progression » sépare les filières course/montagne, et « Priorité » note ton envie de 1 à 5. La clé DUFFEL_API_KEY active les tarifs aériens datés.</p></details>;
}

function PlanningFields({ departIata, arriveeIata, dateDebut, dateFin, budget, prixLive, onDepartChange, onArriveeChange, onDateDebutChange, onDateFinChange, onBudgetChange, onPrixLiveChange }: {
  departIata: string; arriveeIata: string; dateDebut: string; dateFin: string; budget: number; prixLive: boolean;
  onDepartChange: (value: string) => void; onArriveeChange: (value: string) => void; onDateDebutChange: (value: string) => void; onDateFinChange: (value: string) => void; onBudgetChange: (value: number) => void; onPrixLiveChange: (value: boolean) => void;
}) {
  return <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
    <label className="text-sm">Départ (IATA)<input value={departIata} onChange={(event) => onDepartChange(event.target.value.toUpperCase())} className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-1.5 text-sm" /></label>
    <label className="text-sm">Retour (IATA, optionnel)<input value={arriveeIata} onChange={(event) => onArriveeChange(event.target.value.toUpperCase())} placeholder={departIata} className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-1.5 text-sm" /></label>
    <DatePicker id="voyage-date-debut" label="Date de début" value={dateDebut} min={todayPlus(0)} onChange={onDateDebutChange} />
    <DatePicker id="voyage-date-fin" label="Date de fin" value={dateFin} min={dateDebut || todayPlus(0)} onChange={onDateFinChange} />
    <label className="text-sm sm:col-span-2">Budget total (€)<input type="number" value={budget} onChange={(event) => onBudgetChange(Number(event.target.value))} className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-1.5 text-sm" /></label>
    <label className="flex cursor-pointer items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={prixLive} onChange={(event) => onPrixLiveChange(event.target.checked)} />Vérifier les prix de vols aux dates exactes</label>
  </div>;
}

export function todayPlus(days: number): string { const date = new Date(); date.setDate(date.getDate() + days); return date.toISOString().slice(0, 10); }

function PlanningError({ error }: { error: Error | null }) {
  if (!error) return null;
  return <div className="text-sm text-[var(--destructive)]">{error.message ?? "Erreur de planification"}</div>;
}

function PlanningResults({ itineraires, confirmerPending, onConfirm }: { itineraires: Itineraire[] | null; confirmerPending: boolean; onConfirm: (itinerary: Itineraire) => void }) {
  if (!itineraires) return null;
  return <div className="space-y-3"><p className="text-sm font-semibold">{itineraires.length} itinéraire(s) trouvé(s)</p>{itineraires.map((itinerary, index) => <ItineraryCard key={index} itinerary={itinerary} index={index} confirmerPending={confirmerPending} onConfirm={onConfirm} />)}</div>;
}

function ItineraryCard({ itinerary, index, confirmerPending, onConfirm }: { itinerary: Itineraire; index: number; confirmerPending: boolean; onConfirm: (itinerary: Itineraire) => void }) {
  const groupes = grouperParDestination(itinerary.etapes);
  const { totalJours, joursTransport } = dureeVoyage(itinerary.etapes);
  return <div className="space-y-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"><div className="flex items-center justify-between"><span className="text-sm font-semibold">#{index + 1} — {groupes.length} destination(s) · {totalJours} jours · {eur(itinerary.cout_total)}</span><PriceReliability itinerary={itinerary} /></div><p className="text-xs text-[var(--muted-foreground)]">vols et transit {eur(itinerary.cout_transport)} · hébergement {eur(itinerary.cout_hebergement ?? 0)} · nourriture {eur(itinerary.cout_nourriture ?? 0)} · activités {eur(itinerary.cout_activites ?? 0)} · local {eur(itinerary.cout_transport_local ?? 0)}{itinerary.transporteur ? ` · ${itinerary.transporteur}` : ""}</p><TransportNotice days={joursTransport} /><DestinationList groupes={groupes} /><WarningList warnings={itinerary.avertissements} /><button onClick={() => onConfirm(itinerary)} disabled={confirmerPending} className="rounded border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--muted)] disabled:opacity-50">{confirmerPending ? "Confirmation…" : "Confirmer ce voyage"}</button></div>;
}

function PriceReliability({ itinerary }: { itinerary: Itineraire }) {
  const label = itinerary.source_prix_vol === "live" ? "Vols vérifiés" : itinerary.source_prix_vol === "cache_live" ? "Prix live en cache" : "Prix estimés";
  const className = itinerary.fiabilite_prix === "élevée" ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" : "bg-amber-500/15 text-amber-700 dark:text-amber-300";
  return <span className={`rounded-full px-2 py-1 text-xs ${className}`}>{label}</span>;
}

function TransportNotice({ days }: { days: number }) { if (days <= 0) return null; return <p className="text-xs text-[var(--muted-foreground)]">dont {days} jour(s) de transport entre étapes</p>; }

function DestinationList({ groupes }: { groupes: GroupeDestination[] }) { return <ul className="space-y-1.5 text-sm">{groupes.map((group) => <li key={`${group.pays}-${group.destination}`}><span className="font-medium">{group.destination}, {group.pays}</span> — {group.jours} jour(s) : <span className="text-[var(--muted-foreground)]">{group.lieux.join(", ")}</span></li>)}</ul>; }

function WarningList({ warnings }: { warnings?: string[] }) { if (!warnings?.length) return null; return <ul className="space-y-1 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2 text-xs text-amber-800 dark:text-amber-200">{warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>; }
