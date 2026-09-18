"use client";

import { useEffect, useRef, useState, useSyncExternalStore, type RefObject } from "react";
import { handleTabTrap } from "@/components/CommandPaletteParts";
import { isInteractiveOverlayOpen } from "@/lib/interactive-overlays";

type Shortcut = { keys: string[]; label: string };

function shortcuts(isMac: boolean): Shortcut[] {
  const mod = isMac ? "⌘" : "Ctrl";
  return [
    { keys: [mod, "K"], label: "Rechercher, aller à un module" },
    { keys: ["J"], label: "Module suivant" },
    { keys: ["K"], label: "Module précédent" },
    { keys: ["G", "puis", "H"], label: "Accueil (Deck)" },
    { keys: ["G", "puis", "1–4"], label: "Secteur du Deck" },
    { keys: ["Tab"], label: "Naviguer entre les éléments" },
    { keys: ["Échap"], label: "Fermer les dialogues" },
    { keys: ["?"], label: "Afficher cette aide" },
  ];
}

function isTyping(el: EventTarget | null): boolean {
  const node = el as HTMLElement | null;
  if (!node) return false;
  return (
    new Set(["INPUT", "TEXTAREA", "SELECT"]).has(node.tagName) || Boolean(node.isContentEditable)
  );
}

function shouldIgnoreHelpKey(event: KeyboardEvent): boolean {
  return (
    event.metaKey ||
    event.ctrlKey ||
    event.altKey ||
    isTyping(event.target) ||
    isInteractiveOverlayOpen()
  );
}

function handleHelpKey(event: KeyboardEvent, open: () => void): void {
  if (shouldIgnoreHelpKey(event)) return;
  if (event.key !== "?") return;
  event.preventDefault();
  open();
}

function useShortcutsOpen(setOpen: (open: boolean) => void): void {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => handleHelpKey(event, () => setOpen(true));
    const onEvent = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("mc:shortcuts", onEvent);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mc:shortcuts", onEvent);
    };
  }, [setOpen]);
}

function closeOutside(
  event: MouseEvent,
  dialogRef: RefObject<HTMLDivElement | null>,
  close: () => void,
): void {
  if (dialogRef.current && !dialogRef.current.contains(event.target as Node)) close();
}

function useShortcutsLifecycle(
  open: boolean,
  dialogRef: RefObject<HTMLDivElement | null>,
  closeRef: RefObject<HTMLButtonElement | null>,
  close: () => void,
): void {
  useEffect(() => {
    if (!open) return;
    const restore = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      close();
    };
    const onTab = (event: KeyboardEvent) => handleTabTrap(event, dialogRef);
    const onPointer = (event: MouseEvent) => closeOutside(event, dialogRef, close);
    document.addEventListener("keydown", onKey);
    document.addEventListener("keydown", onTab);
    document.addEventListener("mousedown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("keydown", onTab);
      document.removeEventListener("mousedown", onPointer);
      restore?.focus();
    };
  }, [close, closeRef, dialogRef, open]);
}

const noSubscribe = () => () => undefined;
const getPlatform = () => /Mac|iPhone|iPad|iPod/.test(navigator.userAgent);
const getServerPlatform = () => false;

export function ShortcutsHelp() {
  const [open, setOpen] = useState(false);
  const isMac = useSyncExternalStore(noSubscribe, getPlatform, getServerPlatform);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  useShortcutsOpen(setOpen);
  useShortcutsLifecycle(open, dialogRef, closeRef, () => setOpen(false));
  if (!open) return null;
  return (
    <ShortcutsDialog
      isMac={isMac}
      dialogRef={dialogRef}
      closeRef={closeRef}
      close={() => setOpen(false)}
    />
  );
}

function ShortcutsDialog({
  isMac,
  dialogRef,
  closeRef,
  close,
}: {
  isMac: boolean;
  dialogRef: RefObject<HTMLDivElement | null>;
  closeRef: RefObject<HTMLButtonElement | null>;
  close: () => void;
}) {
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
            onClick={close}
            aria-label="Fermer"
            className="rounded-[var(--radius-sm)] px-1.5 text-sm text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
          >
            Échap
          </button>
        </div>
        <ul className="divide-y divide-[var(--border)]">
          {shortcuts(isMac).map((shortcut) => (
            <ShortcutRow key={shortcut.label} shortcut={shortcut} />
          ))}
        </ul>
      </div>
    </div>
  );
}

function ShortcutRow({ shortcut }: { shortcut: Shortcut }) {
  return (
    <li className="flex items-center justify-between gap-4 px-4 py-2.5">
      <span className="text-sm text-[var(--foreground)]">{shortcut.label}</span>
      <ShortcutKeys keys={shortcut.keys} />
    </li>
  );
}

function ShortcutKeys({ keys }: { keys: string[] }) {
  return (
    <span className="flex shrink-0 items-center gap-1">
      {keys.map((key, index) => (
        <ShortcutKey key={`${key}-${index}`} value={key} />
      ))}
    </span>
  );
}

function ShortcutKey({ value }: { value: string }) {
  if (value === "puis") return <span className="text-xs text-[var(--muted-foreground)]">puis</span>;
  return (
    <kbd className="rounded border border-[var(--border)] bg-[var(--muted)] px-1.5 py-0.5 text-[11px] font-medium text-[var(--foreground)]">
      {value}
    </kbd>
  );
}
