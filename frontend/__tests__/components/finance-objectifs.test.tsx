import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/queries/finance", () => ({
  useObjectifPatrimoine: () => ({
    data: {
      objectifs: [
        {
          id: "liberte_financiere",
          label: "Liberté financière",
          objectif_eur: 300_000,
          valeur_eur: 75_000,
          progression_pct: 25,
          restant_eur: 225_000,
          atteint: false,
          echeance: null,
          jours_restants: null,
          epargne_journaliere_eur: null,
        },
        {
          id: "japon",
          label: "Voyage au Japon",
          objectif_eur: 12_000,
          valeur_eur: 3_000,
          progression_pct: 25,
          restant_eur: 9_000,
          atteint: false,
          echeance: "2028-01-11",
          jours_restants: 450,
          epargne_journaliere_eur: 20,
        },
      ],
    },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
  useSetObjectifPatrimoine: () => ({ mutate: vi.fn(), isPending: false }),
}));

import { ObjectifWidget } from "@/components/finance/Finance";

describe("Objectifs patrimoniaux", () => {
  it("place Japon après la liberté financière et affiche son effort journalier", () => {
    render(<ObjectifWidget />);

    const cards = screen.getAllByRole("article");
    expect(within(cards[0]).getByText("Liberté financière")).toBeInTheDocument();
    expect(within(cards[0]).getByText(/sans limite de temps/i)).toBeInTheDocument();
    expect(within(cards[1]).getByText("Voyage au Japon")).toBeInTheDocument();
    expect(within(cards[1]).getByText(/11 janvier 2028/i)).toBeInTheDocument();
    expect(within(cards[1]).getByText(/cible ajustée chaque jour/i)).toBeInTheDocument();
    expect(within(cards[1]).getByText(/450 jours · 20 € à mettre de côté par jour/i)).toBeInTheDocument();
  });
});
