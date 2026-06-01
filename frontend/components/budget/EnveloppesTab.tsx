'use client'

const formatCAD = (v: number) =>
  new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(v ?? 0)

const MOCK_ENVELOPPES = [
  { nom: 'Urgences', alloue: 500, utilise: 0, couleur: '#ef4444', description: 'Fonds d\'urgence mensuel' },
  { nom: 'Voyages', alloue: 200, utilise: 120, couleur: '#6366f1', description: 'Économies vacances' },
  { nom: 'Électronique', alloue: 100, utilise: 0, couleur: '#06b6d4', description: 'Renouvellement appareils' },
  { nom: 'Vêtements', alloue: 150, utilise: 65, couleur: '#8b5cf6', description: 'Garde-robe' },
  { nom: 'Formation', alloue: 100, utilise: 40, couleur: '#f59e0b', description: 'Cours & livres' },
]

export default function EnveloppesTab() {
  return (
    <div className="space-y-4 animate-fade-in-up">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 stagger">
        {MOCK_ENVELOPPES.map((env) => {
          const pct = Math.min(Math.round((env.utilise / env.alloue) * 100), 100)
          const restant = env.alloue - env.utilise
          return (
            <div key={env.nom} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 card-hover animate-fade-in-up">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: env.couleur }} />
                    <h3 className="text-sm font-semibold">{env.nom}</h3>
                  </div>
                  <p className="text-xs text-[var(--muted-foreground)]">{env.description}</p>
                </div>
                <span className="text-xs font-mono text-[var(--muted-foreground)]">{pct}%</span>
              </div>
              <div className="h-2 rounded-full bg-[var(--muted)] overflow-hidden mb-2">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${pct}%`, background: env.couleur }}
                />
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-[var(--muted-foreground)]">{formatCAD(env.utilise)} utilisé</span>
                <span className="font-medium text-[var(--success)]">{formatCAD(restant)} restant</span>
              </div>
            </div>
          )
        })}
      </div>

      <div className="rounded-xl border border-dashed border-[var(--border)] p-6 text-center">
        <p className="text-sm text-[var(--muted-foreground)]">
          Gestion des enveloppes budgétaires — backend à connecter.
        </p>
      </div>
    </div>
  )
}
