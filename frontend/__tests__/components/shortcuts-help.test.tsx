import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ShortcutsHelp } from "@/components/ShortcutsHelp";

describe("ShortcutsHelp", () => {
  it("n'empile pas l'aide au-dessus d'un dialogue ouvert", () => {
    render(
      <>
        <div role="dialog" aria-label="Dialogue ouvert" />
        <ShortcutsHelp />
      </>,
    );

    fireEvent.keyDown(window, { key: "?" });

    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    expect(screen.queryByText("Raccourcis clavier")).not.toBeInTheDocument();
  });

  it("indique les quatre secteurs accessibles par raccourci", () => {
    render(<ShortcutsHelp />);
    fireEvent.keyDown(window, { key: "?" });

    expect(screen.getByRole("dialog", { name: "Raccourcis clavier" })).toHaveTextContent("1–4");
    expect(screen.getByText("Secteur du Deck")).toBeInTheDocument();
  });
});
