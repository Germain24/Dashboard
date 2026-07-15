import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

/** Régression : pendant la phase DE du run automatique, le scoring s'arrête
 *  souvent sous 100 % (tickers sautés : 10471/10490 = 99.8 %). L'onglet ne
 *  doit PAS conditionner le relais de /portfolio/progress (barre DE + graphe
 *  STARR en direct) à `progress_pct >= 100`, sinon plus rien ne s'affiche
 *  dès qu'un run saute quelques tickers (#bug rapporté). */

const api = vi.hoisted(() => ({
  buffettRuns: vi.fn(),
  buffettProgress: vi.fn(),
  portfolioProgress: vi.fn(),
  buffettRun: vi.fn(),
  buffettDeleteRun: vi.fn(),
  buffettStart: vi.fn(),
  buffettAnalyzeTicker: vi.fn(),
  portfolioCreate: vi.fn(),
  optimizationStop: vi.fn(),
}));

vi.mock("@/lib/finance", () => ({ financeApi: api }));

import { BuffettTab } from "@/components/finance/BuffettTab";

describe("BuffettTab — relais de la progression DE", () => {
  beforeEach(() => {
    cleanup();
    sessionStorage.clear();
    vi.clearAllMocks();
    api.buffettRuns.mockResolvedValue([]);
  });

  it("affiche l'optimisation en cours même si le scoring a fini sous 100 % (tickers sautés)", async () => {
    api.buffettProgress.mockResolvedValue({
      run_id: 39, statut: "en_cours", active: true,
      progress_pct: 99.8, n_done: 10471, n_total: 10490, paused_until: null,
    });
    api.portfolioProgress.mockResolvedValue({
      active: true, phase: "optimisation", seed_num: 1, iteration: 42,
      convergence: 0.2, progress_pct: 20, message: "", run_id: 39,
      stop_requested: false, best_score: 0.51,
    });

    render(<BuffettTab />);

    // Ce libellé ne s'affiche que si l'état optProgress du TAB (pas celui du
    // panneau d'actions) est actif — c'est lui qui alimente le graphe STARR.
    expect(await screen.findByText(/Scoring terminé — optimisation du portefeuille en cours/))
      .toBeInTheDocument();
  });

  it("ne relaie pas une optimisation d'un autre run_id", async () => {
    api.buffettProgress.mockResolvedValue({
      run_id: 39, statut: "en_cours", active: true,
      progress_pct: 99.8, n_done: 10471, n_total: 10490, paused_until: null,
    });
    api.portfolioProgress.mockResolvedValue({
      active: true, phase: "optimisation", seed_num: 1, iteration: 42,
      convergence: 0.2, progress_pct: 20, message: "", run_id: 7,
      stop_requested: false, best_score: 0.51,
    });

    render(<BuffettTab />);

    expect(await screen.findByText(/Analyse en cours/)).toBeInTheDocument();
    expect(screen.queryByText(/Scoring terminé — optimisation du portefeuille en cours/))
      .not.toBeInTheDocument();
  });
});
