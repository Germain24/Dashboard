'use client'

/**
 * Enveloppe du contenu principal (desktop).
 *
 * - Accueil (le Deck) : plein écran, scroll interne, aucun padding.
 * - Pages module : on réserve un espace en bas pour que le Dock flottant ne
 *   masque jamais la dernière ligne de contenu.
 * - Pose `data-module` sur <body> : le lavis d'accent du module (globals.css)
 *   vit sur body::before, hors de portée d'un sélecteur depuis <main>.
 */

import { useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'

export function MainShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const onHome = pathname === '/'

  useEffect(() => {
    const segment = pathname.split('/')[1] ?? ''
    if (segment) document.body.dataset.module = segment
    else delete document.body.dataset.module
  }, [pathname])

  return (
    <main
      id="main-content"
      tabIndex={-1}
      className={cn('flex-1 min-w-0 focus:outline-none', !onHome && 'pb-24 md:pb-28')}
    >
      {children}
    </main>
  )
}
