import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SpatialGrid } from "@/components/deck/SpatialGrid";

function activePanel(container: HTMLElement) {
  return container.querySelector(
    '.spatial-chapter[data-active="true"] [data-spatial-panel][data-active="true"]',
  );
}

describe("SpatialGrid", () => {
  it("navigue verticalement entre secteurs et horizontalement entre sous-sections", () => {
    const { container } = render(<SpatialGrid />);

    expect(container.querySelector("#finance")).toHaveAttribute("data-active", "true");
    expect(activePanel(container)).toHaveAttribute("data-module", "budget");

    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(activePanel(container)).toHaveAttribute("data-module", "finance");

    fireEvent.keyDown(window, { key: "ArrowDown" });
    expect(container.querySelector("#projets")).toHaveAttribute("data-active", "true");
    expect(activePanel(container)).toHaveAttribute("data-module", "agenda");

    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(activePanel(container)).toHaveAttribute("data-module", "score");

    fireEvent.keyDown(window, { key: "ArrowLeft" });
    expect(activePanel(container)).toHaveAttribute("data-module", "agenda");

    fireEvent.keyDown(window, { key: "ArrowUp" });
    expect(container.querySelector("#finance")).toHaveAttribute("data-active", "true");
    expect(activePanel(container)).toHaveAttribute("data-module", "budget");
  });

  it("ignore les flèches quand un champ de saisie a le focus", () => {
    const { container } = render(
      <>
        <input aria-label="Recherche" />
        <SpatialGrid />
      </>,
    );
    const input = container.querySelector("input");
    input?.focus();

    fireEvent.keyDown(input!, { key: "ArrowDown" });

    expect(container.querySelector("#finance")).toHaveAttribute("data-active", "true");
  });

  it("ignore les flèches quand un overlay interactif est ouvert", () => {
    const { container } = render(
      <>
        <div role="menu" aria-label="Menu ouvert" />
        <SpatialGrid />
      </>,
    );

    fireEvent.keyDown(window, { key: "ArrowDown" });

    expect(container.querySelector("#finance")).toHaveAttribute("data-active", "true");
    expect(container.querySelector("#projets")).toHaveAttribute("data-active", "false");
  });

  it("présente les fonctions du module sans carte opérationnelle ni compteur redondant", () => {
    const { container } = render(<SpatialGrid />);
    const panel = activePanel(container);

    expect(screen.queryByText("Opérationnel")).not.toBeInTheDocument();
    expect(screen.queryByText("État du module")).not.toBeInTheDocument();
    expect(screen.queryByText("Position")).not.toBeInTheDocument();
    expect(within(panel as HTMLElement).getByText("Revenus et dépenses")).toBeInTheDocument();
    expect(within(panel as HTMLElement).getByText("Prévisions mensuelles")).toBeInTheDocument();
  });
});
