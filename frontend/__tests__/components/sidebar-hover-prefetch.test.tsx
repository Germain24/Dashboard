import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, cleanup, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Sidebar } from '@/components/layout/Sidebar'

const usePathname = vi.fn()
const prefetch = vi.fn()
vi.mock('next/navigation', () => ({
  usePathname: () => usePathname(),
  useRouter: () => ({ prefetch }),
}))

function renderSidebar() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <Sidebar />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  prefetch.mockClear()
})

describe('Sidebar — prefetch au survol', () => {
  it("précharge la route au survol d'un lien de module", () => {
    // pathname sur /finance : le groupe "Finances & Ingénierie" est déplié
    // automatiquement, le lien "Investissement" est donc visible.
    usePathname.mockReturnValue('/finance')
    renderSidebar()
    const finance = screen.getByRole('link', { name: /investissement/i })
    fireEvent.mouseEnter(finance)
    expect(prefetch).toHaveBeenCalledWith('/finance')
  })

  it("précharge l'accueil au survol du lien Accueil", () => {
    usePathname.mockReturnValue('/finance')
    renderSidebar()
    const accueil = screen.getByRole('link', { name: /accueil/i })
    fireEvent.mouseEnter(accueil)
    expect(prefetch).toHaveBeenCalledWith('/')
  })
})
