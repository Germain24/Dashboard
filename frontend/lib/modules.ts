import {
  BookOpen,
  Briefcase,
  Calendar,
  ChefHat,
  Dumbbell,
  GraduationCap,
  HeartPulse,
  LineChart,
  ListTodo,
  Shirt,
  Wallet,
  type LucideIcon,
} from "lucide-react";

export type Module = {
  slug: string;
  label: string;
  description: string;
  icon: LucideIcon;
  conv: string;
  ready?: boolean;
};

export const MODULES: Module[] = [
  {
    slug: "finance",
    label: "Finance",
    description: "Portefeuille long terme + scoring Buffett.",
    icon: LineChart,
    conv: "CONV 4",
  },
  {
    slug: "garderobe",
    label: "Garde-robe",
    description: "Vetements, tenues, score thermique.",
    icon: Shirt,
    conv: "CONV 2",
    ready: true,
  },
  {
    slug: "sante",
    label: "Sante",
    description: "Mesures, nutrition, plan macros.",
    icon: HeartPulse,
    conv: "CONV 3",
    ready: true,
  },
  {
    slug: "agenda",
    label: "Agenda",
    description: "Evenements, rappels.",
    icon: Calendar,
    conv: "CONV 5",
    ready: true,
  },
  {
    slug: "etudes",
    label: "Etudes",
    description: "Suivi des sessions de travail.",
    icon: GraduationCap,
    conv: "CONV 6",
    ready: true,
  },
  {
    slug: "entrainement",
    label: "Entrainement",
    description: "Seances de sport, prise de muscle.",
    icon: Dumbbell,
    conv: "CONV 7",
    ready: true,
  },
  {
    slug: "budget",
    label: "Budget",
    description: "Depenses personnelles.",
    icon: Wallet,
    conv: "CONV 8",
  },
  {
    slug: "cuisine",
    label: "Cuisine",
    description: "Recettes & meal planning.",
    icon: ChefHat,
    conv: "CONV 9",
  },
  {
    slug: "habitudes",
    label: "Habitudes",
    description: "Habit tracker hebdomadaire.",
    icon: ListTodo,
    conv: "CONV 10",
  },
  {
    slug: "livres",
    label: "Livres",
    description: "Lectures en cours, a lire, lus.",
    icon: BookOpen,
    conv: "CONV 11",
  },
  {
    slug: "robot",
    label: "Robot",
    description: "Chat avec l'agent IA.",
    icon: Briefcase,
    conv: "CONV 12",
  },
];
