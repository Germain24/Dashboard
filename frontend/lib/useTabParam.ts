"use client";

/**
 * Onglet actif reflété dans l'URL (`?tab=`) — audit §2.B.
 *
 * Drop-in remplaçant de `useState(defaut)` pour l'onglet d'un module : la valeur
 * vit dans la query string, ce qui apporte d'un coup le lien profond
 * (`/finance?tab=buffett`), le Retour navigateur qui défait un changement
 * d'onglet, la survie au F5 et la mise en favori d'une vue précise.
 *
 * `router.push(..., { scroll: false })` : les changements d'onglet restent
 * navigables avec Retour/Avancer sans faire sauter le scroll. La valeur retournée est
 * toujours dérivée de l'URL, avec repli sur `defaut` si `?tab=` est absent ou
 * inconnu.
 */

import { useCallback } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

type TabOptions<T extends string> = { key?: string; allowed?: readonly T[] };

function optionKey<T extends string>(options?: TabOptions<T>) {
  return options?.key ?? "tab";
}

function isAllowed<T extends string>(raw: string | null, allowed?: readonly T[]) {
  if (raw == null) return false;
  if (!allowed) return true;
  return allowed.includes(raw as T);
}

function activeTab<T extends string>(raw: string | null, defaut: T, allowed?: readonly T[]) {
  if (!isAllowed(raw, allowed)) return defaut;
  return raw as T;
}

export function useTabParam<T extends string>(
  defaut: T,
  options?: TabOptions<T>,
): [T, (id: T) => void] {
  const key = optionKey(options);
  const allowed = options?.allowed;
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const raw = searchParams.get(key);
  const active = activeTab(raw, defaut, allowed);

  const setActive = useCallback(
    (id: T) => {
      const params = new URLSearchParams(searchParams.toString());
      // L'onglet par défaut ne pollue pas l'URL (URL propre au premier chargement).
      if (id === defaut) params.delete(key);
      else params.set(key, id);
      const qs = params.toString();
      router.push(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname, searchParams, key, defaut],
  );

  return [active, setActive];
}
