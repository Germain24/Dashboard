import { beforeEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import {
  DeStarrChart,
  temperatureBuckets,
  temperatureColor,
} from "@/components/finance/DeStarrChart";
import type { OptProgress } from "@/components/finance/buffett-ui";

type ScorePoint = NonNullable<OptProgress["score_history"]>[number];

function point(iteration: number, score: number): ScorePoint {
  return { iteration, seed_num: 1, seed_iteration: iteration, score };
}

function progress(overrides: Partial<OptProgress>): OptProgress {
  return {
    active: true,
    status: "running",
    phase: "optimisation",
    seed_num: 1,
    iteration: 1,
    total_iterations: 1,
    initialization_attempt: 0,
    initialization_max: 0,
    convergence: 0.1,
    progress_pct: 10,
    message: "",
    run_id: 1,
    optimization_id: "opt-1",
    optimization_started_at: 1,
    stop_requested: false,
    best_score: 0.5,
    score_history: [],
    ...overrides,
  };
}

describe("DeStarrChart", () => {
  beforeEach(() => {
    sessionStorage.clear();
    cleanup();
  });

  it("n'affiche rien tant qu'il n'y a pas deux itérations", () => {
    render(<DeStarrChart optProgress={progress({ score_history: [point(1, 0.5)] })} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("ajoute un point par itération même lorsque le meilleur score ne change pas", () => {
    const { rerender } = render(
      <DeStarrChart optProgress={progress({ score_history: [point(1, 0.5)] })} />,
    );
    rerender(
      <DeStarrChart optProgress={progress({
        iteration: 2,
        total_iterations: 2,
        score_history: [point(2, 0.5)],
      })} />,
    );

    expect(screen.getByRole("img")).toHaveAccessibleName(/2 générations/);
    expect(screen.getByText("2 générations")).toBeInTheDocument();
  });

  it("accepte un lot de points incrémentaux retourné par le serveur", () => {
    render(<DeStarrChart optProgress={progress({
      iteration: 3,
      total_iterations: 3,
      best_score: 0.8,
      score_history: [point(1, 0.5), point(2, 0.5), point(3, 0.8)],
    })} />);

    expect(screen.getByRole("img")).toHaveAccessibleName(/3 générations/);
    expect(screen.getByText("min 0,5000 · max 0,8000")).toBeInTheDocument();
  });

  it("reprend l'historique du même run après un remount", () => {
    const { unmount } = render(<DeStarrChart optProgress={progress({
      total_iterations: 2,
      iteration: 2,
      best_score: 0.8,
      score_history: [point(1, 0.5), point(2, 0.8)],
    })} />);
    expect(screen.getByText("2 générations")).toBeInTheDocument();
    unmount();

    render(<DeStarrChart optProgress={progress({
      total_iterations: 2,
      iteration: 2,
      best_score: 0.8,
      score_history: [],
    })} />);
    expect(screen.getByText("min 0,5000 · max 0,8000")).toBeInTheDocument();
  });

  it("ne réutilise pas l'historique d'un autre run", () => {
    const { unmount } = render(<DeStarrChart optProgress={progress({
      run_id: 1,
      total_iterations: 2,
      iteration: 2,
      best_score: 0.8,
      score_history: [point(1, 0.5), point(2, 0.8)],
    })} />);
    unmount();

    render(<DeStarrChart optProgress={progress({
      run_id: 2,
      total_iterations: 2,
      iteration: 2,
      best_score: 0.2,
      score_history: [point(1, 0.1), point(2, 0.2)],
    })} />);
    expect(screen.getByText("min 0,1000 · max 0,2000")).toBeInTheDocument();
  });

  it("remet l'historique à zéro pour une nouvelle optimisation du même run", () => {
    const { unmount } = render(<DeStarrChart optProgress={progress({
      run_id: 1,
      optimization_id: "opt-old",
      total_iterations: 2,
      iteration: 2,
      score_history: [point(1, 0.5), point(2, 0.8)],
    })} />);
    expect(screen.getByText("2 générations")).toBeInTheDocument();
    unmount();

    render(<DeStarrChart optProgress={progress({
      run_id: 1,
      optimization_id: "opt-new",
      total_iterations: 1,
      iteration: 1,
      score_history: [point(1, 0.2)],
    })} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("trace le meilleur global et le meilleur cumulatif de chaque seed", () => {
    render(<DeStarrChart optProgress={progress({
      seed_num: 2,
      iteration: 2,
      total_iterations: 4,
      best_score: 0.9,
      score_history: [
        point(1, 0.4),
        point(2, 0.7),
        { iteration: 3, seed_num: 2, seed_iteration: 1, score: 0.3 },
        { iteration: 4, seed_num: 2, seed_iteration: 2, score: 0.9 },
      ],
    })} />);

    // Un changement de `seed_num` (cycle de rafraîchissement ETF) ne coupe plus
    // la courbe : la recherche est continue, la trace doit l'être aussi.
    expect(screen.getByTestId("score-series")).toBeInTheDocument();
    expect(screen.getByTestId("global-series")).toBeInTheDocument();
    expect(screen.getByText(/global.*0,9000/)).toBeInTheDocument();
    expect(screen.getByText(/seed.*0,9000/)).toBeInTheDocument();
  });

  it("colore la courbe par la température quand elle est fournie", () => {
    render(<DeStarrChart optProgress={progress({
      total_iterations: 3,
      iteration: 3,
      best_score: 0.8,
      score_history: [
        { ...point(1, 0.5), temperature: 0.05 },
        { ...point(2, 0.6), temperature: 0.5 },
        { ...point(3, 0.8), temperature: 1 },
      ],
    })} />);

    const series = screen.getByTestId("score-series");
    expect(series.getAttribute("stroke")).toMatch(/^url\(#/);
    expect(screen.getByRole("img"))
      .toHaveAccessibleName(/température de 0,05 à 1,00/);
    expect(screen.getByText(/^T/)).toHaveTextContent("1,00");
  });

  it("reste monochrome quand aucun point n'a de température", () => {
    render(<DeStarrChart optProgress={progress({
      total_iterations: 2,
      iteration: 2,
      score_history: [point(1, 0.5), point(2, 0.8)],
    })} />);

    // Un historique d'avant le recuit ne doit pas se voir attribuer un dégradé
    // inventé : le trait reste uni.
    expect(screen.getByTestId("score-series")).toHaveAttribute(
      "stroke",
      "var(--temp-cold)",
    );
  });

  it("affiche les tickers forces retenus sur le graphique", () => {
    render(<DeStarrChart optProgress={progress({
      total_iterations: 3,
      iteration: 3,
      score_history: [
        point(1, 0.5),
        {
          ...point(2, 0.6),
          forced_labels: ["CW8.PA ≥ 10.0%", "DFEN.DE ≥ 2.9% (max broker)"],
          forced_action_count: 1,
          forced_etf_count: 1,
        },
        point(3, 0.7),
      ],
    })} />);

    expect(
      screen.getByText(/Exploration 1 · génération 2 · 2 portefeuilles séparés/),
    ).toBeInTheDocument();
    expect(screen.getByText("1 action(s) · 1 ETF/fonds")).toBeInTheDocument();
    expect(
      screen.getByText(/Nouveau meilleur observé.*\+0,1000/),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/CW8\.PA ≥ 10\.0%/).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/DFEN\.DE ≥ 2\.9% \(max broker\)/).length,
    ).toBeGreaterThan(0);
  });
});

describe("temperatureColor", () => {
  it("place le froid, le neutre et le chaud sur la palette divergente", () => {
    expect(temperatureColor(0)).toContain("var(--temp-cold)");
    expect(temperatureColor(0.5)).toContain("var(--temp-mid)");
    expect(temperatureColor(1)).toContain("var(--temp-hot)");
  });

  it("borne les valeurs hors de l'intervalle au lieu d'extrapoler", () => {
    expect(temperatureColor(-3)).toBe(temperatureColor(0));
    expect(temperatureColor(9)).toBe(temperatureColor(1));
  });
});

describe("temperatureBuckets", () => {
  const at = (iteration: number, temperature?: number): ScorePoint => ({
    ...point(iteration, 0.5),
    ...(temperature === undefined ? {} : { temperature }),
  });

  it("rend null quand aucun point n'est daté en température", () => {
    expect(temperatureBuckets([at(1), at(2)], () => 0)).toBeNull();
  });

  it("comble les tranches vides au lieu de trouer le dégradé", () => {
    // Deux points seulement, aux deux extrémités : toutes les tranches
    // intermédiaires sont vides et doivent hériter d'une voisine.
    const buckets = temperatureBuckets(
      [at(1, 0.1), at(100, 0.9)],
      (p) => (p.iteration === 1 ? 0 : 1),
    );
    expect(buckets).not.toBeNull();
    expect(buckets!.every((value) => value !== null)).toBe(true);
    expect(buckets![0]).toBeCloseTo(0.1);
    expect(buckets![buckets!.length - 1]).toBeCloseTo(0.9);
  });
});
