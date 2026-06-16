'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Home, CircleHelp, ChevronRight } from 'lucide-react'
import { MODULE_GROUPS } from '@/lib/modules'
import { cn } from '@/lib/utils'
import { ThemeToggle } from '@/components/ThemeToggle'
import { DensityToggle } from '@/components/DensityToggle'
import { CommandTrigger } from '@/components/CommandTrigger'
import { NotificationsWidget } from '@/components/layout/NotificationsWidget'

export function Sidebar() {
  const pathname = usePathname()
  const activeSlug = pathname?.split('/').filter(Boolean)[0]
  const activeGroup =
    MODULE_GROUPS.find((g) => g.items.some((m) => m.slug === activeSlug))?.group ?? null

  // Accordéon : les modules d'un groupe ne s'affichent qu'une fois le groupe
  // déplié. Le groupe de la page courante est déplié automatiquement.
  const [open, setOpen] = useState<Set<string>>(() => new Set(activeGroup ? [activeGroup] : []))
  useEffect(() => {
    if (activeGroup) setOpen((prev) => (prev.has(activeGroup) ? prev : new Set(prev).add(activeGroup)))
  }, [activeGroup])

  const toggle = (g: string) =>
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(g)) next.delete(g)
      else next.add(g)
      return next
    })

  const isActive = (href: string) =>
    href === '/' ? pathname === '/' : pathname?.startsWith(href)

  return (
    <aside className="glass-panel hidden md:flex md:w-56 lg:w-60 shrink-0 flex-col border-r border-[var(--glass-border)] px-3 py-5">
      {/* Wordmark : serif seul, sans icône — la voix de l'almanach. */}
      <Link
        href="/"
        className="px-3 py-2 mb-3 rounded-[var(--radius)] transition-colors hover:bg-[var(--accent)]"
      >
        <span className="font-display text-[17px] text-[var(--foreground)]">
          Mission Control
        </span>
      </Link>

      {/* Recherche / palette de commandes (déclencheur visible de ⌘K) */}
      <div className="mb-3">
        <CommandTrigger />
      </div>

      {/* Accueil */}
      <NavLink href="/" label="Accueil" icon={Home} active={!!isActive('/')} />

      <div className="my-3 h-px bg-[var(--glass-border)]" aria-hidden="true" />

      {/* Navigation groupée repliable — dérivée de lib/modules.ts (source unique) */}
      <nav className="flex flex-col gap-1 flex-1 overflow-y-auto" aria-label="Modules">
        {MODULE_GROUPS.map((group) => {
          const expanded = open.has(group.group)
          const hasActive = group.items.some((m) => m.slug === activeSlug)
          return (
            <div key={group.group}>
              <button
                type="button"
                onClick={() => toggle(group.group)}
                aria-expanded={expanded}
                className="flex w-full items-center justify-between gap-2 rounded-[var(--radius)] px-3 py-1.5 font-display italic text-[13px] text-[var(--muted-foreground)] transition-colors hover:bg-[var(--accent)] hover:text-[var(--foreground)] select-none"
              >
                <span className="flex items-center gap-1.5">
                  {group.group}
                  {!expanded && hasActive && (
                    <span className="h-1.5 w-1.5 rounded-full bg-[var(--ring)]" aria-hidden="true" />
                  )}
                </span>
                <ChevronRight
                  className={cn('h-3.5 w-3.5 shrink-0 transition-transform duration-150', expanded && 'rotate-90')}
                  aria-hidden="true"
                />
              </button>
              {expanded && (
                <div className="mt-0.5 flex flex-col gap-0.5">
                  {group.items.map((m) => (
                    <NavLink
                      key={m.slug}
                      href={'/' + m.slug}
                      label={m.label}
                      icon={m.icon}
                      active={!!isActive('/' + m.slug)}
                    />
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </nav>

      {/* Pied : notifications + aide · densité + thème */}
      <div className="mt-3 flex items-center justify-between border-t border-[var(--glass-border)] pt-3 px-1">
        <div className="flex items-center gap-1">
          <NotificationsWidget />
          <button
            type="button"
            onClick={() => window.dispatchEvent(new CustomEvent('mc:shortcuts'))}
            aria-label="Raccourcis clavier"
            aria-keyshortcuts="?"
            title="Raccourcis clavier (?)"
            className="flex h-8 w-8 items-center justify-center rounded-md text-[var(--muted-foreground)] transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
          >
            <CircleHelp className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        <div className="flex items-center gap-1">
          <DensityToggle />
          <ThemeToggle />
        </div>
      </div>
    </aside>
  )
}

function NavLink({
  href,
  label,
  icon: Icon,
  active,
}: {
  href: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  active: boolean
}) {
  return (
    <Link
      href={href}
      aria-current={active ? 'page' : undefined}
      className={cn(
        'flex items-center gap-3 px-3 py-2 rounded-[var(--radius)] text-sm font-medium transition-colors duration-200',
        active
          ? 'nav-active'
          : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--accent)]',
      )}
    >
      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span className="truncate">{label}</span>
    </Link>
  )
}
