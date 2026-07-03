import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EmptyState } from "@/components/ui/empty-state";

describe("EmptyState éditorial", () => {
  it("titre en serif italique (voix de l'almanach)", () => {
    render(<EmptyState title="Aucune tenue" />);
    const title = screen.getByText("Aucune tenue");
    expect(title.className).toContain("font-display");
    expect(title.className).toContain("italic");
  });

  it("ornement laiton entre titre et description", () => {
    render(<EmptyState title="Vide" description="Ajoute une pièce." />);
    expect(screen.getByTestId("empty-ornament")).toBeInTheDocument();
    expect(screen.getByText("Ajoute une pièce.")).toBeInTheDocument();
  });

  it("action et icône rendues", () => {
    render(
      <EmptyState title="Vide" icon={<svg data-testid="ic" />} action={<button>Créer</button>} />,
    );
    expect(screen.getByTestId("ic")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Créer" })).toBeInTheDocument();
  });
});
