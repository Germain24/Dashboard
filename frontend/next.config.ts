import type { NextConfig } from "next";

import { securityHeaders } from "./lib/securityHeaders";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Sortie autonome pour une image de production minimale (#200) : .next/standalone
  // embarque un server.js + le strict nécessaire (pas besoin de tout node_modules).
  output: "standalone",
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

export default nextConfig;
