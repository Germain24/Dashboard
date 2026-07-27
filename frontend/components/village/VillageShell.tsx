"use client";

/**
 * Point d'entrée du village.
 *
 * Enveloppe tout le contenu de l'application. La structure rendue ici est
 * **toujours la même**, serveur comme client, quel que soit le mode : un arbre
 * qui change de forme à l'hydratation laisse le DOM rendu par le serveur
 * orphelin à l'écran (on se retrouve avec deux pages module empilées). Le
 * choix du mode se fait donc un cran plus bas, dans `VillageRuntime`, qui
 * renvoie ses enfants tels quels en mode classique.
 *
 * Le `<Suspense>` n'est pas décoratif non plus : `VillageRuntime` appelle
 * `useSearchParams()`, et sans frontière App Router refuse de prérendre.
 */

import { Suspense } from "react";
import { VillageTabsProvider } from "@/lib/village/tabs";
import { VillageRuntime } from "@/components/village/VillageRuntime";

export function VillageShell({ children }: { children: React.ReactNode }) {
  return (
    <VillageTabsProvider>
      {children}
      {/*
        Les enfants sont DEHORS de cette frontière, et ça n'est pas négociable :
        `VillageRuntime` appelle `useSearchParams()`, ce qui oblige Next à
        streamer un placeholder de Suspense pour ce sous-arbre. Y enfermer
        l'application entière laissait cohabiter la version serveur et la
        version client — deux pages module empilées à l'écran.
      */}
      <Suspense fallback={null}>
        <VillageRuntime />
      </Suspense>
    </VillageTabsProvider>
  );
}
