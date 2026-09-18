const BASE = '/api/data'

export type ImportReport = {
  total_inserted: number
  skipped_tables: string[]
  tables: Record<string, { inserted: number; errors: { index: number; error: string }[] }>
}

export type ImportPreview = {
  version: number | null
  exported_at: string | null
  mode: 'replace' | 'merge'
  can_import: boolean
  total_incoming: number
  table_count: number
  tables: Record<string, { incoming: number; current: number }>
  skipped_tables: string[]
  errors: { table: string; index: number; error: string }[]
}

export const fetchTables = (): Promise<string[]> => fetch(`${BASE}/tables`).then((r) => r.json())

/** Télécharge le backup JSON complet (déclenche un download navigateur). */
export async function downloadExport(): Promise<void> {
  const r = await fetch(`${BASE}/export`)
  const blob = await r.blob()
  triggerDownload(blob, `mission-control-backup-${new Date().toISOString().slice(0, 10)}.json`)
}

export async function downloadTableCsv(table: string): Promise<void> {
  const r = await fetch(`${BASE}/export/${table}.csv`)
  const blob = await r.blob()
  triggerDownload(blob, `${table}.csv`)
}

export async function importBackup(data: unknown, mode: 'replace' | 'merge'): Promise<ImportReport> {
  const r = await fetch(`${BASE}/import`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data, mode }),
  })
  if (!r.ok) throw new Error(await responseError(r, 'Import échoué'))
  return r.json()
}

export async function previewBackup(data: unknown, mode: 'replace' | 'merge' = 'replace'): Promise<ImportPreview> {
  const r = await fetch(`${BASE}/import/preview`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data, mode }),
  })
  if (!r.ok) throw new Error(await responseError(r, 'Prévisualisation impossible'))
  return r.json()
}

export const seedDemo = (force = false) =>
  fetch(`${BASE}/seed-demo?force=${force}`, { method: 'POST' }).then(async (r) => {
    if (!r.ok) throw new Error((await r.json().catch(() => ({})))?.detail ?? `Erreur ${r.status}`)
    return r.json()
  })

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

async function responseError(response: Response, fallback: string): Promise<string> {
  const body = await response.json().catch(() => ({})) as { detail?: unknown }
  return typeof body.detail === 'string' ? body.detail : `${fallback} (${response.status})`
}
