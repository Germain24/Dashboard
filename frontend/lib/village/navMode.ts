"use client";

/**
 * Mode de navigation : le village immersif ou la navigation classique.
 *
 * Même mécanique que le thème et la densité : un attribut sur <html>
 * (`data-nav`), posé avant le premier paint par le script anti-flash du layout,
 * persisté dans localStorage. Le mode `classique` rend l'application
 * exactement comme avant — c'est l'échappatoire garantie si le village gêne.
 */

import { useSyncExternalStore } from "react";

export type NavMode = "village" | "classique";

export const NAV_MODE_KEY = "mc-nav";
export const NAV_MODE_EVENT = "mc:nav-mode";
export const DEFAULT_NAV_MODE: NavMode = "classique";

function isMode(v: unknown): v is NavMode {
  return v === "village" || v === "classique";
}

/** Lit le mode courant depuis <html>, qui fait foi côté client. */
export function readNavMode(): NavMode {
  if (typeof document === "undefined") return DEFAULT_NAV_MODE;
  const v = document.documentElement.dataset.nav;
  return isMode(v) ? v : DEFAULT_NAV_MODE;
}

/** Applique, persiste et diffuse le nouveau mode. */
export function setNavMode(mode: NavMode) {
  document.documentElement.dataset.nav = mode;
  try {
    localStorage.setItem(NAV_MODE_KEY, mode);
  } catch {
    // Mode privé / stockage refusé : le choix vaut pour la session, pas au-delà.
  }
  window.dispatchEvent(new CustomEvent(NAV_MODE_EVENT, { detail: mode }));
}

function subscribe(onChange: () => void) {
  window.addEventListener(NAV_MODE_EVENT, onChange);
  // Bascule faite dans un autre onglet.
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(NAV_MODE_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

/**
 * Mode courant, réactif.
 *
 * Le snapshot serveur vaut toujours `classique` : le HTML rendu côté serveur
 * est donc l'application telle qu'elle existe aujourd'hui, et le village prend
 * le relais à l'hydratation. C'est volontaire — ça garantit qu'une page reste
 * lisible même si le JS ne se charge jamais.
 */
export function useNavMode(): NavMode {
  return useSyncExternalStore(subscribe, readNavMode, () => DEFAULT_NAV_MODE);
}
