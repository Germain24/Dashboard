import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PageTransition } from '@/lib/motion/PageTransition'

const mockPathname = vi.fn<() => string>()
vi.mock('next/navigation', () => ({
  usePathname: () => mockPathname(),
}))

describe('PageTransition', () => {
  beforeEach(() => mockPathname.mockReset())

  it('rend les enfants', () => {
    mockPathname.mockReturnValue('/finance')
    render(<PageTransition><p>Contenu</p></PageTransition>)
    expect(screen.getByText('Contenu')).toBeInTheDocument()
  })

  it('expose le module courant (1er segment) comme clé de transition', () => {
    mockPathname.mockReturnValue('/finance/transactions')
    render(<PageTransition><p>A</p></PageTransition>)
    expect(screen.getByTestId('page-transition').dataset.segment).toBe('/finance')
  })

  it('garde la même clé pour une navigation intra-module', () => {
    mockPathname.mockReturnValue('/finance')
    const { rerender } = render(<PageTransition><p>A</p></PageTransition>)
    const first = screen.getByTestId('page-transition').dataset.segment
    mockPathname.mockReturnValue('/finance/transactions')
    rerender(<PageTransition><p>B</p></PageTransition>)
    expect(screen.getByTestId('page-transition').dataset.segment).toBe(first)
  })

  it('change de clé quand on change de module', () => {
    mockPathname.mockReturnValue('/finance')
    const { rerender } = render(<PageTransition><p>A</p></PageTransition>)
    mockPathname.mockReturnValue('/garderobe')
    rerender(<PageTransition><p>B</p></PageTransition>)
    expect(screen.getByTestId('page-transition').dataset.segment).toBe('/garderobe')
  })
})
