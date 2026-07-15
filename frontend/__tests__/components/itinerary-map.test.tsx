import type { ReactNode } from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ItineraryMap, itineraryPoints } from "@/components/voyage/ItineraryMap";
import type { Itineraire } from "@/lib/voyage";

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: ReactNode }) => <div data-testid="map">{children}</div>,
  TileLayer: () => null,
  Marker: ({ children }: { children: ReactNode }) => <div data-testid="marker">{children}</div>,
  Polyline: () => null,
  Popup: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));
vi.mock("leaflet", () => ({
  default: { Icon: { Default: { prototype: {}, mergeOptions: vi.fn() } } },
}));

const ITINERAIRE_COMPLET: Itineraire = {
  etapes: [
    {
      lieu_id: 1, nom: "Table Mountain", pays: "Afrique du Sud", jours: 2,
      date_arrivee: "2026-09-02", date_depart: "2026-09-04",
      lat: -33.96, lon: 18.6,
    },
  ],
  cout_total: 1160, cout_transport: 1000, cout_sejour: 160,
  depart: { iata: "YUL", lat: 45.47, lon: -73.74 },
  arrivee: { iata: "YUL", lat: 45.47, lon: -73.74 },
};

const ITINERAIRE_SANS_COORD: Itineraire = {
  ...ITINERAIRE_COMPLET,
  etapes: [{ ...ITINERAIRE_COMPLET.etapes[0], lat: null, lon: null }],
};

describe("itineraryPoints", () => {
  it("construit départ + étapes + arrivée dans l'ordre", () => {
    const points = itineraryPoints(ITINERAIRE_COMPLET);
    expect(points).toHaveLength(3);
    expect(points?.[0].label).toContain("Départ");
    expect(points?.[1].label).toBe("Table Mountain");
    expect(points?.[2].label).toContain("Arrivée");
  });

  it("renvoie null si une étape n'a pas de coordonnées", () => {
    expect(itineraryPoints(ITINERAIRE_SANS_COORD)).toBeNull();
  });
});

describe("ItineraryMap", () => {
  it("affiche un marqueur par point", () => {
    render(<ItineraryMap itineraire={ITINERAIRE_COMPLET} />);
    expect(screen.getAllByTestId("marker")).toHaveLength(3);
  });

  it("affiche un repli si les coordonnées manquent", () => {
    render(<ItineraryMap itineraire={ITINERAIRE_SANS_COORD} />);
    expect(screen.getByText(/indisponible/)).toBeInTheDocument();
    expect(screen.queryByTestId("map")).not.toBeInTheDocument();
  });
});
