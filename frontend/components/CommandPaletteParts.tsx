import type { RefObject } from "react";

export type NavCommand = { kind: "nav"; id: string; label: string; href: string; hint?: string };
export type DataResult = {
  kind: "data";
  id: string;
  label: string;
  hint?: string;
  href: string;
  type: string;
};
export type ActionCommand = {
  kind: "action";
  id: string;
  label: string;
  hint: string;
  action: () => void;
};
export type Command = NavCommand | DataResult | ActionCommand;

export const TYPE_BADGE: Record<string, string> = {
  transaction: "Budget",
  tache: "Tâche",
  cours: "Études",
  evaluation: "Échéance",
  document: "Documents",
  objectif: "Objectif",
  recette: "Cuisine",
  livre: "Livres",
  musique: "Musique",
  lieu: "Voyage",
  evenement: "Agenda",
  vetement: "Garde-robe",
};

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function mapDataResult(item: { type: string; label: string; hint?: string; href: string }, i: number): DataResult {
  return {
    kind: "data",
    id: `data-${item.type}-${i}`,
    label: item.label,
    hint: item.hint,
    href: item.href,
    type: item.type,
  };
}

async function requestDataResults(q: string, signal: AbortSignal): Promise<DataResult[]> {
  const response = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=5`, { signal });
  if (!response.ok) throw new Error("Recherche temporairement indisponible.");
  const data = await response.json();
  return (data.results ?? []).map(mapDataResult);
}

export async function fetchDataResults(q: string, signal: AbortSignal): Promise<DataResult[]> {
  return requestDataResults(q, signal);
}

export function filterActions(actions: ActionCommand[], query: string): ActionCommand[] {
  return actions.filter(
    (action) => action.label.toLowerCase().includes(query) || action.hint.toLowerCase().includes(query),
  );
}

export function filterNavigation(commands: NavCommand[], query: string): NavCommand[] {
  return commands.filter(
    (command) => command.label.toLowerCase().includes(query) || command.hint?.toLowerCase().includes(query),
  );
}

export function buildResults(
  query: string,
  navigation: NavCommand[],
  actions: ActionCommand[],
  dataResults: DataResult[],
): Command[] {
  const normalized = query.trim().toLowerCase();
  return normalized.startsWith(">")
    ? buildActionResults(normalized, actions)
    : buildNavigationResults(normalized, navigation, dataResults);
}

function buildActionResults(query: string, actions: ActionCommand[]): ActionCommand[] {
  const actionQuery = query.slice(1).trim();
  return actionQuery ? filterActions(actions, actionQuery) : actions;
}

function buildNavigationResults(query: string, navigation: NavCommand[], dataResults: DataResult[]): Command[] {
  const navResults = query ? filterNavigation(navigation, query) : navigation;
  if (dataResults.length > 0) return [...navResults, ...dataResults];
  return navResults;
}

export function getActiveIndex(active: number, resultCount: number): number {
  return Math.min(active, Math.max(resultCount - 1, 0));
}

export function moveActiveIndex(
  key: string,
  active: number,
  resultCount: number,
  setActive: (value: number) => void,
): boolean {
  if (key === "ArrowDown") {
    setActive(Math.min(active + 1, resultCount - 1));
    return true;
  }
  if (key === "ArrowUp") {
    setActive(Math.max(active - 1, 0));
    return true;
  }
  return false;
}

export function handleTabTrap(e: KeyboardEvent, dialogRef: RefObject<HTMLDivElement | null>): void {
  if (e.key !== "Tab") return;
  const focusables = getFocusableElements(dialogRef);
  if (focusables.length === 0) return;
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (!isTabBoundary(e, first, last)) return;
  focusTabBoundary(e, first, last);
}

function focusTabBoundary(e: KeyboardEvent, first: HTMLElement, last: HTMLElement): void {
  e.preventDefault();
  if (e.shiftKey) last.focus();
  else first.focus();
}

function getFocusableElements(dialogRef: RefObject<HTMLDivElement | null>): HTMLElement[] {
  return Array.from(
    dialogRef.current?.querySelectorAll<HTMLElement>('a[href], button, input, [tabindex]:not([tabindex="-1"])') ?? [],
  );
}

function isTabBoundary(e: KeyboardEvent, first: HTMLElement, last: HTMLElement): boolean {
  return e.shiftKey ? document.activeElement === first : document.activeElement === last;
}

export function SectionHeading({ children }: { children: string }) {
  return (
    <div className="px-4 pt-2 pb-1 font-display italic text-xs text-[var(--muted-foreground)]">
      {children}
    </div>
  );
}

function CommandBadge({ command }: { command: Command }) {
  if (command.kind !== "data") return null;
  const badge = TYPE_BADGE[command.type] ?? command.type;
  return <span className="text-[10px] bg-[var(--muted)] px-1.5 py-0.5 rounded font-medium">{badge}</span>;
}

function CommandHint({ command }: { command: Command }) {
  if (!command.hint) return null;
  return <span className="truncate text-xs text-[var(--muted-foreground)] max-w-[160px]">{command.hint}</span>;
}

function CommandMeta({ command }: { command: Command }) {
  return (
    <div className="flex items-center gap-2 shrink-0">
      <CommandBadge command={command} />
      <CommandHint command={command} />
    </div>
  );
}

function CommandHeading({ command, index, navCount }: { command: Command; index: number; navCount: number }) {
  const heading = getCommandHeading(command, index, navCount);
  return heading ? <SectionHeading>{heading}</SectionHeading> : null;
}

function getCommandHeading(command: Command, index: number, navCount: number): string | null {
  if (isFirstData(command, index, navCount)) return "Résultats";
  if (isFirstAction(command, index)) return "Actions rapides";
  return null;
}

function isFirstData(command: Command, index: number, navCount: number): boolean {
  return command.kind === "data" && index === navCount;
}

function isFirstAction(command: Command, index: number): boolean {
  return index === 0 && command.kind === "action";
}

export function CommandOption({
  command,
  index,
  activeIndex,
  listboxId,
  navCount,
  onHover,
  onRun,
}: {
  command: Command;
  index: number;
  activeIndex: number;
  listboxId: string;
  navCount: number;
  onHover: (index: number) => void;
  onRun: (command: Command) => void;
}) {
  const selected = index === activeIndex;
  return (
    <li role="presentation">
      <CommandHeading command={command} index={index} navCount={navCount} />
      <button
        type="button"
        id={`${listboxId}-option-${index}`}
        role="option"
        aria-selected={selected}
        tabIndex={-1}
        onMouseEnter={() => onHover(index)}
        onClick={() => onRun(command)}
        className={optionClassName(selected)}
      >
        <CommandLabel command={command} />
        <CommandMeta command={command} />
      </button>
    </li>
  );
}

function optionClassName(selected: boolean): string {
  return `flex w-full items-center justify-between gap-3 px-4 py-2 text-left text-sm transition-colors ${
    selected ? "bg-[var(--muted)] text-[var(--foreground)]" : "text-[var(--muted-foreground)]"
  }`;
}

function CommandLabel({ command }: { command: Command }) {
  const className = command.kind === "action" ? "text-[var(--ring)]" : "text-[var(--foreground)]";
  return <span className={`font-medium truncate ${className}`}>{command.label}</span>;
}

export function CommandResults({
  results,
  searching,
  activeIndex,
  listboxId,
  navCount,
  onHover,
  onRun,
}: {
  results: Command[];
  searching: boolean;
  activeIndex: number;
  listboxId: string;
  navCount: number;
  onHover: (index: number) => void;
  onRun: (command: Command) => void;
}) {
  if (results.length === 0) {
    return (
      <li role="status" className="px-4 py-3 text-sm text-[var(--muted-foreground)]">
        {searching ? "Recherche en cours" : "Aucun résultat"}
      </li>
    );
  }
  return (
    <>
      {results.map((command, index) => (
        <CommandOption
          key={command.id}
          command={command}
          index={index}
          activeIndex={activeIndex}
          listboxId={listboxId}
          navCount={navCount}
          onHover={onHover}
          onRun={onRun}
        />
      ))}
    </>
  );
}
