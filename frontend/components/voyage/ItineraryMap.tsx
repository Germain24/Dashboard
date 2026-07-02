"use client";

import type { ReactNode } from "react";
import { MapContainer, Marker, Polyline, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Itineraire } from "@/lib/voyage";

// Le bundler ne préserve pas les chemins d'assets relatifs que Leaflet
// utilise par défaut pour ses icônes de marqueur ; sans ce correctif les
// marqueurs s'affichent avec une image cassée.
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

type Point = { lat: number; lon: number; label: string; detail?: ReactNode };

/** Départ -> étapes (ordre du solveur) -> arrivée. `null` si un point du
 * parcours n'a pas de coordonnées connues (jamais de carte partielle). */
export function itineraryPoints(itineraire: Itineraire): Point[] | null {
  const { depart, arrivee, etapes } = itineraire;
  if (depart.lat == null || depart.lon == null) return null;
  if (arrivee.lat == null || arrivee.lon == null) return null;

  const points: Point[] = [{ lat: depart.lat, lon: depart.lon, label: `Départ (${depart.iata})` }];
  for (const e of etapes) {
    if (e.lat == null || e.lon == null) return null;
    points.push({ lat: e.lat, lon: e.lon, label: e.nom, detail: `${e.date_arrivee} → ${e.date_depart}` });
  }
  points.push({ lat: arrivee.lat, lon: arrivee.lon, label: `Arrivée (${arrivee.iata})` });
  return points;
}

export function ItineraryMap({ itineraire }: { itineraire: Itineraire }) {
  const points = itineraryPoints(itineraire);

  if (!points) {
    return (
      <div className="rounded-lg border border-[var(--border)] p-3 text-sm text-[var(--muted-foreground)]">
        Carte indisponible pour cet itinéraire.
      </div>
    );
  }

  const positions: [number, number][] = points.map((p) => [p.lat, p.lon]);

  return (
    <MapContainer
      center={positions[0]}
      zoom={3}
      bounds={positions}
      scrollWheelZoom={false}
      className="h-64 w-full rounded-lg"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Polyline positions={positions} />
      {points.map((p, i) => (
        <Marker key={i} position={[p.lat, p.lon]}>
          <Popup>
            {p.label}
            {p.detail && <div>{p.detail}</div>}
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
