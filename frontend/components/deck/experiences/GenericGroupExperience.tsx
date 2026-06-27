'use client'

/**
 * Repli générique : tout groupe non encore migré en « expérience » dédiée garde
 * un rendu en rangée de cartes-liens (équivalent à l'ancien Deck), enveloppé
 * dans la nouvelle DeckSection pour bénéficier du snap + de l'entrée en stagger.
 */

import Link from 'next/link'
import { DeckSection, FadeUpItem } from '@/components/deck/DeckSection'
import type { MODULE_GROUPS } from '@/lib/modules'
import { cn } from '@/lib/utils'

type Group = (typeof MODULE_GROUPS)[number]

export function GenericGroupExperience({
  group,
  index,
  sectionRef,
}: {
  group: Group
  index: number
  sectionRef?: (el: HTMLElement | null) => void
}) {
  return (
    <DeckSection label={group.group} index={index} sectionRef={sectionRef}>
      <FadeUpItem>
        <p className="text-sm text-[var(--muted-foreground)]">
          {String(index + 1).padStart(2, '0')} / 07
        </p>
        <h2 className="mt-1 font-display text-[clamp(1.75rem,4vw,3rem)] leading-tight text-[var(--foreground)]">
          {group.group}
        </h2>
      </FadeUpItem>

      <div className="mt-6 flex flex-wrap gap-4">
        {group.items.map((m) => {
          const Icon = m.icon
          const disabled = m.ready === false
          const card = (
            <FadeUpItem
              className={cn(
                'group relative flex h-[220px] w-[280px] flex-col justify-between overflow-hidden rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-6 backdrop-blur-[var(--glass-blur)] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow)]',
                disabled ? 'opacity-55' : 'hover:-translate-y-1.5',
              )}
            >
              <span className="flex h-12 w-12 items-center justify-center rounded-[var(--radius)] bg-[var(--accent)] text-[var(--foreground)]">
                <Icon className="h-6 w-6" aria-hidden="true" />
              </span>
              <div>
                <h3 className="font-display text-2xl text-[var(--foreground)]">{m.label}</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--muted-foreground)]">{m.description}</p>
              </div>
            </FadeUpItem>
          )
          return disabled ? (
            <div key={m.slug} aria-disabled>{card}</div>
          ) : (
            <Link
              key={m.slug}
              href={'/' + m.slug}
              aria-label={`${m.label} — ${m.description}`}
              className="rounded-[var(--radius-lg)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)]"
            >
              {card}
            </Link>
          )
        })}
      </div>
    </DeckSection>
  )
}
