import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout";
import { MobileNav } from "@/components/MobileNav";
import { QueryProvider } from "@/components/QueryProvider";

export const metadata: Metadata = {
  title: "Mission Control",
  description:
    "Dashboard personnel — finance, nutrition, garde-robe, agenda, études, …",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Mission Control", statusBarStyle: "black-translucent" },
};

export const viewport = {
  themeColor: "#0a0a0a",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr-CA">
      <head>
        {/* Anti-flash : applique le thème choisi avant le premier paint. */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "(function(){try{var t=localStorage.getItem('mc-theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t);}catch(e){}})();",
          }}
        />
      </head>
      <body className="antialiased">
        <QueryProvider>
          {/* Navigation mobile (fixed header + hamburger drawer) */}
          <MobileNav />

          {/* Layout desktop : sidebar gauche + contenu */}
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 min-w-0">{children}</main>
          </div>
        </QueryProvider>
      </body>
    </html>
  );
}
