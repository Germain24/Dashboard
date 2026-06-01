'use client'

const formatCAD = (v: number) =>
  new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(v ?? 0)

// Données mock en attendant le backend
const MOCK_SUMMARY = {
  revenus: 3200,
  depenses: 1850.75,
  solde: 1349.25,
}

const MOCK_CATEGORIES = [
  { nom: 'Loyer', montant: 900, budget: 900, couleur: '#6366f1' },
  { nom: 'Épicerie', montant: 320.5, budget: 400, couleur: '#22c55e' },
  { nom: 'Transport', montant: 85, budget: 150, couleur: '#f59e0b' },
  { nom: 'Restaurants', montant: 210.25, budget: 200, couleur: '#ef4444' },
  { nom: 'Abonnements', montant: 65, budget: 80, couleur: '#8b5cf6' },
  { nom: 'Loisirs', montant: 120, budget: 150, couleur: '#06b6d4' },
  { nom: 'Divers', montant: 150, budget: 200, couleur: '#71717a' },
]

export default function MoisTab() {
  const summary = MOCK_SUMMARY
  const categories = MOCK_CATEGORIES

  const totalBudget = categories.reduce((s, c) => s + c.budget, 0)
  const depensesPct = Math.round((summary.depenses / summary.revenus) * 100)

  return (
    <div className="space-y-6">
      {/* Stats cards */}
      <div className="grid grid-cols-3 gap-4 stagger">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 card-hover animate-fade-in-up">
          <p className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider mb-1">Revenus</p>
          <p className="text-2xl font-bold font-mono text-[var(--success)]">{formatCAD(summary.revenus)}</p>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 card-hover animate-fade-in-up">
          <p className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider mb-1">Dépenses</p>
          <p className="text-2xl font-bold font-mono text-[var(--destructive)]">{formatCAD(summary.depenses)}</p>
          <p className="text-xs text-[var(--muted-foreground)] mt-1">{depensesPct}% des revenus</p>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 card-hover animate-fade-in-up">
          <p className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider mb-1">Solde</p>
          <p className={`text-2xl font-bold font-mono ${summary.solde >= 0 ? 'text-[var(--success)]' : 'text-[var(--destructive)]'}`}>
            {formatCAD(summary.solde)}
          </p>
        </div>
      </div>

      {/* Dépenses par catégorie */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] overflow-hidden animate-fade-in-up">
        <div className="px-4 py-3 border-b border-[var(--border)]">
          <h2 className="text-sm font-semibold">Dépenses par catégorie</h2>
          <p className="text-xs text-[var(--muted-foreground)] mt-0.5">Budget total : {formatCAD(totalBudget)}</p>
        </div>
        <div className="divide-y divide-[var(--border)]">
          {categories.map((cat) => {
            const pct = Math.min(Math.round((cat.montant / cat.budget) * 100), 100)
            const over = cat.montant > cat.budget
            return (
              <div key={cat.nom} className="px-4 py-3 hover:bg-[var(--muted)] transition-colors duration-150">
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: cat.couleur }} />
                    <span className="text-sm font-medium">{cat.nom}</span>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <span className={over ? 'text-[var(--destructive)] font-medium' : 'text-[var(--foreground)]'}>
                      {formatCAD(cat.montant)}
                    </span>
                    <span className="text-[var(--muted-foreground)] text-xs">/ {formatCAD(cat.budget)}</span>
                  </div>
                </div>
                <div className="h-1.5 rounded-full bg-[var(--muted)] overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${pct}%`,
                      background: over ? 'var(--destructive)' : cat.couleur,
                    }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Note placeholder */}
      <div className="rounded-xl border border-dashed border-[var(--border)] p-6 text-center animate-fade-in-up">
        <p className="text-sm text-[var(--muted-foreground)]">
          Les données réelles seront disponibles une fois le backend Budget connecté.
        </p>
      </div>
    </div>
  )
}
