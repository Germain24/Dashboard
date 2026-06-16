'use client'

/**
 * En-tête de module unifié (liquid glass).
 *
 * Barre de verre collante : titre en serif éditorial, sous-titre, et un
 * contrôle d'onglets segmenté en verre (pastille soulevée pour l'actif).
 * Remplace les en-têtes `px-6 py-5 border-b` + onglets inline dupliqués page
 * par page. Le corps de l'onglet reste géré par chaque page.
 */

import type { ElementType } from 'react'
import { cn } from '@/lib/utils'

export type ModuleTab = {
  id: string
  label: string
  icon?: ElementType
}

interface ModuleHeaderProps {
  title: string
  subtitle?: string
  tabs?: ModuleTab[]
  active?: string
  onChange?: (id: string) => void
  /** Actions optionnelles alignées à droite du titre (boutons, filtres). */
  actions?: React.ReactNode
}

export function ModuleHeader({
  title,
  subtitle,
  tabs,
  active,
  onChange,
  actions,
}: ModuleHeaderProps) {
  return (
    <div className="glass-panel sticky top-0 z-[var(--z-header)] border-b border-[var(--glass-border)] px-6 py-4">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl text-[var(--foreground)]">{title}</h1>
          {subtitle && (
            <p className="mt-0.5 text-sm text-[var(--muted-foreground)]">{subtitle}</p>
          )}
        </div>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>

      {tabs && tabs.length > 0 && (
        <div
          role="tablist"
          className="flex w-fit max-w-full gap-1 overflow-x-auto rounded-[var(--radius-full)] border border-[var(--glass-border)] bg-[var(--field)] p-1 no-scrollbar"
        >
          {tabs.map((tab) => {
            const Icon = tab.icon
            const isActive = active === tab.id
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => onChange?.(tab.id)}
                className={cn(
                  'springy flex shrink-0 items-center gap-1.5 rounded-[var(--radius-full)] px-3.5 py-1.5 text-sm font-medium',
                  isActive
                    ? 'bg-[var(--glass-strong)] text-[var(--foreground)] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow-sm)]'
                    : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)]',
                )}
              >
                {Icon && <Icon size={15} className="shrink-0" />}
                {tab.label}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
