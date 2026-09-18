"use client";

/** Palette de commandes (Cmd/Ctrl+K) : navigation, recherche et ajout rapide. */

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, MutableRefObject, RefObject } from "react";
import { useRouter } from "next/navigation";
import { MODULES } from "@/lib/modules";
import { useDebounce } from "@/lib/hooks";
import { isInteractiveOverlayOpen } from "@/lib/interactive-overlays";
import {
  buildResults,
  CommandResults,
  fetchDataResults,
  getActiveIndex,
  handleTabTrap,
  isAbortError,
  moveActiveIndex,
  type ActionCommand,
  type Command,
  type DataResult,
  type NavCommand,
} from "@/components/CommandPaletteParts";

const NAV_COMMANDS: NavCommand[] = [
  { kind: "nav", id: "home", label: "Accueil", href: "/", hint: "Tableau de bord" },
  {
    kind: "nav",
    id: "parametres",
    label: "Paramètres",
    href: "/parametres",
    hint: "Intégrations & préférences",
  },
  ...MODULES.filter((module) => module.ready && module.slug !== "parametres").map((module) => ({
    kind: "nav" as const,
    id: module.slug,
    label: module.label,
    href: "/" + module.slug,
    hint: module.description,
  })),
];

function buildActionCommands(router: ReturnType<typeof useRouter>): ActionCommand[] {
  const nav = (href: string) => router.push(href);
  return [
    {
      kind: "action",
      id: "quick-depense",
      label: "Catégoriser des transactions",
      hint: "Budget · Transactions",
      action: () => nav("/budget?tab=transactions"),
    },
    {
      kind: "action",
      id: "quick-seance",
      label: "Ouvrir l’entraînement du jour",
      hint: "Entraînement · Aujourd’hui",
      action: () => nav("/entrainement?tab=aujourdhui"),
    },
    {
      kind: "action",
      id: "quick-repas",
      label: "Ouvrir le journal alimentaire",
      hint: "Santé · Courses",
      action: () => nav("/sante?tab=fenetre"),
    },
    {
      kind: "action",
      id: "quick-habitude",
      label: "Cocher une habitude",
      hint: "Habitudes · Aujourd’hui",
      action: () => nav("/habitudes?tab=aujourd-hui"),
    },
    {
      kind: "action",
      id: "quick-revision",
      label: "Planifier une révision",
      hint: "Études · Révision des cours",
      action: () => nav("/etudes?tab=revision"),
    },
  ];
}

function handleGlobalShortcut(
  event: KeyboardEvent,
  open: boolean,
  dialog: HTMLElement | null,
  openPalette: () => void,
  closePalette: () => void,
): void {
  if (isPaletteShortcut(event)) {
    if (isInteractiveOverlayOpen(dialog)) return;
    return togglePalette(event, open, openPalette, closePalette);
  }
  if (event.key === "Escape" && !isInteractiveOverlayOpen(dialog)) closePalette();
}

function isPaletteShortcut(event: KeyboardEvent): boolean {
  return (event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k";
}

function togglePalette(
  event: KeyboardEvent,
  open: boolean,
  openPalette: () => void,
  closePalette: () => void,
): void {
  event.preventDefault();
  if (open) closePalette();
  else openPalette();
}

function useGlobalShortcut(
  open: boolean,
  dialogRef: RefObject<HTMLDivElement | null>,
  openPalette: () => void,
  closePalette: () => void,
): void {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) =>
      handleGlobalShortcut(event, open, dialogRef.current, openPalette, closePalette);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closePalette, dialogRef, open, openPalette]);
}

function usePaletteLifecycle(
  open: boolean,
  dialogRef: RefObject<HTMLDivElement | null>,
  inputRef: RefObject<HTMLInputElement | null>,
  closePalette: () => void,
  searchAbortRef: MutableRefObject<AbortController | null>,
): void {
  useEffect(() => {
    if (!open) return;
    const restore = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    const activeSearch = searchAbortRef.current;
    document.body.style.overflow = "hidden";
    const timer = setTimeout(() => inputRef.current?.focus(), 0);
    const onKey = (event: KeyboardEvent) => handleTabTrap(event, dialogRef);
    const onPointer = (event: MouseEvent) => closeIfOutside(event, dialogRef, closePalette);
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onPointer);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointer);
      document.body.style.overflow = previousOverflow;
      activeSearch?.abort();
      restore?.focus();
    };
  }, [closePalette, dialogRef, inputRef, open, searchAbortRef]);
}

function closeIfOutside(
  event: MouseEvent,
  dialogRef: RefObject<HTMLDivElement | null>,
  closePalette: () => void,
): void {
  if (dialogRef.current && !dialogRef.current.contains(event.target as Node)) closePalette();
}

function useDataSearch(
  debouncedQuery: string,
  searchAbortRef: MutableRefObject<AbortController | null>,
  setDataResults: (results: DataResult[]) => void,
  setSearching: (searching: boolean) => void,
  setSearchError: (error: boolean) => void,
  retryCount: number,
): void {
  useEffect(
    () =>
      runDataSearch(debouncedQuery, searchAbortRef, setDataResults, setSearching, setSearchError),
    [debouncedQuery, searchAbortRef, setDataResults, setSearching, setSearchError, retryCount],
  );
}

function stopSearch(searchAbortRef: MutableRefObject<AbortController | null>): void {
  searchAbortRef.current?.abort();
  searchAbortRef.current = null;
}

function applySearchResults(
  controller: AbortController,
  results: DataResult[],
  setDataResults: (results: DataResult[]) => void,
  setSearchError: (error: boolean) => void,
): void {
  if (!controller.signal.aborted) {
    setDataResults(results);
    setSearchError(false);
  }
}

function clearSearchError(
  error: unknown,
  setDataResults: (results: DataResult[]) => void,
  setSearchError: (error: boolean) => void,
): void {
  if (!isAbortError(error)) {
    setDataResults([]);
    setSearchError(true);
  }
}

function finishSearch(
  controller: AbortController,
  setSearching: (searching: boolean) => void,
): void {
  if (!controller.signal.aborted) setSearching(false);
}

function startDataSearch(
  query: string,
  searchAbortRef: MutableRefObject<AbortController | null>,
  setDataResults: (results: DataResult[]) => void,
  setSearching: (searching: boolean) => void,
  setSearchError: (error: boolean) => void,
): () => void {
  const controller = new AbortController();
  stopSearch(searchAbortRef);
  searchAbortRef.current = controller;
  setSearchError(false);
  queueMicrotask(() => setSearching(!controller.signal.aborted));
  void fetchDataResults(query, controller.signal)
    .then((results) => applySearchResults(controller, results, setDataResults, setSearchError))
    .catch((error: unknown) => clearSearchError(error, setDataResults, setSearchError))
    .finally(() => finishSearch(controller, setSearching));
  return () => controller.abort();
}

function runDataSearch(
  debouncedQuery: string,
  searchAbortRef: MutableRefObject<AbortController | null>,
  setDataResults: (results: DataResult[]) => void,
  setSearching: (searching: boolean) => void,
  setSearchError: (error: boolean) => void,
): (() => void) | undefined {
  const query = debouncedQuery.trim();
  if (query.length < 2 || query.startsWith(">")) {
    stopSearch(searchAbortRef);
    setSearchError(false);
    return undefined;
  }
  return startDataSearch(query, searchAbortRef, setDataResults, setSearching, setSearchError);
}

function updateQuery(
  value: string,
  searchAbortRef: MutableRefObject<AbortController | null>,
  setQuery: (value: string) => void,
  setDataResults: (results: DataResult[]) => void,
  setSearching: (searching: boolean) => void,
  setSearchError: (error: boolean) => void,
  setActive: (value: number) => void,
): void {
  searchAbortRef.current?.abort();
  searchAbortRef.current = null;
  setSearching(false);
  setSearchError(false);
  setDataResults([]);
  setQuery(value);
  setActive(0);
}

function handleInputKey(
  event: ReactKeyboardEvent<HTMLInputElement>,
  activeIndex: number,
  results: Command[],
  setActive: (value: number) => void,
  run: (command: Command | undefined) => void,
): void {
  if (moveActiveIndex(event.key, activeIndex, results.length, setActive)) {
    event.preventDefault();
    return;
  }
  if (event.key === "Enter") {
    event.preventDefault();
    run(results[activeIndex]);
  }
}

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [dataResults, setDataResults] = useState<DataResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const searchAbortRef = useRef<AbortController | null>(null);
  const listboxId = useId();
  const debouncedQuery = useDebounce(query, 250);
  const actionCommands = useMemo(() => buildActionCommands(router), [router]);
  const closePalette = useCallback(() => setOpen(false), []);
  const openPalette = useCallback(() => {
    searchAbortRef.current?.abort();
    searchAbortRef.current = null;
    setQuery("");
    setActive(0);
    setDataResults([]);
    setSearching(false);
    setSearchError(false);
    setOpen(true);
  }, []);
  const run = useCallback(
    (command: Command | undefined) => runCommand(command, closePalette, router),
    [closePalette, router],
  );
  useGlobalShortcut(open, dialogRef, openPalette, closePalette);
  usePaletteLifecycle(open, dialogRef, inputRef, closePalette, searchAbortRef);
  useEffect(() => {
    window.addEventListener("mc:command-palette", openPalette);
    return () => window.removeEventListener("mc:command-palette", openPalette);
  }, [openPalette]);
  useDataSearch(
    debouncedQuery,
    searchAbortRef,
    setDataResults,
    setSearching,
    setSearchError,
    retryCount,
  );
  const results = useMemo(
    () => buildResults(query, NAV_COMMANDS, actionCommands, dataResults),
    [actionCommands, dataResults, query],
  );
  if (!open) return null;

  const activeIndex = getActiveIndex(active, results.length);
  const isActionMode = query.trim().startsWith(">");
  const navCount = results.filter((result) => result.kind === "nav").length;
  return (
    <PaletteDialog
      dialogRef={dialogRef}
      inputRef={inputRef}
      listboxId={listboxId}
      query={query}
      results={results}
      activeIndex={activeIndex}
      navCount={navCount}
      searching={searching}
      searchError={searchError}
      isActionMode={isActionMode}
      searchAbortRef={searchAbortRef}
      setQuery={setQuery}
      setDataResults={setDataResults}
      setSearching={setSearching}
      setSearchError={setSearchError}
      onRetry={() => setRetryCount((count) => count + 1)}
      setActive={setActive}
      run={run}
    />
  );
}

function PaletteDialog({
  dialogRef,
  inputRef,
  listboxId,
  query,
  results,
  activeIndex,
  navCount,
  searching,
  searchError,
  isActionMode,
  searchAbortRef,
  setQuery,
  setDataResults,
  setSearching,
  setSearchError,
  onRetry,
  setActive,
  run,
}: {
  dialogRef: RefObject<HTMLDivElement | null>;
  inputRef: RefObject<HTMLInputElement | null>;
  listboxId: string;
  query: string;
  results: Command[];
  activeIndex: number;
  navCount: number;
  searching: boolean;
  searchError: boolean;
  isActionMode: boolean;
  searchAbortRef: MutableRefObject<AbortController | null>;
  setQuery: (value: string) => void;
  setDataResults: (results: DataResult[]) => void;
  setSearching: (searching: boolean) => void;
  setSearchError: (error: boolean) => void;
  onRetry: () => void;
  setActive: (value: number) => void;
  run: (command: Command | undefined) => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center glass-veil px-3 pt-[15vh] animate-fade-in">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Palette de commandes"
        className="glass-modal max-h-[70dvh] w-full max-w-lg overflow-hidden rounded-[var(--radius-lg)] animate-scale-in"
      >
        <PaletteInput
          inputRef={inputRef}
          listboxId={listboxId}
          query={query}
          results={results}
          activeIndex={activeIndex}
          searching={searching}
          isActionMode={isActionMode}
          searchAbortRef={searchAbortRef}
          setQuery={setQuery}
          setDataResults={setDataResults}
          setSearching={setSearching}
          setSearchError={setSearchError}
          setActive={setActive}
          run={run}
        />
        {searchError && (
          <div
            role="status"
            className="flex items-center justify-between gap-3 border-b border-[var(--glass-border)] px-4 py-2 text-xs text-[var(--destructive)]"
          >
            <span>La recherche dans tes données est indisponible.</span>
            <button
              type="button"
              onClick={onRetry}
              className="font-medium underline underline-offset-2"
            >
              Réessayer
            </button>
          </div>
        )}
        <ul
          id={listboxId}
          role="listbox"
          aria-label="Commandes"
          className="max-h-72 overflow-y-auto py-1"
        >
          <CommandResults
            results={results}
            searching={searching}
            activeIndex={activeIndex}
            listboxId={listboxId}
            navCount={navCount}
            onHover={setActive}
            onRun={run}
          />
        </ul>
        <ResultsAnnouncement searching={searching} resultCount={results.length} />
      </div>
    </div>
  );
}

function PaletteInput({
  inputRef,
  listboxId,
  query,
  results,
  activeIndex,
  searching,
  isActionMode,
  searchAbortRef,
  setQuery,
  setDataResults,
  setSearching,
  setSearchError,
  setActive,
  run,
}: {
  inputRef: RefObject<HTMLInputElement | null>;
  listboxId: string;
  query: string;
  results: Command[];
  activeIndex: number;
  searching: boolean;
  isActionMode: boolean;
  searchAbortRef: MutableRefObject<AbortController | null>;
  setQuery: (value: string) => void;
  setDataResults: (results: DataResult[]) => void;
  setSearching: (searching: boolean) => void;
  setSearchError: (error: boolean) => void;
  setActive: (value: number) => void;
  run: (command: Command | undefined) => void;
}) {
  return (
    <div className="flex items-center border-b border-[var(--glass-border)]">
      <input
        ref={inputRef}
        role="combobox"
        aria-label="Rechercher une commande"
        aria-autocomplete="list"
        aria-expanded="true"
        aria-controls={listboxId}
        aria-activedescendant={
          results[activeIndex] ? `${listboxId}-option-${activeIndex}` : undefined
        }
        value={query}
        onChange={(event) =>
          updateQuery(
            event.target.value,
            searchAbortRef,
            setQuery,
            setDataResults,
            setSearching,
            setSearchError,
            setActive,
          )
        }
        onKeyDown={(event) => handleInputKey(event, activeIndex, results, setActive, run)}
        placeholder={isActionMode ? "Choisir une action…" : "Rechercher une page ou une donnée…"}
        className="flex-1 bg-transparent px-4 py-3 text-sm outline-none placeholder:text-[var(--muted-foreground)]"
      />
      {searching && (
        <span
          aria-hidden="true"
          className="pr-3 text-xs text-[var(--muted-foreground)] animate-pulse"
        >
          Recherche…
        </span>
      )}
    </div>
  );
}

function ResultsAnnouncement({
  searching,
  resultCount,
}: {
  searching: boolean;
  resultCount: number;
}) {
  const text = searching
    ? "Recherche en cours"
    : `${resultCount} résultat${resultCount > 1 ? "s" : ""}`;
  return (
    <p className="sr-only" aria-live="polite">
      {text}
    </p>
  );
}

function runCommand(
  command: Command | undefined,
  closePalette: () => void,
  router: ReturnType<typeof useRouter>,
): void {
  if (!command) return;
  closePalette();
  if (command.kind === "action") command.action();
  else router.push(command.href);
}
