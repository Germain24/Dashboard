import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RecommandationsTab } from "@/components/garderobe/RecommandationsTab";

describe("RecommandationsTab", () => {
  it("affiche le total et un conseil", () => {
    render(
      <RecommandationsTab
        recs={{ total_tenues: 3, conseils: [{ slot: "Chaussures", couleur: "Noir", debloque: 2, total_apres: 5 }] }}
      />,
    );
    expect(screen.getByText(/3/)).toBeInTheDocument();
    expect(screen.getByText(/Ajouter Chaussures Noir/)).toBeInTheDocument();
    expect(screen.getByText(/\+2/)).toBeInTheDocument();
  });

  it("invite quand aucun conseil", () => {
    render(<RecommandationsTab recs={{ total_tenues: 0, conseils: [] }} />);
    expect(screen.getByText(/Ajoute d'abord/i)).toBeInTheDocument();
  });
});
