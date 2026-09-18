import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

const pantryMocks = vi.hoisted(() => ({
  query: vi.fn(),
  add: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
}));

vi.mock("@/lib/queries/cuisine", () => ({
  usePantry: () => pantryMocks.query(),
  useAddPantryItem: () => ({ mutate: pantryMocks.add, isPending: false }),
  useUpdatePantryItem: () => ({ mutate: pantryMocks.update, isPending: false }),
  useDeletePantryItem: () => ({ mutate: pantryMocks.remove, isPending: false }),
}));

vi.mock("@/lib/queries/sante", () => ({
  useSanteAliments: () => ({ data: [] }),
}));

import GardeMangerTab from "@/components/cuisine/GardeMangerTab";

const ITEM = {
  id: 12,
  ingredient: "Avoine",
  quantite: 400,
  unite: "g",
  date_peremption: "2026-10-01",
  rayon: "Épicerie sèche",
  statut: "ok" as const,
};

describe("GardeMangerTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pantryMocks.query.mockReturnValue({ data: [ITEM], isError: false });
  });

  it("edits the pantry entry fields and can clear its package date", () => {
    render(<GardeMangerTab />);
    fireEvent.click(screen.getByRole("button", { name: "Modifier Avoine" }));

    expect(screen.getByRole("heading", { name: "Modifier un article" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Ingrédient/), { target: { value: "Flocons d’avoine" } });
    fireEvent.change(screen.getByLabelText(/Quantité/), { target: { value: "500" } });
    fireEvent.change(screen.getByLabelText(/Date sur l’emballage/), { target: { value: "" } });

    fireEvent.click(screen.getByRole("button", { name: "Enregistrer" }));

    expect(pantryMocks.update).toHaveBeenCalledWith(
      {
        id: ITEM.id,
        patch: {
          ingredient: "Flocons d’avoine",
          quantite: 500,
          unite: "g",
          date_peremption: null,
          rayon: "Épicerie sèche",
        },
      },
      expect.objectContaining({ onSuccess: expect.any(Function), onError: expect.any(Function) }),
    );
  });
});
