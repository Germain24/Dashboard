'use client'

import type { Itineraire } from '@/lib/voyage'
import { buildConfirmerRequest } from '@/lib/voyage'
import { notifySuccess } from '@/lib/toast'
import { usePlanifier, useConfirmerVoyage } from '@/lib/queries/voyage'
import { DatePicker } from '@/components/ui/date-picker'
import dynamic from 'next/dynamic'

const ItineraryMap = dynamic(() => import('./ItineraryMap').then((module) => module.ItineraryMap), { ssr: false })

function CostSummary({ itinerary }: { itinerary: Itineraire }) {
  return <div className="text-sm font-semibold">{itinerary.etapes.length} lieu(x) retenu(s) · {itinerary.cout_total.toFixed(0)} € (transport {itinerary.cout_transport.toFixed(0)} € + hébergement {cost(itinerary.cout_hebergement)} € + nourriture {cost(itinerary.cout_nourriture)} € + activités {cost(itinerary.cout_activites)} € + local {cost(itinerary.cout_transport_local)} €)</div>
}

const cost = (value?: number) => value ?? 0

function PriceSource({ itinerary }: { itinerary: Itineraire }) {
  return <p className="text-xs text-[var(--muted-foreground)]">{itinerary.source_prix_vol === 'estimation' ? 'Prix de vols estimés' : 'Prix de vols vérifiés'}{itinerary.transporteur ? ` · ${itinerary.transporteur}` : ''}</p>
}

function ConfirmButton({ pending, onConfirm }: { pending: boolean; onConfirm: () => void }) {
  return <button onClick={onConfirm} disabled={pending} className="rounded border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--muted)] disabled:opacity-50">{pending ? 'Confirmation…' : 'Confirmer ce voyage'}</button>
}

function ConfirmError({ message }: { message?: string }) {
  if (!message) return null
  return <div className="text-sm text-[var(--destructive)]">{message}</div>
}

export function PlanningResult({ itinerary, pending, error, onConfirm }: { itinerary: Itineraire; pending: boolean; error?: string; onConfirm: () => void }) {
  return <div className="space-y-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"><CostSummary itinerary={itinerary} /><PriceSource itinerary={itinerary} /><ItineraryMap itineraire={itinerary} /><ol className="list-decimal space-y-1 pl-5 text-sm">{itinerary.etapes.map((step) => <li key={step.lieu_id}>{step.nom} — {step.jours} jour(s), du {step.date_arrivee} au {step.date_depart}</li>)}</ol><WarningList warnings={itinerary.avertissements} /><ConfirmButton pending={pending} onConfirm={onConfirm} /><ConfirmError message={error} /></div>
}

function WarningList({ warnings }: { warnings?: string[] }) {
  if (!warnings) return null
  return <>{warnings.map((warning) => <p key={warning} className="text-xs text-amber-700 dark:text-amber-300">{warning}</p>)}</>
}

function ErrorText({ message }: { message?: string }) {
  if (!message) return null
  return <div className="text-sm text-[var(--destructive)]">{message}</div>
}

function PlanningButton({ pending, onClick }: { pending: boolean; onClick: () => void }) {
  return <button onClick={onClick} disabled={pending} className="rounded bg-[var(--primary)] px-4 py-2 text-sm text-[var(--primary-foreground)] disabled:opacity-50">{pending ? 'Calcul en cours…' : 'Planifier'}</button>
}

export function PlanningForm({ departIata, arriveeIata, dateDebut, dateFin, budget, pending, error, resultat, confirmerPending, setDepartIata, setArriveeIata, setDateDebut, setDateFin, setBudget, onSubmit, onConfirm }: { departIata: string; arriveeIata: string; dateDebut: string; dateFin: string; budget: number; pending: boolean; error?: string; resultat: Itineraire | null; confirmerPending: boolean; setDepartIata: (value: string) => void; setArriveeIata: (value: string) => void; setDateDebut: (value: string) => void; setDateFin: (value: string) => void; setBudget: (value: number) => void; onSubmit: () => void; onConfirm: () => void }) {
  return <div className="space-y-4"><div className="grid grid-cols-2 gap-3 sm:grid-cols-3"><label className="text-sm">Départ (IATA)<input value={departIata} onChange={(event) => setDepartIata(event.target.value.toUpperCase())} className="mt-1 w-full rounded border border-[var(--border)] p-1.5" /></label><label className="text-sm">Arrivée (IATA)<input value={arriveeIata} onChange={(event) => setArriveeIata(event.target.value.toUpperCase())} className="mt-1 w-full rounded border border-[var(--border)] p-1.5" /></label><label className="text-sm">Budget total (€)<input type="number" value={budget} onChange={(event) => setBudget(Number(event.target.value))} className="mt-1 w-full rounded border border-[var(--border)] p-1.5" /></label><DatePicker id="planifier-date-debut" label="Date de début" value={dateDebut} min={todayPlus(0)} onChange={setDateDebut} /><DatePicker id="planifier-date-fin" label="Date de fin" value={dateFin} min={dateDebut || todayPlus(0)} onChange={setDateFin} /></div><PlanningButton pending={pending} onClick={onSubmit} /><ErrorText message={error} /><PlanningOutput resultat={resultat} pending={confirmerPending} onConfirm={onConfirm} /></div>
}

function PlanningOutput({ resultat, pending, onConfirm }: { resultat: Itineraire | null; pending: boolean; onConfirm: () => void }) {
  if (!resultat) return null
  return <PlanningResult itinerary={resultat} pending={pending} onConfirm={onConfirm} />
}

function todayPlus(days: number): string {
  const date = new Date()
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

export function usePlanningActions({ candidats, departIata, arriveeIata, dateDebut, dateFin, budget, resultat, setResultat, onConfirmed }: { candidats: number[]; departIata: string; arriveeIata: string; dateDebut: string; dateFin: string; budget: number; resultat: Itineraire | null; setResultat: (value: Itineraire | null) => void; onConfirmed?: () => void }) {
  const planifier = usePlanifier()
  const confirmer = useConfirmerVoyage()
  const submit = () => {
    if (candidats.length === 0 || !dateDebut || !dateFin) return
    planifier.mutate({ candidats, depart_iata: departIata, arrivee_iata: arriveeIata, date_debut: dateDebut, date_fin: dateFin, budget_total: budget }, { onSuccess: setResultat })
  }
  const confirm = () => {
    if (!resultat) return
    confirmer.mutate(buildConfirmerRequest(resultat, { dateDebut, dateFin, departIata, arriveeIata }), { onSuccess: () => { setResultat(null); notifySuccess('Voyage confirmé — checklist et budget disponibles plus bas.'); onConfirmed?.() } })
  }
  return { planifier, confirmer, submit, confirm }
}
