import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";

type GenerateStatusMock = {
  data: Record<string, unknown> | null;
  refetch?: ReturnType<typeof vi.fn>;
};

const { fenetreQ, mutateAsync, stopMutateAsync, patchMutate, genStatusQ } = vi.hoisted(() => ({
  fenetreQ: vi.fn(),
  mutateAsync: vi.fn(),
  stopMutateAsync: vi.fn(),
  patchMutate: vi.fn(),
  genStatusQ: vi.fn((): GenerateStatusMock => ({ data: null })),
}));
vi.mock("@/lib/queries/sante", () => ({
  useFenetreCurrent: () => fenetreQ(),
  useActiveGenerateFenetre: () => ({ data: null, refetch: vi.fn() }),
  useStartGenerateFenetre: () => ({ mutateAsync, isPending: false }),
  useGenerateFenetreStatus: () => genStatusQ(),
  useStopGenerateFenetre: () => ({ mutateAsync: stopMutateAsync, isPending: false }),
  useCartPlan: () => ({ data: undefined }),
  useStartCartFill: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
  useCartFillStatus: () => ({ data: null }),
  usePatchPlan: () => ({ mutate: patchMutate, mutateAsync: vi.fn(), isPending: false }),
  useSanteFavorites: () => ({ data: [] }),
  useSanteAliments: () => ({ data: [] }),
  useAddSanteFavorite: () => ({ mutate: vi.fn() }),
  useRemoveSanteFavorite: () => ({ mutate: vi.fn() }),
}));

import { FenetreTab } from "@/components/sante/FenetreTab";

beforeEach(() => {
  fenetreQ.mockReset();
  mutateAsync.mockReset();
  stopMutateAsync.mockReset();
  patchMutate.mockReset();
  genStatusQ.mockReset();
  genStatusQ.mockReturnValue({ data: null });
});

const WIN = {
  anchor_date: "2026-07-20",
  length: 3,
  poids_used: 51,
  jours: [
    {
      date: "2026-07-20",
      intensite: "medium",
      items: [
        { aliment: "Riz", quantite_g: 300, quantite_str: "300g", calories: 0, proteines: 0, lipides: 0, glucides: 0, prix: 0 },
      ],
      totals: { Calories: 2000, Protéines: 110, Lipides: 70, Glucides: 250 },
      targets: { Calories: 2000, Protéines: 100, Lipides: 70, Glucides: 300 },
    },
  ],
  shopping_list: [{ aliment: "Riz", quantite_g: 900, prix: 1.4, promo: true, dispo_g: 200, a_acheter_g: 700 }],
  score: { couverture_moyenne: 0.82, pct_micros_atteints: 70, cout_total: 42, cout_a_payer: 30, ratio: 0.0195, sous_couverts: ["VitD"] },
  warning: null,
};

describe("FenetreTab", () => {
  it("renders the shopping list, score and under-covered micros", () => {
    fenetreQ.mockReturnValue({ data: WIN, isLoading: false, isError: false });
    render(<FenetreTab goal={null} onSaveMesure={vi.fn()} />);
    expect(screen.getAllByText("Riz").length).toBeGreaterThan(0); // liste de courses + par jour
    expect(screen.getByText("promo")).toBeInTheDocument();
    expect(screen.getByText("VitD")).toBeInTheDocument();
    expect(screen.getByText(/équilibre micros/)).toBeInTheDocument();
    expect(screen.getByText(/équilibre macros/)).toBeInTheDocument();
    expect(screen.getByText(/équilibre global/)).toBeInTheDocument();
    expect(screen.getByText(/2000 \/ 2000 kcal/)).toBeInTheDocument();
    expect(screen.getByText(/110 \/ 100 g/)).toBeInTheDocument();
  });

  it("annonce le jour de courses et le rabais étudiant", () => {
    // Fenêtre jeu-dim : les courses se font la veille, le mercredi, pour rester
    // dans la plage du rabais étudiant Super C (lun→mer).
    fenetreQ.mockReturnValue({
      data: { ...WIN, anchor_date: "2026-07-23", shopping_date: "2026-07-22", length: 4 },
      isLoading: false,
      isError: false,
    });
    render(<FenetreTab goal={null} onSaveMesure={vi.fn()} />);
    expect(screen.getByText(/Courses et cuisine le/)).toBeInTheDocument();
    expect(screen.getByText(/mercredi 22 juillet/)).toBeInTheDocument();
    expect(screen.getByText(/rabais étudiant/)).toBeInTheDocument();
  });

  it("n'affiche aucun jour de courses quand l'API n'en fournit pas", () => {
    fenetreQ.mockReturnValue({ data: WIN, isLoading: false, isError: false });
    render(<FenetreTab goal={null} onSaveMesure={vi.fn()} />);
    expect(screen.queryByText(/Courses et cuisine le/)).not.toBeInTheDocument();
  });

  it("annonce que l'optimisation tourne en tâche de fond", () => {
    fenetreQ.mockReturnValue({ data: WIN, isLoading: false, isError: false });
    genStatusQ.mockReturnValue({
      data: { job_id: "abc", status: "running", message: "Optimisation du plan en cours…",
              anchor_date: null, error: null },
    });
    render(<FenetreTab goal={null} onSaveMesure={vi.fn()} />);
    expect(screen.getByText(/Optimisation du plan en cours/)).toBeInTheDocument();
    expect(screen.getByText(/Tu peux quitter cet onglet/)).toBeInTheDocument();
  });

  it("peut lancer l'optimisation avec les prix enregistrés", async () => {
    fenetreQ.mockReturnValue({ data: WIN, isLoading: false, isError: false });
    mutateAsync.mockResolvedValue({ job_id: "recorded-prices-job" });
    render(<FenetreTab goal={null} onSaveMesure={vi.fn()} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /prix enregistrés/i }));
    });

    expect(mutateAsync).toHaveBeenCalledWith({
      poids: undefined,
      force: true,
      refresh_prices: false,
    });
  });

  it("affiche progression, température et arrêt de la recherche", async () => {
    fenetreQ.mockReturnValue({ data: WIN, isLoading: false, isError: false });
    genStatusQ.mockReturnValue({
      data: {
        job_id: "abc", status: "running", message: "Recherche 12/96",
        anchor_date: null, error: null, attempt: 12, max_attempts: 96,
        solutions_found: 9, pareto_solutions: 3, temperature: 0.42,
        convergence: 0.5, stagnation: 12, patience: 24,
        best_coverage: 0.982, best_cost: 54.2, best_ratio: 0.0181,
        best_items: [{ aliment: "Lentilles", quantite_g: 450 }],
      },
      refetch: vi.fn(),
    });
    render(<FenetreTab goal={null} onSaveMesure={vi.fn()} />);
    expect(screen.getByText(/Température 0.42/)).toBeInTheDocument();
    expect(screen.getByText(/9 solutions/)).toBeInTheDocument();
    expect(screen.getByText(/Meilleur ratio 0.018 pt\/\$/)).toBeInTheDocument();
    expect(screen.getByText(/Voir le meilleur candidat/)).toBeInTheDocument();
    expect(screen.getByText("⏹ Arrêter")).toBeInTheDocument();
    fireEvent.click(screen.getByText("⏹ Arrêter"));
    await act(async () => {});
    expect(stopMutateAsync).toHaveBeenCalledWith("abc");
  });

  it("remonte l'échec d'une génération de fond", () => {
    fenetreQ.mockReturnValue({ data: WIN, isLoading: false, isError: false });
    genStatusQ.mockReturnValue({
      data: { job_id: "abc", status: "failed", message: "Échec de la génération.",
              anchor_date: null, error: "Aucun poids connu et aucun poids fourni." },
    });
    render(<FenetreTab goal={null} onSaveMesure={vi.fn()} />);
    expect(screen.getByText(/Aucun poids connu/)).toBeInTheDocument();
  });

  it("renders an empty state when no window exists", () => {
    fenetreQ.mockReturnValue({ data: undefined, isLoading: false, isError: false });
    render(<FenetreTab goal={null} onSaveMesure={vi.fn()} />);
    expect(screen.getByText(/Aucune fenêtre/)).toBeInTheDocument();
  });

  it("surfaces the optimizer warning when present", () => {
    fenetreQ.mockReturnValue({ data: { ...WIN, warning: "Budget dépassé de 3.20 CAD" }, isLoading: false, isError: false });
    render(<FenetreTab goal={null} onSaveMesure={vi.fn()} />);
    expect(screen.getByText(/Budget dépassé de 3.20 CAD/)).toBeInTheDocument();
  });

  it("shows pantry deduction (à acheter) and out-of-pocket cost", () => {
    fenetreQ.mockReturnValue({ data: WIN, isLoading: false, isError: false });
    render(<FenetreTab goal={null} onSaveMesure={vi.fn()} />);
    expect(screen.getByText(/700 g à acheter/)).toBeInTheDocument();
    expect(screen.getByText(/À payer/)).toBeInTheDocument();
  });

  it("logs per-day consumption via 'J'ai suivi le plan' (feeds the debt/carryover)", () => {
    fenetreQ.mockReturnValue({ data: WIN, isLoading: false, isError: false });
    render(<FenetreTab goal={null} onSaveMesure={vi.fn()} />);

    expect(screen.getByText(/conso non enregistrée/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText("✓ J'ai suivi le plan"));

    expect(patchMutate).toHaveBeenCalledTimes(1);
    const call = patchMutate.mock.calls[0][0];
    expect(call.date).toBe("2026-07-20");
    expect(call.patch.consumed_grams).toEqual({ Riz: 300 });

    // Simule le onSuccess de la mutation → le badge passe à "enregistrée".
    const onSuccess = patchMutate.mock.calls[0][1]?.onSuccess as (() => void) | undefined;
    act(() => onSuccess?.());
    expect(screen.getByText(/✓ conso enregistrée/)).toBeInTheDocument();
  });
});
