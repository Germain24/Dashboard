'use client'

/** Alertes sur les abonnements détectés (#260) : hausses de prix et doublons.
 *  Présentationnel — s'insère dans la section « Abonnements détectés » (#116). */

import type { SubscriptionAlerts as Alerts } from '@/lib/budget'

const formatCAD = (v: number) =>
  new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(v ?? 0)

const fmtPct = (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(1).replace('.', ',')} %`

export function SubscriptionAlerts({ alerts }: { alerts?: Alerts }) {
  if (!alerts || alerts.nb_alertes === 0) return null
  return (
    <div
      className="border-b border-[var(--border)] px-4 py-3"
      style={{ background: 'color-mix(in srgb, var(--warning) 8%, transparent)' }}
    >
      <AlertSummary alerts={alerts} />

      <ul className="space-y-1.5">
        {alerts.hausses.map((h) => (
          <li key={`h-${h.marchand}`} className="flex flex-wrap items-baseline gap-x-2 text-xs">
            <span className="font-medium">{h.marchand}</span>
            <span className="font-mono tabular-nums text-[var(--muted-foreground)]">
              {formatCAD(h.montant_precedent)} → {formatCAD(h.montant_actuel)}
            </span>
            <span className="font-medium" style={{ color: 'var(--destructive)' }}>{fmtPct(h.delta_pct)}</span>
            <span className="text-[var(--muted-foreground)]">depuis le {h.date}</span>
          </li>
        ))}

        {alerts.doublons.map((d) => (
          <li key={`d-${d.type}-${d.service}-${d.mois}`} className="flex flex-wrap items-baseline gap-x-2 text-xs">
            <span className="font-medium">{d.marchands.join(' + ')}</span>
            <span className="text-[var(--muted-foreground)]">
              {d.type === 'meme_service'
                ? `deux abonnements ${d.service} en parallèle`
                : `prélevé ${d.occurrences}× en ${d.mois}`}
            </span>
            <span className="font-mono tabular-nums" style={{ color: 'var(--destructive)' }}>
              {formatCAD(d.montant_redondant)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function AlertSummary({ alerts }: { alerts: Alerts }) {
  const n = alerts.nb_alertes
  return <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2"><h3 className="text-xs font-semibold" style={{ color: 'var(--warning)' }}>⚠ {n} alerte{n > 1 ? 's' : ''} d&apos;abonnement</h3>{alerts.surcout_mensuel > 0 && <span className="text-xs text-[var(--muted-foreground)]">≈ {formatCAD(alerts.surcout_mensuel)}/mois en jeu</span>}</div>
}
