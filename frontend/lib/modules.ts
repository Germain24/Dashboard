import {
  BookOpen,
  Calendar,
  ChefHat,
  Database,
  Dumbbell,
  Film,
  FolderOpen,
  GraduationCap,
  HeartPulse,
  ListTodo,
  Music,
  Settings,
  Shirt,
  Smile,
  Sparkles,
  TrendingUp,
  Tv,
  Wallet,
  Zap,
  type LucideIcon,
} from "lucide-react";

/**
 * Source de vérité unique de la navigation.
 *
 * Tous les points d'entrée de navigation (sidebar desktop, drawer mobile,
 * grille d'accueil, palette de commandes, raccourcis j/k, fil d'Ariane)
 * dérivent de cette liste. Ne jamais redéclarer une liste de modules ailleurs :
 * un module qui n'est pas ici n'existe nulle part dans la nav, et un module
 * présent ici l'est partout, dans le même ordre, avec la même icône.
 */

export type ModuleGroup =
  | "Quotidien"
  | "Culture"
  | "Corps"
  | "Travail & Admin"
  | "Argent"
  | "Système";

/** Ordre d'affichage des groupes dans toutes les surfaces de navigation. */
export const GROUP_ORDER: ModuleGroup[] = [
  "Quotidien",
  "Culture",
  "Corps",
  "Travail & Admin",
  "Argent",
  "Système",
];

export type Module = {
  slug: string;
  label: string;
  description: string;
  icon: LucideIcon;
  group: ModuleGroup;
  /** Module livré et fonctionnel. Défaut implicite : true via la liste ci-dessous. */
  ready?: boolean;
};

export const MODULES: Module[] = [
  // ── Vie quotidienne ───────────────────────────────────────────
  {
    slug: "habitudes",
    label: "Habitudes",
    description: "Habit tracker hebdomadaire.",
    icon: ListTodo,
    group: "Quotidien",
    ready: true,
  },
  {
    slug: "garderobe",
    label: "Garde-robe",
    description: "Vêtements, tenues, score thermique.",
    icon: Shirt,
    group: "Quotidien",
    ready: true,
  },
  {
    slug: "cuisine",
    label: "Cuisine",
    description: "Recettes & meal planning.",
    icon: ChefHat,
    group: "Quotidien",
    ready: true,
  },
  {
    slug: "skincare",
    label: "Skincare",
    description: "Routines matin/soir, produits, fréquence.",
    icon: Sparkles,
    group: "Quotidien",
    ready: true,
  },

  // ── Culture ───────────────────────────────────────────────────
  {
    slug: "livres",
    label: "Livres",
    description: "Lectures en cours, à lire, lus.",
    icon: BookOpen,
    group: "Culture",
    ready: true,
  },
  {
    slug: "film",
    label: "Films",
    description: "À voir, vus, notes.",
    icon: Film,
    group: "Culture",
    ready: true,
  },
  {
    slug: "musique",
    label: "Musique",
    description: "Albums, écoutes, découvertes.",
    icon: Music,
    group: "Culture",
    ready: false,
  },
  {
    slug: "series",
    label: "Séries",
    description: "En cours, à voir, vues.",
    icon: Tv,
    group: "Culture",
    ready: true,
  },

  // ── Santé & Sport ─────────────────────────────────────────────
  {
    slug: "sante",
    label: "Santé",
    description: "Mesures, nutrition, plan macros.",
    icon: HeartPulse,
    group: "Corps",
    ready: true,
  },
  {
    slug: "entrainement",
    label: "Entraînement",
    description: "Séances de sport, prise de muscle.",
    icon: Dumbbell,
    group: "Corps",
    ready: true,
  },
  {
    slug: "journal",
    label: "Journal",
    description: "Suivi d'humeur & tendances.",
    icon: Smile,
    group: "Corps",
    ready: true,
  },

  // ── Organisation ──────────────────────────────────────────────
  {
    slug: "agenda",
    label: "Agenda",
    description: "Événements, rappels.",
    icon: Calendar,
    group: "Travail & Admin",
    ready: true,
  },
  {
    slug: "etudes",
    label: "Études",
    description: "Suivi des sessions de travail.",
    icon: GraduationCap,
    group: "Travail & Admin",
    ready: true,
  },
  {
    slug: "documents",
    label: "Documents",
    description: "Échéances, contrats, garanties, rappels.",
    icon: FolderOpen,
    group: "Travail & Admin",
    ready: true,
  },

  // ── Finances ──────────────────────────────────────────────────
  {
    slug: "finance",
    label: "Finance",
    description: "Portefeuille long terme + scoring Buffett.",
    icon: TrendingUp,
    group: "Argent",
    ready: true,
  },
  {
    slug: "budget",
    label: "Budget",
    description: "Dépenses personnelles.",
    icon: Wallet,
    group: "Argent",
    ready: true,
  },

  // ── Outils ────────────────────────────────────────────────────
  {
    slug: "jobs",
    label: "Jobs",
    description: "Tâches planifiées & automatisations.",
    icon: Settings,
    group: "Système",
    ready: true,
  },
  {
    slug: "donnees",
    label: "Données",
    description: "Export/import, backup & démo.",
    icon: Database,
    group: "Système",
    ready: true,
  },
  {
    slug: "parametres",
    label: "Paramètres",
    description: "Intégrations, préférences, rétention.",
    icon: Settings,
    group: "Système",
    ready: true,
  },
  {
    slug: "routines",
    label: "Routines",
    description: "Automatisations déclenchées par cron ou événement.",
    icon: Zap,
    group: "Système",
    ready: true,
  },
  {
    slug: "snapshot",
    label: "Journal de vie",
    description: "Snapshot quotidien unifié multi-modules.",
    icon: Smile,
    group: "Quotidien",
    ready: true,
  },
];

/** Modules groupés dans l'ordre canonique, pour la nav groupée (sidebar, mobile). */
export const MODULE_GROUPS: { group: ModuleGroup; items: Module[] }[] =
  GROUP_ORDER.map((group) => ({
    group,
    items: MODULES.filter((m) => m.group === group),
  })).filter((g) => g.items.length > 0);

/** Résout un slug de route vers son module (fil d'Ariane, en-têtes de page). */
export function moduleForSlug(slug: string): Module | undefined {
  return MODULES.find((m) => m.slug === slug);
}
