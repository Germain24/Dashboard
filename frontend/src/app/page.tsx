import { Greeting } from "@/components/Greeting";
import { TodayPanel } from "@/components/home/TodayPanel";
import { Deck } from "@/components/deck/Deck";
import Link from "next/link";
import { CalendarDays, GraduationCap, Wallet, Briefcase } from "lucide-react";
import { ModuleAccess } from "@/components/layout/ModuleAccess";

const QUICK_LINKS = [
  { href: "/agenda", label: "Agenda", icon: CalendarDays },
  { href: "/budget", label: "Budget", icon: Wallet },
  { href: "/etudes", label: "Études", icon: GraduationCap },
  { href: "/travail", label: "Travail", icon: Briefcase },
];

export default function HomePage() {
  return (
    <Deck
      intro={
        <div className="deck-today">
          <header className="deck-today-copy glass-panel">
            <p className="deck-kicker">
              <span>01</span>
              Vue du jour
            </p>
            <Greeting />
            <p className="mt-5 max-w-[34ch] text-sm leading-relaxed text-[var(--muted-foreground)] sm:text-base">
              Ta prochaine étape, les urgences du jour et tes raccourcis personnels sont réunis ici.
            </p>
            <nav aria-label="Accès rapide" className="mt-6">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/55">
                Accès rapide
              </p>
              <ul className="mt-2 grid grid-cols-2 gap-2">
                {QUICK_LINKS.map(({ href, label, icon: Icon }) => (
                  <li key={href}>
                    <Link
                      href={href}
                      className="flex min-h-10 items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-2 text-xs font-medium text-white/80 transition-colors hover:border-white/20 hover:bg-white/[0.09] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                    >
                      <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                      {label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
            <ModuleAccess variant="home" />
          </header>
          <div className="deck-today-panel no-scrollbar">
            <TodayPanel />
          </div>
        </div>
      }
    />
  );
}
