"use client";

/**
 * Le village en marche : une **surcouche**, pas un emballage.
 *
 * Il ne rend jamais le contenu de l'application — celui-ci vit à sa place
 * habituelle dans l'arbre. Cette séparation est structurelle : `useSearchParams`
 * force une frontière `<Suspense>`, et y enfermer toute l'application faisait
 * cohabiter le sous-arbre streamé par le serveur et celui rendu par le client
 * (deux pages module empilées, deux barres d'onglets).
 *
 * Le monde reste monté à TOUS les niveaux, contenu compris. C'est ce qui porte
 * la continuité : au niveau 3 il passe simplement derrière la page, flouté, si
 * bien que ressortir fait reculer la caméra depuis la façade au lieu de
 * repartir de zéro.
 */

import { useEffect } from "react";
import { useNavMode } from "@/lib/village/navMode";
import { useVillage } from "@/lib/village/useVillage";
import { useVillageTabs } from "@/lib/village/tabs";
import { VillageHud } from "@/components/village/VillageHud";
import { VillageStage } from "@/components/village/VillageStage";

export function VillageRuntime() {
  const mode = useNavMode();
  const tabs = useVillageTabs();
  const village = mode === "village";
  const { state, dispatch } = useVillage(tabs, village);

  // Marque le document tant que le village est réellement aux commandes : le
  // CSS s'en sert pour masquer le Dock, le fil d'Ariane et la nav mobile, et
  // pour faire passer le monde derrière la page au niveau 3.
  useEffect(() => {
    const root = document.documentElement;
    if (state) {
      root.setAttribute("data-village-active", "");
      root.setAttribute("data-village-level", String(state.level));
    } else {
      root.removeAttribute("data-village-active");
      root.removeAttribute("data-village-level");
    }
    return () => {
      root.removeAttribute("data-village-active");
      root.removeAttribute("data-village-level");
    };
  }, [state]);

  if (!state) return null;

  return (
    <>
      {/* Cliquer avance d'un niveau : le geste au scroll n'est pas devinable
          pour qui arrive, et le clavier ne sert que ceux qui le cherchent. */}
      <div
        className="village-click"
        onClick={() => dispatch("enter")}
        role="presentation"
      >
        <VillageStage state={state} />
      </div>

      <VillageHud state={state} tabLabel={tabs.tabs[state.tabIndex]?.label} />
    </>
  );
}
