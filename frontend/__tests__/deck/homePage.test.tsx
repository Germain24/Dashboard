import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MotionConfig } from "motion/react";

// Mocks data : on vérifie seulement que la page monte le nouveau Deck.
vi.mock("@/lib/queries/sante", () => ({
  useScore: vi.fn(() => ({ isError: true })),
  useWaterToday: vi.fn(() => ({ isError: true })),
}));
vi.mock("@/lib/queries/entrainement", () => ({
  useEntrainementToday: vi.fn(() => ({ isError: true })),
}));
vi.mock("@/lib/queries/skincare", () => ({ useSkincareToday: vi.fn(() => ({ isError: true })) }));
vi.mock("@/components/home/TodayPanel", () => ({ TodayPanel: () => <div>panel-aujourdhui</div> }));
vi.mock("@/components/layout/ModuleAccess", () => ({
  ModuleAccess: ({ variant }: { variant: string }) => <div>module-access-{variant}</div>,
}));
vi.mock("@/components/Greeting", () => ({ Greeting: () => <div>greeting</div> }));
import HomePage from "@/src/app/page";

describe("HomePage", () => {
  it("monte la grille spatiale avec le secteur Santé et l'intro", () => {
    const { container } = render(
      <MotionConfig reducedMotion="always">
        <HomePage />
      </MotionConfig>,
    );
    expect(screen.getByText("panel-aujourdhui")).toBeInTheDocument();
    expect(screen.getByText("module-access-home")).toBeInTheDocument();
    expect(container.querySelector("#sante")).toBeInTheDocument();
  });
});
