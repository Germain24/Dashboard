'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Settings, CheckCircle2, XCircle, Save } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Skeleton } from '@/components/ui/skeleton'

const BASE = '/api/settings'

type SettingsData = {
  preferences: {
    backup_retention_count: number
    jobrun_retention_days: number
    notification_retention_days: number
    music_dir: string
  }
  integrations: {
    tmdb: boolean
    anthropic: boolean
    google_calendar: boolean
    openweather: boolean
  }
}

const INTEGRATION_LABELS: Record<string, string> = {
  tmdb: 'TMDB (Films & Séries)',
  anthropic: 'Claude API (Musique)',
  google_calendar: 'Google Calendar',
  openweather: 'OpenWeather (Météo)',
}

const INTEGRATION_ENV: Record<string, string> = {
  tmdb: 'TMDB_API_KEY',
  anthropic: 'ANTHROPIC_API_KEY',
  google_calendar: 'GOOGLE_REFRESH_TOKEN',
  openweather: 'OPENWEATHER_API_KEY',
}

function fetchSettings(): Promise<SettingsData> {
  return fetch(BASE).then(r => r.json())
}

function patchSettings(patch: Record<string, unknown>): Promise<SettingsData> {
  return fetch(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  }).then(r => r.json())
}

export default function ParametresPage() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['settings'], queryFn: fetchSettings })

  const mutation = useMutation({
    mutationFn: patchSettings,
    onSuccess: (updated) => {
      qc.setQueryData(['settings'], updated)
      toast.success('Préférences sauvegardées.')
    },
    onError: () => toast.error('Erreur lors de la sauvegarde.'),
  })

  const prefs = data?.preferences
  const integrations = data?.integrations

  const [form, setForm] = useState<Record<string, string | number>>({})
  const val = (key: string, fallback: string | number) =>
    key in form ? form[key] : (prefs?.[key as keyof typeof prefs] ?? fallback)

  const save = () => mutation.mutate(form as Record<string, unknown>)

  return (
    <div className="space-y-0 animate-fade-in">
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <div className="flex items-center gap-2 mb-1">
          <Settings size={20} className="text-[var(--muted-foreground)]" />
          <h1 className="text-xl font-semibold tracking-tight">Paramètres</h1>
        </div>
        <p className="text-sm text-[var(--muted-foreground)]">Intégrations & préférences</p>
      </div>

      <div className="p-6 max-w-lg space-y-8 animate-fade-in-up">
        {/* Intégrations */}
        <section>
          <h2 className="text-sm font-semibold mb-3">Intégrations</h2>
          <p className="text-xs text-[var(--muted-foreground)] mb-4">
            Les clés API se configurent dans le fichier <code className="bg-[var(--muted)] px-1 rounded">.env</code> à la racine du projet.
          </p>
          {isLoading ? (
            <div className="space-y-2">{[0,1,2,3].map(i => <Skeleton key={i} className="h-10" />)}</div>
          ) : (
            <div className="space-y-2">
              {Object.entries(integrations ?? {}).map(([key, configured]) => (
                <div key={key} className="flex items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-3">
                  <div>
                    <p className="text-sm font-medium">{INTEGRATION_LABELS[key] ?? key}</p>
                    <p className="text-xs text-[var(--muted-foreground)] font-mono mt-0.5">{INTEGRATION_ENV[key]}</p>
                  </div>
                  {configured ? (
                    <span className="flex items-center gap-1.5 text-xs font-medium text-[var(--success)]">
                      <CheckCircle2 size={14} /> Configurée
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5 text-xs font-medium text-[var(--muted-foreground)]">
                      <XCircle size={14} /> Non configurée
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Préférences */}
        <section>
          <h2 className="text-sm font-semibold mb-4">Préférences</h2>
          {isLoading ? (
            <div className="space-y-3">{[0,1,2,3].map(i => <Skeleton key={i} className="h-12" />)}</div>
          ) : (
            <div className="space-y-4">
              <PrefField
                label="Dossier musique"
                hint="Chemin absolu vers votre bibliothèque musicale"
                type="text"
                value={val('music_dir', '') as string}
                onChange={v => setForm(f => ({ ...f, music_dir: v }))}
              />
              <PrefField
                label="Rétention backups"
                hint="Nombre de fichiers de sauvegarde conservés"
                type="number"
                min={1}
                max={90}
                value={val('backup_retention_count', 14) as number}
                onChange={v => setForm(f => ({ ...f, backup_retention_count: Number(v) }))}
              />
              <PrefField
                label="Rétention JobRun (jours)"
                hint="Durée de conservation des logs de tâches planifiées"
                type="number"
                min={1}
                max={365}
                value={val('jobrun_retention_days', 30) as number}
                onChange={v => setForm(f => ({ ...f, jobrun_retention_days: Number(v) }))}
              />
              <PrefField
                label="Rétention notifications (jours)"
                hint="Durée de conservation des notifications lues"
                type="number"
                min={1}
                max={365}
                value={val('notification_retention_days', 30) as number}
                onChange={v => setForm(f => ({ ...f, notification_retention_days: Number(v) }))}
              />

              <button
                onClick={save}
                disabled={mutation.isPending || Object.keys(form).length === 0}
                className="flex items-center gap-2 px-4 py-2 bg-[var(--ring)] text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-opacity"
              >
                <Save size={14} />
                {mutation.isPending ? 'Sauvegarde…' : 'Sauvegarder'}
              </button>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function PrefField({
  label,
  hint,
  type,
  value,
  onChange,
  min,
  max,
}: {
  label: string
  hint: string
  type: 'text' | 'number'
  value: string | number
  onChange: (v: string) => void
  min?: number
  max?: number
}) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1">{label}</label>
      <p className="text-xs text-[var(--muted-foreground)] mb-1.5">{hint}</p>
      <input
        type={type}
        min={min}
        max={max}
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full border border-[var(--border)] bg-[var(--background)] rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-[var(--ring)]"
      />
    </div>
  )
}
