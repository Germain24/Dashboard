'use client'

import { useState } from 'react'
import { Plus, Trash2, XCircle } from 'lucide-react'
import {
  useContracts, useContractsSummary, useCreateContract, useUpdateContract, useDeleteContract,
} from '@/lib/queries/budget'

const formatCAD = (v: number) =>
  new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(v ?? 0)

const CATEGORIES = ['assurance', 'telecom', 'abonnement', 'autre']
const PERIODICITES = [
  { value: 'mensuel', label: 'Mensuel' },
  { value: 'annuel', label: 'Annuel' },
]

const BADGE_LABEL: Record<string, string> = {
  depassee: 'Échéance dépassée',
  proche: 'Échéance proche',
  ok: 'À jour',
  no_date: 'Pas d’échéance',
}

function EcheanceBadge({ statut }: { statut: string }) {
  const style =
    statut === 'depassee'
      ? { color: 'var(--destructive)', background: 'color-mix(in srgb, var(--destructive) 12%, transparent)' }
      : statut === 'proche'
        ? { color: 'var(--warning)', background: 'color-mix(in srgb, var(--warning) 15%, transparent)' }
        : { color: 'var(--muted-foreground)', background: 'var(--muted)' }
  return (
    <span
      className="inline-flex items-center rounded-[var(--radius-sm)] px-1.5 py-0.5 text-[10px] font-medium"
      style={style}
    >
      {BADGE_LABEL[statut] ?? statut}
    </span>
  )
}

export default function ContratsTab() {
  const [statutFilter, setStatutFilter] = useState<'' | 'actif' | 'resilie'>('actif')
  const [showForm, setShowForm] = useState(false)
  const [nom, setNom] = useState('')
  const [categorie, setCategorie] = useState(CATEGORIES[0])
  const [montant, setMontant] = useState('')
  const [periodicite, setPeriodicite] = useState<'mensuel' | 'annuel'>('mensuel')
  const [dateEcheance, setDateEcheance] = useState('')

  const contractsQ = useContracts(statutFilter || undefined)
  const summaryQ = useContractsSummary()
  const createMutation = useCreateContract()
  const updateMutation = useUpdateContract()
  const deleteMutation = useDeleteContract()

  const contracts = contractsQ.data ?? []
  const summary = summaryQ.data ?? { cout_mensuel: 0, prochaines_echeances: [] }
  const loading = contractsQ.isLoading

  const resetForm = () => {
    setNom('')
    setCategorie(CATEGORIES[0])
    setMontant('')
    setPeriodicite('mensuel')
    setDateEcheance('')
    setShowForm(false)
  }

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const montantNum = parseFloat(montant)
    if (!nom.trim() || Number.isNaN(montantNum)) return
    createMutation.mutate(
      { nom: nom.trim(), categorie, montant: montantNum, periodicite, date_echeance: dateEcheance || null },
      { onSuccess: resetForm },
    )
  }

  const onResilier = (id: number) => {
    updateMutation.mutate({ id, patch: { statut: 'resilie', date_resiliation: new Date().toISOString().slice(0, 10) } })
  }

  const onDelete = (id: number) => {
    deleteMutation.mutate(id)
  }

  return (
    <div className="space-y-4 animate-fade-in-up">
      {/* Coût mensuel total (#362) */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold">Contrats & abonnements suivis</h2>
            <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
              Saisie manuelle — assurances, box internet, salle de sport… (distinct de la détection auto).
            </p>
          </div>
          <div className="text-right">
            <p className="text-lg font-semibold font-mono">{formatCAD(summary.cout_mensuel)}</p>
            <p className="text-xs text-[var(--muted-foreground)]">coût mensuel actif</p>
          </div>
        </div>
      </div>

      {/* Formulaire d'ajout */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        {!showForm ? (
          <button
            type="button"
            onClick={() => setShowForm(true)}
            className="inline-flex items-center gap-2 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90"
          >
            <Plus size={14} aria-hidden="true" />
            Ajouter un contrat
          </button>
        ) : (
          <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-2">
            <div className="flex flex-col gap-1">
              <label htmlFor="contract-name" className="text-xs text-[var(--muted-foreground)]">Nom</label>
              <input
                id="contract-name"
                value={nom} onChange={(e) => setNom(e.target.value)} required
                className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm"
                placeholder="Ex. Assurance auto"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="contract-category" className="text-xs text-[var(--muted-foreground)]">Catégorie</label>
              <select
                id="contract-category"
                value={categorie} onChange={(e) => setCategorie(e.target.value)}
                className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm"
              >
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="contract-amount" className="text-xs text-[var(--muted-foreground)]">Montant</label>
              <input
                id="contract-amount"
                type="number" step="0.01" value={montant} onChange={(e) => setMontant(e.target.value)} required
                className="w-24 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm"
                placeholder="0.00"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="contract-period" className="text-xs text-[var(--muted-foreground)]">Périodicité</label>
              <select
                id="contract-period"
                value={periodicite} onChange={(e) => setPeriodicite(e.target.value as 'mensuel' | 'annuel')}
                className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm"
              >
                {PERIODICITES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor="contract-deadline" className="text-xs text-[var(--muted-foreground)]">Échéance (optionnel)</label>
              <input
                id="contract-deadline"
                type="date" value={dateEcheance} onChange={(e) => setDateEcheance(e.target.value)}
                className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-sm"
              />
            </div>
            <div className="flex items-center gap-2">
              <button
                type="submit"
                disabled={createMutation.isPending}
                className="rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50"
              >
                {createMutation.isPending ? 'Ajout…' : 'Ajouter'}
              </button>
              <button
                type="button" onClick={resetForm}
                className="text-xs text-[var(--muted-foreground)] underline hover:text-[var(--foreground)]"
              >
                Annuler
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Liste des contrats */}
      <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] px-4 py-3">
          <h2 className="text-sm font-semibold">
            Contrats
            <span className="ml-2 text-xs font-normal text-[var(--muted-foreground)]">{contracts.length}</span>
          </h2>
          <select
            value={statutFilter} onChange={(e) => setStatutFilter(e.target.value as '' | 'actif' | 'resilie')}
            aria-label="Filtrer par statut"
            className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs"
          >
            <option value="actif">Actifs</option>
            <option value="resilie">Résiliés</option>
            <option value="">Tous</option>
          </select>
        </div>
        {loading ? (
          <div className="space-y-2 p-4">
            {[0, 1, 2].map((i) => <div key={i} className="h-10 rounded skeleton-shimmer" />)}
          </div>
        ) : contracts.length === 0 ? (
          <p className="p-6 text-center text-sm text-[var(--muted-foreground)]">
            Aucun contrat suivi pour ce filtre.
          </p>
        ) : (
          <div className="divide-y divide-[var(--border)]">
            {contracts.map((c) => (
              <div key={c.id} className="flex items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{c.nom}</p>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {c.categorie} · {c.periodicite === 'annuel' ? 'Annuel' : 'Mensuel'}
                    {c.date_echeance && <> · échéance {c.date_echeance}</>}
                    {c.statut === 'resilie' && c.date_resiliation && <> · résilié le {c.date_resiliation}</>}
                  </p>
                  <div className="mt-1">
                    {c.statut === 'resilie'
                      ? <span className="inline-flex items-center rounded-[var(--radius-sm)] bg-[var(--muted)] px-1.5 py-0.5 text-[10px] text-[var(--muted-foreground)]">Résilié</span>
                      : <EcheanceBadge statut={c.statut_echeance} />}
                  </div>
                </div>
                <span className="font-mono text-sm font-semibold">{formatCAD(c.montant)}</span>
                <div className="flex items-center gap-1">
                  {c.statut === 'actif' && (
                    <button
                      type="button" onClick={() => onResilier(c.id)}
                      title="Marquer comme résilié"
                      className="rounded-md p-1.5 text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
                    >
                      <XCircle size={14} aria-hidden="true" />
                    </button>
                  )}
                  <button
                    type="button" onClick={() => onDelete(c.id)}
                    title="Supprimer"
                    className="rounded-md p-1.5 text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--destructive)]"
                  >
                    <Trash2 size={14} aria-hidden="true" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
