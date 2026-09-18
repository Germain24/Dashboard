"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, ArrowUpRight } from "lucide-react";
import { gsap } from "gsap";
import { SPATIAL_ACCENTS } from "@/lib/design/colors";
import { MODULES, type Module, type ModuleGroup } from "@/lib/modules";
import { isInteractiveOverlayOpen } from "@/lib/interactive-overlays";

type Chapter = {
  id: string;
  title: string;
  eyebrow: string;
  description: string;
  groups: ModuleGroup[];
  accent: string;
};

const CHAPTERS: Chapter[] = [
  {
    id: "finance",
    title: "Finance",
    eyebrow: "Capital & trajectoire",
    description: "Piloter les flux, protéger le patrimoine et construire les options de demain.",
    groups: ["Finances & Ingénierie"],
    accent: SPATIAL_ACCENTS.finance,
  },
  {
    id: "projets",
    title: "Projets",
    eyebrow: "Système & exécution",
    description: "Transformer les objectifs en séquences concrètes, mesurables et automatisées.",
    groups: ["Exécution & Système", "Carrière & Études", "Configuration"],
    accent: SPATIAL_ACCENTS.projets,
  },
  {
    id: "sante",
    title: "Santé",
    eyebrow: "Corps & performance",
    description: "Lire les signaux du corps, organiser l’effort et rendre la récupération visible.",
    groups: ["Santé & Performance"],
    accent: SPATIAL_ACCENTS.sante,
  },
  {
    id: "vie",
    title: "Vie",
    eyebrow: "Culture & horizons",
    description: "Habiter pleinement le temps libre, le style, les voyages et les curiosités.",
    groups: ["Culture & Loisirs", "Style & Horizons"],
    accent: SPATIAL_ACCENTS.vie,
  },
];

function modulesFor(chapter: Chapter) {
  return MODULES.filter((module) => chapter.groups.includes(module.group));
}

function isTyping(target: EventTarget | null) {
  const element = target as HTMLElement | null;
  return (
    element?.isContentEditable ||
    element?.tagName === "INPUT" ||
    element?.tagName === "TEXTAREA" ||
    element?.tagName === "SELECT"
  );
}

function ModulePanel({
  module,
  chapter,
  index,
  active,
  intro,
}: {
  module: Module;
  chapter: Chapter;
  index: number;
  active: boolean;
  intro?: ReactNode;
}) {
  const Icon = module.icon;
  return (
    <article
      className="spatial-panel"
      data-spatial-panel
      data-module={module.slug}
      data-active={active ? "true" : "false"}
      aria-hidden={!active}
      inert={!active}
    >
      <div className="spatial-panel-content">
        <p className="spatial-kicker" data-reveal>
          <span>{String(index).padStart(2, "0")}</span>
          {chapter.eyebrow}
        </p>
        <div className="spatial-title-row" data-reveal>
          <span className="spatial-module-icon">
            <Icon aria-hidden="true" />
          </span>
          <h3>{module.label}</h3>
        </div>
        <p className="spatial-panel-description" data-reveal>
          {module.description}
        </p>

        <div className="spatial-glass-card spatial-functions-card" data-reveal>
          <span className="spatial-data-label">Fonctions principales</span>
          <ul>
            {module.capabilities.map((capability) => (
              <li key={capability}>{capability}</li>
            ))}
          </ul>
        </div>

        <Link href={`/${module.slug}`} className="spatial-open-link" data-reveal>
          Ouvrir {module.label}
          <ArrowUpRight aria-hidden="true" />
        </Link>
        {intro && <div className="spatial-intro-slot">{intro}</div>}
      </div>
    </article>
  );
}

function SpatialChapter({
  chapter,
  chapterIndex,
  activeChapter,
  activePanel,
  trackRef,
  intro,
}: {
  chapter: Chapter;
  chapterIndex: number;
  activeChapter: number;
  activePanel: number;
  trackRef: (element: HTMLDivElement | null) => void;
  intro?: ReactNode;
}) {
  const modules = modulesFor(chapter);
  const chapterActive = chapterIndex === activeChapter;

  return (
    <section
      id={chapter.id}
      className="spatial-chapter"
      aria-label={chapter.title}
      aria-hidden={!chapterActive}
      data-active={chapterActive ? "true" : "false"}
      style={{ "--spatial-accent": chapter.accent } as CSSProperties}
    >
      <div className="spatial-chapter-label">
        <span>{String(chapterIndex + 1).padStart(2, "0")}</span>
        {chapter.title}
      </div>
      <div ref={trackRef} className="spatial-track">
        {modules.map((module, moduleIndex) => (
          <ModulePanel
            key={module.slug}
            module={module}
            chapter={chapter}
            index={moduleIndex + 1}
            active={chapterActive && activePanel === moduleIndex}
            intro={moduleIndex === 0 ? intro : undefined}
          />
        ))}
      </div>
    </section>
  );
}

export function SpatialGrid({ intro }: { intro?: ReactNode }) {
  const stageRef = useRef<HTMLDivElement>(null);
  const trackRefs = useRef<(HTMLDivElement | null)[]>([]);
  const [activeChapter, setActiveChapter] = useState(0);
  const [activePanel, setActivePanel] = useState(0);
  const panelCounts = useMemo(() => CHAPTERS.map((chapter) => modulesFor(chapter).length), []);
  const reducedMotion =
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const goVertical = useCallback(
    (delta: number) => {
      const nextChapter = Math.max(0, Math.min(CHAPTERS.length - 1, activeChapter + delta));
      if (nextChapter === activeChapter) return;
      setActiveChapter(nextChapter);
      setActivePanel(0);
    },
    [activeChapter],
  );

  const goHorizontal = useCallback(
    (delta: number) => {
      setActivePanel((current) =>
        Math.max(0, Math.min(panelCounts[activeChapter] - 1, current + delta)),
      );
    },
    [activeChapter, panelCounts],
  );

  const goToChapter = useCallback((index: number) => {
    setActiveChapter(Math.max(0, Math.min(CHAPTERS.length - 1, index)));
    setActivePanel(0);
  }, []);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (
        event.metaKey ||
        event.ctrlKey ||
        event.altKey ||
        isTyping(event.target) ||
        isInteractiveOverlayOpen()
      )
        return;
      if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key)) return;
      event.preventDefault();
      if (event.key === "ArrowUp") goVertical(-1);
      if (event.key === "ArrowDown") goVertical(1);
      if (event.key === "ArrowLeft") goHorizontal(-1);
      if (event.key === "ArrowRight") goHorizontal(1);
    };
    const handleDeckGoto = (event: Event) => goToChapter((event as CustomEvent<number>).detail);

    window.addEventListener("keydown", handleKey);
    window.addEventListener("mc:deck-goto", handleDeckGoto);
    return () => {
      window.removeEventListener("keydown", handleKey);
      window.removeEventListener("mc:deck-goto", handleDeckGoto);
    };
  }, [goHorizontal, goToChapter, goVertical]);

  useLayoutEffect(() => {
    const duration = reducedMotion ? 0 : 0.9;
    gsap.to(stageRef.current, {
      y: -activeChapter * window.innerHeight,
      duration,
      ease: "power3.inOut",
      overwrite: true,
    });
    trackRefs.current.forEach((track, index) => {
      gsap.to(track, {
        x: index === activeChapter ? -activePanel * window.innerWidth : 0,
        duration,
        ease: "power3.inOut",
        overwrite: true,
      });
    });

    const currentTrack = trackRefs.current[activeChapter];
    const currentPanel =
      currentTrack?.querySelectorAll<HTMLElement>("[data-spatial-panel]")[activePanel];
    const revealItems = currentPanel?.querySelectorAll("[data-reveal]");
    if (revealItems?.length) {
      gsap.fromTo(
        revealItems,
        { y: reducedMotion ? 0 : 32, autoAlpha: 0 },
        {
          y: 0,
          autoAlpha: 1,
          duration: reducedMotion ? 0 : 0.72,
          stagger: reducedMotion ? 0 : 0.09,
          delay: reducedMotion ? 0 : 0.2,
          ease: "power3.out",
          overwrite: true,
        },
      );
    }
  }, [activeChapter, activePanel, reducedMotion]);

  useEffect(() => {
    const handleResize = () => {
      gsap.set(stageRef.current, { y: -activeChapter * window.innerHeight });
      trackRefs.current.forEach((track, index) => {
        gsap.set(track, { x: index === activeChapter ? -activePanel * window.innerWidth : 0 });
      });
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [activeChapter, activePanel]);

  const currentChapter = CHAPTERS[activeChapter];
  const currentModules = modulesFor(currentChapter);
  const currentPanelLabel = currentModules[activePanel]?.label;

  return (
    <div className="spatial-grid" aria-label="Dashboard spatial">
      <nav className="spatial-grid-nav" aria-label="Secteurs principaux">
        {CHAPTERS.map((chapter, index) => (
          <button
            key={chapter.id}
            type="button"
            data-active={index === activeChapter ? "true" : "false"}
            aria-current={index === activeChapter ? "page" : undefined}
            onClick={() => goToChapter(index)}
          >
            <span>{String(index + 1).padStart(2, "0")}</span>
            {chapter.title}
          </button>
        ))}
      </nav>

      <div ref={stageRef} className="spatial-grid-stage">
        {CHAPTERS.map((chapter, index) => (
          <SpatialChapter
            key={chapter.id}
            chapter={chapter}
            chapterIndex={index}
            activeChapter={activeChapter}
            activePanel={index === activeChapter ? activePanel : 0}
            trackRef={(element) => {
              trackRefs.current[index] = element;
            }}
            intro={index === 0 ? intro : undefined}
          />
        ))}
      </div>

      <div className="spatial-position" aria-live="polite">
        <span>
          {String(activeChapter + 1).padStart(2, "0")} / {String(CHAPTERS.length).padStart(2, "0")}
        </span>
        <strong>{currentChapter.title}</strong>
        <i />
        <span>
          {String(activePanel + 1).padStart(2, "0")} /{" "}
          {String(panelCounts[activeChapter]).padStart(2, "0")}
        </span>
        <strong>{currentPanelLabel}</strong>
      </div>

      <div className="spatial-keyboard-hint" aria-hidden="true">
        <span>
          <kbd>↑</kbd>
          <kbd>↓</kbd>
          Secteurs
        </span>
        <span>
          <kbd>←</kbd>
          <kbd>→</kbd>
          Sous-sections
        </span>
      </div>

      <div className="spatial-dpad" aria-label="Navigation spatiale">
        <button
          type="button"
          onClick={() => goVertical(-1)}
          disabled={activeChapter === 0}
          aria-label="Secteur précédent"
        >
          <ArrowUp />
        </button>
        <button
          type="button"
          onClick={() => goHorizontal(-1)}
          disabled={activePanel === 0}
          aria-label="Sous-section précédente"
        >
          <ArrowLeft />
        </button>
        <button
          type="button"
          onClick={() => goHorizontal(1)}
          disabled={activePanel === panelCounts[activeChapter] - 1}
          aria-label="Sous-section suivante"
        >
          <ArrowRight />
        </button>
        <button
          type="button"
          onClick={() => goVertical(1)}
          disabled={activeChapter === CHAPTERS.length - 1}
          aria-label="Secteur suivant"
        >
          <ArrowDown />
        </button>
      </div>
    </div>
  );
}
