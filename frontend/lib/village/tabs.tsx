"use client";

/**
 * Registre d'onglets du village.
 *
 * Contrairement à ce qu'on pourrait croire, `?tab=` ne pilote rien dans ce
 * repo : chaque module garde son onglet actif dans un `useState` local et le
 * passe à `ModuleHeader`. Le village ne peut donc pas changer d'onglet en
 * poussant une URL — il doit appeler le `onChange` du module.
 *
 * D'où ce registre : `ModuleHeader` publie au montage ses onglets, celui qui
 * est actif, et sa fonction de sélection. Le village lit et appelle. Une seule
 * source de vérité, celle qui est déjà à l'écran ; rien à redéclarer dans
 * `lib/modules.ts`, donc rien qui puisse dériver en silence.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

export type PublishedTab = { id: string; label: string };

export type TabsPayload = {
  tabs: PublishedTab[];
  activeId?: string;
  select?: (id: string) => void;
};

type Publish = (payload: TabsPayload) => void;

export type TabsView = { tabs: PublishedTab[]; activeIndex: number };

const EMPTY: TabsView = { tabs: [], activeIndex: 0 };

/**
 * TROIS contextes, et la séparation est essentielle : la fonction de
 * publication doit garder une identité stable. Réunies dans un seul objet,
 * publier changerait la valeur du contexte, ce qui relancerait l'effet de
 * publication, dont le nettoyage publierait un registre vide, qui relancerait
 * l'effet… Le registre oscillait ainsi entre « 6 onglets » et « aucun ».
 */
const TabsContext = createContext<TabsView>(EMPTY);
const PublishContext = createContext<Publish | null>(null);
const SelectContext = createContext<((index: number) => void) | null>(null);

export function VillageTabsProvider({ children }: { children: React.ReactNode }) {
  const [view, setView] = useState<TabsView>(EMPTY);
  // La fonction de sélection change d'identité à chaque rendu de la page ;
  // la garder dans une ref évite de re-rendre tout le village pour ça.
  const selectRef = useRef<TabsPayload["select"]>(undefined);
  const tabsRef = useRef<PublishedTab[]>([]);

  const publish = useCallback<Publish>(({ tabs, activeId, select }) => {
    selectRef.current = select;
    tabsRef.current = tabs;
    const found = tabs.findIndex((t) => t.id === activeId);
    const activeIndex = found === -1 ? 0 : found;
    setView((prev) =>
      prev.activeIndex === activeIndex &&
      prev.tabs.length === tabs.length &&
      prev.tabs.every((t, i) => t.id === tabs[i].id && t.label === tabs[i].label)
        ? prev
        : { tabs, activeIndex },
    );
  }, []);

  const selectIndex = useCallback((index: number) => {
    const tab = tabsRef.current[index];
    if (tab) selectRef.current?.(tab.id);
  }, []);

  return (
    <PublishContext.Provider value={publish}>
      <SelectContext.Provider value={selectIndex}>
        <TabsContext.Provider value={view}>{children}</TabsContext.Provider>
      </SelectContext.Provider>
    </PublishContext.Provider>
  );
}

/** Onglets du module affiché et index de l'onglet actif (vide hors module). */
export function useVillageTabs(): TabsView {
  return useContext(TabsContext);
}

/** Active l'onglet d'index donné, en passant par le module lui-même. */
export function useSelectVillageTab() {
  return useContext(SelectContext);
}

/**
 * Publie les onglets du module courant. Appelé par `ModuleHeader` ; inerte
 * hors du village (pas de provider monté).
 */
export function usePublishVillageTabs(payload: TabsPayload | null) {
  const publish = useContext(PublishContext);
  // Signature du contenu : c'est elle, et non l'identité des objets, qui doit
  // déclencher une republication.
  const key = payload
    ? `${payload.activeId ?? ""}|${payload.tabs.map((t) => `${t.id} ${t.label}`).join(",")}`
    : "";

  const latest = useRef(payload);
  useEffect(() => {
    latest.current = payload;
  });

  useEffect(() => {
    if (!publish) return;
    publish(latest.current ?? { tabs: [] });
    return () => publish({ tabs: [] });
  }, [key, publish]);
}
