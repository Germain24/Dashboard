'use client'

import { StaggerGroup, StaggerItem } from '@/lib/motion/Stagger'
import { CHART_SERIES } from '@/lib/design/colors'

const formatCAD = (v: number) =>
  new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(v ?? 0)

const MOCK_ENVELOPPES = [
  { nom: 'Urgences', alloue: 500, utilise: 0, description: 'Fonds d\'urgence mensuel' },
  { nom: 'Voyages', alloue: 200, utilise: 120, description: 'Économies vacances' },
  { nom: 'Électronique', alloue: 100, utilise: 0, description: 'Renouvellement appareils' },
  { nom: 'Vêtements', alloue: 150, utilise: 65, description: 'Garde-robe' },
  { nom: 'Formation', alloue: 100, utilise: 40, description: 'Cours & livres' },
]

export default function EnveloppesTab() {
  return (
    <div className="space-y-4 animate-fade-in-up">
      <StaggerGroup className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {MOCK_ENVELOPPES.map((env, i) => {
          const pct = Math.min(Math.round((env.utilise / env.alloue) * 100), 100)
          const restant = env.alloue - env.utilise
          const couleur = CHART_SERIES[i % CHART_SERIES.length]
          return (
            <StaggerItem key={env.nom}>
              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 card-hover">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: couleur }} />
                      <h3 className="text-sm font-semibold">{env.nom}</h3>
                    </div>
                    <p className="text-xs text-[var(--muted-foreground)]">{env.description}</p>
                  </div>
                  <span className="text-xs font-mono text-[var(--muted-foreground)]">{pct}%</span>
                </div>
                <div className="h-2 rounded-full bg-[var(--muted)] overflow-hidden mb-2">
                  <div
                    className="h-full rounded-full bar-fill"
                    style={{ width: `${pct}%`, background: couleur }}
                  />
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-[var(--muted-foreground)]">{formatCAD(env.utilise)} utilisé</span>
                  <span className="font-medium text-[var(--success)]">{formatCAD(restant)} restant</span>
                </div>
              </div>
            </StaggerItem>
          )
        })}
      </StaggerGroup>

      <div className="rounded-xl border border-dashed border-[var(--border)] p-6 text-center">
        <p className="text-sm text-[var(--muted-foreground)]">
          Gestion des enveloppes budgétaires — backend à connecter.
        </p>
      </div>
    </div>
  )
}
