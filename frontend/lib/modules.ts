import {
  BookOpen,
  Briefcase,
  Calendar,
  ChefHat,
  Database,
  Dumbbell,
  Film,
  FolderOpen,
  Gamepad2,
  Gauge,
  GraduationCap,
  HeartPulse,
  Languages,
  ListTodo,
  Music,
  Settings,
  Shirt,
  Smile,
  Sparkles,
  Target,
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
  | "Exécution & Système"
  | "Finances & Ingénierie"
  | "Santé & Performance"
  | "Carrière & Études"
  | "Culture & Loisirs"
  | "Style & Horizons";

/** Ordre d'affichage des groupes dans toutes les surfaces de navigation. */
export const GROUP_ORDER: ModuleGroup[] = [
  "Exécution & Système",
  "Finances & Ingénierie",
  "Santé & Performance",
  "Carrière & Études",
  "Culture & Loisirs",
  "Style & Horizons",
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
  // ── 🕒 Exécution & Système — la tour de contrôle ──────────────
  {
    slug: "agenda",
    label: "Agenda",
    description: "Time-blocking : cours, shifts, blocs de focus.",
    icon: Calendar,
    group: "Exécution & Système",
    ready: true,
  },
  {
    slug: "journal",
    label: "Journal",
    description: "Quick capture matin/soir : humeur & tendances.",
    icon: Smile,
    group: "Exécution & Système",
    ready: true,
  },
  {
    slug: "snapshot",
    label: "Journal de vie",
    description: "Snapshot quotidien unifié multi-modules.",
    icon: Smile,
    group: "Exécution & Système",
    ready: true,
  },
  {
    slug: "vue-360",
    label: "Vue 360",
    description: "Synthèse de toute ta vie : bien-être, insights, corrélations.",
    icon: Gauge,
    group: "Exécution & Système",
    ready: true,
  },
  {
    slug: "habitudes",
    label: "Habitudes",
    description: "Habit tracker hebdomadaire.",
    icon: ListTodo,
    group: "Exécution & Système",
    ready: true,
  },
  {
    slug: "documents",
    label: "Documents",
    description: "Échéances, contrats, garanties, rappels.",
    icon: FolderOpen,
    group: "Exécution & Système",
    ready: true,
  },
  {
    slug: "jobs",
    label: "Jobs",
    description: "Tâches planifiées & automatisations.",
    icon: Settings,
    group: "Exécution & Système",
    ready: true,
  },
  {
    slug: "routines",
    label: "Routines",
    description: "Automatisations déclenchées par cron ou événement.",
    icon: Zap,
    group: "Exécution & Système",
    ready: true,
  },
  {
    slug: "donnees",
    label: "Données",
    description: "Export/import, backup & démo.",
    icon: Database,
    group: "Exécution & Système",
    ready: true,
  },
  {
    slug: "parametres",
    label: "Paramètres",
    description: "Variables constantes, intégrations, rétention.",
    icon: Settings,
    group: "Exécution & Système",
    ready: true,
  },

  // ── 💰 Finances & Ingénierie ──────────────────────────────────
  {
    slug: "budget",
    label: "Budget",
    description: "Trésorerie : flux entrants, sortants, dépenses.",
    icon: Wallet,
    group: "Finances & Ingénierie",
    ready: true,
  },
  {
    slug: "finance",
    label: "Investissement",
    description: "Portefeuille long terme + scoring Buffett (quant).",
    icon: TrendingUp,
    group: "Finances & Ingénierie",
    ready: true,
  },

  // ── 🔋 Santé & Performance ────────────────────────────────────
  {
    slug: "entrainement",
    label: "Entraînement",
    description: "Muscu (surcharge progressive) & course à pied.",
    icon: Dumbbell,
    group: "Santé & Performance",
    ready: true,
  },
  {
    slug: "cuisine",
    label: "Cuisine",
    description: "Recettes, macros cibles, listes de courses.",
    icon: ChefHat,
    group: "Santé & Performance",
    ready: true,
  },
  {
    slug: "sante",
    label: "Santé",
    description: "Mesures, nutrition, sommeil, récupération.",
    icon: HeartPulse,
    group: "Santé & Performance",
    ready: true,
  },
  {
    slug: "skincare",
    label: "Skincare",
    description: "Routines matin/soir, produits, fréquence.",
    icon: Sparkles,
    group: "Santé & Performance",
    ready: true,
  },

  // ── 🏢 Carrière & Études ──────────────────────────────────────
  {
    slug: "etudes",
    label: "Études",
    description: "Cours, examens, coefficients, GPA.",
    icon: GraduationCap,
    group: "Carrière & Études",
    ready: true,
  },
  {
    slug: "travail",
    label: "Travail",
    description: "Shifts barista, validation d'heures, revenus à venir.",
    icon: Briefcase,
    group: "Carrière & Études",
    ready: true,
  },
  {
    slug: "objectifs",
    label: "Objectifs long terme",
    description: "Masters, concours gendarmerie, gestion d'actifs.",
    icon: Target,
    group: "Carrière & Études",
    ready: true,
  },

  // ── 🎭 Culture & Loisirs ──────────────────────────────────────
  {
    slug: "musique",
    label: "Musique",
    description: "Bibliothèque locale, ambiances par mood, tri automatisé.",
    icon: Music,
    group: "Culture & Loisirs",
    ready: true,
  },
  {
    slug: "film",
    label: "Films",
    description: "À voir, vus, notes.",
    icon: Film,
    group: "Culture & Loisirs",
    ready: true,
  },
  {
    slug: "series",
    label: "Séries",
    description: "En cours, à voir, vues.",
    icon: Tv,
    group: "Culture & Loisirs",
    ready: true,
  },
  {
    slug: "livres",
    label: "Livres",
    description: "Lectures en cours, à lire, lus.",
    icon: BookOpen,
    group: "Culture & Loisirs",
    ready: true,
  },
  {
    slug: "gaming",
    label: "Gaming",
    description: "Objectifs, builds de personnages, filtres d'items.",
    icon: Gamepad2,
    group: "Culture & Loisirs",
    ready: true,
  },

  // ── 🌐 Style & Horizons ───────────────────────────────────────
  {
    slug: "garderobe",
    label: "Garde-robe",
    description: "Inventaire, wishlists, moodboards.",
    icon: Shirt,
    group: "Style & Horizons",
    ready: true,
  },
  {
    slug: "langues",
    label: "Langues & International",
    description: "Japonais (vocab, kanjis) & masterplan Asie.",
    icon: Languages,
    group: "Style & Horizons",
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
