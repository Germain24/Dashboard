"use client";

/**
 * Aide-mémoire des raccourcis clavier.
 *
 * Découverte : touche « ? » (hors champ de saisie) ou bouton d'aide de la
 * sidebar (évènement « mc:shortcuts »). Rend visibles des accélérateurs qui
 * n'étaient documentés nulle part (⌘K, j/k, g puis h). Fermeture par Échap ou
 * clic sur l'arrière-plan ; le focus revient à l'élément déclencheur.
 */

import { useEffect, useRef, useState } from "react";

type Shortcut = { keys: string[]; label: string };

function shortcuts(isMac: boolean): Shortcut[] {
  return [
    { keys: [isMac ? "⌘" : "Ctrl", "K"], label: "Rechercher, aller à un module" },
    { keys: ["J"], label: "Module suivant" },
    { keys: ["K"], label: "Module précédent" },
    { keys: ["G", "puis", "H"], label: "Accueil" },
    { keys: ["?"], label: "Afficher cette aide" },
  ];
}

function isTyping(el: EventTarget | null): boolean {
  const node = el as HTMLElement | null;
  if (!node) return false;
  const tag = node.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || node.isContentEditable;
}

export function ShortcutsHelp() {
  const [open, setOpen] = useState(false);
  const [isMac, setIsMac] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    setIsMac(/Mac|iPhone|iPad|iPod/.test(navigator.userAgent));
  }, []);

  // Ouverture : touche « ? » globale + évènement du bouton d'aide.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.metaKey || e.ctrlKey || e.altKey || isTyping(e.target)) return;
      if (e.key === "?") {
        e.preventDefault();
        setOpen(true);
      }
    }
    function onEvent() {
      setOpen(true);
    }
    window.addEventListener("keydown", onKey);
    window.addEventListener("mc:shortcuts", onEvent);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mc:shortcuts", onEvent);
    };
  }, []);

  // Gestion du focus + fermeture clavier quand le modal est ouvert.
  useEffect(() => {
    if (!open) return;
    restoreRef.current = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();

    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        return;
      }
      if (e.key !== "Tab") return;
      // Piège à focus : maintient le Tab à l'intérieur du modal.
      const focusables = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button, [href], input, [tabindex]:not([tabindex="-1"])',
      );
      if (!focusables || focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    // Fermeture au clic hors du modal, sans handler sur un div non interactif.
    function onPointer(e: MouseEvent) {
      if (dialogRef.current && !dialogRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointer);
      restoreRef.current?.focus();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-title"
        className="w-full max-w-sm overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-[var(--shadow-lg)]"
      >
        <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
          <h2 id="shortcuts-title" className="text-sm font-semibold">
            Raccourcis clavier
          </h2>
          <button
            ref={closeRef}
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Fermer"
            className="rounded-[var(--radius-sm)] px-1.5 text-sm text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
          >
            Échap
          </button>
        </div>
        <ul className="divide-y divide-[var(--border)]">
          {shortcuts(isMac).map((s) => (
            <li key={s.label} className="flex items-center justify-between gap-4 px-4 py-2.5">
              <span className="text-sm text-[var(--foreground)]">{s.label}</span>
              <span className="flex shrink-0 items-center gap-1">
                {s.keys.map((k, i) =>
                  k === "puis" ? (
                    <span key={i} className="text-xs text-[var(--muted-foreground)]">
                      puis
                    </span>
                  ) : (
                    <kbd
                      key={i}
                      className="rounded border border-[var(--border)] bg-[var(--muted)] px-1.5 py-0.5 text-[11px] font-medium text-[var(--foreground)]"
                    >
                      {k}
                    </kbd>
                  ),
                )}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
