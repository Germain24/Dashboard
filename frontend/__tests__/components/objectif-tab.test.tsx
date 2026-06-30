import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

const baseData = {
  total_emplacements: 2,
  total_remplis: 1,
  non_rattaches: 0,
  non_rattaches_items: [] as { vetement_id: string; vetement_nom: string; type_objectif: string | null }[],
  types: [
    {
      nom: "T-shirts",
      ordre: 0,
      quantite_objectif: 2,
      echelle: ["Uniqlo U", "Visvim"],
      rempli: 1,
      emplacements: [
        { statut: "rempli", vetement_id: "v1", vetement_nom: "Tee", marque: "Visvim", position: 100, hors_echelle: false, image: "Haut/tee.png" },
        { statut: "vide", vetement_id: null, vetement_nom: null, marque: null, position: null, hors_echelle: false, image: null },
      ],
      excedent: [],
    },
  ],
};

let mockData = { ...baseData };

const autoMutate = vi.hoisted(() => vi.fn());

vi.mock("@/lib/queries/garderobe", () => ({
  useObjectif: () => ({
    isLoading: false,
    isError: false,
    data: mockData,
  }),
  useSyncObjectif: () => ({ mutate: vi.fn(), isPending: false }),
  useAutoRattacher: () => ({ mutate: autoMutate, isPending: false }),
}));

import { ObjectifTab } from "@/components/garderobe/ObjectifTab";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("ObjectifTab", () => {
  it("affiche l'en-tête global et un type", () => {
    mockData = { ...baseData };
    render(<ObjectifTab />, { wrapper });
    expect(screen.getByText(/1\/2/)).toBeInTheDocument();      // total rempli/emplacements
    expect(screen.getByText("T-shirts")).toBeInTheDocument();
    expect(screen.getByText("Visvim")).toBeInTheDocument();    // marque possédée
  });

  it("affiche la vignette pixel art d'un emplacement rempli", () => {
    mockData = { ...baseData };
    render(<ObjectifTab />, { wrapper });
    const img = screen.getByAltText("Tee") as HTMLImageElement;
    expect(img.getAttribute("src")).toBe("/garderobe/assets/Haut/tee.png");
  });

  it("affiche un avertissement quand des pièces sont non rattachées", () => {
    mockData = {
      ...baseData,
      non_rattaches: 1,
      non_rattaches_items: [{ vetement_id: "x", vetement_nom: "Truc", type_objectif: "Inexistant" }],
    };
    render(<ObjectifTab />, { wrapper });
    expect(screen.getByText(/non rattachée/)).toBeInTheDocument();
    expect(screen.getByText(/Truc/)).toBeInTheDocument();
  });

  it("le bouton Rattacher automatiquement déclenche la mutation", () => {
    render(<ObjectifTab />, { wrapper });
    fireEvent.click(screen.getByText(/Rattacher automatiquement/i));
    expect(autoMutate).toHaveBeenCalled();
  });
});
