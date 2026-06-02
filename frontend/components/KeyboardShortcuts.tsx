"use client";

/**
 * Raccourcis clavier globaux de navigation entre modules.
 *
 *   j / k        : module suivant / précédent (ordre de la liste MODULES)
 *   g puis h     : accueil
 *
 * Ignoré quand le focus est dans un champ de saisie. (« n = nouveau » est
 * spécifique à chaque module : laissé à l'implémentation de chaque vue.)
 */

import { useEffect, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";
import { MODULES } from "@/lib/modules";

function isTyping(el: EventTarget | null): boolean {
  const node = el as HTMLElement | null;
  if (!node) return false;
  const tag = node.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || node.isContentEditable;
}

export function KeyboardShortcuts() {
  const router = useRouter();
  const pathname = usePathname() ?? "/";
  const lastKey = useRef<{ key: string; at: number } | null>(null);

  useEffect(() => {
    const slugs = MODULES.map((m) => m.slug);

    function go(delta: number) {
      const current = pathname.split("/").filter(Boolean)[0];
      const idx = current ? slugs.indexOf(current) : -1;
      const next = idx === -1 ? (delta > 0 ? 0 : slugs.length - 1) : (idx + delta + slugs.length) % slugs.length;
      router.push("/" + slugs[next]);
    }

    function onKey(e: KeyboardEvent) {
      if (e.metaKey || e.ctrlKey || e.altKey || isTyping(e.target)) return;
      const now = Date.now();
      // Séquence "g h" -> accueil
      if (lastKey.current && lastKey.current.key === "g" && now - lastKey.current.at < 600 && e.key === "h") {
        router.push("/");
        lastKey.current = null;
        return;
      }
      if (e.key === "j") go(1);
      else if (e.key === "k") go(-1);
      lastKey.current = { key: e.key, at: now };
    }

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router, pathname]);

  return null;
}
