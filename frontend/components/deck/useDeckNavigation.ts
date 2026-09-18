"use client";

/**
 * Navigation à deux axes du Deck :
 * - ↑ / ↓ changent de quartier et sélectionnent son premier bâtiment ;
 * - ← / → circulent entre les bâtiments du quartier courant.
 * Les fonctions de calcul restent pures et testables.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useReducedMotion } from "motion/react";
import { isInteractiveOverlayOpen } from "@/lib/interactive-overlays";

export function nextSectionIndex(current: number, key: string, total: number): number {
  const fwd = key === "ArrowDown";
  const back = key === "ArrowUp";
  if (fwd) return Math.min(current + 1, total - 1);
  if (back) return Math.max(current - 1, 0);
  return current;
}

export function nextSubsectionIndex(current: number, key: string, total: number): number {
  if (total <= 0) return 0;
  if (key === "ArrowRight") return Math.min(current + 1, total - 1);
  if (key === "ArrowLeft") return Math.max(current - 1, 0);
  return current;
}

export function useDeckNavigation(total: number, subsectionCounts: number[] = []) {
  const sectionRefs = useRef<(HTMLElement | null)[]>([]);
  const [active, setActive] = useState(0);
  const [selection, setSelection] = useState({ section: 0, subsection: 0 });
  const reduced = useReducedMotion();
  const currentActive = Math.min(active, Math.max(0, total - 1));
  const currentSubsection =
    selection.section === currentActive
      ? Math.min(selection.subsection, Math.max(0, (subsectionCounts[currentActive] ?? 0) - 1))
      : 0;

  const registerSection = useCallback((index: number, node: HTMLElement | null) => {
    sectionRefs.current[index] = node;
  }, []);

  const goTo = useCallback(
    (i: number) => {
      const clamped = Math.max(0, Math.min(i, total - 1));
      setSelection({ section: clamped, subsection: 0 });
      sectionRefs.current[clamped]?.scrollIntoView({
        behavior: reduced ? "auto" : "smooth",
        block: "start",
      });
    },
    [reduced, total],
  );

  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            const idx = sectionRefs.current.indexOf(e.target as HTMLElement);
            if (idx !== -1) {
              setActive(idx);
              setSelection((previous) =>
                previous.section === idx ? previous : { section: idx, subsection: 0 },
              );
            }
          }
        });
      },
      { threshold: 0.5 },
    );
    sectionRefs.current.forEach((s) => s && io.observe(s));
    return () => io.disconnect();
  }, [total]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target;
      if (
        e.metaKey ||
        e.ctrlKey ||
        e.altKey ||
        (target instanceof Element &&
          target.closest('input, textarea, select, [contenteditable="true"]')) ||
        isInteractiveOverlayOpen()
      )
        return;

      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        const next = nextSectionIndex(currentActive, e.key, total);
        if (next === currentActive) return;
        e.preventDefault();
        goTo(next);
        return;
      }

      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        const subsectionTotal = subsectionCounts[currentActive] ?? 0;
        const next = nextSubsectionIndex(currentSubsection, e.key, subsectionTotal);
        if (next === currentSubsection) return;
        e.preventDefault();
        setSelection({ section: currentActive, subsection: next });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [currentActive, currentSubsection, goTo, subsectionCounts, total]);

  const selectSubsection = useCallback(
    (subsection: number) => {
      const max = Math.max(0, (subsectionCounts[currentActive] ?? 0) - 1);
      setSelection({
        section: currentActive,
        subsection: Math.max(0, Math.min(subsection, max)),
      });
    },
    [currentActive, subsectionCounts],
  );

  return {
    active: currentActive,
    subsection: currentSubsection,
    registerSection,
    goTo,
    selectSubsection,
  };
}
