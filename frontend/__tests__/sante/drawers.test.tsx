import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PlanItem } from "@/lib/sante";

const { addFavorite, removeFavorite } = vi.hoisted(() => ({
  addFavorite: vi.fn(),
  removeFavorite: vi.fn(),
}));

vi.mock("@/lib/queries/sante", () => ({
  useSanteFavorites: () => ({ data: ["Avoine"] }),
  useSanteAliments: () => ({ data: [{ nom: "Avoine" }] }),
  useAddSanteFavorite: () => ({ mutate: addFavorite }),
  useRemoveSanteFavorite: () => ({ mutate: removeFavorite }),
}));

import { ConsoDrawer } from "@/components/sante/ConsoDrawer";
import { MicrosDrawer } from "@/components/sante/MicrosDrawer";

const planItems: PlanItem[] = [
  {
    aliment: "Riz",
    quantite_g: 180,
    quantite_str: "180 g",
    calories: 220,
    proteines: 4,
    lipides: 1,
    glucides: 48,
    prix: 0.45,
  },
];

function MicrosHarness() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Ouvrir les micronutriments
      </button>
      <MicrosDrawer
        open={open}
        onClose={() => setOpen(false)}
        targets={{ VitC: 75 }}
        totals={{ VitC: 25 }}
      />
    </>
  );
}

describe("drawers Santé", () => {
  beforeEach(() => {
    addFavorite.mockClear();
    removeFavorite.mockClear();
  });

  it("migre le tiroir de micronutriments vers un dialogue accessible et restaure le focus", async () => {
    render(<MicrosHarness />);

    const trigger = screen.getByRole("button", { name: "Ouvrir les micronutriments" });
    trigger.focus();
    fireEvent.click(trigger);

    expect(
      await screen.findByRole("dialog", { name: "Détail micronutriments" }),
    ).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Fermer" })).toHaveFocus());

    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(trigger).toHaveFocus();
  });

  it("garde les quantités et la recherche de consommation libellées et défilables", () => {
    const onClose = vi.fn();
    render(
      <ConsoDrawer
        open
        onClose={onClose}
        planItems={planItems}
        initialConsumed={{ Avoine_g: 60 }}
        onSave={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(
      screen.getByRole("dialog", { name: /ce que j'ai mangé aujourd'hui/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("spinbutton", { name: "Quantité consommée pour Riz, en grammes" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("spinbutton", { name: "Quantité consommée pour Avoine, en grammes" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: "Rechercher un aliment à ajouter" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retirer Avoine des favoris" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByText(/Pré-rempli avec le plan généré/).parentElement).toHaveClass(
      "overflow-y-auto",
    );

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });
});
