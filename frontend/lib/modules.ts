import {
  BookOpen,
  Briefcase,
  Calendar,
  ChefHat,
  CreditCard,
  Database,
  Dumbbell,
  Film,
  FolderOpen,
  Gamepad2,
  Gauge,
  GraduationCap,
  HeartPulse,
  Landmark,
  Languages,
  Music,
  Plane,
  Settings,
  Shirt,
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
  | "Style & Horizons"
  | "Configuration";

/** Ordre d'affichage des groupes dans toutes les surfaces de navigation. */
export const GROUP_ORDER: ModuleGroup[] = [
  "Exécution & Système",
  "Finances & Ingénierie",
  "Santé & Performance",
  "Carrière & Études",
  "Culture & Loisirs",
  "Style & Horizons",
  "Configuration",
];

/** Intitulés affichés dans la navigation : plus courts et orientés action.
 * Les clés internes restent stables pour préserver les liens et préférences.
 */
export const GROUP_LABELS: Record<ModuleGroup, string> = {
  "Exécution & Système": "Aujourd’hui & pilotage",
  "Finances & Ingénierie": "Argent & patrimoine",
  "Santé & Performance": "Santé, forme & nutrition",
  "Carrière & Études": "Travail & apprentissage",
  "Culture & Loisirs": "Culture & divertissement",
  "Style & Horizons": "Projets & vie personnelle",
  Configuration: "Système & données",
};

export type Module = {
  slug: string;
  label: string;
  description: string;
  /** Fonctions concrètes affichées dans l'aperçu spatial du module. */
  capabilities: readonly [string, string, string];
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
    description: "Organise tes journées, engagements et échéances au même endroit.",
    capabilities: ["Planning semaine et mois", "Cours, shifts et focus", "Récurrences et échéances"],
    icon: Calendar,
    group: "Exécution & Système",
    ready: true,
  },
  {
    slug: "score",
    label: "Tableau de bord personnel",
    description: "Une vue quotidienne de ton énergie, tes habitudes et tes progrès.",
    capabilities: ["Score quotidien", "Journal de vie et Vue 360", "Bilans sommeil, sport et nutrition"],
    icon: Gauge,
    group: "Exécution & Système",
    ready: true,
  },

  // ── ⚙️ Configuration — documents, données, routines, paramètres ────
  {
    slug: "documents",
    label: "Documents",
    description: "Échéances, contrats, garanties, rappels.",
    capabilities: ["Contrats et garanties", "Échéances documentaires", "Rappels centralisés"],
    icon: FolderOpen,
    group: "Configuration",
    ready: true,
  },
  {
    slug: "jobs",
    label: "Jobs",
    description: "Tâches planifiées & automatisations.",
    capabilities: ["Tâches planifiées", "Suivi des exécutions", "Alertes et historique"],
    icon: Settings,
    group: "Configuration",
    ready: true,
  },
  {
    slug: "routines",
    label: "Routines",
    description: "Automatisations déclenchées par cron ou événement.",
    capabilities: ["Déclencheurs programmés", "Routines événementielles", "Suivi des automatisations"],
    icon: Zap,
    group: "Configuration",
    ready: true,
  },
  {
    slug: "donnees",
    label: "Données",
    description: "Export/import, backup & démo.",
    capabilities: ["Imports et exports", "Sauvegardes", "Jeux de données de démonstration"],
    icon: Database,
    group: "Configuration",
    ready: true,
  },
  {
    slug: "parametres",
    label: "Paramètres",
    description: "Variables constantes, intégrations, rétention.",
    capabilities: ["Variables du système", "Intégrations", "Rétention des données"],
    icon: Settings,
    group: "Configuration",
    ready: true,
  },

  // ── 💰 Finances & Ingénierie ──────────────────────────────────
  {
    slug: "budget",
    label: "Budget & trésorerie",
    description: "Pilote les revenus, dépenses, épargne et prévisions mensuelles.",
    capabilities: ["Revenus et dépenses", "Prévisions mensuelles", "Contrats et épargne"],
    icon: Wallet,
    group: "Finances & Ingénierie",
    ready: true,
  },
  {
    slug: "finance",
    label: "Investissements",
    description: "Analyse, optimise et suis tes portefeuilles multi-courtiers.",
    capabilities: ["Portefeuille multi-brokers", "Analyse Buffett", "Allocation, risque et fiscalité"],
    icon: TrendingUp,
    group: "Finances & Ingénierie",
    ready: true,
  },
  {
    slug: "patrimoine",
    label: "Patrimoine net",
    description: "Centralise actifs, dettes, comptes et objectifs patrimoniaux.",
    capabilities: ["Valeur nette", "Actifs, comptes et emprunts", "Objectifs patrimoniaux"],
    icon: Landmark,
    group: "Finances & Ingénierie",
    ready: true,
  },
  {
    slug: "credit",
    label: "Crédit & capacité d’emprunt",
    description: "Comprends ton utilisation du crédit et les leviers d’amélioration.",
    capabilities: ["Capacité d'emprunt", "Utilisation du crédit", "Plan d'amélioration"],
    icon: CreditCard,
    group: "Finances & Ingénierie",
    ready: true,
  },

  // ── 🔋 Santé & Performance ────────────────────────────────────
  {
    slug: "entrainement",
    label: "Entraînement & performances",
    description: "Planifie tes séances et mesure ta progression en force et endurance.",
    capabilities: ["Séances et programmes", "Progression des charges", "Course et performances"],
    icon: Dumbbell,
    group: "Santé & Performance",
    ready: true,
  },
  {
    slug: "cuisine",
    label: "Nutrition & cuisine",
    description: "Transforme tes objectifs nutritionnels en repas et courses concrètes.",
    capabilities: ["Recettes et menus", "Objectifs de macros", "Listes de courses"],
    icon: ChefHat,
    group: "Santé & Performance",
    ready: true,
  },
  {
    slug: "sante",
    label: "Santé & récupération",
    description: "Suis tes mesures, ton sommeil, ta nutrition et ta récupération.",
    capabilities: ["Mesures corporelles", "Sommeil et récupération", "Nutrition et hydratation"],
    icon: HeartPulse,
    group: "Santé & Performance",
    ready: true,
  },
  {
    slug: "skincare",
    label: "Skincare",
    description: "Routines matin/soir, produits, fréquence.",
    capabilities: ["Routines matin et soir", "Produits et actifs", "Fréquences et suivi"],
    icon: Sparkles,
    group: "Santé & Performance",
    ready: true,
  },

  // ── 🏢 Carrière & Études ──────────────────────────────────────
  {
    slug: "etudes",
    label: "Études",
    description: "Cours, examens, coefficients, GPA.",
    capabilities: ["Cours et examens", "Notes et coefficients", "GPA et progression"],
    icon: GraduationCap,
    group: "Carrière & Études",
    ready: true,
  },
  {
    slug: "travail",
    label: "Travail",
    description: "Shifts barista, validation d'heures, revenus à venir.",
    capabilities: ["Shifts et heures", "Validation du temps travaillé", "Revenus à venir"],
    icon: Briefcase,
    group: "Carrière & Études",
    ready: true,
  },
  {
    slug: "objectifs",
    label: "Objectifs long terme",
    description: "Masters, concours gendarmerie, gestion d'actifs.",
    capabilities: ["Jalons de carrière", "Plans d'action", "Progression long terme"],
    icon: Target,
    group: "Carrière & Études",
    ready: true,
  },

  // ── 🎭 Culture & Loisirs ──────────────────────────────────────
  {
    slug: "musique",
    label: "Musique",
    description: "Bibliothèque locale, ambiances par mood, tri automatisé.",
    capabilities: ["Bibliothèque locale", "Ambiances par humeur", "Tri automatisé"],
    icon: Music,
    group: "Culture & Loisirs",
    ready: true,
  },
  {
    slug: "film",
    label: "Films",
    description: "À voir, vus, notes.",
    capabilities: ["Liste à voir", "Historique de visionnage", "Notes et découvertes"],
    icon: Film,
    group: "Culture & Loisirs",
    ready: true,
  },
  {
    slug: "series",
    label: "Séries",
    description: "En cours, à voir, vues.",
    capabilities: ["Séries en cours", "Liste à voir", "Progression des épisodes"],
    icon: Tv,
    group: "Culture & Loisirs",
    ready: true,
  },
  {
    slug: "livres",
    label: "Livres",
    description: "Lectures en cours, à lire, lus.",
    capabilities: ["Lectures en cours", "Bibliothèque à lire", "Historique et notes"],
    icon: BookOpen,
    group: "Culture & Loisirs",
    ready: true,
  },
  {
    slug: "gaming",
    label: "Gaming",
    description: "Objectifs, builds de personnages, filtres d'items.",
    capabilities: ["Objectifs de jeu", "Builds de personnages", "Filtres d'équipement"],
    icon: Gamepad2,
    group: "Culture & Loisirs",
    ready: true,
  },

  // ── 🌐 Style & Horizons ───────────────────────────────────────
  {
    slug: "garderobe",
    label: "Garde-robe",
    description: "Inventaire, wishlists, moodboards.",
    capabilities: ["Inventaire des vêtements", "Tenues et moodboards", "Wishlist"],
    icon: Shirt,
    group: "Style & Horizons",
    ready: true,
  },
  {
    slug: "voyage",
    label: "Voyage",
    description: "Wishlist de lieux à visiter, planification d'itinéraire.",
    capabilities: ["Destinations souhaitées", "Itinéraires", "Préparation du voyage"],
    icon: Plane,
    group: "Style & Horizons",
    ready: true,
  },
  {
    slug: "langues",
    label: "Langues & International",
    description: "Japonais (vocab, kanjis) & masterplan Asie.",
    capabilities: ["Vocabulaire japonais", "Kanjis et révisions", "Plan international"],
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
