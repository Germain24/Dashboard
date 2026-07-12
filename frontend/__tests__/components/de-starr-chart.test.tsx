import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { DeStarrChart } from '@/components/finance/DeStarrChart'
import type { OptProgress } from '@/components/finance/buffett-ui'

function progress(overrides: Partial<OptProgress>): OptProgress {
  return {
    active: true, phase: 'optimisation', seed_num: 1, iteration: 1,
    convergence: 0.1, progress_pct: 10, message: '', run_id: 1,
    stop_requested: false, best_score: null,
    ...overrides,
  }
}

describe('DeStarrChart', () => {
  beforeEach(() => {
    sessionStorage.clear()
    cleanup()
  })

  it("n'affiche rien tant qu'il n'y a pas 2 points", () => {
    const { rerender } = render(<DeStarrChart optProgress={progress({ best_score: 0.5 })} />)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    rerender(<DeStarrChart optProgress={progress({ best_score: 0.5 })} />)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('affiche le graphique après 2 valeurs distinctes du même run', () => {
    const { rerender } = render(<DeStarrChart optProgress={progress({ best_score: 0.5 })} />)
    rerender(<DeStarrChart optProgress={progress({ best_score: 0.8 })} />)
    expect(screen.getByRole('img')).toBeInTheDocument()
    expect(screen.getByText('min 0,5000')).toBeInTheDocument()
    expect(screen.getByText('max 0,8000')).toBeInTheDocument()
  })

  it('reprend l\'historique déjà accumulé après un remount (refresh de page simulé)', () => {
    const { rerender, unmount } = render(<DeStarrChart optProgress={progress({ best_score: 0.5 })} />)
    rerender(<DeStarrChart optProgress={progress({ best_score: 0.8 })} />)
    expect(screen.getByText('max 0,8000')).toBeInTheDocument()

    unmount()
    // Remount "à froid" du même composant, comme après un refresh de page --
    // l'historique doit être repris depuis sessionStorage (même run_id), pas
    // reparti à un seul point.
    render(<DeStarrChart optProgress={progress({ best_score: 0.8 })} />)
    expect(screen.getByText('max 0,8000')).toBeInTheDocument()
    expect(screen.getByText('min 0,5000')).toBeInTheDocument()
  })

  it("ne réutilise pas l'historique d'un run_id différent", () => {
    const { rerender, unmount } = render(<DeStarrChart optProgress={progress({ run_id: 1, best_score: 0.5 })} />)
    rerender(<DeStarrChart optProgress={progress({ run_id: 1, best_score: 0.8 })} />)
    unmount()

    const { rerender: rerender2 } = render(<DeStarrChart optProgress={progress({ run_id: 2, best_score: 0.1 })} />)
    rerender2(<DeStarrChart optProgress={progress({ run_id: 2, best_score: 0.2 })} />)
    expect(screen.getByText('min 0,1000')).toBeInTheDocument()
    expect(screen.getByText('max 0,2000')).toBeInTheDocument()
  })
})
