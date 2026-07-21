import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";

describe("Primitives UI accessibles", () => {
  it("associe chaque erreur à un champ avec des identifiants uniques", () => {
    render(
      <>
        <Input label="Nom" error="Nom requis" />
        <Input label="Ville" error="Ville requise" />
      </>,
    );

    const name = screen.getByRole("textbox", { name: "Nom" });
    const city = screen.getByRole("textbox", { name: "Ville" });
    expect(name.id).not.toBe(city.id);
    expect(name).toHaveAttribute("aria-invalid", "true");
    expect(name).toHaveAccessibleDescription("Nom requis");
    expect(city).toHaveAccessibleDescription("Ville requise");
  });

  it("annonce la direction de tri et expose une pagination nommée", () => {
    render(
      <DataTable
        data={[
          { id: 1, label: "B", amount: 20 },
          { id: 2, label: "A", amount: 10 },
          { id: 3, label: "C", amount: 30 },
        ]}
        columns={[
          { key: "label", header: "Libellé", sortable: true },
          { key: "amount", header: "Montant" },
        ]}
        pageSize={2}
        ariaLabel="Transactions"
      />,
    );

    const table = screen.getByRole("table", { name: "Transactions" });
    const labelHeader = within(table).getByRole("columnheader", { name: "Libellé" });
    fireEvent.click(within(labelHeader).getByRole("button"));
    expect(labelHeader).toHaveAttribute("aria-sort", "ascending");
    expect(screen.getByRole("button", { name: "Page précédente" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Page suivante" })).toBeEnabled();
  });
});
