'use client'

import { useState } from 'react'
import { Clock, Users, ChefHat, Flame } from 'lucide-react'

type Recette = {
  id: number
  nom: string
  temps_prep: number // minutes
  portions: number
  calories_par_portion: number
  difficulte: 'facile' | 'moyen' | 'difficile'
  tags: string[]
  ingredientsCount: number
}

const DIFFICULTE_CONFIG = {
  facile: { label: 'Facile', color: 'var(--success)' },
  moyen: { label: 'Moyen', color: '#f59e0b' },
  difficile: { label: 'Difficile', color: 'var(--destructive)' },
}

const MOCK_RECETTES: Recette[] = [
  { id: 1, nom: 'Poulet rôti aux herbes', temps_prep: 90, portions: 4, calories_par_portion: 380, difficulte: 'facile', tags: ['protéines', 'forno'], ingredientsCount: 8 },
  { id: 2, nom: 'Pâtes carbonara', temps_prep: 25, portions: 2, calories_par_portion: 520, difficulte: 'moyen', tags: ['rapide', 'pâtes'], ingredientsCount: 6 },
  { id: 3, nom: 'Buddha bowl quinoa', temps_prep: 30, portions: 1, calories_par_portion: 450, difficulte: 'facile', tags: ['végé', 'healthy'], ingredientsCount: 10 },
  { id: 4, nom: 'Soupe miso', temps_prep: 20, portions: 2, calories_par_portion: 150, difficulte: 'facile', tags: ['rapide', 'healthy'], ingredientsCount: 5 },
  { id: 5, nom: 'Risotto aux champignons', temps_prep: 45, portions: 3, calories_par_portion: 420, difficulte: 'difficile', tags: ['réconfort', 'végé'], ingredientsCount: 9 },
]

export default function RecettesTab() {
  const [recherche, setRecherche] = useState('')

  const filtrees = MOCK_RECETTES.filter(r =>
    r.nom.toLowerCase().includes(recherche.toLowerCase()) ||
    r.tags.some(t => t.toLowerCase().includes(recherche.toLowerCase()))
  )

  return (
    <div className="space-y-4">
      {/* Barre de recherche */}
      <div className="animate-fade-in-up">
        <input
          type="text"
          placeholder="Rechercher une recette..."
          value={recherche}
          onChange={e => setRecherche(e.target.value)}
          className="w-full max-w-sm rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)] transition-all duration-150"
        />
      </div>

      {/* Grille recettes */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 stagger">
        {filtrees.map(recette => {
          const diff = DIFFICULTE_CONFIG[recette.difficulte]
          return (
            <div key={recette.id} className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 card-hover animate-fade-in-up cursor-pointer group">
              <div className="flex items-start justify-between mb-2">
                <h3 className="text-sm font-semibold group-hover:text-[var(--ring)] transition-colors duration-150">
                  {recette.nom}
                </h3>
                <span className="text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 ml-2"
                  style={{ color: diff.color, background: `color-mix(in_srgb,${diff.color}_12%,transparent)` }}>
                  {diff.label}
                </span>
              </div>

              <div className="flex flex-wrap gap-3 text-xs text-[var(--muted-foreground)] mb-3">
                <span className="flex items-center gap-1">
                  <Clock size={11} />
                  {recette.temps_prep} min
                </span>
                <span className="flex items-center gap-1">
                  <Users size={11} />
                  {recette.portions} pers.
                </span>
                <span className="flex items-center gap-1">
                  <Flame size={11} />
                  {recette.calories_par_portion} kcal
                </span>
                <span className="flex items-center gap-1">
                  <ChefHat size={11} />
                  {recette.ingredientsCount} ing.
                </span>
              </div>

              <div className="flex flex-wrap gap-1">
                {recette.tags.map(tag => (
                  <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--muted)] text-[var(--muted-foreground)]">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {filtrees.length === 0 && (
        <div className="rounded-xl border border-dashed border-[var(--border)] p-8 text-center animate-fade-in-up">
          <p className="text-sm text-[var(--muted-foreground)]">Aucune recette trouvée.</p>
        </div>
      )}

      <div className="rounded-xl border border-dashed border-[var(--border)] p-6 text-center animate-fade-in-up">
        <p className="text-sm text-[var(--muted-foreground)]">
          Les recettes seront chargées depuis le backend Cuisine.
        </p>
      </div>
    </div>
  )
}
