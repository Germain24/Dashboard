import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

function Harness() {
  const [tab, setTab] = useState("un");
  return (
    <Tabs value={tab} onValueChange={setTab}>
      <TabsList>
        <TabsTrigger value="un">Un</TabsTrigger>
        <TabsTrigger value="deux">Deux</TabsTrigger>
      </TabsList>
      <TabsContent value="un">Panneau un</TabsContent>
      <TabsContent value="deux">Panneau deux</TabsContent>
    </Tabs>
  );
}

describe("Tabs — pastille animée", () => {
  it("rend la pastille dans l'onglet actif uniquement", () => {
    render(<Harness />);
    const active = screen.getByRole("tab", { name: "Un" });
    const inactive = screen.getByRole("tab", { name: "Deux" });
    expect(active.querySelector('[data-testid="tab-pill"]')).not.toBeNull();
    expect(inactive.querySelector('[data-testid="tab-pill"]')).toBeNull();
  });

  it("déplace la pastille vers l'onglet cliqué", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("tab", { name: "Deux" }));
    expect(
      screen.getByRole("tab", { name: "Deux" }).querySelector('[data-testid="tab-pill"]'),
    ).not.toBeNull();
    expect(screen.getByText("Panneau deux")).toBeInTheDocument();
  });

  it("conserve la navigation clavier (flèches)", () => {
    render(<Harness />);
    const first = screen.getByRole("tab", { name: "Un" });
    first.focus();
    fireEvent.keyDown(first, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Deux" })).toHaveFocus();
    expect(
      screen.getByRole("tab", { name: "Deux" }).querySelector('[data-testid="tab-pill"]'),
    ).not.toBeNull();
  });
});
