"use client";

/**
 * Palette de commandes (Cmd/Ctrl+K) — navigation + recherche de données + ajout rapide.
 *
 * - Navigation : modules, accueil, paramètres
 * - Recherche données (#546) : résultats depuis /api/search?q= (transactions, recettes, livres)
 * - Ajout rapide (#547) : "> dépense | séance | habitude | repas" pour actions directes
 * - Piège à focus, navigation clavier complète, dégradation propre si API indisponible.
 */

import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { MODULES } from "@/lib/modules";
import { useDebounce } from "@/lib/hooks";

// ── Types ────────────────────────────────────────────────────────────────────

type NavCommand = { kind: "nav"; id: string; label: string; href: string; hint?: string };
type DataResult = { kind: "data"; id: string; label: string; hint?: string; href: string; type: string };
type ActionCommand = { kind: "action"; id: string; label: string; hint: string; action: () => void };

type Command = NavCommand | DataResult | ActionCommand;

// ── Commandes navigation statiques ───────────────────────────────────────────

const NAV_COMMANDS: NavCommand[] = [
  { kind: "nav", id: "home", label: "Accueil", href: "/", hint: "Tableau de bord" },
  { kind: "nav", id: "parametres", label: "Paramètres", href: "/parametres", hint: "Intégrations & préférences" },
  // parametres a déjà son entrée statique ci-dessus : l'exclure évite une clé dupliquée.
  ...MODULES.filter(m => m.ready && m.slug !== "parametres").map((m) => ({
    kind: "nav" as const,
    id: m.slug,
    label: m.label,
    href: "/" + m.slug,
    hint: m.description,
  })),
];

// ── Helpers recherche distante ────────────────────────────────────────────────

async function fetchDataResults(q: string): Promise<DataResult[]> {
  try {
    const r = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=5`);
    if (!r.ok) return [];
    const data = await r.json();
    return (data.results ?? []).map((item: { type: string; label: string; hint?: string; href: string }, i: number) => ({
      kind: "data" as const,
      id: `data-${item.type}-${i}`,
      label: item.label,
      hint: item.hint,
      href: item.href,
      type: item.type,
    }));
  } catch {
    return [];
  }
}

const TYPE_BADGE: Record<string, string> = {
  transaction: "Budget",
  recette: "Cuisine",
  livre: "Livres",
};

// ── Quick-add actions (#547) ─────────────────────────────────────────────────

function buildActionCommands(router: ReturnType<typeof useRouter>): ActionCommand[] {
  const nav = (href: string) => router.push(href);
  return [
    {
      kind: "action",
      id: "quick-depense",
      label: "+ Nouvelle dépense",
      hint: "Ouvre Budget",
      action: () => nav("/budget"),
    },
    {
      kind: "action",
      id: "quick-seance",
      label: "+ Nouvelle séance",
      hint: "Ouvre Entraînement",
      action: () => nav("/entrainement"),
    },
    {
      kind: "action",
      id: "quick-repas",
      label: "+ Nouveau repas",
      hint: "Ouvre Santé (journal alimentaire)",
      action: () => nav("/sante"),
    },
    {
      kind: "action",
      id: "quick-habitude",
      label: "+ Cocher une habitude",
      hint: "Ouvre Habitudes",
      action: () => nav("/habitudes"),
    },
  ];
}

// ── Composant ────────────────────────────────────────────────────────────────

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [dataResults, setDataResults] = useState<DataResult[]>([]);
  const [searching, setSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  const debouncedQuery = useDebounce(query, 250);
  const actionCommands = useMemo(() => buildActionCommands(router), [router]);

  // Recherche distante déclenchée par la requête debouncée
  useEffect(() => {
    const q = debouncedQuery.trim();
    if (q.length < 2 || q.startsWith(">")) {
      setDataResults([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    fetchDataResults(q).then((res) => {
      setDataResults(res);
      setSearching(false);
    });
  }, [debouncedQuery]);

  // Ouverture/fermeture globale
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
    function open() { setOpen(true); }
    window.addEventListener("mc:command-palette", open);
    return () => window.removeEventListener("mc:command-palette", open);
  }, []);

  // Piège à focus, clic extérieur, restauration du focus
  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActive(0);
    setDataResults([]);
    restoreRef.current = document.activeElement as HTMLElement | null;
    const t = setTimeout(() => inputRef.current?.focus(), 0);

    function onKey(e: KeyboardEvent) {
      if (e.key !== "Tab") return;
      const focusables = dialogRef.current?.querySelectorAll<HTMLElement>(
        'a[href], button, input, [tabindex]:not([tabindex="-1"])',
      );
      if (!focusables || focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
    function onPointer(e: MouseEvent) {
      if (dialogRef.current && !dialogRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onPointer);
    return () => {
      clearTimeout(t);
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointer);
      restoreRef.current?.focus();
    };
  }, [open]);

  // Commandes affichées selon la requête
  const results = useMemo<Command[]>(() => {
    const q = query.trim().toLowerCase();

    // Mode ajout rapide : ">" ou "> xxx"
    if (q.startsWith(">")) {
      const sub = q.slice(1).trim();
      if (!sub) return actionCommands;
      return actionCommands.filter(
        (a) => a.label.toLowerCase().includes(sub) || a.hint.toLowerCase().includes(sub),
      );
    }

    // Navigation filtrée
    const navFiltered = !q
      ? NAV_COMMANDS
      : NAV_COMMANDS.filter(
          (c) => c.label.toLowerCase().includes(q) || c.hint?.toLowerCase().includes(q),
        );

    // Données distantes
    if (dataResults.length > 0) {
      return [...navFiltered, ...dataResults];
    }
    return navFiltered;
  }, [query, dataResults, actionCommands]);

  const run = useCallback(
    (cmd: Command | undefined) => {
      if (!cmd) return;
      setOpen(false);
      if (cmd.kind === "action") {
        cmd.action();
      } else {
        router.push(cmd.href);
      }
    },
    [router],
  );

  if (!open) return null;

  const isActionMode = query.trim().startsWith(">");
  const showDataResults = dataResults.length > 0 && !isActionMode;
  const navCount = results.filter((r) => r.kind === "nav").length;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 backdrop-blur-[6px] pt-[15vh] animate-fade-in">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Palette de commandes"
        className="glass-modal w-full max-w-lg overflow-hidden rounded-[var(--radius-lg)] animate-scale-in"
      >
        <div className="flex items-center border-b border-[var(--glass-border)]">
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)); }
              else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
              else if (e.key === "Enter") { e.preventDefault(); run(results[active]); }
            }}
            placeholder={isActionMode ? "Choisir une action…" : "Rechercher… (> pour actions)"}
            className="flex-1 bg-transparent px-4 py-3 text-sm outline-none placeholder:text-[var(--muted-foreground)]"
          />
          {searching && (
            <span className="pr-3 text-xs text-[var(--muted-foreground)] animate-pulse">Recherche…</span>
          )}
        </div>

        <ul className="max-h-72 overflow-y-auto py-1">
          {results.length === 0 ? (
            <li className="px-4 py-3 text-sm text-[var(--muted-foreground)]">Aucun résultat</li>
          ) : (
            results.map((c, i) => {
              const isData = c.kind === "data";
              const isAction = c.kind === "action";
              const badge = isData ? (TYPE_BADGE[(c as DataResult).type] ?? (c as DataResult).type) : null;
              const isFirstData = isData && i === navCount;

              return (
                <li key={c.id}>
                  {isFirstData && (
                    <div className="px-4 pt-2 pb-1 font-display italic text-xs text-[var(--muted-foreground)]">
                      Résultats
                    </div>
                  )}
                  {i === 0 && isAction && (
                    <div className="px-4 pt-2 pb-1 font-display italic text-xs text-[var(--muted-foreground)]">
                      Actions rapides
                    </div>
                  )}
                  <button
                    type="button"
                    onMouseEnter={() => setActive(i)}
                    onClick={() => run(c)}
                    className={`flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-sm transition-colors ${
                      i === active ? "bg-[var(--muted)] text-[var(--foreground)]" : "text-[var(--muted-foreground)]"
                    }`}
                  >
                    <span className={`font-medium truncate ${isAction ? "text-[var(--ring)]" : "text-[var(--foreground)]"}`}>
                      {c.label}
                    </span>
                    <div className="flex items-center gap-2 shrink-0">
                      {badge && (
                        <span className="text-[10px] bg-[var(--muted)] px-1.5 py-0.5 rounded font-medium">
                          {badge}
                        </span>
                      )}
                      {c.hint && (
                        <span className="truncate text-xs text-[var(--muted-foreground)] max-w-[160px]">{c.hint}</span>
                      )}
                    </div>
                  </button>
                </li>
              );
            })
          )}
        </ul>

        <div className="border-t border-[var(--glass-border)] px-4 py-2 text-[11px] text-[var(--muted-foreground)]">
          ↑↓ naviguer · Entrée ouvrir · Échap fermer · ⌘/Ctrl+K basculer
          {!isActionMode && <span className="ml-3 opacity-60">· <kbd className="font-mono">&gt;</kbd> actions rapides</span>}
        </div>
      </div>
    </div>
  );
}
