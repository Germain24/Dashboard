import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Source_Serif_4 } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout";

// Polices auto-hébergées via next/font : zéro requête bloquante, pas de FOUT.
// Corps et UI : Plus Jakarta Sans (variable font-jakarta, reliée à font-sans).
const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-jakarta",
  display: "swap",
});

// Titres : Source Serif 4, serif éditorial « Savile Row » (variable font-serif).
const sourceSerif = Source_Serif_4({
  subsets: ["latin"],
  weight: ["400", "600"],
  style: ["normal", "italic"],
  variable: "--font-source-serif",
  display: "swap",
});
import { MobileNav } from "@/components/MobileNav";
import { QueryProvider } from "@/components/QueryProvider";
import { CommandPalette } from "@/components/CommandPalette";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import { KeyboardShortcuts } from "@/components/KeyboardShortcuts";
import { ShortcutsHelp } from "@/components/ShortcutsHelp";

export const metadata: Metadata = {
  title: { default: "Mission Control", template: "%s · Mission Control" },
  description:
    "Dashboard personnel : finance, nutrition, garde-robe, agenda, études, …",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Mission Control", statusBarStyle: "black-translucent" },
};

export const viewport = {
  themeColor: "#15181C",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr-CA" className={`${jakarta.variable} ${sourceSerif.variable}`}>
      <head>
        {/* Anti-flash : applique le thème choisi avant le premier paint. */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "(function(){try{var t=localStorage.getItem('mc-theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t);var d=localStorage.getItem('mc-density');if(d==='compact')document.documentElement.setAttribute('data-density','compact');}catch(e){}})();",
          }}
        />
      </head>
      <body className="antialiased">
        {/* Lien d'évitement : premier élément focusable, masqué jusqu'au focus
            clavier. Permet de sauter les ~13 liens de nav et d'atteindre le
            contenu directement (Tab depuis le haut de page). */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[60] focus:rounded-md focus:bg-[var(--foreground)] focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-[var(--background)] focus:shadow-[var(--shadow-md)]"
        >
          Aller au contenu
        </a>
        <QueryProvider>
          {/* Palette de commandes globale (Cmd/Ctrl+K) + raccourcis j/k */}
          <CommandPalette />
          <KeyboardShortcuts />
          <ShortcutsHelp />

          {/* Navigation mobile (fixed header + hamburger drawer) */}
          <MobileNav />

          {/* Layout desktop : sidebar gauche + contenu */}
          <div className="flex min-h-screen">
            <Sidebar />
            <main id="main-content" tabIndex={-1} className="flex-1 min-w-0 focus:outline-none">
              <Breadcrumbs />
              {children}
            </main>
          </div>
        </QueryProvider>
      </body>
    </html>
  );
}
