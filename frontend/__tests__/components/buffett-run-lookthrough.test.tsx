import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  buffettEquityLookthrough: vi.fn(),
  backtest: vi.fn(),
  backtestWalkForward: vi.fn(),
  selectBuffettScenario: vi.fn(),
}));

vi.mock("@/lib/finance", () => ({ financeApi: api }));

import { BuffettRunDetailView } from "@/components/finance/BuffettRunDetailView";

describe("BuffettRunDetailView — sélecteur ETF / Actions", () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    api.buffettEquityLookthrough.mockResolvedValue({
      version: 2,
      generated_at: "2026-08-31",
      total_pct: 100,
      known_equities_pct: 95,
      other_equities_pct: 2,
      unknown_pct: 2,
      non_equity_pct: 1,
      equity_coverage_pct: 97,
      rows: [
        {
          ticker: "AAPL",
          name: "Apple Inc.",
          weight_pct: 5,
          sources: ["CW8.PA"],
        },
      ],
      etfs: [
        {
          ticker: "CW8.PA",
          status: "complete",
          source: "index_composition_cache",
          known_holdings: 100,
          holdings_coverage_pct: 99,
        },
      ],
    });
  });

  it("charge les actions une seule fois et permet de revenir aux ETF", async () => {
    const selected = {
      run: {
        id: 65,
        run_date: "2026-08-31",
        statut: "termine",
        created_at: "2026-08-31T10:00:00",
      },
      top_results: [],
      allocation_cible: [
        {
          id: 1,
          ticker: "CW8.PA",
          nom: "Amundi MSCI World",
          secteur: "ETF",
          allocation_pct: 50,
          allocations: [{ broker: "BoursDirect2", type: "shares", shares: 2, eur: 5000 }],
        },
        {
          id: 2,
          ticker: "EXEL",
          nom: "Exelixis, Inc.",
          secteur: "Healthcare",
          allocation_pct: 5,
          score: 76.9,
          buffett_quality_score: 86.6,
          durability_score: 89,
          dilution_discipline_score: 100,
          financial_moat_proxy_score: 78.7,
          score_confidence_pct: 63.3,
          buffett_rules_score: 79.4,
          allocations: [{ broker: "Trading212", type: "pie", pie_pct: 58, eur: 716 }],
        },
      ],
    };

    render(
      <BuffettRunDetailView
        selected={selected as never}
        onBack={vi.fn()}
        onError={vi.fn()}
        onReload={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByRole("columnheader", { name: "Actif" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Analyse" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Durabilité" })).not.toBeInTheDocument();
    const exelRow = screen.getByText("EXEL").closest("tr");
    expect(exelRow).not.toBeNull();
    expect(within(exelRow!).getByText(/Qualité/)).toBeInTheDocument();
    fireEvent.click(within(exelRow!).getByText("Détails du score"));
    expect(within(exelRow!).getByText("Moat financier")).toBeInTheDocument();
    expect(within(exelRow!).getByText("78,7")).toBeInTheDocument();

    expect(screen.getByRole("tab", { name: "ETF" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("tab", { name: "Actions" }));

    expect(await screen.findByText("Apple Inc.")).toBeInTheDocument();
    expect(screen.getByText("5,00 %")).toBeInTheDocument();
    expect(api.buffettEquityLookthrough).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("tab", { name: "ETF" }));
    expect(screen.getByText("Amundi MSCI World")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Actions" }));

    await waitFor(() => expect(screen.getByText("Apple Inc.")).toBeInTheDocument());
    expect(api.buffettEquityLookthrough).toHaveBeenCalledTimes(1);
  });
});
