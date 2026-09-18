'use client'

import type { Tache, TacheCreate } from '@/lib/agenda'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { EmptyState } from '@/components/ui/empty-state'
import { Spinner } from '@/components/ui/spinner'
import { cn } from '@/lib/utils'

export const PRIORITE_LABELS: Record<number, string> = { 1: '🔴 Très haute', 2: '🟠 Haute', 3: '🟡 Normale', 4: '🟢 Basse', 5: '⚪ Très basse' }

const isOverdue = (task: Tache) => Boolean(task.deadline && task.deadline < new Date().toISOString().split('T')[0] && task.statut === 'todo')

function TaskCheck({ task, onDone }: { task: Tache; onDone: (id: number) => void }) {
  return <button onClick={() => onDone(task.id)} className={cn('mt-0.5 h-4 w-4 shrink-0 rounded-full border-2 transition-colors', task.statut === 'done' ? 'border-[var(--success)] bg-[var(--success)]' : 'border-[var(--muted-foreground)] hover:border-[var(--success)]')} title="Marquer comme fait" />
}

function TaskTitle({ task }: { task: Tache }) {
  return <div className={cn('text-sm font-medium', task.statut === 'done' ? 'line-through text-[var(--muted-foreground)]' : 'text-[var(--foreground)]')}>{task.titre}</div>
}

function TaskDeadline({ task, overdue }: { task: Tache; overdue: boolean }) {
  if (!task.deadline) return null
  return <span className={overdue ? 'font-semibold text-[var(--destructive)]' : ''}>📅 {task.deadline}</span>
}

function TaskCategory({ task }: { task: Tache }) {
  if (!task.categorie) return null
  return <span className="rounded-[var(--radius-sm)] bg-[var(--muted)] px-1.5 py-0.5">{task.categorie}</span>
}

function TaskMeta({ task, overdue }: { task: Tache; overdue: boolean }) {
  return <div className="mt-1 flex flex-wrap gap-2 text-xs text-[var(--muted-foreground)]"><span>{PRIORITE_LABELS[task.priorite]}</span><TaskDeadline task={task} overdue={overdue} /><TaskCategory task={task} />{task.duree_estimee_min && <span>⏱ {task.duree_estimee_min} min</span>}</div>
}

export function TacheRow({ task, onDone, onDelete }: { task: Tache; onDone: (id: number) => void; onDelete: (id: number) => void }) {
  const overdue = isOverdue(task)
  return <div className={cn('mb-2 flex items-start gap-3 rounded-[var(--radius)] border p-3', overdue ? 'border-[var(--destructive-muted)] bg-[var(--destructive-muted)]' : 'border-[var(--border)] bg-[var(--card)]')}><TaskCheck task={task} onDone={onDone} /><div className="min-w-0 flex-1"><TaskTitle task={task} /><TaskMeta task={task} overdue={overdue} /><TaskNote note={task.note} /></div><button onClick={() => onDelete(task.id)} className="text-lg leading-none text-[var(--border)] transition-colors hover:text-[var(--destructive)]" aria-label="Supprimer">×</button></div>
}

function TaskNote({ note }: { note: string | null }) {
  if (!note) return null
  return <p className="mt-1 text-xs italic text-[var(--muted-foreground)]">{note}</p>
}

export function TaskFilters({ filter, setFilter, showForm, toggleForm }: { filter: 'todo' | 'done' | 'all'; setFilter: (value: 'todo' | 'done' | 'all') => void; showForm: boolean; toggleForm: () => void }) {
  return <div className="flex items-center gap-2"><div className="flex overflow-hidden rounded-[var(--radius)] border border-[var(--border)] text-sm">{(['todo', 'done', 'all'] as const).map((value) => <button key={value} onClick={() => setFilter(value)} className={cn('px-3 py-1.5 transition-colors', filter === value ? 'bg-[var(--primary)] text-[var(--primary-foreground)]' : 'bg-transparent text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)]')}>{value === 'todo' ? 'À faire' : value === 'done' ? 'Fait' : 'Tout'}</button>)}</div><Button size="sm" className="ml-auto" onClick={toggleForm}>{showForm ? '− Fermer' : '+ Ajouter'}</Button></div>
}

export function TaskForm({ form, setForm, onCreate, onCancel }: { form: TacheCreate; setForm: (update: (current: TacheCreate) => TacheCreate) => void; onCreate: () => void; onCancel: () => void }) {
  return <div className="space-y-3 rounded-[var(--radius-lg)] border border-[var(--border)] bg-[var(--muted)] p-4"><Input placeholder="Titre de la tâche *" value={form.titre} onChange={(event) => setForm((current) => ({ ...current, titre: event.target.value }))} /><div className="grid grid-cols-2 gap-3"><Input label="Deadline" type="date" value={form.deadline || ''} onChange={(event) => setForm((current) => ({ ...current, deadline: event.target.value || null }))} /><Select label="Priorité" value={String(form.priorite)} onChange={(event) => setForm((current) => ({ ...current, priorite: +event.target.value }))}>{[1, 2, 3, 4, 5].map((priority) => <option key={priority} value={priority}>{PRIORITE_LABELS[priority]}</option>)}</Select></div><Input placeholder="Catégorie (ex: etudes, courses…)" value={form.categorie || ''} onChange={(event) => setForm((current) => ({ ...current, categorie: event.target.value || null }))} /><Textarea placeholder="Note (optionnel)" rows={2} value={form.note || ''} onChange={(event) => setForm((current) => ({ ...current, note: event.target.value || null }))} /><div className="flex gap-2"><Button size="sm" onClick={onCreate}>Créer</Button><Button variant="secondary" size="sm" onClick={onCancel}>Annuler</Button></div></div>
}

export function TaskList({ tasks, loading, filter, onDone, onDelete }: { tasks: Tache[]; loading: boolean; filter: 'todo' | 'done' | 'all'; onDone: (id: number) => void; onDelete: (id: number) => void }) {
  if (loading) return <Spinner size="sm" label="Chargement…" />
  if (tasks.length === 0) return <EmptyState title={`Aucune tâche ${filter === 'todo' ? 'à faire' : ''}`} description="Appuie sur + Ajouter pour en créer une." />
  return <>{tasks.map((task) => <TacheRow key={task.id} task={task} onDone={onDone} onDelete={onDelete} />)}</>
}
