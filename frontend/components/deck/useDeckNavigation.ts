'use client'

/**
 * Navigation du Deck : section active (IntersectionObserver), saut programmé et
 * raccourcis clavier ↑↓←→. `nextSectionIndex` est pure et testée.
 */

import { useEffect, useRef, useState } from 'react'

export function nextSectionIndex(current: number, key: string, total: number): number {
  const fwd = key === 'ArrowDown' || key === 'ArrowRight'
  const back = key === 'ArrowUp' || key === 'ArrowLeft'
  if (fwd) return Math.min(current + 1, total - 1)
  if (back) return Math.max(current - 1, 0)
  return current
}

export function useDeckNavigation(total: number) {
  const sectionRefs = useRef<(HTMLElement | null)[]>([])
  const [active, setActive] = useState(0)

  const goTo = (i: number) => {
    const clamped = Math.max(0, Math.min(i, total - 1))
    sectionRefs.current[clamped]?.scrollIntoView({ behavior: 'smooth' })
  }

  // Si le nombre de sections diminue (ex. intro retirée), garde l'index actif
  // dans les bornes pour ne pas pointer au-delà de la dernière section.
  useEffect(() => {
    setActive((a) => Math.min(a, Math.max(0, total - 1)))
  }, [total])

  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            const idx = sectionRefs.current.indexOf(e.target as HTMLElement)
            if (idx !== -1) setActive(idx)
          }
        })
      },
      { threshold: 0.5 },
    )
    sectionRefs.current.forEach((s) => s && io.observe(s))
    return () => io.disconnect()
  }, [total])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (target.closest('input, textarea, [contenteditable="true"]')) return
      const next = nextSectionIndex(active, e.key, total)
      if (next !== active) {
        e.preventDefault()
        goTo(next)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, total])

  return { active, sectionRefs, goTo }
}
