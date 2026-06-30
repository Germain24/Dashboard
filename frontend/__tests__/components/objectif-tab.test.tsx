import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

vi.mock("@/lib/queries/garderobe", () => ({
  useObjectif: () => ({
    isLoading: false,
    isError: false,
    data: {
      total_emplacements: 2,
      total_remplis: 1,
      types: [
        {
          nom: "T-shirts",
          ordre: 0,
          quantite_objectif: 2,
          echelle: ["Uniqlo U", "Visvim"],
          rempli: 1,
          emplacements: [
            { statut: "rempli", vetement_id: "v1", vetement_nom: "Tee", marque: "Visvim", position: 100, hors_echelle: false },
            { statut: "vide", vetement_id: null, vetement_nom: null, marque: null, position: null, hors_echelle: false },
          ],
          excedent: [],
        },
      ],
    },
  }),
  useSyncObjectif: () => ({ mutate: vi.fn(), isPending: false }),
}));

import { ObjectifTab } from "@/components/garderobe/ObjectifTab";

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("ObjectifTab", () => {
  it("affiche l'en-tête global et un type", () => {
    render(<ObjectifTab />, { wrapper });
    expect(screen.getByText(/1\/2/)).toBeInTheDocument();      // total rempli/emplacements
    expect(screen.getByText("T-shirts")).toBeInTheDocument();
    expect(screen.getByText("Visvim")).toBeInTheDocument();    // marque possédée
  });
});
