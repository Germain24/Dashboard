import { beforeEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { DeStarrChart } from "@/components/finance/DeStarrChart";
import type { OptProgress } from "@/components/finance/buffett-ui";

type ScorePoint = NonNullable<OptProgress["score_history"]>[number];

function point(iteration: number, score: number): ScorePoint {
  return { iteration, seed_num: 1, seed_iteration: iteration, score };
}

function progress(overrides: Partial<OptProgress>): OptProgress {
  return {
    active: true,
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
    expect(screen.getByText("2 itérations")).toBeInTheDocument();
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
    expect(screen.getByText("2 itérations")).toBeInTheDocument();
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
});
