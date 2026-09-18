'use client'

/** TachesTab — liste des tâches triées par urgence + formulaire d'ajout. */

import { useState } from 'react'
import type { TacheCreate } from '@/lib/agenda'
import { useAgendaTasks, useCreateTask, useDeleteTask, useMarkTaskDone } from '@/lib/queries/agenda'
import { TaskFilters, TaskForm, TaskList } from './TachesParts'

export default function TachesTab() {
  const [filter, setFilter] = useState<'todo' | 'done' | 'all'>('todo')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<TacheCreate>({ titre: '', priorite: 3 })
  const tasksQ = useAgendaTasks(filter === 'all' ? undefined : filter)
  const createMutation = useCreateTask()
  const doneMutation = useMarkTaskDone()
  const deleteMutation = useDeleteTask()
  const create = () => {
    if (!form.titre.trim()) return
    createMutation.mutate(form, { onSuccess: () => { setForm({ titre: '', priorite: 3 }); setShowForm(false) } })
  }
  const tasks = tasksQ.data ?? []
  return <div className="space-y-4"><TaskFilters filter={filter} setFilter={setFilter} showForm={showForm} toggleForm={() => setShowForm((current) => !current)} />{showForm && <TaskForm form={form} setForm={setForm} onCreate={create} onCancel={() => setShowForm(false)} />}<TaskList tasks={tasks} loading={tasksQ.isLoading} filter={filter} onDone={(id) => doneMutation.mutate(id)} onDelete={(id) => deleteMutation.mutate(id)} /></div>
}
