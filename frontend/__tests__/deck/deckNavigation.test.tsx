import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { nextSectionIndex, nextSubsectionIndex } from "@/components/deck/useDeckNavigation";
import { DeckRail } from "@/components/deck/DeckRail";

describe("nextSectionIndex", () => {
  it("avance uniquement avec ArrowDown (borné en haut)", () => {
    expect(nextSectionIndex(0, "ArrowDown", 3)).toBe(1);
    expect(nextSectionIndex(2, "ArrowDown", 3)).toBe(2); // borné
    expect(nextSectionIndex(0, "ArrowRight", 3)).toBe(0);
  });
  it("recule uniquement avec ArrowUp (borné à 0)", () => {
    expect(nextSectionIndex(1, "ArrowUp", 3)).toBe(0);
    expect(nextSectionIndex(0, "ArrowUp", 3)).toBe(0); // borné
    expect(nextSectionIndex(1, "ArrowLeft", 3)).toBe(1);
  });
  it("ignore les autres touches", () => {
    expect(nextSectionIndex(1, "Enter", 3)).toBe(1);
  });
});

describe("nextSubsectionIndex", () => {
  it("circule horizontalement sans changer de secteur", () => {
    expect(nextSubsectionIndex(0, "ArrowRight", 4)).toBe(1);
    expect(nextSubsectionIndex(1, "ArrowLeft", 4)).toBe(0);
  });

  it("reste borné au premier et au dernier sous-secteur", () => {
    expect(nextSubsectionIndex(3, "ArrowRight", 4)).toBe(3);
    expect(nextSubsectionIndex(0, "ArrowLeft", 4)).toBe(0);
    expect(nextSubsectionIndex(0, "ArrowRight", 0)).toBe(0);
  });
});

describe("DeckRail", () => {
  it("rend un seul rail, un bouton par section et le libellé actif", () => {
    const onJump = vi.fn();
    render(<DeckRail total={3} active={1} labels={["A", "B", "C"]} onJump={onJump} />);

    expect(screen.getAllByRole("navigation")).toHaveLength(1);
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(3);
    expect(buttons[1]).toHaveAttribute("aria-current", "true");
    expect(buttons[1]).toHaveAccessibleName("B, section 2 sur 3, actuelle");
    expect(screen.getByText("B")).toBeVisible();
    expect(screen.queryByText("A")).not.toBeInTheDocument();
    expect(screen.queryByText("C")).not.toBeInTheDocument();
  });

  it("saute vers la section choisie et met à jour la progression", () => {
    const onJump = vi.fn();
    const { rerender } = render(
      <DeckRail total={3} active={0} labels={["A", "B", "C"]} onJump={onJump} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "C, section 3 sur 3" }));
    expect(onJump).toHaveBeenCalledWith(2);

    rerender(<DeckRail total={3} active={2} labels={["A", "B", "C"]} onJump={onJump} />);
    expect(screen.getByRole("button", { name: "C, section 3 sur 3, actuelle" })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(screen.getByTestId("deck-rail-progress")).toHaveStyle({
      "--deck-rail-progress": "1",
    });
  });
});
