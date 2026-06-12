'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Zap, Play, Trash2, Plus, X, Clock, Radio } from 'lucide-react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { useAddRoutine, useDeleteRoutine, useRoutines, useRunRoutine, useUpdateRoutine } from '@/lib/queries/routines'
import type { Routine } from '@/lib/routines'
import { Skeleton } from '@/components/ui/skeleton'

function TriggerBadge({ type, value }: { type: string; value: string }) {
  const Icon = type === 'cron' ? Clock : Radio
  return (
    <span className="flex items-center gap-1 text-xs text-[var(--muted-foreground)] font-mono">
      <Icon size={11} />
      {value || (type === 'cron' ? 'pas de cron' : 'pas d\'événement')}
    </span>
  )
}

function AddModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [triggerType, setTriggerType] = useState<'cron' | 'event'>('cron')
  const [triggerValue, setTriggerValue] = useState('')
  const add = useAddRoutine()

  const submit = () => {
    if (!name.trim()) return
    add.mutate(
      { name: name.trim(), description, trigger_type: triggerType, trigger_value: triggerValue },
      {
        onSuccess: () => { toast.success('Routine créée'); onClose() },
        onError: () => toast.error('Erreur création'),
      }
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl p-6 w-full max-w-md shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-base">Nouvelle routine</h2>
          <button onClick={onClose}><X size={18} /></button>
        </div>
        <div className="space-y-3">
          <input
            className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-sm"
            placeholder="Nom *"
            value={name}
            onChange={e => setName(e.target.value)}
            autoFocus
          />
          <input
            className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-sm"
            placeholder="Description (optionnel)"
            value={description}
            onChange={e => setDescription(e.target.value)}
          />
          <div className="flex gap-2">
            {(['cron', 'event'] as const).map(t => (
              <button
                key={t}
                onClick={() => setTriggerType(t)}
                className={`flex-1 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                  triggerType === t
                    ? 'border-[var(--primary)] bg-[var(--primary)] text-[var(--primary-foreground)]'
                    : 'border-[var(--border)] text-[var(--muted-foreground)]'
                }`}
              >
                {t === 'cron' ? '⏱ Cron' : '⚡ Événement'}
              </button>
            ))}
          </div>
          <input
            className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-sm font-mono"
            placeholder={triggerType === 'cron' ? 'ex: 0 7 * * * (7h chaque jour)' : 'ex: budget.transaction_created'}
            value={triggerValue}
            onChange={e => setTriggerValue(e.target.value)}
          />
        </div>
        <div className="flex gap-2 mt-4">
          <button
            onClick={submit}
            disabled={!name.trim() || add.isPending}
            className="flex-1 py-2 rounded-lg bg-[var(--primary)] text-[var(--primary-foreground)] text-sm font-medium disabled:opacity-40"
          >
            {add.isPending ? 'Création…' : 'Créer'}
          </button>
          <button onClick={onClose} className="flex-1 py-2 rounded-lg border border-[var(--border)] text-sm">
            Annuler
          </button>
        </div>
      </div>
    </div>
  )
}

function RoutineCard({ routine }: { routine: Routine }) {
  const update = useUpdateRoutine()
  const del = useDeleteRoutine()
  const run = useRunRoutine()

  return (
    <div className={`flex items-start gap-3 p-4 rounded-xl border transition-colors ${
      routine.enabled ? 'border-[var(--border)] bg-[var(--card)]' : 'border-[var(--border)] bg-[var(--card)] opacity-50'
    }`}>
      <div className={`mt-0.5 p-2 rounded-lg ${routine.enabled ? 'bg-[var(--primary)]/10' : 'bg-[var(--accent)]'}`}>
        <Zap size={14} className={routine.enabled ? 'text-[var(--primary)]' : 'text-[var(--muted-foreground)]'} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium truncate">{routine.name}</p>
          {routine.last_run_at && (
            <span className="text-xs text-[var(--muted-foreground)]">
              · dernier run {new Date(routine.last_run_at).toLocaleDateString('fr-FR')}
            </span>
          )}
        </div>
        {routine.description && (
          <p className="text-xs text-[var(--muted-foreground)] mt-0.5">{routine.description}</p>
        )}
        <div className="mt-1">
          <TriggerBadge type={routine.trigger_type} value={routine.trigger_value} />
        </div>
        {routine.actions.length > 0 && (
          <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
            {routine.actions.length} action{routine.actions.length > 1 ? 's' : ''}
          </p>
        )}
      </div>
      <div className="flex items-center gap-1 shrink-0">
        <button
          onClick={() => update.mutate(
            { id: routine.id, patch: { enabled: !routine.enabled } },
            { onError: () => toast.error('Erreur') }
          )}
          className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
            routine.enabled ? 'bg-[var(--primary)]' : 'bg-[var(--accent)]'
          }`}
          title={routine.enabled ? 'Désactiver' : 'Activer'}
        >
          <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-lg transition ${
            routine.enabled ? 'translate-x-4' : 'translate-x-0'
          }`} />
        </button>
        <button
          onClick={() => run.mutate(routine.id, {
            onSuccess: (d) => toast.success(`✓ ${d.result}`),
            onError: () => toast.error('Erreur exécution'),
          })}
          disabled={run.isPending}
          className="p-1.5 rounded-lg hover:bg-[var(--accent)] text-[var(--muted-foreground)] disabled:opacity-40"
          title="Exécuter maintenant"
        >
          <Play size={13} />
        </button>
        <button
          onClick={() => del.mutate(routine.id, {
            onSuccess: () => toast.success('Supprimée'),
            onError: () => toast.error('Erreur'),
          })}
          className="p-1.5 rounded-lg hover:bg-red-500/10 text-red-500"
          title="Supprimer"
        >
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  )
}

function BuiltinCard({ id, label, description, jobId }: { id: string; label: string; description: string; jobId: string }) {
  const run = useRunRoutine()
  return (
    <div className="flex items-start gap-3 p-4 rounded-xl border border-dashed border-[var(--border)] bg-[var(--accent)]/30">
      <div className="mt-0.5 p-2 rounded-lg bg-amber-500/10">
        <Zap size={14} className="text-amber-500" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-[var(--muted-foreground)] mt-0.5">{description}</p>
        <span className="text-xs text-[var(--muted-foreground)] font-mono">intégré · job: {jobId}</span>
      </div>
    </div>
  )
}

function RoutinesContent() {
  const { data: routines, isLoading } = useRoutines()
  const [showAdd, setShowAdd] = useState(false)

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <p className="text-sm text-[var(--muted-foreground)]">
          {routines?.length ?? 0} routine{(routines?.length ?? 0) > 1 ? 's' : ''} configurée{(routines?.length ?? 0) > 1 ? 's' : ''}
        </p>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--primary)] text-[var(--primary-foreground)] text-xs font-medium"
        >
          <Plus size={14} /> Nouvelle routine
        </button>
      </div>

      <div className="space-y-3 mb-6">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-[var(--muted-foreground)]">Intégrées</h2>
        <BuiltinCard
          id="briefing_matin"
          label="☀️ Briefing matin"
          description="Agenda du jour, habitudes, objectif calorique — chaque jour à 7h."
          jobId="briefing_matin"
        />
        <BuiltinCard
          id="recap_soir"
          label="🌙 Récap du soir"
          description="Dépenses, habitudes, agenda de demain — chaque soir à 21h."
          jobId="recap_soir"
        />
      </div>

      <div className="space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-[var(--muted-foreground)]">Personnalisées</h2>
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <Skeleton key={i} className="h-20 rounded-xl" />
            ))}
          </div>
        ) : !routines?.length ? (
          <div className="text-center py-8 text-[var(--muted-foreground)]">
            <Zap size={28} className="mx-auto mb-2 opacity-30" />
            <p className="text-sm">Aucune routine personnalisée</p>
            <p className="text-xs mt-1">Créez une routine pour automatiser des actions récurrentes.</p>
          </div>
        ) : (
          routines.map(r => <RoutineCard key={r.id} routine={r} />)
        )}
      </div>

      {showAdd && <AddModal onClose={() => setShowAdd(false)} />}
    </div>
  )
}

export default function RoutinesPage() {
  return (
    <div className="space-y-0 animate-fade-in">
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <div className="flex items-center gap-2 mb-1">
          <Zap size={20} className="text-[var(--muted-foreground)]" />
          <h1 className="text-xl font-semibold tracking-tight">Routines</h1>
        </div>
        <p className="text-sm text-[var(--muted-foreground)]">Automatisations déclenchées par cron ou événement</p>
      </div>
      <div className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Routines">
          <RoutinesContent />
        </ErrorBoundary>
      </div>
    </div>
  )
}
