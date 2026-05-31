'use client'
import { useEffect, useState } from 'react'
import { fetchJobs, forceRun, pauseJob, resumeJob } from '@/lib/jobs'

const JOB_LABELS: Record<string, string> = {
  portfolio_snapshot: 'Snapshot portefeuille',
  nutrition_plan: 'Plan nutrition',
  backup_db: 'Backup base de données',
  weather_refresh: 'Météo',
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  const load = () => fetchJobs().then((j: any[]) => { setJobs(j); setLoading(false) })
  useEffect(() => { load() }, [])

  const handleRun = async (job_id: string) => {
    await forceRun(job_id)
    setTimeout(load, 1000)
  }

  if (loading) {
    return (
      <div className="p-6">
        <div className="h-64 w-full rounded-lg bg-[var(--muted)] animate-pulse" />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Jobs automatiques</h1>

      {jobs.length === 0 && (
        <p className="text-sm text-[var(--muted-foreground)]">Aucun job configuré.</p>
      )}

      <div className="space-y-3">
        {jobs.map((job: any) => (
          <div key={job.job_id} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
            <div className="flex items-center justify-between gap-4">
              <div className="space-y-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-sm text-[var(--card-foreground)]">
                    {JOB_LABELS[job.job_id] ?? job.job_id}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    job.paused
                      ? 'bg-[var(--muted)] text-[var(--muted-foreground)]'
                      : 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                  }`}>
                    {job.paused ? 'En pause' : 'Actif'}
                  </span>
                </div>
                {job.next_run && (
                  <div className="text-xs text-[var(--muted-foreground)]">
                    Prochain run : {new Date(job.next_run).toLocaleString('fr-CA')}
                  </div>
                )}
                {job.last_run && (
                  <div className="text-xs text-[var(--muted-foreground)]">
                    Dernier : {job.last_run.status === 'success' ? '✅' : '❌'}{' '}
                    {new Date(job.last_run.started_at).toLocaleString('fr-CA')}
                  </div>
                )}
              </div>
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={() => handleRun(job.job_id)}
                  className="rounded border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-xs font-medium text-[var(--foreground)] hover:bg-[var(--muted)] transition-colors"
                >
                  Lancer
                </button>
                {job.paused ? (
                  <button
                    onClick={() => resumeJob(job.job_id).then(load)}
                    className="rounded border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-xs font-medium text-[var(--foreground)] hover:bg-[var(--muted)] transition-colors"
                  >
                    Reprendre
                  </button>
                ) : (
                  <button
                    onClick={() => pauseJob(job.job_id).then(load)}
                    className="rounded border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-xs font-medium text-[var(--foreground)] hover:bg-[var(--muted)] transition-colors"
                  >
                    Pause
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
