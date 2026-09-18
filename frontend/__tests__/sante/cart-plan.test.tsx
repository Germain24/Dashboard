import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/queries/sante", () => ({
  useFenetreCurrent: () => ({
    data: {
      anchor_date: "2026-07-20", length: 3, poids_used: 51,
      jours: [], shopping_list: [],
      score: { couverture_moyenne: 0.8, pct_micros_atteints: 70, cout_total: 42, cout_a_payer: 30, ratio: 0.019, sous_couverts: [] },
      warning: null,
    }, isLoading: false, isError: false,
  }),
  useActiveGenerateFenetre: () => ({ data: null, refetch: vi.fn() }),
  useStartGenerateFenetre: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useStopGenerateFenetre: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useGenerateFenetreStatus: () => ({ data: null }),
  useCartPlan: () => ({
    data: {
      anchor_date: "2026-07-20",
      items: [
        { aliment: "Riz", product_id: "222", product_name: "Basmati Rice 2 kg", href: "/products/222-rice-2-kg", format: "2 kg", qty: 2, prix_estime: 8.0, a_verifier: false },
        { aliment: "Licorne", product_id: null, product_name: null, href: null, format: null, qty: 1, prix_estime: null, a_verifier: true },
      ],
      total_estime: 16.0,
    },
  }),
  useStartCartFill: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
  useCartFillStatus: () => ({ data: null }),
  usePatchPlan: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false }),
  useSanteFavorites: () => ({ data: [] }),
  useSanteAliments: () => ({ data: [] }),
  useAddSanteFavorite: () => ({ mutate: vi.fn() }),
  useRemoveSanteFavorite: () => ({ mutate: vi.fn() }),
}));

import { FenetreTab } from "@/components/sante/FenetreTab";

describe("FenetreTab — Panier Super C", () => {
  it("renders matched product, qty, total and the à-vérifier flag", () => {
    render(<FenetreTab goal={null} onSaveMesure={vi.fn()} />);
    expect(screen.getByText("Basmati Rice 2 kg")).toBeInTheDocument();
    expect(screen.getByText("× 2")).toBeInTheDocument();
    expect(screen.getByText(/à vérifier/)).toBeInTheDocument();
    expect(screen.getByText(/Total du panier/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Ajouter au panier Super C/i })).toBeInTheDocument();
  });
});
