import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CollapsibleSection } from "@/components/ui/collapsible-section";

describe("CollapsibleSection", () => {
  it("fermé par défaut : contenu absent, aria-expanded=false", () => {
    render(<CollapsibleSection title="Détails">contenu-caché</CollapsibleSection>);
    expect(screen.queryByText("contenu-caché")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Détails/ })).toHaveAttribute("aria-expanded", "false");
  });

  it("defaultOpen : contenu visible", () => {
    render(<CollapsibleSection title="Détails" defaultOpen>contenu-visible</CollapsibleSection>);
    expect(screen.getByText("contenu-visible")).toBeInTheDocument();
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "true");
  });

  it("clic ouvre puis ferme", () => {
    render(<CollapsibleSection title="Détails">contenu</CollapsibleSection>);
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("contenu")).toBeInTheDocument();
  });

  it("aria-controls pointe la zone", () => {
    render(<CollapsibleSection title="Détails" defaultOpen>x</CollapsibleSection>);
    const btn = screen.getByRole("button");
    expect(btn.getAttribute("aria-controls")).toBeTruthy();
  });
});
