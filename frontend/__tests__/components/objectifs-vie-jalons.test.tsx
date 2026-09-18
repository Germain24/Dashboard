import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { LifeGoal } from "@/lib/routines";
import { ObjectifsVie } from "@/components/ObjectifsVie";

const mocks = vi.hoisted(() => ({ goals: vi.fn(), metrics: vi.fn() }));

vi.mock("@/lib/queries/routines", () => ({
  useLifeGoals: mocks.goals,
  useLifeGoalMetrics: mocks.metrics,
  useCreateLifeGoal: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteLifeGoal: () => ({ mutate: vi.fn() }),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

function renderAvec(goals: LifeGoal[]) {
  mocks.goals.mockReturnValue({ data: goals });
  mocks.metrics.mockReturnValue({ data: [{ metric: "epargne", label: "Épargne nette ($)" }] });
  render(<ObjectifsVie />, { wrapper });
}

const goal = (objectifs: LifeGoal["objectifs"]): LifeGoal => ({
  id: 1, titre: "Forme & épargne", echeance: null, objectifs, pct_global: 50,
  jalons_en_retard: objectifs.filter((o) => o.statut === "en_retard").length,
});

describe("ObjectifsVie — jalons datés", () => {
  beforeEach(() => vi.clearAllMocks());

  it("affiche la date et le statut d'un jalon en retard", () => {
    renderAvec([
      goal([{
        label: "Épargner 2000", metric: "epargne", baseline: 0, cible: 2000,
        courant: 500, pct: 25, atteint: false, date: "2026-06-01", statut: "en_retard",
      }]),
    ]);

    expect(screen.getByText("2026-06-01")).toBeInTheDocument();
    // Pastille sur le jalon lui-même…
    expect(screen.getByText("En retard")).toBeInTheDocument();
    // …et compteur remonté sur l'objectif.
    expect(screen.getByText(/1 jalon en retard/i)).toBeInTheDocument();
  });

  it("affiche un jalon à venir sans alerte de retard", () => {
    renderAvec([
      goal([{
        label: "Épargner 2000", metric: "epargne", baseline: 0, cible: 2000,
        courant: 500, pct: 25, atteint: false, date: "2026-12-01", statut: "a_venir",
      }]),
    ]);

    expect(screen.getByText("2026-12-01")).toBeInTheDocument();
    expect(screen.queryByText(/en retard/i)).not.toBeInTheDocument();
  });

  it("reste lisible pour un sous-objectif sans date (ancien format)", () => {
    renderAvec([
      goal([{
        label: "Perdre 5 kg", metric: "poids", baseline: 80, cible: 75,
        courant: 77, pct: 60, atteint: false, date: null, statut: "a_venir",
      }]),
    ]);

    expect(screen.getByText(/Perdre 5 kg/)).toBeInTheDocument();
    expect(screen.getByText(/60%/)).toBeInTheDocument();
    expect(screen.queryByText(/en retard/i)).not.toBeInTheDocument();
  });

  it("signale le nombre de jalons en retard sur l'objectif", () => {
    renderAvec([
      goal([
        {
          label: "A", metric: "epargne", baseline: 0, cible: 100, courant: 0,
          pct: 0, atteint: false, date: "2026-06-01", statut: "en_retard",
        },
        {
          label: "B", metric: "poids", baseline: 80, cible: 75, courant: 80,
          pct: 0, atteint: false, date: "2026-05-01", statut: "en_retard",
        },
      ]),
    ]);

    expect(screen.getByText(/2 jalons en retard/i)).toBeInTheDocument();
  });

  it("marque un jalon atteint", () => {
    renderAvec([
      goal([{
        label: "Épargner 2000", metric: "epargne", baseline: 0, cible: 2000,
        courant: 2500, pct: 100, atteint: true, date: "2026-06-01", statut: "atteint",
      }]),
    ]);

    expect(screen.getByText(/atteint/i)).toBeInTheDocument();
    expect(screen.queryByText(/en retard/i)).not.toBeInTheDocument();
  });
});
