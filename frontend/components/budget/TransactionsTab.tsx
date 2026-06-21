'use client'

import { useRef, useState } from 'react'
import { ArrowDownLeft, ArrowUpRight, Upload, Download, Wand2 } from 'lucide-react'
import {
  useBudgetCategories, useBudgetTransactions, useImportCsv, useSetTransactionTags,
  useRuleSuggestions, useLearnRules,
} from '@/lib/queries/budget'

const formatCAD = (v: number) =>
  new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(v ?? 0)

export default function TransactionsTab() {
  const [msg, setMsg] = useState<string | null>(null)
  const [tagFilter, setTagFilter] = useState('')   // '' tous · '__none__' sans tag · tag
  const [catFilter, setCatFilter] = useState('')   // '' tous · 'none' sans catégorie · id
  const [bankFilter, setBankFilter] = useState('') // '' toutes · nom de banque
  const [typeFilter, setTypeFilter] = useState('') // '' tous · 'credit' · 'debit'
  const [sortBy, setSortBy] = useState('date-desc')
  const fileRef = useRef<HTMLInputElement>(null)

  const txsQ = useBudgetTransactions()
  const categoriesQ = useBudgetCategories()
  const txs: any[] = Array.isArray(txsQ.data) ? txsQ.data : []
  const categories: any[] = Array.isArray(categoriesQ.data) ? categoriesQ.data : []
  const loading = txsQ.isLoading || categoriesQ.isLoading

  const bankOf = (t: any) => (t.compte ?? '').split('-')[0] || ''
  const typeOf = (t: any) => (t.compte ?? '').split('-')[1] || ''
  const allTags = Array.from(new Set(txs.flatMap((t: any) => t.tags ?? []))).sort()
  const banks = Array.from(new Set(txs.map(bankOf).filter(Boolean))).sort()
  const types = Array.from(new Set(txs.map(typeOf).filter(Boolean))).sort()
  const TYPE_LABEL: Record<string, string> = { credit: 'Crédit', debit: 'Débit' }
  const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

  const filtered = txs.filter((t: any) => {
    const tags = t.tags ?? []
    if (tagFilter === '__none__' && tags.length > 0) return false
    if (tagFilter && tagFilter !== '__none__' && !tags.includes(tagFilter)) return false
    if (catFilter === 'none' && t.category_id != null) return false
    if (catFilter && catFilter !== 'none' && String(t.category_id) !== catFilter) return false
    if (bankFilter && bankOf(t) !== bankFilter) return false
    if (typeFilter && typeOf(t) !== typeFilter) return false
    return true
  })
  const SORTERS: Record<string, (a: any, b: any) => number> = {
    'date-desc': (a, b) => (b.date ?? '').localeCompare(a.date ?? ''),
    'date-asc': (a, b) => (a.date ?? '').localeCompare(b.date ?? ''),
    'amount-desc': (a, b) => Math.abs(b.montant) - Math.abs(a.montant),
    'amount-asc': (a, b) => Math.abs(a.montant) - Math.abs(b.montant),
    'alpha': (a, b) => (a.marchand ?? '').localeCompare(b.marchand ?? ''),
  }
  const visible = [...filtered].sort(SORTERS[sortBy] ?? SORTERS['date-desc'])
  const anyFilter = !!(tagFilter || catFilter || bankFilter || typeFilter)
  const filteredDep = filtered.filter((t: any) => t.montant < 0).reduce((s: number, t: any) => s + -t.montant, 0)
  const tagsMutation = useSetTransactionTags()
  const importMutation = useImportCsv()
  const importing = importMutation.isPending

  const catName = (id: number | null) =>
    id == null ? 'Sans catégorie' : (categories.find((c: any) => c.id === id)?.nom ?? `#${id}`)

  // Tags multiples (#119)
  const addTag = (tx: any) => {
    const tag = window.prompt('Nouveau tag :')?.trim()
    if (!tag) return
    tagsMutation.mutate({ id: tx.id, tags: [...(tx.tags ?? []), tag] })
  }
  const removeTag = (tx: any, tag: string) => {
    tagsMutation.mutate({ id: tx.id, tags: (tx.tags ?? []).filter((t: string) => t !== tag) })
  }

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setMsg(null)
    importMutation.mutate({ file }, {
      onSuccess: (r) => {
        setMsg(
          r?.imported != null
            ? `${r.imported} importée(s), ${r.categorised ?? 0} auto-catégorisée(s)${r.errors ? `, ${r.errors} erreur(s)` : ''}.`
            : 'Import échoué.',
        )
      },
      onError: () => setMsg('Import échoué.'),
      onSettled: () => {
        if (fileRef.current) fileRef.current.value = ''
      },
    })
  }

  return (
    <div className="space-y-4 animate-fade-in-up">
      {/* Import CSV (#115) */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div>
          <h2 className="text-sm font-semibold">Importer un relevé</h2>
          <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
            CSV (Desjardins, RBC, générique) ou OFX/QFX — catégorisation auto via tes règles.
          </p>
          {msg && <p className="mt-1 text-xs text-[var(--success)]">{msg}</p>}
        </div>
        <input ref={fileRef} id="csv-import" type="file" accept=".csv,text/csv,.ofx,.qfx" onChange={onFile} className="hidden" />
        <div className="flex items-center gap-2">
          <a
            href={`/api/budget/export/annual?year=${new Date().getFullYear()}`}
            download
            className="inline-flex items-center gap-2 rounded-md border border-[var(--border)] px-3 py-1.5 text-sm font-medium hover:bg-[var(--accent)]"
            title="Exporter les transactions de l'année en CSV (déclaration / bilan)"
          >
            <Download size={14} aria-hidden="true" />
            Export {new Date().getFullYear()}
          </a>
          <label
            htmlFor="csv-import"
            className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90"
          >
            <Upload size={14} aria-hidden="true" />
            {importing ? 'Import…' : 'Importer un relevé'}
          </label>
        </div>
      </div>

      {/* Règles apprises de l'historique (#258) */}
      <LearnedRulesSection />

      {/* Liste des transactions */}
      <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] px-4 py-3">
          <h2 className="text-sm font-semibold">
            Transactions
            <span className="ml-2 text-xs font-normal text-[var(--muted-foreground)]">
              {visible.length}{anyFilter && <> · {formatCAD(filteredDep)} de dépenses</>}
            </span>
          </h2>
          <div className="flex flex-wrap items-center gap-1.5">
            {banks.length > 1 && (
              <select value={bankFilter} onChange={(e) => setBankFilter(e.target.value)} aria-label="Filtrer par banque"
                className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs">
                <option value="">Toutes banques</option>
                {banks.map((b) => <option key={b} value={b}>{cap(b)}</option>)}
              </select>
            )}
            {types.length > 1 && (
              <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} aria-label="Filtrer par carte"
                className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs">
                <option value="">Crédit + débit</option>
                {types.map((t) => <option key={t} value={t}>{TYPE_LABEL[t] ?? cap(t)}</option>)}
              </select>
            )}
            <select value={catFilter} onChange={(e) => setCatFilter(e.target.value)} aria-label="Filtrer par catégorie"
              className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs">
              <option value="">Toutes catégories</option>
              <option value="none">Sans catégorie</option>
              {categories.map((c: any) => <option key={c.id} value={String(c.id)}>{c.nom}</option>)}
            </select>
            <select value={tagFilter} onChange={(e) => setTagFilter(e.target.value)} aria-label="Filtrer par tag"
              className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs">
              <option value="">Tous les tags</option>
              <option value="__none__">Sans tag</option>
              {allTags.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} aria-label="Trier"
              className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs">
              <option value="date-desc">Date ↓ (récent)</option>
              <option value="date-asc">Date ↑ (ancien)</option>
              <option value="amount-desc">Montant ↓</option>
              <option value="amount-asc">Montant ↑</option>
              <option value="alpha">A → Z</option>
            </select>
            {anyFilter && (
              <button type="button" onClick={() => { setTagFilter(''); setCatFilter(''); setBankFilter(''); setTypeFilter('') }}
                className="text-xs text-[var(--muted-foreground)] underline hover:text-[var(--foreground)]">Réinitialiser</button>
            )}
          </div>
        </div>
        {loading ? (
          <div className="space-y-2 p-4">
            {[0, 1, 2, 3].map((i) => <div key={i} className="h-10 rounded skeleton-shimmer" />)}
          </div>
        ) : visible.length === 0 ? (
          <p className="p-6 text-center text-sm text-[var(--muted-foreground)]">
            {txs.length === 0
              ? 'Aucune transaction. Importe un relevé CSV ou OFX pour commencer.'
              : 'Aucune transaction pour ce filtre.'}
          </p>
        ) : (
          <div className="divide-y divide-[var(--border)]">
            {visible.map((tx: any) => {
              const revenu = tx.montant > 0
              return (
                <div key={tx.id} className="flex items-center gap-3 px-4 py-3 transition-colors duration-150 hover:bg-[var(--muted)]">
                  <div className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full ${
                    revenu
                      ? 'bg-[color-mix(in_srgb,var(--success)_15%,transparent)]'
                      : 'bg-[color-mix(in_srgb,var(--destructive)_10%,transparent)]'
                  }`}>
                    {revenu
                      ? <ArrowDownLeft size={14} className="text-[var(--success)]" aria-hidden="true" />
                      : <ArrowUpRight size={14} className="text-[var(--destructive)]" aria-hidden="true" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{tx.marchand || tx.description || '—'}</p>
                    <p className="text-xs text-[var(--muted-foreground)]">
                      {catName(tx.category_id)} · {tx.date}
                      {typeOf(tx) && <span className="ml-1.5 rounded bg-[var(--muted)] px-1 py-0.5 text-[10px]">{TYPE_LABEL[typeOf(tx)] ?? cap(typeOf(tx))}</span>}
                    </p>
                    <div className="mt-1 flex flex-wrap items-center gap-1">
                      {(tx.tags ?? []).map((tag: string) => (
                        <span key={tag} className="inline-flex items-center gap-1 rounded-[var(--radius-sm)] bg-[var(--muted)] px-1.5 py-0.5 text-[10px] text-[var(--muted-foreground)]">
                          {tag}
                          <button type="button" onClick={() => removeTag(tx, tag)} aria-label={`Retirer le tag ${tag}`}
                            className="hover:text-[var(--destructive)]">×</button>
                        </span>
                      ))}
                      <select
                        aria-label="Ajouter un tag"
                        value=""
                        onChange={(e) => {
                          const v = e.target.value
                          e.target.value = ''
                          if (!v) return
                          if (v === '__new__') { addTag(tx); return }
                          tagsMutation.mutate({ id: tx.id, tags: [...(tx.tags ?? []), v] })
                        }}
                        className="rounded-[var(--radius-sm)] border border-dashed border-[var(--border)] px-1.5 py-0.5 text-[10px] text-[var(--muted-foreground)] hover:bg-[var(--muted)]">
                        <option value="">+ tag</option>
                        {allTags.filter((t) => !(tx.tags ?? []).includes(t)).map((t) => (
                          <option key={t} value={t}>{t}</option>
                        ))}
                        <option value="__new__">Nouveau tag…</option>
                      </select>
                    </div>
                  </div>
                  <span className={`font-mono text-sm font-semibold ${revenu ? 'text-[var(--success)]' : 'text-[var(--foreground)]'}`}>
                    {revenu ? '+' : ''}{formatCAD(tx.montant)}
                  </span>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

/** Règles apprises de l'historique catégorisé à la main (#258, sans ML). */
function LearnedRulesSection() {
  const { data } = useRuleSuggestions()
  const learn = useLearnRules()
  const [done, setDone] = useState<string | null>(null)
  const suggestions = data?.suggestions ?? []
  if (suggestions.length === 0) return null

  const onLearn = () => {
    setDone(null)
    learn.mutate(undefined, {
      onSuccess: (r) =>
        setDone(`${r.created} règle(s) créée(s), ${r.recategorised} transaction(s) recatégorisée(s).`),
      onError: () => setDone('Apprentissage échoué.'),
    })
  }

  return (
    <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--card)] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-1.5 text-sm font-semibold">
            <Wand2 size={14} aria-hidden="true" /> Règles suggérées
          </h2>
          <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
            Apprises de tes catégorisations manuelles répétées — applicables aux futurs imports.
          </p>
          {done && <p className="mt-1 text-xs text-[var(--success)]">{done}</p>}
        </div>
        <button
          type="button"
          onClick={onLearn}
          disabled={learn.isPending}
          className="inline-flex items-center gap-2 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50"
        >
          <Wand2 size={14} aria-hidden="true" />
          {learn.isPending ? 'Apprentissage…' : `Créer ${suggestions.length} règle(s)`}
        </button>
      </div>
      <ul className="mt-3 flex flex-wrap gap-2">
        {suggestions.map((s) => (
          <li key={s.pattern} className="rounded-[var(--radius-sm)] bg-[var(--muted)] px-2 py-1 text-xs text-[var(--muted-foreground)]">
            <span className="font-mono font-medium text-[var(--foreground)]">{s.pattern}</span> → {s.category_nom}
            <span className="ml-1 opacity-70">({s.occurrences}×)</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
