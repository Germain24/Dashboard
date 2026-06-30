import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { Vetement } from "@/lib/garderobe";

const mutate = vi.fn();

vi.mock("@/lib/queries/garderobe", () => ({
  useUploadVetementPhoto: () => ({ mutateAsync: vi.fn() }),
  useUpdateVetement: () => ({ mutate }),
  useObjectif: () => ({ data: { types: [{ nom: "T-shirts" }, { nom: "Polos" }] } }),
}));

import { InventaireTab } from "@/components/garderobe/InventaireTab";

const tee: Vetement = {
  id: "v1", nom: "Tee", marque: "Uniqlo", categorie: "Haut",
  sous_categorie: null, matiere: null, couleur: "Noir",
  temp_min: null, temp_max: null, etat_propre: null, usure_max: null,
  portes: 0, impermeable: false, style: null, extra: null,
  type_objectif: "T-shirts",
  image: null,
  proprete_pct: 100, vie_pct: 100, needs_wash: false, is_worn_out: false,
  ports_avant_lavage: 3, thermal_score: 0, saison: "toutes", entretien: null,
};

describe("InventaireTab — rattachement type objectif", () => {
  beforeEach(() => mutate.mockClear());

  it("le select montre le type courant et PATCH au changement", () => {
    render(<InventaireTab wardrobe={[tee]} />);
    const select = screen.getByTitle(/type objectif/i) as HTMLSelectElement;
    expect(select.value).toBe("T-shirts");
    fireEvent.change(select, { target: { value: "Polos" } });
    expect(mutate).toHaveBeenCalledWith({ id: "v1", patch: { type_objectif: "Polos" } });
  });

  it("l'option vide envoie null (déliaison)", () => {
    render(<InventaireTab wardrobe={[tee]} />);
    const select = screen.getByTitle(/type objectif/i) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "" } });
    expect(mutate).toHaveBeenCalledWith({ id: "v1", patch: { type_objectif: null } });
  });
});
