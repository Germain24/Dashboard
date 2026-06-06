'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowDownLeft, ArrowUpRight, Upload } from 'lucide-react'
import { fetchTransactions, fetchCategories, importCsv } from '@/lib/budget'

const formatCAD = (v: number) =>
  new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD' }).format(v ?? 0)

export default function TransactionsTab() {
  const [txs, setTxs] = useState<any[]>([])
  const [categories, setCategories] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [importing, setImporting] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = useCallback(() => {
    void Promise.all([
      fetchTransactions().then((d) => (Array.isArray(d) ? d : [])),
      fetchCategories().then((d) => (Array.isArray(d) ? d : [])),
    ]).then(([t, c]) => { setTxs(t); setCategories(c); setLoading(false) })
  }, [])
  useEffect(() => load(), [load])

  const catName = (id: number | null) =>
    id == null ? 'Sans catégorie' : (categories.find((c: any) => c.id === id)?.nom ?? `#${id}`)

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImporting(true)
    setMsg(null)
    importCsv(file)
      .then((r) => {
        setMsg(
          r?.imported != null
            ? `${r.imported} importée(s), ${r.categorised ?? 0} auto-catégorisée(s)${r.errors ? `, ${r.errors} erreur(s)` : ''}.`
            : 'Import échoué.',
        )
        load()
      })
      .catch(() => setMsg('Import échoué.'))
      .finally(() => {
        setImporting(false)
        if (fileRef.current) fileRef.current.value = ''
      })
  }

  return (
    <div className="space-y-4 animate-fade-in-up">
      {/* Import CSV (#115) */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div>
          <h2 className="text-sm font-semibold">Importer un relevé</h2>
          <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">
            CSV Desjardins, RBC ou générique — catégorisation auto via tes règles.
          </p>
          {msg && <p className="mt-1 text-xs text-[var(--success)]">{msg}</p>}
        </div>
        <input ref={fileRef} id="csv-import" type="file" accept=".csv,text/csv" onChange={onFile} className="hidden" />
        <label
          htmlFor="csv-import"
          className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-[var(--primary)] px-3 py-1.5 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90"
        >
          <Upload size={14} aria-hidden="true" />
          {importing ? 'Import…' : 'Importer CSV'}
        </label>
      </div>

      {/* Liste des transactions */}
      <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <div className="border-b border-[var(--border)] px-4 py-3">
          <h2 className="text-sm font-semibold">Transactions</h2>
        </div>
        {loading ? (
          <div className="space-y-2 p-4">
            {[0, 1, 2, 3].map((i) => <div key={i} className="h-10 rounded skeleton-shimmer" />)}
          </div>
        ) : txs.length === 0 ? (
          <p className="p-6 text-center text-sm text-[var(--muted-foreground)]">
            Aucune transaction. Importe un relevé CSV pour commencer.
          </p>
        ) : (
          <div className="divide-y divide-[var(--border)]">
            {txs.map((tx: any) => {
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
                    <p className="text-xs text-[var(--muted-foreground)]">{catName(tx.category_id)} · {tx.date}</p>
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
