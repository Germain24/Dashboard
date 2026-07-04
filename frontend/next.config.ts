import type { NextConfig } from "next";
import createBundleAnalyzer from "@next/bundle-analyzer";

import { securityHeaders } from "./lib/securityHeaders";

// `npm run analyze` (ANALYZE=true) : repère les régressions de taille par
// route et les barrels index.ts qui tirent un module entier. Jamais actif
// pendant un build normal.
const withBundleAnalyzer = createBundleAnalyzer({
  enabled: process.env.ANALYZE === "true",
});

const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Sortie autonome pour une image de production minimale (#200) : .next/standalone
  // embarque un server.js + le strict nécessaire (pas besoin de tout node_modules).
  output: "standalone",
  images: {
    remotePatterns: [
      // Posters films/séries (TMDB) et couvertures livres (Open Library).
      { protocol: "https", hostname: "image.tmdb.org" },
      { protocol: "https", hostname: "covers.openlibrary.org" },
      // Médias servis par le backend local (garde-robe, musique, photos de
      // progression) : dashboard perso, jamais un hôte distant non maîtrisé.
      { protocol: "http", hostname: "127.0.0.1" },
      { protocol: "http", hostname: "localhost" },
    ],
  },
  // Le lint tourne en étape CI dédiée (#196) ; on ne bloque pas le build dessus
  // (dette lint pré-existante suivie séparément). Les erreurs de type restent
  // bloquantes (tsc).
  eslint: { ignoreDuringBuilds: true },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/:path*`,
      },
    ];
  },
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};

export default withBundleAnalyzer(nextConfig);
