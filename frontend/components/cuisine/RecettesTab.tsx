'use client'
import { useEffect, useState } from 'react'
import { fetchRecipes, importFromUrl } from '@/lib/cuisine'

export function RecettesTab() {
  const [recipes, setRecipes] = useState<any[]>([])
  const [search, setSearch] = useState('')
  const [urlImport, setUrlImport] = useState('')
  const [loading, setLoading] = useState(false)

  const load = () => fetchRecipes(search || undefined).then(setRecipes)
  useEffect(() => { load() }, [search])

  const handleImport = async () => {
    if (!urlImport) return
    setLoading(true)
    try {
      await importFromUrl(urlImport)
      setUrlImport('')
      load()
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Rechercher une recette..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 rounded border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
        />
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Importer depuis une URL (JSON-LD)..."
          value={urlImport}
          onChange={e => setUrlImport(e.target.value)}
          className="flex-1 rounded border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
        />
        <button
          onClick={handleImport}
          disabled={loading}
          className="rounded bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50"
        >
          {loading ? 'Import...' : 'Importer'}
        </button>
      </div>
      {recipes.length === 0 ? (
        <p className="text-sm text-[var(--muted-foreground)]">Aucune recette trouvée.</p>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {recipes.map((r: any) => (
            <div key={r.id} className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4 space-y-2">
              {r.image_url && (
                <img src={r.image_url} alt={r.titre} className="w-full h-32 object-cover rounded-md" />
              )}
              <div className="font-medium text-sm text-[var(--card-foreground)]">{r.titre}</div>
              <div className="text-xs text-[var(--muted-foreground)]">
                {r.portions} portions · {(r.temps_prep ?? 0) + (r.temps_cuisson ?? 0)} min
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
