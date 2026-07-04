import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, cleanup, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Sidebar } from '@/components/layout/Sidebar'

const usePathname = vi.fn()
vi.mock('next/navigation', () => ({
  usePathname: () => usePathname(),
  useRouter: () => ({ prefetch: vi.fn() }),
}))

function renderSidebar() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <Sidebar />
    </QueryClientProvider>,
  )
}

afterEach(() => cleanup())

describe('Sidebar — indicateur actif animé (pastille layoutId)', () => {
  it('rend la pastille dans le lien actif uniquement', () => {
    usePathname.mockReturnValue('/finance')
    renderSidebar()
    const links = screen.getAllByRole('link')
    const active = links.filter((l) => l.getAttribute('aria-current') === 'page')
    expect(active).toHaveLength(1)
    expect(active[0].querySelector('[data-testid="nav-pill"]')).not.toBeNull()
    const inactive = links.filter((l) => l.getAttribute('aria-current') !== 'page')
    for (const link of inactive) {
      expect(link.querySelector('[data-testid="nav-pill"]')).toBeNull()
    }
  })

  it("suit la page courante : la pastille est sur l'Accueil quand pathname est /", () => {
    usePathname.mockReturnValue('/')
    renderSidebar()
    const accueil = screen.getByRole('link', { name: /accueil/i })
    expect(accueil.querySelector('[data-testid="nav-pill"]')).not.toBeNull()
  })
})
