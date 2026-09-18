'use client'

import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { Download, Upload, Database, FileSpreadsheet, AlertTriangle, ShieldCheck } from 'lucide-react'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ModuleHeader } from '@/components/layout'
import { downloadExport, downloadTableCsv, type ImportPreview, type ImportReport } from '@/lib/data'
import { useImportBackup, usePreviewBackup, useSeedDemo, useTables } from '@/lib/queries/donnees'

type SelectedBackup = { data: unknown; fileName: string; preview: ImportPreview }
const EMPTY_TABLES: string[] = []

export default function DonneesPage() {
  const [table, setTable] = useState('')
  const [exporting, setExporting] = useState(false)
  const [report, setReport] = useState<ImportReport | null>(null)
  const [selectedBackup, setSelectedBackup] = useState<SelectedBackup | null>(null)
  const [confirmMode, setConfirmMode] = useState<'replace' | 'merge' | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const tablesQ = useTables()
  const tables = tablesQ.isError ? EMPTY_TABLES : tablesQ.data ?? EMPTY_TABLES
  const selectedTable = table && tables.includes(table) ? table : tables[0] ?? ''
  const importMutation = useImportBackup()
  const previewMutation = usePreviewBackup()
  const seedMutation = useSeedDemo()
  const busy = exporting || previewMutation.isPending || importMutation.isPending || seedMutation.isPending

  const onExport = async () => {
    setExporting(true)
    try { await downloadExport(); toast.success('Backup exporté.') }
    catch { toast.error('Export impossible.') }
    finally { setExporting(false) }
  }

  const onPreviewFile = async () => {
    const file = fileRef.current?.files?.[0]
    if (!file) { toast.error('Choisis un fichier de backup.'); return }
    setReport(null)
    let data: unknown
    try {
      data = JSON.parse(await file.text())
    } catch {
      setSelectedBackup(null)
      setConfirmMode(null)
      toast.error('Fichier JSON invalide.')
      return
    }
    setConfirmMode(null)
    try {
      const result = await previewMutation.mutateAsync({ data, mode: 'replace' })
      setSelectedBackup({ data, fileName: file.name, preview: result })
      if (result.can_import) toast.success('Backup vérifié. Relis le détail avant de confirmer.')
    } catch (e) {
      setSelectedBackup(null)
      toast.error(e instanceof Error ? e.message : 'Prévisualisation impossible.')
    }
  }

  const onConfirmImport = async () => {
    if (!selectedBackup || !confirmMode) return
    try {
      const rep = await importMutation.mutateAsync({ data: selectedBackup.data, mode: confirmMode })
      setReport(rep)
      setSelectedBackup(null)
      setConfirmMode(null)
      if (fileRef.current) fileRef.current.value = ''
      toast.success(`Import terminé : ${rep.total_inserted} enregistrements.`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Import impossible. Aucune modification partielle n’a été conservée.')
    }
  }

  const onSeed = () => {
    seedMutation.mutate(false, {
      onSuccess: (r) =>
        toast.success(`Démo ajoutée : ${Object.values(r.seeded as Record<string, number>).reduce((a, b) => a + b, 0)} enregistrements.`),
      onError: (e) => {
        const msg = e instanceof Error ? e.message : 'Erreur'
        if (msg.includes('existent') || msg.includes('409')) {
          if (confirm('Des données existent déjà. Ajouter quand même les données de démo ?')) {
            seedMutation.mutate(true, {
              onSuccess: () => toast.success('Démo ajoutée.'),
              onError: () => toast.error('Échec.'),
            })
          }
        } else { toast.error(msg) }
      },
    })
  }

  const errorCount = report
    ? Object.values(report.tables).reduce((a, t) => a + t.errors.length, 0)
    : 0

  return (
    <div className="space-y-0">
      <ModuleHeader title="Données" subtitle="Export, import, backup & données de démo" />

      <ErrorBoundary label="Données">
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
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--warning)]" />
            L’aperçu vérifie les lignes et indique quelles tables seront touchées. La restauration est annulée en entier si la base refuse une ligne.
          </p>
          <input ref={fileRef} type="file" accept="application/json"
            aria-label="Fichier de backup JSON"
            onChange={() => { setSelectedBackup(null); setConfirmMode(null); setReport(null) }}
            className="block w-full text-xs file:mr-3 file:rounded-md file:border-0 file:bg-[var(--muted)] file:px-3 file:py-1.5 file:text-sm" />
          <div className="mt-3">
            <button onClick={() => void onPreviewFile()} disabled={busy}
              className="rounded-md border border-[var(--border)] px-3 py-2 text-sm font-medium hover:bg-[var(--muted)] disabled:opacity-50">
              {previewMutation.isPending ? 'Vérification du backup…' : 'Prévisualiser le backup'}
            </button>
          </div>
          {selectedBackup && (
            <div className="mt-4 space-y-3 rounded-lg border border-[var(--border)] p-3" aria-live="polite">
              <div>
                <h3 className="text-sm font-semibold">Aperçu : {selectedBackup.fileName}</h3>
                <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                  {selectedBackup.preview.total_incoming} enregistrements dans {selectedBackup.preview.table_count} tables
                  {selectedBackup.preview.exported_at ? ` · exporté le ${selectedBackup.preview.exported_at}` : ''}
                </p>
              </div>
              {Object.entries(selectedBackup.preview.tables).length > 0 && (
                <ul className="divide-y divide-[var(--border)] rounded-md border border-[var(--border)] text-xs">
                  {Object.entries(selectedBackup.preview.tables).map(([name, counts]) => (
                    <li key={name} className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-3 py-2">
                      <span className="font-medium">{name}</span>
                      <span className="text-[var(--muted-foreground)]">
                        {counts.current} actuels · {counts.incoming} dans le backup
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {selectedBackup.preview.table_count === 0 && (
                <p className="text-xs text-[var(--muted-foreground)]" role="status">
                  Aucune table reconnue dans ce fichier : rien ne peut être restauré.
                </p>
              )}
              {selectedBackup.preview.skipped_tables.length > 0 && (
                <p className="text-xs text-[var(--muted-foreground)]">
                  Tables inconnues ignorées : {selectedBackup.preview.skipped_tables.join(', ')}
                </p>
              )}
              {!selectedBackup.preview.can_import && (
                <div className="rounded-md border border-[var(--destructive)]/40 bg-[var(--destructive)]/5 p-3 text-xs" role="alert">
                  <p className="font-semibold">Ce backup ne peut pas être restauré en l’état.</p>
                  <ul className="mt-1 space-y-1 text-[var(--destructive)]">
                    {selectedBackup.preview.errors.map((error, i) => (
                      <li key={`${error.table}-${error.index}-${i}`}>
                        {error.table ? `${error.table}${error.index >= 0 ? `[${error.index}]` : ''} : ` : ''}{error.error}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {selectedBackup.preview.can_import && selectedBackup.preview.table_count > 0 && !confirmMode && (
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => setConfirmMode('replace')} disabled={busy}
                    className="rounded-md bg-[var(--destructive)] px-3 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50">
                    Remplacer {selectedBackup.preview.table_count} tables…
                  </button>
                  <button onClick={() => setConfirmMode('merge')} disabled={busy}
                    className="rounded-md border border-[var(--border)] px-3 py-2 text-sm font-medium hover:bg-[var(--muted)] disabled:opacity-50">
                    Fusionner les données…
                  </button>
                </div>
              )}
              {confirmMode && selectedBackup.preview.can_import && (
                <div className={`rounded-md border p-3 ${confirmMode === 'replace' ? 'border-[var(--destructive)]/50 bg-[var(--destructive)]/5' : 'border-[var(--border)] bg-[var(--muted)]/40'}`} role="group" aria-labelledby="restore-confirm-title" aria-describedby="restore-confirm-description">
                  <h3 id="restore-confirm-title" className="text-sm font-semibold">
                    {confirmMode === 'replace' ? 'Confirmer le remplacement ?' : 'Confirmer la fusion ?'}
                  </h3>
                  <p id="restore-confirm-description" className="mt-1 text-xs text-[var(--muted-foreground)]">
                    {confirmMode === 'replace'
                      ? `Les données actuelles des ${selectedBackup.preview.table_count} tables listées seront remplacées par celles du fichier.`
                      : `Les ${selectedBackup.preview.total_incoming} enregistrements seront ajoutés. Un conflit en base annulera toute la fusion.`}
                    {' '}Aucune restauration partielle ne sera conservée en cas d’erreur.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button onClick={() => void onConfirmImport()} disabled={busy}
                      className={`rounded-md px-3 py-2 text-sm font-medium text-white disabled:opacity-50 ${confirmMode === 'replace' ? 'bg-[var(--destructive)] hover:opacity-90' : 'bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90'}`}>
                      {importMutation.isPending ? 'Restauration…' : confirmMode === 'replace' ? 'Confirmer et remplacer' : 'Confirmer la fusion'}
                    </button>
                    <button onClick={() => setConfirmMode(null)} disabled={busy}
                      className="rounded-md border border-[var(--border)] px-3 py-2 text-sm font-medium hover:bg-[var(--muted)] disabled:opacity-50">
                      Annuler
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
          {report && (
            <div className="mt-3 rounded-lg border border-[var(--border)] p-3 text-xs">
              <p className="flex items-center gap-1.5 font-medium"><ShieldCheck className="h-4 w-4 text-[var(--success)]" /> {report.total_inserted} enregistrements importés{errorCount > 0 ? `, ${errorCount} erreur(s)` : ''}.</p>
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
            <select value={selectedTable} onChange={(e) => setTable(e.target.value)} aria-label="Table"
              className="flex-1 rounded-md border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring)]">
              {tables.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <button onClick={() => selectedTable && void downloadTableCsv(selectedTable)} disabled={busy || !selectedTable}
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
      </ErrorBoundary>
    </div>
  )
}
