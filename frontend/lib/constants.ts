/**
 * Constantes partagées : seuils métier et couleurs sémantiques.
 * Évite la dispersion de valeurs magiques dans les composants.
 */

/** Couleurs sémantiques (référencent les variables CSS du thème). */
export const COLORS = {
  success: "var(--success, #16a34a)",
  destructive: "var(--destructive)",
  warning: "#f59e0b",
  ring: "var(--ring)",
  muted: "var(--muted-foreground)",
} as const;

/** Score thermique d'une tenue (garde-robe). */
export const THERMAL = {
  /** Bonus multiplicatif par couche supplémentaire. */
  layerBonus: 0.1,
  /** Apport d'un body en coton. */
  bodyBonus: 1.5,
  /** Écart toléré (±) entre score et cible avant alerte. */
  tolerance: 2,
} as const;

/** Seuils de concentration de portefeuille (HHI). */
export const HHI = {
  high: 0.25,
  moderate: 0.1,
} as const;

/** Seuils Buffett (score MOAT). */
export const BUFFETT = {
  /** Score d'un ETF (catégorie à part). */
  etfScore: 200,
  /** Seuil d'éligibilité par défaut. */
  eligible: 80,
} as const;

/** Couleur d'une variation de performance. */
export function perfColor(pct: number | null | undefined): string {
  if (pct == null) return COLORS.muted;
  if (pct > 0) return COLORS.success;
  if (pct < 0) return COLORS.destructive;
  return COLORS.muted;
}
