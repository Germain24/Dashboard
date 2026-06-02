"use client";

/**
 * Palette de commandes (Cmd/Ctrl+K) — navigation rapide entre modules.
 *
 * Sans dépendance externe : overlay + input + liste filtrée, navigation
 * clavier (↑/↓/Entrée/Échap). Montée globalement dans le layout.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { MODULES } from "@/lib/modules";

type Command = { id: string; label: string; href: string; hint?: string };

const COMMANDS: Command[] = [
  { id: "home", label: "Accueil", href: "/", hint: "Dashboard" },
  ...MODULES.map((m) => ({ id: m.slug, label: m.label, href: "/" + m.slug, hint: m.description })),
  { id: "jobs", label: "Jobs", href: "/jobs", hint: "Tâches planifiées" },
];

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Ouverture/fermeture via Cmd/Ctrl+K.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      // focus après le rendu
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return COMMANDS;
    return COMMANDS.filter(
      (c) => c.label.toLowerCase().includes(q) || c.hint?.toLowerCase().includes(q),
    );
  }, [query]);

  function run(cmd: Command | undefined) {
    if (!cmd) return;
    setOpen(false);
    router.push(cmd.href);
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-[15vh]"
      onClick={() => setOpen(false)}
      role="dialog"
      aria-modal="true"
      aria-label="Palette de commandes"
    >
      <div
        className="w-full max-w-lg overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-[var(--shadow-lg)]"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setActive((a) => Math.min(a + 1, results.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, 0));
            } else if (e.key === "Enter") {
              e.preventDefault();
              run(results[active]);
            }
          }}
          placeholder="Aller à…"
          className="w-full border-b border-[var(--border)] bg-transparent px-4 py-3 text-sm outline-none placeholder:text-[var(--muted-foreground)]"
        />
        <ul className="max-h-72 overflow-y-auto py-1">
          {results.length === 0 ? (
            <li className="px-4 py-3 text-sm text-[var(--muted-foreground)]">Aucun résultat</li>
          ) : (
            results.map((c, i) => (
              <li key={c.id}>
                <button
                  type="button"
                  onMouseEnter={() => setActive(i)}
                  onClick={() => run(c)}
                  className={`flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-sm ${
                    i === active ? "bg-[var(--muted)] text-[var(--foreground)]" : "text-[var(--muted-foreground)]"
                  }`}
                >
                  <span className="font-medium text-[var(--foreground)]">{c.label}</span>
                  {c.hint && <span className="truncate text-xs text-[var(--muted-foreground)]">{c.hint}</span>}
                </button>
              </li>
            ))
          )}
        </ul>
        <div className="border-t border-[var(--border)] px-4 py-2 text-[10px] text-[var(--muted-foreground)]">
          ↑↓ naviguer · Entrée ouvrir · Échap fermer · ⌘/Ctrl+K basculer
        </div>
      </div>
    </div>
  );
}
