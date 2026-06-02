import type { MetadataRoute } from "next";

/** Manifest PWA — permet d'installer le dashboard comme app locale. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Mission Control",
    short_name: "Mission Control",
    description: "Dashboard personnel — finance, nutrition, garde-robe, agenda, études…",
    start_url: "/",
    display: "standalone",
    background_color: "#0a0a0a",
    theme_color: "#0a0a0a",
    icons: [
      { src: "/favicon.ico", sizes: "any", type: "image/x-icon" },
    ],
  };
}
