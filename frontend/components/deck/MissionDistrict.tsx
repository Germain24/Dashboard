"use client";

import { useSyncExternalStore, type CSSProperties } from "react";
import { motion, useReducedMotion, useTransform, type MotionValue } from "motion/react";
import { MODULE_GROUPS, type Module, type ModuleGroup } from "@/lib/modules";
import { cn } from "@/lib/utils";

const WORLD_WIDTH = 1800;
const WORLD_HEIGHT = 1200;
const WORLD_CENTER = { x: WORLD_WIDTH / 2, y: WORLD_HEIGHT / 2 };

const DISTRICT_LAYOUT: Record<
  ModuleGroup,
  { x: number; y: number; shortLabel: string; accent: string }
> = {
  "Exécution & Système": {
    x: 350,
    y: 270,
    shortLabel: "Le Cadre",
    accent: "var(--warning)",
  },
  "Finances & Ingénierie": {
    x: 850,
    y: 205,
    shortLabel: "Le Comptoir",
    accent: "var(--info)",
  },
  "Santé & Performance": {
    x: 1420,
    y: 340,
    shortLabel: "Les Jardins",
    accent: "var(--success)",
  },
  "Carrière & Études": {
    x: 1430,
    y: 855,
    shortLabel: "L’Académie",
    accent: "var(--tertiary)",
  },
  "Culture & Loisirs": {
    x: 900,
    y: 985,
    shortLabel: "La Place",
    accent: "var(--info)",
  },
  "Style & Horizons": {
    x: 275,
    y: 825,
    shortLabel: "Les Ateliers",
    accent: "var(--muted-foreground)",
  },
  Configuration: {
    x: 900,
    y: 600,
    shortLabel: "Le Noyau",
    accent: "var(--ring)",
  },
};

const MODULE_OFFSETS = [
  { x: -150, y: -38 },
  { x: 0, y: -105 },
  { x: 154, y: -24 },
  { x: -92, y: 112 },
  { x: 96, y: 116 },
];

const CAMERA_TARGETS = [
  { x: 900, y: 600, desktopScale: 1.12, mobileScale: 0.72 },
  ...MODULE_GROUPS.map(({ group }) => {
    const district = DISTRICT_LAYOUT[group];
    return {
      x: district.x,
      y: district.y,
      desktopScale: 1.54,
      mobileScale: 1.02,
    };
  }),
];

function subscribeMobile(callback: () => void) {
  const query = window.matchMedia("(max-width: 767px)");
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}

function getMobileSnapshot() {
  return window.matchMedia("(max-width: 767px)").matches;
}

function getServerMobileSnapshot() {
  return false;
}

type CameraFrame = {
  x: number;
  y: number;
  scale: number;
};

export type CinematicCameraKeyframes = {
  stops: number[];
  x: number[];
  y: number[];
  scale: number[];
  blur: number[];
  gate: number[];
};

function cameraValues(isMobile: boolean): CameraFrame[] {
  return CAMERA_TARGETS.map((target) => {
    const scale = isMobile ? target.mobileScale : target.desktopScale;
    return {
      x: -(target.x - WORLD_CENTER.x) * scale,
      y: -(target.y - WORLD_CENTER.y) * scale,
      scale,
    };
  });
}

function lerp(from: number, to: number, amount: number) {
  return from + (to - from) * amount;
}

/**
 * Construit le mouvement « traversée de décor » de la vidéo de référence.
 * La caméra aspire d'abord le point de sortie, le décor remplit ensuite
 * l'objectif (pic de zoom + flou), puis la scène suivante se révèle et se pose.
 */
export function buildCinematicCameraKeyframes(
  values: CameraFrame[],
  isMobile = false,
): CinematicCameraKeyframes {
  const frames: CinematicCameraKeyframes = {
    stops: [0],
    x: [values[0]?.x ?? 0],
    y: [values[0]?.y ?? 0],
    scale: [values[0]?.scale ?? 1],
    blur: [0],
    gate: [0],
  };

  for (let index = 0; index < values.length - 1; index += 1) {
    const from = values[index];
    const to = values[index + 1];
    const segmentStart = index / (values.length - 1);
    const segmentEnd = (index + 1) / (values.length - 1);
    const duration = segmentEnd - segmentStart;
    const peakScale = Math.max(from.scale, to.scale) * (isMobile ? 1.42 : 1.68);
    const phases = [
      { at: 0.28, travel: 0.16, scale: lerp(from.scale, peakScale, 0.36), blur: 1, gate: 0.1 },
      { at: 0.46, travel: 0.44, scale: peakScale, blur: isMobile ? 4 : 8, gate: 0.92 },
      {
        at: 0.6,
        travel: 0.78,
        scale: lerp(peakScale, to.scale, 0.42),
        blur: isMobile ? 2 : 4,
        gate: 0.54,
      },
      { at: 0.8, travel: 1, scale: to.scale * 1.055, blur: 0.5, gate: 0.08 },
      { at: 1, travel: 1, scale: to.scale, blur: 0, gate: 0 },
    ];

    for (const phase of phases) {
      frames.stops.push(segmentStart + duration * phase.at);
      frames.x.push(lerp(from.x, to.x, phase.travel));
      frames.y.push(lerp(from.y, to.y, phase.travel));
      frames.scale.push(phase.scale);
      frames.blur.push(phase.blur);
      frames.gate.push(phase.gate);
    }
  }

  return frames;
}

function Building({
  module,
  index,
  x,
  y,
  selected,
  onSelect,
}: {
  module: Module;
  index: number;
  x: number;
  y: number;
  selected: boolean;
  onSelect?: (index: number) => void;
}) {
  return (
    <a
      href={`/${module.slug}`}
      className="district-building-link"
      aria-label={`${module.label} — ${module.description}`}
      aria-current={selected ? "location" : undefined}
      onFocus={() => onSelect?.(index)}
      onMouseEnter={() => onSelect?.(index)}
    >
      <g
        className={cn("district-building", selected && "is-selected")}
        transform={`translate(${x} ${y})`}
        style={{ "--building-delay": `${index * 70}ms` } as CSSProperties}
      >
        <title>{module.label}</title>
        <ellipse cx="0" cy="0" rx="72" ry="48" className="district-landmark-hit" />
        <ellipse cx="0" cy="0" rx="65" ry="42" className="district-landmark-ring" />
        <g className="district-landmark-index" transform="translate(-50 -36)">
          <circle r="15" />
          <text textAnchor="middle" dominantBaseline="central">
            {String(index + 1).padStart(2, "0")}
          </text>
        </g>
        <g className="district-building-sign" transform="translate(0 63)">
          <rect x="-57" y="-14" width="114" height="28" rx="14" />
          <text textAnchor="middle" dominantBaseline="central">
            {module.label}
          </text>
        </g>
      </g>
    </a>
  );
}

function District({
  group,
  index,
  active,
  selectedModule,
  onSelectModule,
}: {
  group: (typeof MODULE_GROUPS)[number];
  index: number;
  active: number;
  selectedModule: number;
  onSelectModule?: (index: number) => void;
}) {
  const layout = DISTRICT_LAYOUT[group.group];
  const isActive = active === index + 1;

  return (
    <g
      className={cn("district-quarter", isActive && "is-active")}
      data-district={group.group}
      style={{ "--district-accent": layout.accent } as CSSProperties}
      transform={`translate(${layout.x} ${layout.y})`}
    >
      <ellipse className="district-quarter-focus" rx="244" ry="174" />

      {group.items.map((module, moduleIndex) => {
        const offset = MODULE_OFFSETS[moduleIndex] ?? {
          x: (moduleIndex - 2) * 78,
          y: moduleIndex % 2 ? 90 : -70,
        };
        return (
          <Building
            key={module.slug}
            module={module}
            index={moduleIndex}
            x={offset.x}
            y={offset.y}
            selected={isActive && selectedModule === moduleIndex}
            onSelect={isActive ? onSelectModule : undefined}
          />
        );
      })}

      <g className="district-quarter-label" transform="translate(0 196)">
        <text textAnchor="middle">{layout.shortLabel}</text>
        <text className="district-quarter-number" textAnchor="middle" y="22">
          QUARTIER {String(index + 1).padStart(2, "0")}
        </text>
      </g>
    </g>
  );
}

function LivingModules({ active, selectedModule }: { active: number; selectedModule: number }) {
  return (
    <div className="district-life-layer" aria-hidden="true">
      {MODULE_GROUPS.flatMap((group, groupIndex) => {
        const district = DISTRICT_LAYOUT[group.group];
        return group.items.map((module, moduleIndex) => {
          const offset = MODULE_OFFSETS[moduleIndex] ?? MODULE_OFFSETS[0];
          const Icon = module.icon;
          const visible = active === groupIndex + 1 && selectedModule === moduleIndex;

          return (
            <span
              key={module.slug}
              className={cn("district-life", visible && "is-active")}
              data-module={module.slug}
              style={
                {
                  "--life-x": `${district.x + offset.x}px`,
                  "--life-y": `${district.y + offset.y}px`,
                  "--life-delay": `${-(moduleIndex + groupIndex) * 0.37}s`,
                } as CSSProperties
              }
            >
              <span className="district-life-workbench">
                <Icon className="district-life-icon" strokeWidth={1.7} />
                <span className="district-life-scan" />
                <span className="district-life-particle particle-one" />
                <span className="district-life-particle particle-two" />
                <span className="district-life-particle particle-three" />
              </span>
              <span className={`district-life-worker sprite-${(groupIndex + moduleIndex) % 8}`}>
                <span className="district-life-worker-arm" />
              </span>
            </span>
          );
        });
      })}
    </div>
  );
}

export function MissionDistrict({
  progress,
  active,
  selectedModule,
  onSelectModule,
}: {
  progress: MotionValue<number>;
  active: number;
  selectedModule: number;
  onSelectModule?: (index: number) => void;
}) {
  const reduced = useReducedMotion();
  const isMobile = useSyncExternalStore(
    subscribeMobile,
    getMobileSnapshot,
    getServerMobileSnapshot,
  );
  const values = cameraValues(isMobile);
  const cinematic = buildCinematicCameraKeyframes(values, isMobile);
  const x = useTransform(progress, cinematic.stops, cinematic.x);
  const y = useTransform(progress, cinematic.stops, cinematic.y);
  const scale = useTransform(progress, cinematic.stops, cinematic.scale);
  const cameraFilter = useTransform(
    progress,
    cinematic.stops,
    cinematic.blur.map((blur) => `blur(${blur}px) brightness(${1 - blur * 0.025})`),
  );
  const gateOpacity = useTransform(progress, cinematic.stops, cinematic.gate);
  const gateScale = useTransform(
    progress,
    cinematic.stops,
    cinematic.gate.map((gate) => 1.18 - gate * 0.18),
  );
  const reducedCamera = values[Math.max(0, Math.min(active, values.length - 1))];
  const selectedOffset =
    active > 0 ? (MODULE_OFFSETS[selectedModule] ?? MODULE_OFFSETS[0]) : { x: 0, y: 0 };
  const focusTransition = reduced
    ? { duration: 0 }
    : {
        x: { duration: 1.05, ease: [0.65, 0, 0.35, 1] as const },
        y: { duration: 1.05, ease: [0.65, 0, 0.35, 1] as const },
        scale: {
          duration: 1.05,
          times: [0, 0.48, 1],
          ease: [0.65, 0, 0.35, 1] as const,
        },
      };
  const focusKey = `${active}-${selectedModule}`;

  return (
    <div className="district-viewport" data-overview={active === 0 ? "true" : "false"}>
      <div className="district-sky" aria-hidden="true" />
      <div className="district-world-anchor">
        <motion.div
          className="district-world"
          style={
            reduced
              ? {
                  x: reducedCamera.x,
                  y: reducedCamera.y,
                  scale: reducedCamera.scale,
                }
              : { x, y, scale, filter: cameraFilter }
          }
        >
          <motion.div
            className="district-focus"
            animate={{
              x: -selectedOffset.x,
              y: -selectedOffset.y,
              scale: reduced ? (active > 0 ? 1.19 : 1) : active > 0 ? [1.19, 1.48, 1.19] : 1,
            }}
            transition={focusTransition}
          >
            <svg
              viewBox={`0 0 ${WORLD_WIDTH} ${WORLD_HEIGHT}`}
              role="img"
              aria-label="Carte illustrée des quartiers et modules de Mission Control"
            >
              <image
                href="/images/districts/mission-control-city-game-v3.png"
                width={WORLD_WIDTH}
                height={WORLD_HEIGHT}
                preserveAspectRatio="xMidYMid slice"
                className="district-city-art"
              />

              <g
                className={cn("district-hub", active === 0 && "is-active")}
                transform="translate(900 600)"
                style={{ "--district-accent": "var(--warning)" } as CSSProperties}
              >
                <circle r="80" className="district-hub-ring" />
                <circle r="48" className="district-hub-ring district-hub-ring-inner" />
                <circle r="9" className="district-hub-pulse" />
                <text x="0" y="112" textAnchor="middle" className="district-hub-title">
                  MISSION CONTROL
                </text>
              </g>

              {MODULE_GROUPS.map((group, index) => (
                <District
                  key={group.group}
                  group={group}
                  index={index}
                  active={active}
                  selectedModule={selectedModule}
                  onSelectModule={onSelectModule}
                />
              ))}
            </svg>
            <LivingModules active={active} selectedModule={selectedModule} />
          </motion.div>
        </motion.div>
      </div>
      {!reduced && (
        <>
          <motion.div
            className="district-camera-gate"
            style={{ opacity: gateOpacity, scale: gateScale }}
            data-camera-transition="push-through"
            aria-hidden="true"
          >
            <span className="district-camera-gate-edge district-camera-gate-edge-left" />
            <span className="district-camera-gate-edge district-camera-gate-edge-right" />
          </motion.div>
          {active > 0 && <div key={focusKey} className="district-focus-wipe" aria-hidden="true" />}
        </>
      )}
      <div className="district-atmosphere" aria-hidden="true" />
    </div>
  );
}
