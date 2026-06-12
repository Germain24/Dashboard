import { describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

vi.mock('@/lib/documents', () => ({
  fetchDocuments: vi.fn().mockResolvedValue([
    { id: 1, titre: 'CNI', type: 'cni', statut_expiration: 'ok', notes: '', organisme: '', tags: '[]', date_expiration: null, date_emission: null, fichier_url: null, created_at: '', updated_at: '' },
  ]),
  fetchEcheances: vi.fn().mockResolvedValue([
    { id: 2, titre: 'Passeport', type: 'passeport', statut_expiration: 'warning', notes: '', organisme: '', tags: '[]', date_expiration: '2026-09-01', date_emission: null, fichier_url: null, created_at: '', updated_at: '' },
  ]),
  createDocument: vi.fn().mockResolvedValue({ id: 3, titre: 'Contrat', type: 'contrat', statut_expiration: 'no_date', notes: '', organisme: '', tags: '[]', date_expiration: null, date_emission: null, fichier_url: null, created_at: '', updated_at: '' }),
  updateDocument: vi.fn().mockResolvedValue({}),
  deleteDocument: vi.fn().mockResolvedValue(undefined),
}))

import { documentsKeys, useAddDocument, useDocuments, useEcheances } from '@/lib/queries/documents'

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

describe('documentsKeys', () => {
  it('generates stable list key', () => {
    const k1 = documentsKeys.list({ type: 'cni' })
    const k2 = documentsKeys.list({ type: 'cni' })
    expect(k1).toEqual(k2)
  })

  it('distinguishes list from echeances', () => {
    expect(documentsKeys.list()[1]).toBe('list')
    expect(documentsKeys.echeances(30)[1]).toBe('echeances')
  })
})

describe('useDocuments', () => {
  it('returns document list', async () => {
    const { result } = renderHook(() => useDocuments(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toHaveLength(1)
    expect(result.current.data![0].titre).toBe('CNI')
  })
})

describe('useEcheances', () => {
  it('returns upcoming expirations', async () => {
    const { result } = renderHook(() => useEcheances(90), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data![0].statut_expiration).toBe('warning')
  })
})

describe('useAddDocument', () => {
  it('mutation resolves successfully', async () => {
    const { result } = renderHook(() => useAddDocument(), { wrapper: createWrapper() })
    result.current.mutate({ titre: 'Contrat', type: 'contrat' } as any)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.titre).toBe('Contrat')
  })
})
