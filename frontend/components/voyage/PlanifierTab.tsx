'use client'

import { useState } from 'react'
import type { Itineraire } from '@/lib/voyage'
import { PlanningForm, usePlanningActions } from './PlanifierParts'

export function PlanifierTab({ candidats, onConfirmed }: { candidats: number[]; onConfirmed?: () => void }) {
  const [departIata, setDepartIata] = useState('YUL')
  const [arriveeIata, setArriveeIata] = useState('YUL')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [budget, setBudget] = useState(3000)
  const [resultat, setResultat] = useState<Itineraire | null>(null)
  const actions = usePlanningActions({ candidats, departIata, arriveeIata, dateDebut, dateFin, budget, resultat, setResultat, onConfirmed })
  const planningError = actions.planifier.isError ? actions.planifier.error?.message ?? 'Erreur de planification' : undefined
  return <PlanningForm departIata={departIata} arriveeIata={arriveeIata} dateDebut={dateDebut} dateFin={dateFin} budget={budget} pending={actions.planifier.isPending} error={planningError} resultat={resultat} confirmerPending={actions.confirmer.isPending} setDepartIata={setDepartIata} setArriveeIata={setArriveeIata} setDateDebut={setDateDebut} setDateFin={setDateFin} setBudget={setBudget} onSubmit={actions.submit} onConfirm={actions.confirm} />
}
