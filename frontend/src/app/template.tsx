"use client";

/**
 * Template App Router : remonté à chaque navigation, ce qui permet une
 * transition d'entrée cohérente entre les modules. Respecte
 * `prefers-reduced-motion` (l'animation est désactivée via CSS si réduite).
 */

export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="page-transition">{children}</div>;
}
