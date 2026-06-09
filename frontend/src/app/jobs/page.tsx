'use client'
import { useEffect, useState } from 'react'
import { fetchJobs, fetchRuns, forceRun, pauseJob, resumeJob } from '@/lib/jobs'

const JOB_LABELS: Record<string, string> = {
  portfolio_snapshot: 'Snapshot portefeuille',
  nutrition_plan: 'Plan nutrition',
  backup_db: 'Backup base de données',
  weather_refresh: 'Météo',
  agenda_reminders: 'Rappels agenda',
  habit_reminders: 'Rappels habitudes',
  purge_old: 'Purge (JobRun & notifications)',
}

type JobRun = { id: number; started_at: string; finished_at: string | null; status: string; log: string }
type Job = { job_id: string; next_run: string | null; paused: boolean; last_run: JobRun | null; last_failed: boolean }

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)

  const load = () => {
    fetchJobs().then((j: Job[]) => { setJobs(j); setLoading(false) }).catch(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  if (loading) {
    return <div className="p-6"><div className="h-64 w-full rounded-lg bg-[var(--muted)] animate-pulse" /></div>
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Jobs automatiques</h1>
      {jobs.length === 0 && <p className="text-sm text-[var(--muted-foreground)]">Aucun job configuré.</p>}
      <div className="space-y-3">
        {jobs.map((job) => <JobCard key={job.job_id} job={job} onChange={load} />)}
      </div>
    </div>
  )
}

function JobCard({ job, onChange }: { job: Job; onChange: () => void }) {
  const [showHistory, setShowHistory] = useState(false)
  const [runs, setRuns] = useState<JobRun[] | null>(null)

  const toggleHistory = async () => {
    const next = !showHistory
    setShowHistory(next)
    if (next && runs === null) {
      try { setRuns(await fetchRuns(job.job_id)) } catch { setRuns([]) }
    }
  }

  const handleRun = async () => { await forceRun(job.job_id); setRuns(null); setTimeout(onChange, 1000) }

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="flex items-center justify-between gap-4">
        <div className="space-y-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm text-[var(--card-foreground)]">{JOB_LABELS[job.job_id] ?? job.job_id}</span>
            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              job.paused ? 'bg-[var(--muted)] text-[var(--muted-foreground)]'
                : 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'}`}>
              {job.paused ? 'En pause' : 'Actif'}
            </span>
            {job.last_failed && (
              <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800 dark:bg-red-900/30 dark:text-red-400">
                ⚠ Dernier run en échec
              </span>
            )}
          </div>
          {job.next_run && (
            <div className="text-xs text-[var(--muted-foreground)]">Prochain run : {new Date(job.next_run).toLocaleString('fr-CA')}</div>
          )}
          {job.last_run && (
            <div className="text-xs text-[var(--muted-foreground)]">
              Dernier : {job.last_run.status === 'success' ? '✅' : job.last_run.status === 'running' ? '⏳' : '❌'}{' '}
              {new Date(job.last_run.started_at).toLocaleString('fr-CA')}
            </div>
          )}
          <button onClick={() => void toggleHistory()} className="text-xs text-[var(--ring)] hover:underline">
            {showHistory ? 'Masquer l’historique' : 'Historique'}
          </button>
        </div>
        <div className="flex gap-2 shrink-0">
          <button onClick={() => void handleRun()}
            className="rounded border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-xs font-medium text-[var(--foreground)] hover:bg-[var(--muted)] transition-colors">
            Lancer
          </button>
          {job.paused ? (
            <button onClick={() => void resumeJob(job.job_id).then(onChange)}
              className="rounded border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-xs font-medium text-[var(--foreground)] hover:bg-[var(--muted)] transition-colors">Reprendre</button>
          ) : (
            <button onClick={() => void pauseJob(job.job_id).then(onChange)}
              className="rounded border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-xs font-medium text-[var(--foreground)] hover:bg-[var(--muted)] transition-colors">Pause</button>
          )}
        </div>
      </div>

      {showHistory && (
        <div className="mt-3 border-t border-[var(--border)] pt-2">
          {runs === null && <p className="text-xs text-[var(--muted-foreground)]">Chargement…</p>}
          {runs && runs.length === 0 && <p className="text-xs text-[var(--muted-foreground)]">Aucune exécution enregistrée.</p>}
          {runs && runs.length > 0 && (
            <ul className="space-y-1">
              {runs.map((r) => (
                <li key={r.id} className="flex items-center gap-2 text-xs">
                  <span>{r.status === 'success' ? '✅' : r.status === 'running' ? '⏳' : '❌'}</span>
                  <span className="text-[var(--muted-foreground)]">{new Date(r.started_at).toLocaleString('fr-CA')}</span>
                  {r.log && <span className="truncate text-[var(--muted-foreground)]">— {r.log}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
