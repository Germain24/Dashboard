'use client'

import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { Download, Upload, Database, FileSpreadsheet, AlertTriangle } from 'lucide-react'
import {
  fetchTables, downloadExport, downloadTableCsv, importBackup, seedDemo,
  type ImportReport,
} from '@/lib/data'

export default function DonneesPage() {
  const [tables, setTables] = useState<string[]>([])
  const [table, setTable] = useState('')
  const [busy, setBusy] = useState(false)
  const [report, setReport] = useState<ImportReport | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetchTables().then((t) => { setTables(t); if (t[0]) setTable(t[0]) }).catch(() => setTables([]))
  }, [])

  const onExport = async () => {
    setBusy(true)
    try { await downloadExport(); toast.success('Backup exporté.') }
    catch { toast.error('Export impossible.') }
    finally { setBusy(false) }
  }

  const onImportFile = async (file: File, mode: 'replace' | 'merge') => {
    setBusy(true); setReport(null)
    try {
      const data = JSON.parse(await file.text())
      const rep = await importBackup(data, mode)
      setReport(rep)
      toast.success(`Import terminé : ${rep.total_inserted} enregistrements.`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Import impossible.')
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const onSeed = async () => {
    setBusy(true)
    try {
      const r = await seedDemo(false)
      toast.success(`Démo ajoutée : ${Object.values(r.seeded as Record<string, number>).reduce((a, b) => a + b, 0)} enregistrements.`)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Erreur'
      if (msg.includes('existent') || msg.includes('409')) {
        if (confirm('Des données existent déjà. Ajouter quand même les données de démo ?')) {
          try { await seedDemo(true); toast.success('Démo ajoutée.') } catch { toast.error('Échec.') }
        }
      } else { toast.error(msg) }
    } finally { setBusy(false) }
  }

  const errorCount = report
    ? Object.values(report.tables).reduce((a, t) => a + t.errors.length, 0)
    : 0

  return (
    <div className="space-y-0 animate-fade-in">
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <h1 className="text-xl font-semibold tracking-tight">Données</h1>
        <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Export, import, backup & données de démo</p>
      </div>

      <div className="max-w-2xl space-y-4 p-6">
        {/* Export complet */}
        <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold"><Download className="h-4 w-4" /> Backup complet (JSON)</h2>
          <p className="mb-3 text-xs text-[var(--muted-foreground)]">Télécharge toutes tes données dans un fichier JSON.</p>
          <button onClick={() => void onExport()} disabled={busy}
            className="rounded-md bg-[var(--primary)] px-3 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50">
            Exporter le backup
          </button>
        </section>

        {/* Import */}
        <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold"><Upload className="h-4 w-4" /> Restaurer un backup</h2>
          <p className="mb-2 flex items-start gap-1.5 text-xs text-[var(--muted-foreground)]">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--warning,#d97706)]" />
            « Remplacer » vide chaque table présente dans le fichier avant import.
          </p>
          <input ref={fileRef} type="file" accept="application/json"
            aria-label="Fichier de backup JSON"
            className="block w-full text-xs file:mr-3 file:rounded-md file:border-0 file:bg-[var(--muted)] file:px-3 file:py-1.5 file:text-sm" />
          <div className="mt-3 flex gap-2">
            <button onClick={() => { const f = fileRef.current?.files?.[0]; if (f) void onImportFile(f, 'replace'); else toast.error('Choisis un fichier.') }}
              disabled={busy}
              className="rounded-md bg-[var(--destructive)] px-3 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50">
              Remplacer
            </button>
            <button onClick={() => { const f = fileRef.current?.files?.[0]; if (f) void onImportFile(f, 'merge'); else toast.error('Choisis un fichier.') }}
              disabled={busy}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-sm font-medium hover:bg-[var(--muted)] disabled:opacity-50">
              Fusionner
            </button>
          </div>
          {report && (
            <div className="mt-3 rounded-lg border border-[var(--border)] p-3 text-xs">
              <p className="font-medium">{report.total_inserted} enregistrements importés{errorCount > 0 ? `, ${errorCount} erreur(s)` : ''}.</p>
              {report.skipped_tables.length > 0 && (
                <p className="mt-1 text-[var(--muted-foreground)]">Tables ignorées : {report.skipped_tables.join(', ')}</p>
              )}
              {errorCount > 0 && (
                <ul className="mt-1 space-y-0.5 text-[var(--destructive)]">
                  {Object.entries(report.tables).flatMap(([t, info]) =>
                    info.errors.slice(0, 3).map((er, i) => <li key={`${t}-${i}`}>{t}[{er.index}] : {er.error}</li>),
                  )}
                </ul>
              )}
            </div>
          )}
        </section>

        {/* Export CSV par table */}
        <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold"><FileSpreadsheet className="h-4 w-4" /> Export CSV par table</h2>
          <div className="mt-2 flex gap-2">
            <select value={table} onChange={(e) => setTable(e.target.value)} aria-label="Table"
              className="flex-1 rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]">
              {tables.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <button onClick={() => table && void downloadTableCsv(table)} disabled={busy || !table}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-sm font-medium hover:bg-[var(--muted)] disabled:opacity-50">
              Télécharger CSV
            </button>
          </div>
        </section>

        {/* Démo */}
        <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <h2 className="mb-1 flex items-center gap-2 text-sm font-semibold"><Database className="h-4 w-4" /> Données de démo</h2>
          <p className="mb-3 text-xs text-[var(--muted-foreground)]">Remplit l'UI avec un petit jeu de données réaliste (budget, habitudes, livres, agenda).</p>
          <button onClick={() => void onSeed()} disabled={busy}
            className="rounded-md border border-[var(--border)] px-3 py-2 text-sm font-medium hover:bg-[var(--muted)] disabled:opacity-50">
            Ajouter des données de démo
          </button>
        </section>
      </div>
    </div>
  )
}
