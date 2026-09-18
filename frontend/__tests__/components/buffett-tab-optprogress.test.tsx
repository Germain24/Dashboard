import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

/** Régression : pendant la phase DE du run automatique, le scoring s'arrête
 *  souvent sous 100 % (tickers sautés : 10471/10490 = 99.8 %). L'onglet ne
 *  doit PAS conditionner le relais de /portfolio/progress (barre DE + graphe
 *  STARR en direct) à `progress_pct >= 100`, sinon plus rien ne s'affiche
 *  dès qu'un run saute quelques tickers (#bug rapporté). */

const api = vi.hoisted(() => ({
  buffettRuns: vi.fn(),
  buffettLiveState: vi.fn(),
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
import { DeProgressBar } from "@/components/finance/buffett-ui";

describe("BuffettTab — relais de la progression DE", () => {
  beforeEach(() => {
    cleanup();
    sessionStorage.clear();
    vi.clearAllMocks();
    api.buffettRuns.mockResolvedValue([]);
  });

  it("affiche l'optimisation en cours même si le scoring a fini sous 100 % (tickers sautés)", async () => {
    const analysis = {
      run_id: 39,
      statut: "en_cours",
      active: true,
      progress_pct: 99.8,
      n_done: 10471,
      n_total: 10490,
      paused_until: null,
      phase: "optimisation",
      throughput_per_min: 12,
      eta_seconds: 90,
      cache_hits: 10000,
      error_counts: {},
    };
    const optimization = {
      active: true,
      phase: "optimisation",
      seed_num: 1,
      iteration: 42,
      total_iterations: 42,
      initialization_attempt: 0,
      initialization_max: 0,
      convergence: 0.2,
      progress_pct: 20,
      message: "",
      run_id: 39,
      optimization_id: "opt-39",
      optimization_started_at: 1,
      stop_requested: false,
      best_score: 0.51,
    };
    api.buffettLiveState.mockResolvedValue({ analysis, optimization });

    render(<BuffettTab />);

    // Ce libellé ne s'affiche que si l'état optProgress du TAB (pas celui du
    // panneau d'actions) est actif — c'est lui qui alimente le graphe STARR.
    expect(
      await screen.findByText(/Scoring terminé — optimisation du portefeuille en cours/),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Arrêter/ })).toHaveLength(1);
    expect(screen.getAllByRole("progressbar")).toHaveLength(1);
  });

  it("ne relaie pas une optimisation d'un autre run_id", async () => {
    const analysis = {
      run_id: 39,
      statut: "en_cours",
      active: true,
      progress_pct: 99.8,
      n_done: 10471,
      n_total: 10490,
      paused_until: null,
      phase: "optimisation",
      throughput_per_min: 12,
      eta_seconds: 90,
      cache_hits: 10000,
      error_counts: {},
    };
    const optimization = {
      active: true,
      phase: "optimisation",
      seed_num: 1,
      iteration: 42,
      total_iterations: 42,
      initialization_attempt: 0,
      initialization_max: 0,
      convergence: 0.2,
      progress_pct: 20,
      message: "",
      run_id: 7,
      optimization_id: "opt-7",
      optimization_started_at: 1,
      stop_requested: false,
      best_score: 0.51,
    };
    api.buffettLiveState.mockResolvedValue({ analysis, optimization });

    render(<BuffettTab />);

    expect(await screen.findByText(/Analyse en cours/)).toBeInTheDocument();
    expect(
      screen.queryByText(/Scoring terminé — optimisation du portefeuille en cours/),
    ).not.toBeInTheDocument();
  });

  it("affiche le run actif même si le chargement de l'historique échoue", async () => {
    api.buffettRuns.mockRejectedValueOnce(new Error("socket hang up"));
    api.buffettLiveState.mockResolvedValue({
      analysis: {
        run_id: 59,
        statut: "en_cours",
        active: true,
        progress_pct: 100,
        n_done: 15329,
        n_total: 15329,
        phase: "preparation",
        throughput_per_min: 0,
        cache_hits: 0,
        error_counts: {},
      },
      optimization: {
        active: true,
        phase: "preparation",
        seed_num: 0,
        iteration: 0,
        total_iterations: 0,
        initialization_attempt: 0,
        initialization_max: 0,
        convergence: 0,
        progress_pct: 0,
        message: "Compositions ETF — tour 2 · 59 à vérifier",
        run_id: 59,
        optimization_id: "prep-59",
        optimization_started_at: 1,
        stop_requested: false,
        best_score: null,
      },
    });

    render(<BuffettTab />);

    expect(
      await screen.findByText(/Scoring terminé — préparation du portefeuille en cours/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Compositions ETF — tour 2/)).toBeInTheDocument();
  });

  it("signale une préparation sans activité récente", async () => {
    api.buffettLiveState.mockResolvedValue({
      analysis: {
        run_id: 61,
        statut: "en_cours",
        active: true,
        progress_pct: 100,
        phase: "preparation",
        throughput_per_min: 0,
        cache_hits: 0,
        error_counts: {},
      },
      optimization: {
        active: true,
        phase: "preparation",
        seed_num: 0,
        iteration: 0,
        total_iterations: 0,
        initialization_attempt: 0,
        initialization_max: 0,
        convergence: 0,
        progress_pct: 0,
        message: "Indices officiels 12/100",
        run_id: 61,
        optimization_id: "prep-61",
        optimization_started_at: 1,
        stop_requested: false,
        best_score: null,
        last_activity_at: 1,
        seconds_since_activity: 130,
        stalled: true,
      },
    });

    render(<BuffettTab />);

    expect(
      await screen.findByText(/Aucune nouvelle activité depuis plus de 2 minutes/),
    ).toBeInTheDocument();
  });

  it("récupère automatiquement une hydratation initiale interrompue", async () => {
    const live = {
      analysis: {
        run_id: 60,
        statut: "en_cours",
        active: true,
        progress_pct: 100,
        n_done: 100,
        n_total: 100,
        phase: "preparation",
        throughput_per_min: 0,
        cache_hits: 0,
        error_counts: {},
      },
      optimization: {
        active: true,
        phase: "preparation",
        seed_num: 0,
        iteration: 0,
        total_iterations: 0,
        initialization_attempt: 0,
        initialization_max: 0,
        convergence: 0,
        progress_pct: 0,
        message: "Compositions ETF — reprise",
        run_id: 60,
        optimization_id: "prep-60",
        optimization_started_at: 1,
        stop_requested: false,
        best_score: null,
      },
    };
    api.buffettLiveState.mockRejectedValueOnce(new Error("socket hang up")).mockResolvedValue(live);

    render(<BuffettTab />);

    expect(await screen.findByText(/Compositions ETF — reprise/)).toBeInTheDocument();
    expect(api.buffettLiveState).toHaveBeenCalledTimes(2);
  });
});

describe("DeProgressBar — préparation mesurable", () => {
  it("affiche la progression réelle d'un téléchargement groupé", () => {
    render(
      <DeProgressBar
        optProgress={{
          active: true,
          status: "running",
          termination_reason: null,
          phase: "preparation",
          seed_num: 0,
          iteration: 0,
          total_iterations: 0,
          initialization_attempt: 0,
          initialization_max: 0,
          convergence: 0,
          progress_pct: 0,
          message: "Téléchargement des cours… 25/100 titres",
          run_id: 62,
          optimization_id: "prep-62",
          optimization_started_at: 1,
          stop_requested: false,
          best_score: null,
        }}
      />,
    );

    expect(screen.getByText("25%")).toBeInTheDocument();
    expect(screen.getByRole("progressbar").firstElementChild).toHaveStyle({ width: "25%" });
  });
});
