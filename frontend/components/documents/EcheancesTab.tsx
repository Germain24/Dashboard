'use client'

import { useState } from 'react'
import { AlertTriangle, Calendar, CheckCircle2, FileText } from 'lucide-react'
import { type DocType, TYPE_LABELS } from '@/lib/documents'
import { useEcheances } from '@/lib/queries/documents'
import { Skeleton } from '@/components/ui/skeleton'

const EXPIRY_CONFIG = {
  ok:      { label: 'Valide',         color: 'text-green-500',  bg: 'bg-green-500/10', icon: CheckCircle2 },
  warning: { label: 'Expire bientôt', color: 'text-amber-500',  bg: 'bg-amber-500/10', icon: AlertTriangle },
  expired: { label: 'Expiré',         color: 'text-red-500',    bg: 'bg-red-500/10',   icon: AlertTriangle },
  no_date: { label: '—',              color: 'text-[var(--muted-foreground)]', bg: '', icon: FileText },
}

const HORIZON_OPTIONS = [
  { label: '30 jours', value: 30 },
  { label: '90 jours', value: 90 },
  { label: '1 an',     value: 365 },
]

export default function EcheancesTab() {
  const [days, setDays] = useState(90)
  const { data: docs, isLoading } = useEcheances(days)

  const expired = docs?.filter(d => d.statut_expiration === 'expired') ?? []
  const warning = docs?.filter(d => d.statut_expiration === 'warning') ?? []
  const ok      = docs?.filter(d => d.statut_expiration === 'ok') ?? []

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <Calendar size={16} className="text-[var(--muted-foreground)]" />
        <span className="text-sm text-[var(--muted-foreground)]">Horizon :</span>
        {HORIZON_OPTIONS.map(o => (
          <button
            key={o.value}
            onClick={() => setDays(o.value)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              days === o.value
                ? 'bg-[var(--primary)] text-[var(--primary-foreground)]'
                : 'bg-[var(--accent)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 rounded-xl" />
          ))}
        </div>
      ) : !docs?.length ? (
        <div className="text-center py-12 text-[var(--muted-foreground)]">
          <CheckCircle2 size={32} className="mx-auto mb-2 opacity-30 text-green-500" />
          <p className="text-sm">Aucune échéance dans les {days} prochains jours</p>
        </div>
      ) : (
        <div className="space-y-6">
          {[
            { group: expired, title: 'Expirés', status: 'expired' as const },
            { group: warning, title: 'À renouveler bientôt', status: 'warning' as const },
            { group: ok,      title: 'Valides',  status: 'ok' as const },
          ]
            .filter(s => s.group.length > 0)
            .map(({ group, title, status }) => {
              const cfg = EXPIRY_CONFIG[status]
              const Icon = cfg.icon
              return (
                <div key={status}>
                  <h3 className={`flex items-center gap-1.5 text-xs font-semibold mb-2 ${cfg.color}`}>
                    <Icon size={13} /> {title}
                  </h3>
                  <div className="space-y-2">
                    {group.map(doc => (
                      <div
                        key={doc.id}
                        className={`flex items-center justify-between p-3 rounded-xl border border-[var(--border)] ${cfg.bg}`}
                      >
                        <div>
                          <p className="text-sm font-medium">{doc.titre}</p>
                          <p className="text-xs text-[var(--muted-foreground)]">
                            {TYPE_LABELS[doc.type as DocType]}
                            {doc.organisme ? ` · ${doc.organisme}` : ''}
                          </p>
                        </div>
                        {doc.date_expiration && (
                          <span className={`text-xs font-medium ${cfg.color}`}>
                            {new Date(doc.date_expiration).toLocaleDateString('fr-FR')}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
        </div>
      )}
    </div>
  )
}
