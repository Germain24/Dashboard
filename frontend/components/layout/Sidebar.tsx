'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  Target,
  BookOpen,
  Shirt,
  ChefHat,
  Heart,
  Dumbbell,
  Calendar,
  GraduationCap,
  TrendingUp,
  CreditCard,
  Settings,
  Sparkles,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { ThemeToggle } from '@/components/ThemeToggle'
import { DensityToggle } from '@/components/DensityToggle'

const NAV_GROUPS = [
  {
    label: 'Vie quotidienne',
    items: [
      { href: '/habitudes', icon: Target, label: 'Habitudes' },
      { href: '/livres', icon: BookOpen, label: 'Livres' },
      { href: '/garderobe', icon: Shirt, label: 'Garde-robe' },
      { href: '/cuisine', icon: ChefHat, label: 'Cuisine' },
      { href: '/skincare', icon: Sparkles, label: 'Skincare' },
    ],
  },
  {
    label: 'Santé & Sport',
    items: [
      { href: '/sante', icon: Heart, label: 'Santé' },
      { href: '/entrainement', icon: Dumbbell, label: 'Entraînement' },
    ],
  },
  {
    label: 'Organisation',
    items: [
      { href: '/agenda', icon: Calendar, label: 'Agenda' },
      { href: '/etudes', icon: GraduationCap, label: 'Études' },
    ],
  },
  {
    label: 'Finances',
    items: [
      { href: '/finance', icon: TrendingUp, label: 'Finance' },
      { href: '/budget', icon: CreditCard, label: 'Budget' },
    ],
  },
  {
    label: 'Système',
    items: [
      { href: '/jobs', icon: Settings, label: 'Jobs' },
    ],
  },
]

export function Sidebar() {
  const pathname = usePathname()

  const isActive = (href: string) =>
    href === '/'
      ? pathname === '/'
      : pathname?.startsWith(href)

  return (
    <aside className="hidden md:flex w-60 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--sidebar)] px-3 py-5">
      {/* Logo / Titre */}
      <Link
        href="/"
        className="flex items-center gap-2.5 px-3 py-2 mb-4 rounded-md transition-colors hover:bg-[var(--muted)] cursor-pointer"
      >
        <LayoutDashboard className="h-5 w-5 text-[var(--foreground)]" />
        <span className="text-sm font-semibold tracking-tight text-[var(--foreground)]">
          Mission Control
        </span>
      </Link>

      {/* Navigation groupée */}
      <nav className="flex flex-col gap-4 flex-1 overflow-y-auto">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            <p className="px-3 mb-1 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)] select-none">
              {group.label}
            </p>
            <div className="flex flex-col gap-0.5">
              {group.items.map(({ href, icon: Icon, label }) => {
                const active = isActive(href)
                return (
                  <Link
                    key={href}
                    href={href}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors cursor-pointer',
                      active
                        ? 'bg-[var(--accent)] text-[var(--foreground)]'
                        : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]'
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                    <span>{label}</span>
                  </Link>
                )
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Pied : toggle de thème */}
      <div className="mt-3 flex items-center justify-between border-t border-[var(--border)] pt-3 px-1">
        <span className="text-xs text-[var(--muted-foreground)] select-none">Affichage</span>
        <div className="flex items-center gap-1">
          <DensityToggle />
          <ThemeToggle />
        </div>
      </div>
    </aside>
  )
}
