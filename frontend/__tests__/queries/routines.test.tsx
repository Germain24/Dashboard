import { describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

vi.mock('@/lib/routines', () => ({
  fetchRoutines: vi.fn().mockResolvedValue([
    { id: 1, name: 'Briefing test', description: '', trigger_type: 'cron', trigger_value: '0 7 * * *', actions: [], enabled: true, last_run_at: null, created_at: '' },
  ]),
  createRoutine: vi.fn().mockResolvedValue({ id: 2, name: 'Nouvelle', description: '', trigger_type: 'event', trigger_value: '', actions: [], enabled: true, last_run_at: null, created_at: '' }),
  updateRoutine: vi.fn().mockResolvedValue({ id: 1, enabled: false }),
  deleteRoutine: vi.fn().mockResolvedValue(undefined),
  runRoutine: vi.fn().mockResolvedValue({ result: 'ok' }),
}))

import { routinesKeys, useAddRoutine, useRoutines, useRunRoutine } from '@/lib/queries/routines'

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

describe('routinesKeys', () => {
  it('generates stable list key', () => {
    expect(routinesKeys.list()).toEqual(routinesKeys.list())
  })
  it('all key is parent of list', () => {
    expect(routinesKeys.list()[0]).toBe(routinesKeys.all[0])
  })
})

describe('useRoutines', () => {
  it('returns routines list', async () => {
    const { result } = renderHook(() => useRoutines(), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toHaveLength(1)
    expect(result.current.data![0].name).toBe('Briefing test')
  })
})

describe('useAddRoutine', () => {
  it('resolves with new routine', async () => {
    const { result } = renderHook(() => useAddRoutine(), { wrapper: createWrapper() })
    result.current.mutate({ name: 'Nouvelle' })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.name).toBe('Nouvelle')
  })
})

describe('useRunRoutine', () => {
  it('returns result string', async () => {
    const { result } = renderHook(() => useRunRoutine(), { wrapper: createWrapper() })
    result.current.mutate(1)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.result).toBe('ok')
  })
})
