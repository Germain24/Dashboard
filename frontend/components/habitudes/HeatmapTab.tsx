'use client'

const HABITUDES = [
  { id: 1, nom: 'Méditation' },
  { id: 2, nom: 'Lecture' },
  { id: 3, nom: 'Sport' },
  { id: 4, nom: 'Journaling' },
  { id: 5, nom: 'Pleine nature' },
  { id: 6, nom: 'Appel famille' },
]

// Génère les 28 derniers jours
function getLast28Days(): string[] {
  const days: string[] = []
  for (let i = 27; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    days.push(d.toISOString().slice(0, 10))
  }
  return days
}

// Mock: quelques jours cochés aléatoirement (seed déterministe)
function mockChecked(habitId: number, date: string): boolean {
  const hash = (habitId * 13 + date.split('').reduce((a, c) => a + c.charCodeAt(0), 0)) % 3
  return hash !== 0
}

const JOURS_ABREV = ['D', 'L', 'M', 'M', 'J', 'V', 'S']

export default function HeatmapTab() {
  const days = getLast28Days()

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <h2 className="text-sm font-semibold mb-1">Heatmap — 28 derniers jours</h2>
        <p className="text-xs text-[var(--muted-foreground)] mb-4">Vue d'ensemble de ta régularité</p>

        <div className="space-y-3 overflow-x-auto">
          {/* En-tête jours */}
          <div className="flex gap-1">
            <div className="w-28 flex-shrink-0" />
            {days.map((d) => {
              const dow = new Date(d + 'T12:00:00').getDay()
              return (
                <div key={d} className="w-7 text-center text-[10px] text-[var(--muted-foreground)]">
                  {JOURS_ABREV[dow]}
                </div>
              )
            })}
          </div>

          {/* Lignes habitudes */}
          {HABITUDES.map((h) => (
            <div key={h.id} className="flex items-center gap-1">
              <div className="w-28 flex-shrink-0 text-xs text-[var(--muted-foreground)] truncate pr-2">
                {h.nom}
              </div>
              {days.map((d) => {
                const ok = mockChecked(h.id, d)
                return (
                  <div
                    key={d}
                    title={`${h.nom} — ${d}`}
                    className={`w-7 h-7 rounded-md transition-colors duration-150 ${
                      ok
                        ? 'bg-[var(--success)] opacity-80'
                        : 'bg-[var(--muted)]'
                    }`}
                  />
                )
              })}
            </div>
          ))}
        </div>

        {/* Légende */}
        <div className="flex items-center gap-2 mt-4 text-xs text-[var(--muted-foreground)]">
          <div className="w-4 h-4 rounded bg-[var(--muted)]" />
          <span>Non fait</span>
          <div className="w-4 h-4 rounded bg-[var(--success)] opacity-80 ml-3" />
          <span>Complété</span>
        </div>
      </div>

      <p className="text-xs text-[var(--muted-foreground)] animate-fade-in-up">
        Données mock — le backend Habitudes fournira les vraies entrées.
      </p>
    </div>
  )
}
