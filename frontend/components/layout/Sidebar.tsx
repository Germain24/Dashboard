'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Home, LayoutDashboard, CircleHelp } from 'lucide-react'
import { MODULE_GROUPS } from '@/lib/modules'
import { cn } from '@/lib/utils'
import { ThemeToggle } from '@/components/ThemeToggle'
import { DensityToggle } from '@/components/DensityToggle'
import { CommandTrigger } from '@/components/CommandTrigger'
import { NotificationsWidget } from '@/components/layout/NotificationsWidget'

export function Sidebar() {
  const pathname = usePathname()

  const isActive = (href: string) =>
    href === '/' ? pathname === '/' : pathname?.startsWith(href)

  return (
    <aside className="hidden md:flex md:w-56 lg:w-60 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--sidebar)] px-3 py-5">
      {/* Logo / Titre */}
      <Link
        href="/"
        className="flex items-center gap-2.5 px-3 py-2 mb-3 rounded-md transition-colors hover:bg-[var(--muted)]"
      >
        <LayoutDashboard className="h-5 w-5 shrink-0 text-[var(--foreground)]" aria-hidden="true" />
        <span className="font-display text-base font-semibold tracking-tight text-[var(--foreground)]">
          Mission Control
        </span>
      </Link>

      {/* Recherche / palette de commandes (déclencheur visible de ⌘K) */}
      <div className="mb-3">
        <CommandTrigger />
      </div>

      {/* Accueil */}
      <NavLink href="/" label="Accueil" icon={Home} active={!!isActive('/')} />

      <div className="my-3 h-px bg-[var(--border)]" aria-hidden="true" />

      {/* Navigation groupée — dérivée de lib/modules.ts (source unique) */}
      <nav className="flex flex-col gap-4 flex-1 overflow-y-auto" aria-label="Modules">
        {MODULE_GROUPS.map((group) => (
          <div key={group.group}>
            <p className="px-3 mb-1 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)] select-none">
              {group.group}
            </p>
            <div className="flex flex-col gap-0.5">
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
          </div>
        ))}
      </nav>

      {/* Pied : notifications + aide · densité + thème */}
      <div className="mt-3 flex items-center justify-between border-t border-[var(--border)] pt-3 px-1">
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
        'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
        active
          ? 'nav-active'
          : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]',
      )}
    >
      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span className="truncate">{label}</span>
    </Link>
  )
}
