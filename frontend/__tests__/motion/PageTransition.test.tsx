import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { PageTransition } from "@/lib/motion/PageTransition";
import { durations, EASE_CAMERA } from "@/lib/motion/tokens";

const mockPathname = vi.fn<() => string>();
const motionState = vi.hoisted(() => ({ reduced: false }));

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
}));

vi.mock("motion/react", async () => {
  const React = await import("react");

  const MotionDiv = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement> & {
      initial?: unknown;
      animate?: unknown;
      exit?: unknown;
    }
  >(({ initial, animate, exit, ...props }, ref) =>
    React.createElement("div", {
      ...props,
      ref,
      "data-testid": "page-transition-scene",
      "data-initial": JSON.stringify(initial),
      "data-animate": JSON.stringify(animate),
      "data-exit": JSON.stringify(exit),
    }),
  );

  return {
    AnimatePresence: ({ children, mode }: { children: React.ReactNode; mode?: string }) =>
      React.createElement(
        "div",
        { "data-testid": "page-transition-presence", "data-mode": mode },
        children,
      ),
    motion: { div: MotionDiv },
    useReducedMotion: () => motionState.reduced,
  };
});

describe("PageTransition", () => {
  beforeEach(() => {
    mockPathname.mockReset();
    motionState.reduced = false;
  });

  it("rend les enfants", () => {
    mockPathname.mockReturnValue("/finance");
    render(
      <PageTransition>
        <p>Contenu</p>
      </PageTransition>,
    );
    expect(screen.getByText("Contenu")).toBeInTheDocument();
  });

  it("expose le module courant (1er segment) comme clé de transition", () => {
    mockPathname.mockReturnValue("/finance/transactions");
    render(
      <PageTransition>
        <p>A</p>
      </PageTransition>,
    );
    expect(screen.getByTestId("page-transition").dataset.segment).toBe("/finance");
  });

  it("garde la même clé pour une navigation intra-module", () => {
    mockPathname.mockReturnValue("/finance");
    const { rerender } = render(
      <PageTransition>
        <p>A</p>
      </PageTransition>,
    );
    const wrapper = screen.getByTestId("page-transition");
    const scene = screen.getByTestId("page-transition-scene");

    mockPathname.mockReturnValue("/finance/transactions");
    rerender(
      <PageTransition>
        <p>B</p>
      </PageTransition>,
    );

    expect(screen.getByTestId("page-transition")).toBe(wrapper);
    expect(screen.getByTestId("page-transition-scene")).toBe(scene);
    expect(wrapper.dataset.segment).toBe("/finance");
  });

  it("change de clé quand on change de module", () => {
    mockPathname.mockReturnValue("/finance");
    const { rerender } = render(
      <PageTransition>
        <p>A</p>
      </PageTransition>,
    );
    const wrapper = screen.getByTestId("page-transition");
    const scene = screen.getByTestId("page-transition-scene");

    mockPathname.mockReturnValue("/garderobe");
    rerender(
      <PageTransition>
        <p>B</p>
      </PageTransition>,
    );

    expect(screen.getByTestId("page-transition")).toBe(wrapper);
    expect(screen.getByTestId("page-transition-scene")).not.toBe(scene);
    expect(wrapper.dataset.segment).toBe("/garderobe");
  });

  it("enchaîne une sortie courte et une entrée spatiale en mode wait", () => {
    mockPathname.mockReturnValue("/finance");
    render(
      <PageTransition>
        <p>A</p>
      </PageTransition>,
    );

    expect(screen.getByTestId("page-transition-presence")).toHaveAttribute("data-mode", "wait");

    const scene = screen.getByTestId("page-transition-scene");
    const initial = JSON.parse(scene.dataset.initial ?? "{}");
    const animate = JSON.parse(scene.dataset.animate ?? "{}");
    const exit = JSON.parse(scene.dataset.exit ?? "{}");

    expect(initial).toMatchObject({
      opacity: 0,
      y: 18,
      scale: 0.985,
      filter: "blur(10px)",
    });
    expect(exit).toMatchObject({
      opacity: 0,
      y: -8,
      scale: 0.992,
      filter: "blur(4px)",
      transition: { duration: durations.routeExit, ease: EASE_CAMERA },
    });
    expect(animate).toMatchObject({
      opacity: 1,
      y: 0,
      scale: 1,
      filter: "blur(0px)",
      transition: { duration: durations.routeEnter, ease: EASE_CAMERA },
      transitionEnd: { transform: "none", filter: "none" },
    });
    expect(durations.routeExit + durations.routeEnter).toBe(0.8);
  });

  it("rend un contenu statique sans scène quand reduced-motion est actif", () => {
    motionState.reduced = true;
    mockPathname.mockReturnValue("/finance");
    render(
      <PageTransition>
        <p>Statique</p>
      </PageTransition>,
    );

    expect(screen.getByTestId("page-transition")).toHaveAttribute("data-segment", "/finance");
    expect(screen.getByText("Statique")).toBeInTheDocument();
    expect(screen.queryByTestId("page-transition-presence")).not.toBeInTheDocument();
    expect(screen.queryByTestId("page-transition-scene")).not.toBeInTheDocument();
  });
});
