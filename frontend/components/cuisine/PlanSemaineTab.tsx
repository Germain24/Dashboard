'use client'

const JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
const REPAS = ['Déjeuner', 'Dîner']

const MOCK_PLAN: Record<string, Record<string, string>> = {
  Lundi: { Déjeuner: 'Poulet rôti aux herbes', Dîner: 'Soupe miso' },
  Mardi: { Déjeuner: 'Buddha bowl quinoa', Dîner: 'Pâtes carbonara' },
  Mercredi: { Déjeuner: '', Dîner: 'Risotto aux champignons' },
  Jeudi: { Déjeuner: 'Soupe miso', Dîner: '' },
  Vendredi: { Déjeuner: 'Pâtes carbonara', Dîner: 'Poulet rôti aux herbes' },
  Samedi: { Déjeuner: '', Dîner: '' },
  Dimanche: { Déjeuner: 'Buddha bowl quinoa', Dîner: '' },
}

// Obtient l'index du jour courant (0 = Lundi)
function getTodayIndex(): number {
  const dow = new Date().getDay()
  return dow === 0 ? 6 : dow - 1
}

export default function PlanSemaineTab() {
  const todayIdx = getTodayIndex()

  return (
    <div className="space-y-4 animate-fade-in-up">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 stagger">
        {JOURS.map((jour, idx) => {
          const isToday = idx === todayIdx
          return (
            <div
              key={jour}
              className={`rounded-xl border p-3 animate-fade-in-up transition-all duration-200 ${
                isToday
                  ? 'border-[var(--ring)] bg-[color-mix(in_srgb,var(--ring)_6%,transparent)]'
                  : 'border-[var(--border)] bg-[var(--card)] card-hover'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
                  {jour}
                </h3>
                {isToday && (
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-[var(--ring)] text-white">
                    Auj.
                  </span>
                )}
              </div>
              <div className="space-y-1.5">
                {REPAS.map(repas => {
                  const recette = MOCK_PLAN[jour]?.[repas] ?? ''
                  return (
                    <div key={repas} className="text-xs">
                      <span className="text-[var(--muted-foreground)]">{repas} : </span>
                      {recette ? (
                        <span className="font-medium">{recette}</span>
                      ) : (
                        <span className="text-[var(--muted-foreground)] italic">—</span>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      <div className="rounded-xl border border-dashed border-[var(--border)] p-6 text-center animate-fade-in-up">
        <p className="text-sm text-[var(--muted-foreground)]">
          Le plan de repas sera synchronisé avec le backend Cuisine.
        </p>
      </div>
    </div>
  )
}
