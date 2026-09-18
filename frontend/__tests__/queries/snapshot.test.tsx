import { describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

vi.mock('@/lib/snapshot', () => ({
  fetchSnapshots: vi.fn().mockResolvedValue([
    { date: '2026-06-11', data: { date: '2026-06-11', habitudes: { done: 5, total: 6, pct: 83 } } },
  ]),
  fetchWellbeing: vi.fn().mockResolvedValue({
    score: 78, label: 'Bonne journée', date: '2026-06-11',
    components: { habitudes: 25, humeur: 20, nutrition: 20, entrainement: 13 },
  }),
  fetchTemplates: vi.fn().mockResolvedValue([
    { id: 'semaine_type', name: 'Semaine type', description: 'test', trigger_type: 'cron', trigger_value: '', actions: [] },
  ]),
  fetchVacationMode: vi.fn().mockResolvedValue({ mode_vacances: false }),
  fetchSnapshot: vi.fn().mockResolvedValue({ date: '2026-06-11', data: {}, cached: true }),
  activateTemplate: vi.fn().mockResolvedValue({ id: 1, name: 'Semaine type' }),
  setVacationMode: vi.fn().mockResolvedValue({ mode_vacances: true }),
}))

import { snapshotKeys, useSnapshots, useTemplates, useWellbeing } from '@/lib/queries/snapshot'

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

describe('snapshotKeys', () => {
  it('list and wellbeing are distinct', () => {
    expect(snapshotKeys.list(30)).not.toEqual(snapshotKeys.wellbeing())
  })
})

describe('useSnapshots', () => {
  it('returns snapshot list', async () => {
    const { result } = renderHook(() => useSnapshots(30), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toHaveLength(1)
    expect(result.current.data![0].date).toBe('2026-06-11')
  })
})

describe('useWellbeing', () => {
  it('returns score and label', async () => {
    const { result } = renderHook(() => useWellbeing(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.score).toBe(78)
    expect(result.current.data?.label).toBe('Bonne journée')
  })
})

describe('useTemplates', () => {
  it('returns templates', async () => {
    const { result } = renderHook(() => useTemplates(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data![0].id).toBe('semaine_type')
  })
})
