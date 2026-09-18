const BASE = '/api/admin'

export type DocType =
  | 'cni' | 'passeport' | 'contrat' | 'garantie'
  | 'assurance' | 'fiscal' | 'medical' | 'autre'

export type ExpiryStatus = 'ok' | 'warning' | 'expired' | 'no_date'

export type Document = {
  id: number
  titre: string
  type: DocType
  notes: string
  date_expiration: string | null
  date_emission: string | null
  organisme: string
  fichier_url: string | null
  tags: string  // JSON
  statut_expiration: ExpiryStatus
  created_at: string
  updated_at: string
}

export const TYPE_LABELS: Record<DocType, string> = {
  cni: 'CNI',
  passeport: 'Passeport',
  contrat: 'Contrat',
  garantie: 'Garantie',
  assurance: 'Assurance',
  fiscal: 'Fiscal',
  medical: 'Médical',
  autre: 'Autre',
}

export const ALL_TYPES: DocType[] = ['cni', 'passeport', 'contrat', 'garantie', 'assurance', 'fiscal', 'medical', 'autre']

const json = (r: Response) => r.json()
const jsonHeaders = { 'Content-Type': 'application/json' }

export const fetchDocuments = (opts?: { type?: DocType; q?: string }): Promise<Document[]> => {
  const p = new URLSearchParams()
  if (opts?.type) p.set('type', opts.type)
  if (opts?.q) p.set('q', opts.q)
  const qs = p.toString()
  return fetch(`${BASE}/documents${qs ? '?' + qs : ''}`).then(json)
}

export const fetchEcheances = (days = 90): Promise<Document[]> =>
  fetch(`${BASE}/documents/echeances?days=${days}`).then(json)

export const createDocument = (data: Partial<Document> & { titre: string }): Promise<Document> =>
  fetch(`${BASE}/documents`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(data),
  }).then(json)

export const updateDocument = (id: number, patch: Partial<Document>): Promise<Document> =>
  fetch(`${BASE}/documents/${id}`, {
    method: 'PATCH',
    headers: jsonHeaders,
    body: JSON.stringify(patch),
  }).then(json)

export const deleteDocument = (id: number): Promise<void> =>
  fetch(`${BASE}/documents/${id}`, { method: 'DELETE' }).then(() => undefined)
