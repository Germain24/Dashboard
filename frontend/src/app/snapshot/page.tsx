'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Activity, Calendar, ChevronLeft, ChevronRight, Zap } from 'lucide-react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ModuleHeader } from '@/components/layout'
import { useActivateTemplate, useEnergyBudget, useHeatmap, useSetVacationMode, useSnapshot, useSnapshots, useTemplates, useVacationMode, useWellbeing } from '@/lib/queries/snapshot'
import type { SnapshotData } from '@/lib/snapshot'
import { Skeleton } from '@/components/ui/skeleton'

// ─── Wellbeing Widget ─────────────────────────────────────────────────────────

function WellbeingWidget() {
  const { data, isLoading } = useWellbeing()

  if (isLoading) return <Skeleton className="h-24 rounded-xl" />
  if (!data) return null

  const color =
    data.score >= 85 ? 'text-green-500' :
    data.score >= 70 ? 'text-blue-500' :
    data.score >= 55 ? 'text-amber-500' :
    'text-red-500'

  const arc = (score: number) => {
    const r = 28
    const circ = 2 * Math.PI * r
    return circ - (score / 100) * circ
  }

  return (
    <div className="flex items-center gap-4 p-4 rounded-xl border border-[var(--border)] bg-[var(--card)]">
      <div className="relative w-16 h-16 shrink-0">
        <svg width="64" height="64" viewBox="0 0 64 64">
          <circle cx="32" cy="32" r="28" fill="none" stroke="var(--accent)" strokeWidth="6" />
          <circle
            cx="32" cy="32" r="28" fill="none"
            stroke={data.score >= 85 ? '#22c55e' : data.score >= 70 ? '#3b82f6' : data.score >= 55 ? '#f59e0b' : '#ef4444'}
            strokeWidth="6" strokeLinecap="round"
            strokeDasharray={`${2 * Math.PI * 28}`}
            strokeDashoffset={arc(data.score)}
            transform="rotate(-90 32 32)"
          />
        </svg>
        <span className={`absolute inset-0 flex items-center justify-center text-sm font-bold ${color}`}>
          {data.score}
        </span>
      </div>
      <div>
        <p className="font-semibold text-sm">{data.label}</p>
        <p className="text-xs text-[var(--muted-foreground)] mt-0.5">Score bien-être du jour</p>
        <div className="flex gap-3 mt-1">
          {Object.entries(data.components).map(([k, v]) => (
            <div key={k} className="text-xs text-[var(--muted-foreground)]">
              {k.slice(0, 4)} <span className="font-medium text-[var(--foreground)]">{v}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Snapshot Day Card ────────────────────────────────────────────────────────

function SnapshotCard({ snap }: { snap: { date: string; data: SnapshotData } }) {
  const date = new Date(snap.date + 'T12:00:00')
  const days_fr = ['dim', 'lun', 'mar', 'mer', 'jeu', 'ven', 'sam']
  const months_fr = ['jan', 'fév', 'mars', 'avr', 'mai', 'juin', 'juil', 'août', 'sep', 'oct', 'nov', 'déc']
  const d = snap.data

  return (
    <div className="flex items-start gap-3 p-3 rounded-xl border border-[var(--border)] bg-[var(--card)] hover:bg-[var(--accent)] transition-colors">
      <div className="text-center w-10 shrink-0">
        <div className="text-xs text-[var(--muted-foreground)]">{days_fr[date.getDay()]}</div>
        <div className="text-lg font-bold leading-none">{date.getDate()}</div>
        <div className="text-xs text-[var(--muted-foreground)]">{months_fr[date.getMonth()]}</div>
      </div>
      <div className="flex-1 min-w-0 grid grid-cols-2 gap-y-1 gap-x-4 text-xs">
        {d.habitudes && (
          <span>✓ {d.habitudes.done}/{d.habitudes.total} habitudes</span>
        )}
        {d.budget && d.budget.depenses_total > 0 && (
          <span>💰 {d.budget.depenses_total.toFixed(0)} €</span>
        )}
        {d.sante?.poids && (
          <span>⚖️ {d.sante.poids} kg</span>
        )}
        {d.humeur && (
          <span>😊 humeur {d.humeur.valeur}/10</span>
        )}
        {d.entrainement?.nb_seances && d.entrainement.nb_seances > 0 && (
          <span>💪 {d.entrainement.nb_seances} séance(s)</span>
        )}
        {d.agenda && (
          <span>📅 {d.agenda.nb_evenements} événement(s)</span>
        )}
      </div>
    </div>
  )
}

// ─── Templates ────────────────────────────────────────────────────────────────

function TemplatesSection() {
  const { data: templates } = useTemplates()
  const activate = useActivateTemplate()

  if (!templates?.length) return null

  return (
    <div>
      <h2 className="text-xs font-semibold text-[var(--muted-foreground)] mb-3">
        Modèles de routines
      </h2>
      <div className="space-y-2">
        {templates.map(t => (
          <div key={t.id} className="flex items-center gap-3 p-3 rounded-xl border border-dashed border-[var(--border)]">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium">{t.name}</p>
              <p className="text-xs text-[var(--muted-foreground)]">{t.description}</p>
            </div>
            <button
              onClick={() => activate.mutate(t.id, {
                onSuccess: () => toast.success(`Routine « ${t.name} » activée`),
                onError: () => toast.error('Erreur activation'),
              })}
              disabled={activate.isPending}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-[var(--primary)] text-[var(--primary-foreground)] text-xs font-medium shrink-0 disabled:opacity-40"
            >
              Activer <ChevronRight size={12} />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Vacation mode ────────────────────────────────────────────────────────────

function VacationToggle() {
  const { data } = useVacationMode()
  const set = useSetVacationMode()
  const active = data?.mode_vacances ?? false

  return (
    <div className="flex items-center justify-between p-3 rounded-xl border border-[var(--border)] bg-[var(--card)]">
      <div>
        <p className="text-sm font-medium">Mode vacances</p>
        <p className="text-xs text-[var(--muted-foreground)]">Suspend les rappels habitudes & agenda</p>
      </div>
      <button
        onClick={() => set.mutate(!active, {
          onSuccess: () => toast.success(active ? 'Mode vacances désactivé' : 'Mode vacances activé 🏖️'),
        })}
        className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
          active ? 'bg-amber-500' : 'bg-[var(--accent)]'
        }`}
      >
        <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow-lg transition ${
          active ? 'translate-x-5' : 'translate-x-0'
        }`} />
      </button>
    </div>
  )
}

// ─── Budget d'énergie du jour (#232) ──────────────────────────────────────────

function EnergyBudget() {
  const { data } = useEnergyBudget()
  if (!data) return null
  const pct = data.capacite > 0 ? Math.max(0, Math.min(100, (data.restant / data.capacite) * 100)) : 0
  const color = data.statut === 'dépassé' ? 'var(--warning-foreground)' : data.statut === 'serré' ? '#f59e0b' : 'var(--ring)'
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-4">
      <div className="mb-1.5 flex items-center justify-between">
        <h2 className="flex items-center gap-1.5 text-xs font-semibold text-[var(--muted-foreground)]"><Zap size={13} /> Budget d&apos;énergie du jour</h2>
        <span className="text-sm font-semibold tabular-nums" style={{ color }}>{data.restant} / {data.capacite}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[var(--muted)]">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
      <p className="mt-1.5 text-xs text-[var(--muted-foreground)]">
        Coût prévu {data.cout_prevu} ({data.n_activites} activités){data.statut === 'dépassé' ? ' — journée trop chargée, allège.' : data.statut === 'serré' ? ' — peu de marge.' : ''}
      </p>
    </div>
  )
}

// ─── Time machine : rejoue l'état d'une date passée (#230) ────────────────────

function TimeMachine() {
  const today = new Date().toISOString().slice(0, 10)
  const [date, setDate] = useState(today)
  const { data: snap, isLoading } = useSnapshot(date)
  const shift = (days: number) => {
    const d = new Date(date + 'T12:00:00')
    d.setDate(d.getDate() + days)
    const iso = d.toISOString().slice(0, 10)
    if (iso <= today) setDate(iso)
  }
  return (
    <div>
      <h2 className="mb-3 flex items-center gap-1.5 text-xs font-semibold text-[var(--muted-foreground)]">
        <Calendar size={13} /> Time machine — rejoue une journée passée
      </h2>
      <div className="mb-2 flex items-center gap-2">
        <button onClick={() => shift(-1)} aria-label="Jour précédent" className="rounded-lg border border-[var(--border)] p-1.5 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"><ChevronLeft size={15} /></button>
        <input type="date" value={date} max={today} onChange={(e) => setDate(e.target.value)} className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1.5 text-sm" />
        <button onClick={() => shift(1)} disabled={date >= today} aria-label="Jour suivant" className="rounded-lg border border-[var(--border)] p-1.5 text-[var(--muted-foreground)] hover:text-[var(--foreground)] disabled:opacity-40"><ChevronRight size={15} /></button>
      </div>
      {isLoading ? (
        <Skeleton className="h-16 rounded-xl" />
      ) : snap ? (
        <SnapshotCard snap={snap} />
      ) : (
        <p className="text-sm text-[var(--muted-foreground)]">Aucune donnée pour cette date.</p>
      )}
    </div>
  )
}

// ─── Heatmap annuelle multi-métriques (#233) ─────────────────────────────────

function AnnualHeatmap() {
  const [metric, setMetric] = useState('Humeur')
  const { data } = useHeatmap(metric)
  const byDate = new Map((data?.cells ?? []).map((c) => [c.date, c.value]))
  const min = data?.min ?? 0
  const max = data?.max ?? 0
  // 53 semaines alignées au lundi
  const today = new Date()
  const end = new Date(today); end.setDate(end.getDate() + (7 - ((end.getDay() + 6) % 7)) - 1) // dimanche courant
  const start = new Date(end); start.setDate(start.getDate() - 53 * 7 + 1)
  const weeks: Date[][] = []
  const cur = new Date(start)
  while (cur <= end) {
    const week: Date[] = []
    for (let i = 0; i < 7; i++) { week.push(new Date(cur)); cur.setDate(cur.getDate() + 1) }
    weeks.push(week)
  }
  const level = (iso: string): number => {
    if (!byDate.has(iso)) return 0
    if (max === min) return 3
    const n = (byDate.get(iso)! - min) / (max - min)
    return 1 + Math.min(3, Math.floor(n * 4))
  }
  const bg = (lv: number) => lv === 0 ? 'var(--muted)' : `color-mix(in srgb, var(--ring) ${lv * 25}%, transparent)`

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h2 className="flex items-center gap-1.5 text-xs font-semibold text-[var(--muted-foreground)]"><Activity size={13} /> Heatmap annuelle</h2>
        <select value={metric} onChange={(e) => setMetric(e.target.value)} className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs">
          {(data?.available ?? [metric]).map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>
      <div className="overflow-x-auto no-scrollbar">
        <div className="flex gap-[3px]">
          {weeks.map((week, wi) => (
            <div key={wi} className="flex flex-col gap-[3px]">
              {week.map((d) => {
                const iso = d.toISOString().slice(0, 10)
                const future = d > today
                return <div key={iso} title={`${iso}${byDate.has(iso) ? ` : ${byDate.get(iso)}` : ''}`} className="h-2.5 w-2.5 rounded-[2px]" style={{ background: future ? 'transparent' : bg(level(iso)) }} />
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Page principale ──────────────────────────────────────────────────────────

function SnapshotContent() {
  const [days, setDays] = useState(14)
  const { data: snapshots, isLoading } = useSnapshots(days)

  return (
    <div className="space-y-6">
      <WellbeingWidget />
      <EnergyBudget />
      <TimeMachine />
      <VacationToggle />
      <TemplatesSection />

      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-semibold text-[var(--muted-foreground)]">
            Historique
          </h2>
          <div className="flex gap-1">
            {[7, 14, 30].map(d => (
              <button
                key={d}
                onClick={() => setDays(d)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                  days === d
                    ? 'bg-[var(--primary)] text-[var(--primary-foreground)]'
                    : 'bg-[var(--accent)] text-[var(--muted-foreground)]'
                }`}
              >
                {d}j
              </button>
            ))}
          </div>
        </div>
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-16 rounded-xl" />
            ))}
          </div>
        ) : !snapshots?.length ? (
          <div className="text-center py-8 text-[var(--muted-foreground)]">
            <Activity size={28} className="mx-auto mb-2 opacity-30" />
            <p className="text-sm">Aucun snapshot disponible</p>
            <p className="text-xs mt-1">Les snapshots sont générés automatiquement chaque soir à 23h55.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {snapshots.map(s => <SnapshotCard key={s.date} snap={s} />)}
          </div>
        )}
      </div>

      <AnnualHeatmap />
    </div>
  )
}

export default function SnapshotPage() {
  return (
    <div className="space-y-0 animate-fade-in">
      <ModuleHeader title="Journal de vie" subtitle="Snapshot quotidien multi-modules + score bien-être" />
      <div className="p-6 animate-fade-in-up">
        <ErrorBoundary label="Journal de vie">
          <SnapshotContent />
        </ErrorBoundary>
      </div>
    </div>
  )
}
