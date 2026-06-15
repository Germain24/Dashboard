'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Zap, Play, Trash2, Plus, X, Clock, Radio, ShieldAlert, History, RotateCcw, Undo2, Lightbulb } from 'lucide-react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ModuleHeader } from '@/components/layout'
import {
  useAddRoutine, useDeleteRoutine, useRoutines, useRunRoutine, useUpdateRoutine,
  useKillSwitch, useSetKillSwitch, useRoutineRuns, useBuilderOptions,
  useRecipes, useRunRecipe, useRerunRun, useRollbackRun, useAutomationSuggestions,
} from '@/lib/queries/routines'
import type { Routine, RoutineAction, AutomationSuggestion } from '@/lib/routines'
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

const FREQ = [
  { id: 'daily', label: 'Chaque jour' },
  { id: 'weekly', label: 'Chaque semaine' },
  { id: 'monthly', label: 'Chaque mois' },
] as const
const WEEKDAYS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']

/** Construit une expression cron 5 champs (min heure jour mois jour-semaine). */
function buildCron(freq: string, hour: number, minute: number, weekday: number, dom: number): string {
  const m = Math.max(0, Math.min(59, minute))
  const h = Math.max(0, Math.min(23, hour))
  if (freq === 'weekly') return `${m} ${h} * * ${weekday}` // cron: 0=dim..6=sam
  if (freq === 'monthly') return `${m} ${h} ${Math.max(1, Math.min(28, dom))} * *`
  return `${m} ${h} * * *`
}

/** Constructeur d'automatisations no-code « SI … ALORS … » (#205). */
function AddModal({ onClose }: { onClose: () => void }) {
  const add = useAddRoutine()
  const { data: opts } = useBuilderOptions()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  // Déclencheur
  const [mode, setMode] = useState<'schedule' | 'event' | 'webhook'>('schedule')
  const [freq, setFreq] = useState('daily')
  const [hour, setHour] = useState(7)
  const [minute, setMinute] = useState(0)
  const [weekday, setWeekday] = useState(1) // lundi (cron 1)
  const [dom, setDom] = useState(1)
  const [eventValue, setEventValue] = useState('')
  // Token de webhook entrant (#219) — secret, généré une fois.
  const [webhookToken] = useState(() =>
    (globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2)).replace(/-/g, ''))
  // Actions
  const [actions, setActions] = useState<RoutineAction[]>([])

  // cron weekday : nos boutons Lun..Dim -> cron 1..6,0
  const cronWeekday = weekday === 7 ? 0 : weekday
  const triggerType = mode === 'schedule' ? 'cron' : mode === 'event' ? 'event' : 'webhook'
  const triggerValue =
    mode === 'schedule' ? buildCron(freq, hour, minute, cronWeekday, dom)
      : mode === 'event' ? eventValue
        : webhookToken
  const webhookUrl =
    typeof window !== 'undefined' ? `${window.location.origin}/api/automatisations/webhooks/${webhookToken}` : ''

  const addAction = () => setActions((a) => [...a, { type: 'notify', titre: '', message: '' }])
  const updateAction = (i: number, patch: Partial<RoutineAction>) =>
    setActions((a) => a.map((act, j) => (j === i ? { ...act, ...patch } as RoutineAction : act)))
  const removeAction = (i: number) => setActions((a) => a.filter((_, j) => j !== i))

  const valid = name.trim() && (mode !== 'event' || eventValue) && actions.length > 0
  const pad = (n: number) => String(n).padStart(2, '0')

  const submit = () => {
    if (!valid) return
    add.mutate(
      { name: name.trim(), description, trigger_type: triggerType, trigger_value: triggerValue, actions },
      {
        onSuccess: () => { toast.success('Automatisation créée'); onClose() },
        onError: () => toast.error('Erreur création'),
      },
    )
  }

  const cls = 'rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm'
  const eventLabel = opts?.events.find((e) => e.value === eventValue)?.label

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 py-10 backdrop-blur-sm">
      <div className="glass-modal w-full max-w-lg rounded-[var(--radius-lg)] p-5">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-lg">Nouvelle automatisation</h2>
          <button onClick={onClose} aria-label="Fermer"><X size={18} /></button>
        </div>

        <div className="space-y-4">
          <input className={`${cls} w-full`} placeholder="Nom * (ex. Rappel pesée du lundi)" value={name} onChange={(e) => setName(e.target.value)} autoFocus />

          {/* SI : déclencheur */}
          <fieldset className="rounded-[var(--radius)] border border-[var(--glass-border)] p-3">
            <legend className="px-1 text-xs font-semibold text-[var(--muted-foreground)]">SI…</legend>
            <div className="mb-2 flex gap-2">
              {([['schedule', '⏱ À une heure'], ['event', '⚡ Sur événement'], ['webhook', '🔗 Webhook']] as const).map(([m, label]) => (
                <button key={m} onClick={() => setMode(m)}
                  className={`flex-1 rounded-lg border py-1.5 text-xs font-medium transition-colors ${mode === m ? 'border-[var(--primary)] bg-[color-mix(in_srgb,var(--ring)_12%,transparent)] text-[var(--foreground)]' : 'border-[var(--border)] text-[var(--muted-foreground)]'}`}>
                  {label}
                </button>
              ))}
            </div>
            {mode === 'schedule' ? (
              <div className="flex flex-wrap items-center gap-2">
                <select className={cls} value={freq} onChange={(e) => setFreq(e.target.value)}>
                  {FREQ.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
                </select>
                {freq === 'weekly' && (
                  <select className={cls} value={weekday} onChange={(e) => setWeekday(+e.target.value)}>
                    {WEEKDAYS.map((d, i) => <option key={d} value={i + 1 === 7 ? 7 : i + 1}>{d}</option>)}
                  </select>
                )}
                {freq === 'monthly' && (
                  <select className={cls} value={dom} onChange={(e) => setDom(+e.target.value)}>
                    {Array.from({ length: 28 }, (_, i) => i + 1).map((d) => <option key={d} value={d}>le {d}</option>)}
                  </select>
                )}
                <span className="text-sm text-[var(--muted-foreground)]">à</span>
                <input type="number" min={0} max={23} className={`${cls} w-16 tabular-nums`} value={hour} onChange={(e) => setHour(+e.target.value)} />
                <span>:</span>
                <input type="number" min={0} max={59} className={`${cls} w-16 tabular-nums`} value={minute} onChange={(e) => setMinute(+e.target.value)} />
              </div>
            ) : mode === 'event' ? (
              <select className={`${cls} w-full`} value={eventValue} onChange={(e) => setEventValue(e.target.value)}>
                <option value="">— Choisir un événement —</option>
                {opts?.events.map((ev) => <option key={ev.value} value={ev.value}>{ev.label}</option>)}
              </select>
            ) : (
              <div className="space-y-1.5">
                <p className="text-xs text-[var(--muted-foreground)]">
                  Un POST sur cette URL (secrète) déclenchera la routine. À créer pour obtenir l'URL.
                </p>
                <code className="block break-all rounded-[var(--radius)] bg-[var(--muted)] px-2 py-1.5 text-[11px] text-[var(--foreground)]">
                  POST {webhookUrl}
                </code>
              </div>
            )}
          </fieldset>

          {/* ALORS : actions */}
          <fieldset className="rounded-[var(--radius)] border border-[var(--glass-border)] p-3">
            <legend className="px-1 text-xs font-semibold text-[var(--muted-foreground)]">ALORS…</legend>
            <div className="space-y-2">
              {actions.length === 0 && <p className="text-xs text-[var(--muted-foreground)]">Ajoute au moins une action.</p>}
              {actions.map((act, i) => (
                <div key={i} className="rounded-lg border border-[var(--border)] p-2">
                  <div className="flex items-center gap-2">
                    <select className={`${cls} flex-1`} value={act.type}
                      onChange={(e) => {
                        const v = e.target.value
                        updateAction(i,
                          v === 'notify' ? { type: 'notify', titre: '', message: '' }
                            : v === 'webhook' ? { type: 'webhook', url: '' }
                              : { type: 'job', job_id: '' })
                      }}>
                      {opts?.action_types.map((t) => <option key={t.type} value={t.type}>{t.label}</option>)}
                    </select>
                    <button onClick={() => removeAction(i)} aria-label="Retirer" className="p-1 text-[var(--muted-foreground)] hover:text-[var(--destructive)]"><Trash2 size={15} /></button>
                  </div>
                  {act.type === 'notify' ? (
                    <div className="mt-2 space-y-2">
                      <input className={`${cls} w-full`} placeholder="Titre" value={(act as { titre?: string }).titre ?? ''} onChange={(e) => updateAction(i, { titre: e.target.value })} />
                      <input className={`${cls} w-full`} placeholder="Message" value={(act as { message?: string }).message ?? ''} onChange={(e) => updateAction(i, { message: e.target.value })} />
                    </div>
                  ) : act.type === 'webhook' ? (
                    <input className={`${cls} mt-2 w-full`} placeholder="https://exemple.com/webhook" value={(act as { url?: string }).url ?? ''} onChange={(e) => updateAction(i, { url: e.target.value })} />
                  ) : (
                    <select className={`${cls} mt-2 w-full`} value={(act as { job_id?: string }).job_id ?? ''} onChange={(e) => updateAction(i, { job_id: e.target.value })}>
                      <option value="">— Choisir une automatisation —</option>
                      {opts?.jobs.map((j) => <option key={j.id} value={j.id}>{j.label}</option>)}
                    </select>
                  )}
                </div>
              ))}
              <button onClick={addAction} className="flex items-center gap-1.5 rounded-lg border border-dashed border-[var(--border)] px-3 py-1.5 text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
                <Plus size={13} /> Ajouter une action
              </button>
            </div>
          </fieldset>

          {/* Aperçu */}
          <p className="rounded-lg bg-[var(--accent)] px-3 py-2 text-xs text-[var(--muted-foreground)]">
            <span className="font-medium text-[var(--foreground)]">Aperçu :</span>{' '}
            {mode === 'schedule'
              ? `${FREQ.find((f) => f.id === freq)?.label}${freq === 'weekly' ? ' ' + WEEKDAYS[weekday - 1] : freq === 'monthly' ? ` le ${dom}` : ''} à ${pad(hour)}:${pad(minute)}`
              : mode === 'webhook' ? 'appel webhook entrant'
                : eventLabel ? `quand : ${eventLabel}` : 'choisis un événement'}
            {' → '}{actions.length} action{actions.length > 1 ? 's' : ''}
          </p>

          <input className={`${cls} w-full`} placeholder="Description (optionnel)" value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>

        <div className="mt-5 flex gap-2">
          <button onClick={submit} disabled={!valid || add.isPending}
            className="flex-1 rounded-lg bg-[var(--primary)] py-2 text-sm font-medium text-[var(--primary-foreground)] disabled:opacity-40">
            {add.isPending ? 'Création…' : 'Créer l’automatisation'}
          </button>
          <button onClick={onClose} className="flex-1 rounded-lg border border-[var(--border)] py-2 text-sm">Annuler</button>
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
      <KillSwitchBanner />

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

      <RecipesSection />

      <div className="space-y-3 mb-6">
        <h2 className="text-xs font-semibold text-[var(--muted-foreground)]">Intégrées</h2>
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
        <h2 className="text-xs font-semibold text-[var(--muted-foreground)]">Personnalisées</h2>
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

      <SuggestionsSection />

      <AuditLog />

      {showAdd && <AddModal onClose={() => setShowAdd(false)} />}
    </div>
  )
}

/** Kill switch global (#217) : coupe toutes les automatisations d'un coup. */
function KillSwitchBanner() {
  const { data } = useKillSwitch()
  const setKill = useSetKillSwitch()
  const on = data?.enabled ?? false
  return (
    <div
      className={`mb-6 flex items-center justify-between gap-3 rounded-[var(--radius-lg)] border px-4 py-3 ${
        on
          ? 'border-[var(--destructive)] bg-[var(--destructive-muted)]'
          : 'border-[var(--glass-border)] bg-[var(--card)] backdrop-blur-[var(--glass-blur)]'
      }`}
    >
      <div className="flex items-center gap-2.5">
        <ShieldAlert size={18} className={on ? 'text-[var(--destructive)]' : 'text-[var(--muted-foreground)]'} />
        <div>
          <p className="text-sm font-medium text-[var(--foreground)]">
            {on ? 'Automatisations désactivées' : 'Kill switch global'}
          </p>
          <p className="text-xs text-[var(--muted-foreground)]">
            {on
              ? 'Aucune routine ne s’exécute (manuelle ou planifiée). Chaque tentative est journalisée.'
              : 'Coupe toutes les automatisations d’un seul interrupteur en cas de besoin.'}
          </p>
        </div>
      </div>
      <button
        type="button"
        onClick={() => setKill.mutate(!on)}
        disabled={setKill.isPending}
        aria-pressed={on}
        className={`shrink-0 rounded-[var(--radius-full)] px-3.5 py-1.5 text-sm font-medium transition-colors ${
          on
            ? 'bg-[var(--destructive)] text-[var(--destructive-foreground)]'
            : 'border border-[var(--border)] text-[var(--foreground)] hover:bg-[var(--accent)]'
        }`}
      >
        {on ? 'Réactiver' : 'Tout couper'}
      </button>
    </div>
  )
}

/** Recettes : chaînes d'actions cross-module lancées à la demande (#215).
 *  Confirmation unique en deux temps (Lancer → Confirmer). */
function RecipesSection() {
  const { data: recipes } = useRecipes()
  const run = useRunRecipe()
  const [confirming, setConfirming] = useState<string | null>(null)

  if (!recipes?.length) return null

  const launch = (id: string) => {
    run.mutate(id, {
      onSuccess: (r) => toast.success(r.result?.startsWith('bloqu') ? 'Bloqué (kill switch)' : 'Recette lancée'),
      onError: () => toast.error('Échec de la recette'),
    })
    setConfirming(null)
  }

  return (
    <div className="space-y-3 mb-6">
      <h2 className="text-xs font-semibold text-[var(--muted-foreground)]">Recettes (lancer à la demande)</h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {recipes.map((rec) => (
          <div key={rec.id} className="flex flex-col rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
            <p className="text-sm font-medium text-[var(--foreground)]">{rec.emoji} {rec.name}</p>
            <p className="mt-1 flex-1 text-xs text-[var(--muted-foreground)]">{rec.description}</p>
            <p className="mt-2 text-[11px] text-[var(--muted-foreground)]">{rec.nb_actions} action{rec.nb_actions > 1 ? 's' : ''} enchaînées</p>
            {confirming === rec.id ? (
              <div className="mt-3 flex gap-2">
                <button onClick={() => launch(rec.id)} disabled={run.isPending}
                  className="flex-1 rounded-lg bg-[var(--primary)] py-1.5 text-xs font-medium text-[var(--primary-foreground)] disabled:opacity-40">
                  Confirmer ?
                </button>
                <button onClick={() => setConfirming(null)} className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs">
                  Annuler
                </button>
              </div>
            ) : (
              <button onClick={() => setConfirming(rec.id)}
                className="mt-3 flex items-center justify-center gap-1.5 rounded-lg border border-[var(--border)] py-1.5 text-xs font-medium hover:bg-[var(--accent)]">
                <Play size={13} /> Lancer
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

/** Suggestions d'automatisation apprises des habitudes (#218). */
function SuggestionsSection() {
  const { data } = useAutomationSuggestions()
  const add = useAddRoutine()
  const suggestions = data?.suggestions ?? []
  if (!suggestions.length) return null

  const createReminder = (s: AutomationSuggestion) => {
    const [hh, mm] = s.heure.split(':').map(Number)
    const cronDow = (s.weekday + 1) % 7 // python lun=0 -> cron dim=0..sam=6
    add.mutate(
      {
        name: `Rappel : ${s.titre}`,
        trigger_type: 'cron',
        trigger_value: `${mm} ${hh} * * ${cronDow}`,
        actions: [{ type: 'notify', titre: s.titre, message: `Rappel ${s.jour} — ${s.titre}` }] as RoutineAction[],
      },
      {
        onSuccess: () => toast.success(`Rappel créé : ${s.titre} (${s.jour})`),
        onError: () => toast.error('Échec de la création'),
      },
    )
  }

  return (
    <div className="mt-8">
      <h2 className="mb-3 flex items-center gap-1.5 text-xs font-semibold text-[var(--muted-foreground)]">
        <Lightbulb size={13} /> Suggestions (apprises de tes habitudes)
      </h2>
      <ul className="space-y-2">
        {suggestions.map((s) => (
          <li
            key={`${s.titre}-${s.weekday}`}
            className="flex items-center gap-3 rounded-[var(--radius-lg)] border border-dashed border-[var(--border)] bg-[var(--accent)]/30 px-4 py-2.5 text-sm"
          >
            <span className="min-w-0 flex-1 text-[var(--foreground)]">{s.message}</span>
            <button
              type="button"
              onClick={() => createReminder(s)}
              disabled={add.isPending}
              className="shrink-0 rounded-[var(--radius)] bg-[var(--ring)] px-3 py-1 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              Créer le rappel
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Journal d'audit des déclenchements (#217). */
function AuditLog() {
  const { data: runs } = useRoutineRuns(20)
  const rerun = useRerunRun()
  const rollback = useRollbackRun()
  if (!runs?.length) return null
  const STATUS: Record<string, { label: string; cls: string }> = {
    ok: { label: 'OK', cls: 'bg-[var(--success-muted)] text-[var(--success-foreground)]' },
    blocked: { label: 'Bloqué', cls: 'bg-[var(--warning-muted)] text-[var(--warning-foreground)]' },
    error: { label: 'Erreur', cls: 'bg-[var(--destructive-muted)] text-[var(--destructive-foreground)]' },
  }
  const reversibleCount = (run: { created_ids?: string }): number => {
    try {
      return (JSON.parse(run.created_ids || '{}').notifications ?? []).length
    } catch {
      return 0
    }
  }
  const onRerun = (id: number) =>
    rerun.mutate(id, {
      onSuccess: (r) => toast.success(r.result || 'Routine ré-exécutée'),
      onError: () => toast.error('Échec de la ré-exécution'),
    })
  const onRollback = (id: number) =>
    rollback.mutate(id, {
      onSuccess: (r) => toast.success(r.result || 'Annulé'),
      onError: () => toast.error('Échec du rollback'),
    })
  return (
    <div className="mt-8">
      <h2 className="mb-3 flex items-center gap-1.5 text-xs font-semibold text-[var(--muted-foreground)]">
        <History size={13} /> Journal des déclenchements
      </h2>
      <ul className="divide-y divide-[var(--glass-border)] rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)]">
        {runs.map((run) => {
          const s = STATUS[run.status] ?? STATUS.ok
          return (
            <li key={run.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
              <span className={`shrink-0 rounded-[var(--radius-full)] px-2 py-0.5 text-[11px] font-medium ${s.cls}`}>
                {s.label}
              </span>
              <span className="min-w-0 flex-1 truncate text-[var(--foreground)]">
                {run.routine_name}
                <span className="ml-2 text-xs text-[var(--muted-foreground)]">{run.detail}</span>
              </span>
              {run.rolled_back && (
                <span className="shrink-0 rounded-[var(--radius-full)] bg-[var(--muted)] px-2 py-0.5 text-[11px] text-[var(--muted-foreground)]">
                  annulé
                </span>
              )}
              <button
                type="button"
                onClick={() => onRerun(run.id)}
                disabled={rerun.isPending}
                title="Ré-exécuter cette routine"
                className="shrink-0 rounded-[var(--radius)] p-1 text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)] disabled:opacity-50"
              >
                <RotateCcw size={14} />
              </button>
              {!run.rolled_back && reversibleCount(run) > 0 && (
                <button
                  type="button"
                  onClick={() => onRollback(run.id)}
                  disabled={rollback.isPending}
                  title="Annuler (supprime les notifications créées)"
                  className="shrink-0 rounded-[var(--radius)] p-1 text-[var(--muted-foreground)] hover:bg-[var(--destructive-muted)] hover:text-[var(--destructive-foreground)] disabled:opacity-50"
                >
                  <Undo2 size={14} />
                </button>
              )}
              <time className="shrink-0 text-xs text-[var(--muted-foreground)] tabular-nums">
                {new Date(run.ran_at).toLocaleString('fr-CA', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
              </time>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default function RoutinesPage() {
  return (
    <div className="space-y-0 animate-fade-in">
      <ModuleHeader title="Routines" subtitle="Automatisations déclenchées par cron ou événement" />
      <div className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Routines">
          <RoutinesContent />
        </ErrorBoundary>
      </div>
    </div>
  )
}
