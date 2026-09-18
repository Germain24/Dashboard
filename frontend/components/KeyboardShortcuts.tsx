"use client";

/**
 * Raccourcis clavier globaux de navigation entre modules.
 *
 *   j / k             : module suivant / précédent (ordre de la liste MODULES)
 *   g puis h          : accueil
 *   g puis 1, 2, 3, 4 : secteur du Deck (accueil uniquement)
 *
 * Ignoré quand le focus est dans un champ de saisie ou qu'un overlay est ouvert.
 */

import { useEffect, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";
import { MODULES } from "@/lib/modules";
import { isInteractiveOverlayOpen } from "@/lib/interactive-overlays";

function isTyping(el: EventTarget | null): boolean {
  const node = el as HTMLElement | null;
  if (!node) return false;
  const tag = node.tagName;
  return new Set(["INPUT", "TEXTAREA", "SELECT"]).has(tag) || Boolean(node.isContentEditable);
}

function createNavigator(pathname: string, router: ReturnType<typeof useRouter>) {
  const slugs = MODULES.map((module) => module.slug);
  return (delta: number) => {
    const current = pathname.split("/").filter(Boolean)[0];
    const index = current ? slugs.indexOf(current) : -1;
    const next =
      index === -1
        ? delta > 0
          ? 0
          : slugs.length - 1
        : (index + delta + slugs.length) % slugs.length;
    router.push("/" + slugs[next]);
  };
}

function getSequenceAction(
  event: KeyboardEvent,
  router: ReturnType<typeof useRouter>,
): (() => void) | null {
  if (event.key === "h") return () => router.push("/");
  const section = Number.parseInt(event.key, 10);
  if (section >= 1 && section <= 4) {
    return () => window.dispatchEvent(new CustomEvent("mc:deck-goto", { detail: section - 1 }));
  }
  return null;
}

function hasRecentG(
  lastKey: React.MutableRefObject<{ key: string; at: number } | null>,
  now: number,
): boolean {
  return Boolean(lastKey.current && lastKey.current.key === "g" && now - lastKey.current.at < 800);
}

function handleKeySequence(
  event: KeyboardEvent,
  now: number,
  lastKey: React.MutableRefObject<{ key: string; at: number } | null>,
  router: ReturnType<typeof useRouter>,
): boolean {
  if (!hasRecentG(lastKey, now)) return false;
  const action = getSequenceAction(event, router);
  if (!action) return false;
  action();
  lastKey.current = null;
  return true;
}

function handleNavigationKey(event: KeyboardEvent, go: (delta: number) => void): void {
  if (event.key === "j") go(1);
  if (event.key === "k") go(-1);
}

function shouldIgnoreShortcut(event: KeyboardEvent): boolean {
  return (
    event.metaKey ||
    event.ctrlKey ||
    event.altKey ||
    isTyping(event.target) ||
    isInteractiveOverlayOpen()
  );
}

export function KeyboardShortcuts() {
  const router = useRouter();
  const pathname = usePathname() ?? "/";
  const lastKey = useRef<{ key: string; at: number } | null>(null);

  useEffect(() => {
    const go = createNavigator(pathname, router);

    function onKey(e: KeyboardEvent) {
      if (shouldIgnoreShortcut(e)) {
        lastKey.current = null;
        return;
      }
      const now = Date.now();
      if (handleKeySequence(e, now, lastKey, router)) return;
      handleNavigationKey(e, go);
      lastKey.current = { key: e.key, at: now };
    }

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router, pathname]);

  return null;
}
