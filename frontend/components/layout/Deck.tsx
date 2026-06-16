'use client'

/**
 * Le Deck — navigation immersive de l'accueil (remplace la sidebar).
 *
 * Deux axes de scroll, façon « stories » :
 *   - vertical   : une section plein écran par catégorie (snap mandatory)
 *   - horizontal : les modules de la catégorie, en rangée de cartes de verre
 *
 * Chaque carte « pop » en arrivant dans le viewport (scroll-driven animation,
 * dégradation propre si non supporté). Un rail de points à droite indique la
 * catégorie courante et permet d'y sauter. Clavier : ↑/↓ catégories, ←/→
 * modules, Entrée ouvre.
 */

import { useEffect, useRef, useState, type ReactNode } from 'react'
import Link from 'next/link'
import { ChevronDown } from 'lucide-react'
import { MODULE_GROUPS } from '@/lib/modules'
import { cn } from '@/lib/utils'

/** Une section « intro » optionnelle (ex. volet Aujourd'hui) précède les
 *  catégories. Le rail de points en tient compte (décalage d'index). */
export function Deck({ intro }: { intro?: ReactNode }) {
  const deckRef = useRef<HTMLDivElement>(null)
  const sectionRefs = useRef<(HTMLElement | null)[]>([])
  const [active, setActive] = useState(0)
  const introOffset = intro ? 1 : 0
  const totalSections = MODULE_GROUPS.length + introOffset

  // Catégorie active = section la plus proche du centre du viewport.
  useEffect(() => {
    const deck = deckRef.current
    if (!deck) return
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            const idx = sectionRefs.current.indexOf(e.target as HTMLElement)
            if (idx !== -1) setActive(idx)
          }
        })
      },
      { root: deck, threshold: 0.5 },
    )
    sectionRefs.current.forEach((s) => s && io.observe(s))
    return () => io.disconnect()
  }, [])

  const goTo = (idx: number) => {
    const clamped = Math.max(0, Math.min(idx, totalSections - 1))
    sectionRefs.current[clamped]?.scrollIntoView({ behavior: 'smooth' })
  }

  return (
    <div className="relative">
      <div ref={deckRef} className="deck no-scrollbar" aria-label="Accueil">
        {intro && (
          <section
            ref={(el) => { sectionRefs.current[0] = el }}
            className="deck-section"
            aria-label="Aujourd'hui"
          >
            <div className="deck-pop mx-auto w-full max-w-[1280px] px-[max(24px,calc((100vw-1280px)/2+24px))]">
              {intro}
            </div>
            <button
              type="button"
              onClick={() => goTo(1)}
              className="deck-hint absolute bottom-6 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1 text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
              aria-label="Explorer les modules"
            >
              <span className="text-xs">{MODULE_GROUPS[0].group}</span>
              <ChevronDown className="h-5 w-5" aria-hidden="true" />
            </button>
          </section>
        )}
        {MODULE_GROUPS.map((group, gi) => (
          <section
            key={group.group}
            ref={(el) => { sectionRefs.current[gi + introOffset] = el }}
            className="deck-section"
            aria-label={group.group}
          >
            <div className="deck-pop">
              <header className="px-[max(24px,calc((100vw-1280px)/2+24px))]">
                <p className="text-sm text-[var(--muted-foreground)]">
                  {String(gi + 1).padStart(2, '0')} / {String(MODULE_GROUPS.length).padStart(2, '0')}
                </p>
                <h2 className="mt-1 font-display text-[clamp(1.75rem,4vw,3rem)] leading-tight text-[var(--foreground)]">
                  {group.group}
                </h2>
              </header>

              <div className="deck-row no-scrollbar mt-6" role="list">
                {group.items.map((m) => {
                  const Icon = m.icon
                  const disabled = m.ready === false
                  const Card = (
                    <div
                      role="listitem"
                      className={cn(
                        'springy group relative flex h-[min(58vh,420px)] w-[min(78vw,300px)] shrink-0 flex-col justify-between',
                        'overflow-hidden rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] p-6',
                        'backdrop-blur-[var(--glass-blur)] backdrop-saturate-[1.8]',
                        'shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow)]',
                        disabled
                          ? 'opacity-55'
                          : 'hover:-translate-y-1.5 hover:shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow-lg)] hover:border-[color-mix(in_srgb,var(--ring)_35%,transparent)]',
                      )}
                    >
                      <span className="flex h-12 w-12 items-center justify-center rounded-[var(--radius)] bg-[var(--accent)] text-[var(--foreground)]">
                        <Icon className="h-6 w-6" aria-hidden="true" />
                      </span>
                      <div>
                        <h3 className="font-display text-2xl text-[var(--foreground)]">{m.label}</h3>
                        <p className="mt-2 text-sm leading-relaxed text-[var(--muted-foreground)]">
                          {m.description}
                        </p>
                        {disabled && (
                          <span className="mt-3 inline-flex rounded-[var(--radius-full)] bg-[var(--muted)] px-2.5 py-0.5 text-xs text-[var(--muted-foreground)]">
                            Bientôt
                          </span>
                        )}
                      </div>
                    </div>
                  )
                  return disabled ? (
                    <div key={m.slug} aria-disabled className="min-h-[44px]">{Card}</div>
                  ) : (
                    <Link
                      key={m.slug}
                      href={'/' + m.slug}
                      className="min-h-[44px] rounded-[var(--radius-lg)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ring)]"
                      aria-label={`${m.label} — ${m.description}`}
                    >
                      {Card}
                    </Link>
                  )
                })}
              </div>
            </div>

            {/* Indice « scroll vers le bas » : seulement hors dernière section. */}
            {gi < MODULE_GROUPS.length - 1 && (
              <button
                type="button"
                onClick={() => goTo(gi + introOffset + 1)}
                className="deck-hint absolute bottom-6 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1 text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
                aria-label="Catégorie suivante"
              >
                <span className="text-xs">{MODULE_GROUPS[gi + 1].group}</span>
                <ChevronDown className="h-5 w-5" aria-hidden="true" />
              </button>
            )}
          </section>
        ))}
      </div>

      {/* Rail de points (section courante + saut direct). */}
      <nav
        className="fixed right-4 top-1/2 z-[var(--z-sidebar)] hidden -translate-y-1/2 flex-col gap-2.5 md:flex"
        aria-label="Navigation des sections"
      >
        {Array.from({ length: totalSections }).map((_, si) => {
          const label = si < introOffset ? "Aujourd'hui" : MODULE_GROUPS[si - introOffset].group
          return (
            <button
              key={si}
              type="button"
              onClick={() => goTo(si)}
              aria-current={si === active ? 'true' : undefined}
              aria-label={label}
              title={label}
              className={cn(
                'springy rounded-full',
                si === active
                  ? 'h-6 w-2.5 bg-[var(--ring)]'
                  : 'h-2.5 w-2.5 bg-[color-mix(in_srgb,var(--muted-foreground)_40%,transparent)] hover:bg-[var(--muted-foreground)]',
              )}
            />
          )
        })}
      </nav>
    </div>
  )
}
