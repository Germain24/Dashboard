'use client'

/**
 * Le Dock — barre de verre flottante, persistante sur toutes les pages.
 * Remplace la sidebar : retour à l'accueil (le Deck), palette de commandes,
 * notifications, densité et thème. Posé en bas-centre, façon dock macOS.
 */

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Home, Search, CircleHelp } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ThemeToggle } from '@/components/ThemeToggle'
import { DensityToggle } from '@/components/DensityToggle'
import { NotificationsWidget } from '@/components/layout/NotificationsWidget'

export function Dock() {
  const pathname = usePathname()
  const onHome = pathname === '/'

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[var(--z-header)] hidden justify-center md:flex">
      <nav
        aria-label="Navigation principale"
        className="glass-panel pointer-events-auto flex items-center gap-1 rounded-[var(--radius-full)] border border-[var(--glass-border)] p-1.5 shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow-lg)]"
      >
        <Link
          href="/"
          aria-label="Accueil"
          aria-current={onHome ? 'page' : undefined}
          className={cn(
            'springy flex h-10 w-10 items-center justify-center rounded-[var(--radius-full)]',
            onHome
              ? 'bg-[color-mix(in_srgb,var(--ring)_12%,transparent)] text-[var(--nav-active-fg)]'
              : 'text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)]',
          )}
        >
          <Home className="h-5 w-5" aria-hidden="true" />
        </Link>

        <button
          type="button"
          onClick={() => window.dispatchEvent(new CustomEvent('mc:command-palette'))}
          aria-label="Rechercher et naviguer"
          aria-keyshortcuts="Meta+K Control+K"
          className="springy flex h-10 items-center gap-2 rounded-[var(--radius-full)] px-4 text-sm text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
        >
          <Search className="h-4 w-4" aria-hidden="true" />
          <span>Rechercher</span>
        </button>

        <span className="mx-0.5 h-6 w-px bg-[var(--glass-border)]" aria-hidden="true" />

        <NotificationsWidget />
        <button
          type="button"
          onClick={() => window.dispatchEvent(new CustomEvent('mc:shortcuts'))}
          aria-label="Raccourcis clavier"
          aria-keyshortcuts="?"
          title="Raccourcis clavier (?)"
          className="flex h-10 w-10 items-center justify-center rounded-[var(--radius-full)] text-[var(--muted-foreground)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--foreground)]"
        >
          <CircleHelp className="h-5 w-5" aria-hidden="true" />
        </button>
        <DensityToggle />
        <ThemeToggle />
      </nav>
    </div>
  )
}
