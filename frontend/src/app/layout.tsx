import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout";
import { MobileNav } from "@/components/MobileNav";

export const metadata: Metadata = {
  title: "Mission Control",
  description:
    "Dashboard personnel — finance, nutrition, garde-robe, agenda, études, …",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr-CA">
      <body className="antialiased">
        {/* Navigation mobile (fixed header + hamburger drawer) */}
        <MobileNav />

        {/* Layout desktop : sidebar gauche + contenu */}
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 min-w-0">{children}</main>
        </div>
      </body>
    </html>
  );
}
