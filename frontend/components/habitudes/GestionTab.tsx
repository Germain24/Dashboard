'use client'

import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { GripVertical, Plus, Archive, X, Link2 } from 'lucide-react'
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
  arrayMove,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { updateHabit, type Habit, type Streak, type Gamification } from '@/lib/habitudes'
import {
  habitudesKeys, useArchiveHabit, useCreateHabit, useGamification,
  useHabits, useStreaks, useUpdateHabit,
} from '@/lib/queries/habitudes'
import { Skeleton } from '@/components/ui/skeleton'

function parseLinked(raw: string | undefined): number[] {
  try {
    const v = JSON.parse(raw || '[]')
    return Array.isArray(v) ? v.filter((x): x is number => typeof x === 'number') : []
  } catch {
    return []
  }
}

export default function GestionTab() {
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [linkingId, setLinkingId] = useState<number | null>(null)

  const habitsQ = useHabits()
  const habits = habitsQ.isError ? [] : habitsQ.data ?? null
  const streaksQ = useStreaks()
  const gamiQ = useGamification()
  const streaks = (Array.isArray(streaksQ.data) ? streaksQ.data : []) as Streak[]
  const gami = (Array.isArray(gamiQ.data) ? gamiQ.data : []) as Gamification[]
  const archiveMutation = useArchiveHabit()
  const updateMutation = useUpdateHabit()

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id || !habits) return
    const from = habits.findIndex((h) => h.id === active.id)
    const to = habits.findIndex((h) => h.id === over.id)
    const reordered = arrayMove(habits, from, to)
    // Optimiste : on pousse l'ordre dans le cache puis on persiste.
    qc.setQueryData(habitudesKeys.habits(), reordered)
    try {
      await Promise.all(reordered.map((h, i) => updateHabit(h.id, { ordre: i })))
    } catch {
      toast.error("Impossible de sauvegarder l'ordre.")
    } finally {
      void qc.invalidateQueries({ queryKey: habitudesKeys.all })
    }
  }

  const handleArchive = (h: Habit) => {
    if (!confirm(`Archiver "${h.nom}" ? Elle ne sera plus visible dans la checklist.`)) return
    archiveMutation.mutate(h.id, {
      onSuccess: () => toast.success(`"${h.nom}" archivée.`),
      onError: () => toast.error("Impossible d'archiver cette habitude."),
    })
  }

  const handleToggleLink = (h: Habit, targetId: number) => {
    const current = parseLinked(h.linked_ids)
    const next = current.includes(targetId)
      ? current.filter((id) => id !== targetId)
      : [...current, targetId]
    updateMutation.mutate(
      { id: h.id, patch: { linked_ids: JSON.stringify(next) } },
      { onError: () => toast.error('Impossible de mettre à jour les liaisons.') },
    )
  }

  return (
    <div className="space-y-4 max-w-md">
      <div className="flex items-center justify-between">
        <p className="text-sm text-[var(--muted-foreground)]">
          Glisse pour réordonner · 🔗 pour lier · archive pour désactiver
        </p>
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-1.5 rounded-md bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          Nouvelle
        </button>
      </div>

      {showForm && (
        <NewHabitForm
          onClose={() => setShowForm(false)}
          onCreated={() => setShowForm(false)}
        />
      )}

      {habits === null && (
        <div className="space-y-2">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-12" />)}
        </div>
      )}

      {habits !== null && habits.length === 0 && (
        <p className="rounded-xl border border-dashed border-[var(--border)] p-4 text-center text-sm text-[var(--muted-foreground)]">
          Aucune habitude. Crée-en une !
        </p>
      )}

      {habits && habits.length > 0 && (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={(e) => void handleDragEnd(e)}>
          <SortableContext items={habits.map((h) => h.id)} strategy={verticalListSortingStrategy}>
            <div className="space-y-1.5">
              {habits.map((h) => (
                <SortableHabitRow
                  key={h.id}
                  habit={h}
                  others={habits.filter((o) => o.id !== h.id)}
                  streak={streaks.find((s) => s.habit_id === h.id)}
                  gami={gami.find((g) => g.habit_id === h.id)}
                  linkingOpen={linkingId === h.id}
                  onToggleLinking={() => setLinkingId((v) => (v === h.id ? null : h.id))}
                  onToggleLink={(targetId) => void handleToggleLink(h, targetId)}
                  onArchive={(x) => void handleArchive(x)}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}
    </div>
  )
}

function SortableHabitRow({
  habit, others, streak, gami, linkingOpen, onToggleLinking, onToggleLink, onArchive,
}: {
  habit: Habit
  others: Habit[]
  streak?: Streak
  gami?: Gamification
  linkingOpen: boolean
  onToggleLinking: () => void
  onToggleLink: (targetId: number) => void
  onArchive: (h: Habit) => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: habit.id,
  })
  const style = { transform: CSS.Transform.toString(transform), transition }
  const linked = parseLinked(habit.linked_ids)

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`rounded-xl border bg-[var(--card)] transition-shadow ${
        isDragging ? 'border-[var(--ring)] shadow-md opacity-80' : 'border-[var(--border)]'
      }`}
    >
      <div className="flex items-center gap-2 px-3 py-2.5">
        <button
          {...attributes}
          {...listeners}
          type="button"
          aria-label="Déplacer"
          className="shrink-0 cursor-grab touch-none text-[var(--muted-foreground)] active:cursor-grabbing"
        >
          <GripVertical className="h-4 w-4" aria-hidden="true" />
        </button>

        {/* icône emoji ou pastille couleur (#140) */}
        {habit.icone ? (
          <span className="text-base leading-none" aria-hidden="true">{habit.icone}</span>
        ) : (
          <span
            className="h-3 w-3 shrink-0 rounded-full"
            style={{ background: habit.couleur || 'var(--muted-foreground)' }}
            aria-hidden="true"
          />
        )}

        <span className="flex-1 truncate text-sm font-medium">{habit.nom}</span>

        {/* niveau (#142) */}
        {gami && gami.level > 1 && (
          <span className="shrink-0 rounded-full bg-[color-mix(in_srgb,var(--ring)_14%,transparent)] px-2 py-0.5 text-[11px] font-bold text-[var(--ring)]" title={`${gami.xp} XP · ${gami.xp_to_next} pour le niveau suivant`}>
            Nv {gami.level}
          </span>
        )}

        {/* meilleure série (#134) */}
        {streak && streak.best_streak > 0 && (
          <span className="shrink-0 text-[11px] text-[var(--muted-foreground)]" title="Série en cours · meilleure série">
            {streak.streak}🔥 / {streak.best_streak} max
          </span>
        )}

        <span className="shrink-0 text-xs text-[var(--muted-foreground)]">
          {habit.frequence === 'weekly' ? 'hebdo' : 'quotidien'}
        </span>

        <button
          type="button"
          onClick={onToggleLinking}
          aria-label={`Lier ${habit.nom}`}
          aria-expanded={linkingOpen}
          className={`shrink-0 rounded p-1.5 transition-colors ${
            linked.length > 0 ? 'text-[var(--ring)]' : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
          }`}
        >
          <Link2 className="h-4 w-4" aria-hidden="true" />
        </button>

        <button
          type="button"
          onClick={() => onArchive(habit)}
          aria-label={`Archiver ${habit.nom}`}
          className="shrink-0 rounded p-1.5 text-[var(--muted-foreground)] hover:text-[var(--destructive)] transition-colors"
        >
          <Archive className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      {/* panneau de liaison (#139) */}
      {linkingOpen && (
        <div className="border-t border-[var(--border)] px-3 py-2.5">
          <p className="mb-2 text-xs text-[var(--muted-foreground)]">
            Cocher « {habit.nom} » cochera aussi automatiquement :
          </p>
          {others.length === 0 ? (
            <p className="text-xs text-[var(--muted-foreground)]">Aucune autre habitude à lier.</p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {others.map((o) => {
                const on = linked.includes(o.id)
                return (
                  <button
                    key={o.id}
                    type="button"
                    onClick={() => onToggleLink(o.id)}
                    className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                      on
                        ? 'border-[var(--ring)] bg-[color-mix(in_srgb,var(--ring)_12%,transparent)] text-[var(--ring)]'
                        : 'border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]'
                    }`}
                  >
                    {on ? '✓ ' : ''}{o.nom}
                  </button>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const EMOJI_CHOICES = ['💪', '📖', '🧘', '💧', '🏃', '🥗', '😴', '🧠', '🎯', '✍️']

function NewHabitForm({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [nom, setNom] = useState('')
  const [frequence, setFrequence] = useState('daily')
  const [type, setType] = useState('binaire')
  const [icone, setIcone] = useState('')
  const [couleur, setCouleur] = useState('#6366f1')
  const createMutation = useCreateHabit()
  const saving = createMutation.isPending

  const submit = () => {
    if (!nom.trim()) { toast.error('Nom requis.'); return }
    createMutation.mutate(
      { nom: nom.trim(), frequence, type, icone: icone || null, couleur },
      {
        onSuccess: () => { toast.success(`"${nom}" créée.`); onCreated() },
        onError: () => toast.error('Impossible de créer cette habitude.'),
      },
    )
  }

  const inputCls = 'w-full rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]'

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold">Nouvelle habitude</p>
        <button type="button" onClick={onClose} className="p-1 text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      <label className="block">
        <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Nom</span>
        <input value={nom} onChange={(e) => setNom(e.target.value)} placeholder="Méditation, Sport…" className={inputCls} />
      </label>
      <div className="grid grid-cols-2 gap-3">
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Fréquence</span>
          <select value={frequence} onChange={(e) => setFrequence(e.target.value)} className={inputCls}>
            <option value="daily">Quotidien</option>
            <option value="weekly">Hebdomadaire</option>
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Type</span>
          <select value={type} onChange={(e) => setType(e.target.value)} className={inputCls}>
            <option value="binaire">Binaire</option>
            <option value="quantifiable">Quantifiable</option>
          </select>
        </label>
      </div>
      {/* couleur + icône (#140) */}
      <div className="grid grid-cols-[auto_1fr] items-center gap-3">
        <label className="flex items-center gap-2">
          <span className="text-xs font-medium text-[var(--muted-foreground)]">Couleur</span>
          <input
            type="color"
            value={couleur}
            onChange={(e) => setCouleur(e.target.value)}
            aria-label="Couleur"
            className="h-7 w-9 cursor-pointer rounded border border-[var(--border)] bg-transparent p-0.5"
          />
        </label>
        <div>
          <span className="mb-1 block text-xs font-medium text-[var(--muted-foreground)]">Icône</span>
          <div className="flex flex-wrap gap-1">
            {EMOJI_CHOICES.map((e) => (
              <button
                key={e}
                type="button"
                onClick={() => setIcone((v) => (v === e ? '' : e))}
                aria-pressed={icone === e}
                className={`rounded-md border px-1.5 py-0.5 text-base leading-none transition-colors ${
                  icone === e ? 'border-[var(--ring)] bg-[color-mix(in_srgb,var(--ring)_12%,transparent)]' : 'border-[var(--border)] hover:bg-[var(--muted)]'
                }`}
              >
                {e}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onClose} className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-[var(--muted)]">
          Annuler
        </button>
        <button type="button" onClick={() => void submit()} disabled={saving}
          className="rounded-md bg-[var(--primary)] px-4 py-1.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-60">
          {saving ? 'Création…' : 'Créer'}
        </button>
      </div>
    </div>
  )
}
