'use client'

/**
 * Rail de points latéral : indique la section courante et permet d'y sauter.
 * L'indicateur actif s'allonge (anim CSS via .springy déjà en place).
 */

import { cn } from '@/lib/utils'

export function DeckRail({
  total,
  active,
  labels,
  onJump,
}: {
  total: number
  active: number
  labels: string[]
  onJump: (i: number) => void
}) {
  return (
    <nav
      className="fixed right-4 top-1/2 z-[var(--z-sidebar)] hidden -translate-y-1/2 flex-col gap-2.5 md:flex"
      aria-label="Navigation des sections"
    >
      {Array.from({ length: total }).map((_, i) => (
        <button
          key={i}
          type="button"
          onClick={() => onJump(i)}
          aria-current={i === active ? 'true' : undefined}
          aria-label={labels[i]}
          title={labels[i]}
          className={cn(
            'springy rounded-full',
            i === active
              ? 'h-6 w-2.5 bg-[var(--ring)]'
              : 'h-2.5 w-2.5 bg-[color-mix(in_srgb,var(--muted-foreground)_40%,transparent)] hover:bg-[var(--muted-foreground)]',
          )}
        />
      ))}
    </nav>
  )
}
