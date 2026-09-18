import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Dialog, DialogBody } from '@/components/ui/dialog'

describe('Dialog', () => {
  it('rend le contenu quand ouvert, rien quand fermé', () => {
    const { rerender } = render(
      <Dialog open onClose={() => {}}><DialogBody>Bonjour</DialogBody></Dialog>,
    )
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    rerender(<Dialog open={false} onClose={() => {}}><DialogBody>Bonjour</DialogBody></Dialog>)
    return waitFor(
      () => expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
      { timeout: 3000 },
    )
  })

  it('appelle onClose au clic sur le voile', () => {
    const onClose = vi.fn()
    render(<Dialog open onClose={onClose}><DialogBody>Corps</DialogBody></Dialog>)
    fireEvent.click(screen.getByTestId('dialog-backdrop'))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('appelle onClose sur Échap', () => {
    const onClose = vi.fn()
    render(<Dialog open onClose={onClose}><DialogBody>Corps</DialogBody></Dialog>)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledOnce()
  })
})
