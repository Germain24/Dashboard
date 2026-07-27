"use client";

/**
 * Façade d'un bâtiment (ou vue d'un quartier).
 *
 * Rend l'image isométrique quand elle existe dans `public/village/`, sinon une
 * façade procédurale bâtie sur l'accent du quartier et l'icône du module. Le
 * repli n'est pas un pis-aller temporaire : il reste la garantie qu'un module
 * ajouté demain, sans visuel, s'affiche correctement.
 */

import Image from "next/image";
import type { LucideIcon } from "lucide-react";

type Props = {
  /** Visuel généré, ou `null` pour la façade procédurale. */
  src: string | null;
  /** Couleur d'accent du quartier (hex). */
  accent: string;
  icon: LucideIcon;
  label: string;
  /** L'élément est-il celui qu'on regarde ? Pilote le chargement prioritaire. */
  active?: boolean;
  /**
   * Voisin immédiat de l'élément actif. On le charge sans attendre : le rail
   * n'a qu'une case d'avance, et une image encore paresseuse au moment où on
   * arrive dessus laisse une carte vide le temps du décodage.
   */
  near?: boolean;
};

export function VillageArt({
  src,
  accent,
  icon: Icon,
  label,
  active = false,
  near = false,
}: Props) {
  if (src) {
    return (
      <Image
        src={src}
        alt=""
        fill
        sizes="(max-width: 768px) 92vw, 720px"
        priority={active}
        loading={active || near ? "eager" : "lazy"}
        className="object-contain"
      />
    );
  }

  /*
    Les encres du design system (marine, bordeaux) sont presque noires : mêlées
    à du transparent sur un fond sombre, elles disparaissent. On les mélange
    donc au `--foreground` du thème courant, ce qui les éclaircit en sombre et
    les fonce en clair — la façade garde du contraste dans les deux thèmes.
  */
  const ink = `color-mix(in srgb, ${accent} 55%, var(--foreground))`;
  const tint = (pct: number) => `color-mix(in srgb, ${ink} ${pct}%, transparent)`;

  return (
    <div
      aria-hidden="true"
      className="absolute inset-0 overflow-hidden rounded-[var(--radius-lg)]"
      style={{
        background: `linear-gradient(160deg, ${tint(30)}, ${tint(10)})`,
        border: `1px solid ${tint(28)}`,
        boxShadow: `inset 0 1px 0 0 ${tint(35)}`,
      }}
    >
      {/* Bandeau de toit */}
      <div className="absolute inset-x-0 top-0 h-[18%]" style={{ background: tint(45) }} />
      {/* Trame de fenêtres */}
      <div className="absolute inset-x-[12%] top-[28%] grid grid-cols-4 gap-[6%]">
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            className="aspect-square rounded-[3px]"
            style={{ background: tint(i % 3 === 0 ? 55 : 24) }}
          />
        ))}
      </div>
      <Icon
        className="absolute bottom-[8%] right-[8%] h-[26%] w-auto"
        style={{ color: tint(70) }}
        strokeWidth={1.25}
      />
      <span className="sr-only">{label}</span>
    </div>
  );
}
