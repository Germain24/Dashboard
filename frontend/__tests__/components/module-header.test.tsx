import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ModuleHeader, ModuleTabPanel } from "@/components/layout";

vi.mock("@/components/FreshnessIndicator", () => ({
  FreshnessIndicator: () => null,
}));

const panelId = "test-module-panel";

function Harness() {
  const [active, setActive] = useState("overview");
  return (
    <>
      <ModuleHeader
        title="Module test"
        tabs={[
          { id: "overview", label: "Vue d’ensemble" },
          { id: "activity", label: "Activité" },
          { id: "settings", label: "Réglages" },
        ]}
        active={active}
        onChange={setActive}
        panelId={panelId}
      />
      <ModuleTabPanel panelId={panelId} activeTab={active}>
        Contenu de {active}
      </ModuleTabPanel>
    </>
  );
}

describe("ModuleHeader", () => {
  it("relie les onglets au panneau actif avec le contrat ARIA", () => {
    render(<Harness />);

    const firstTab = screen.getByRole("tab", { name: "Vue d’ensemble" });
    const panel = screen.getByRole("tabpanel");

    expect(screen.getByRole("tablist", { name: "Sections de Module test" })).toBeInTheDocument();
    expect(firstTab).toHaveAttribute("aria-controls", panelId);
    expect(firstTab).toHaveAttribute("id", `${panelId}-tab-overview`);
    expect(panel).toHaveAttribute("id", panelId);
    expect(panel).toHaveAttribute("aria-labelledby", `${panelId}-tab-overview`);
  });

  it("met à jour le panneau et le focus lors de la navigation au clavier", async () => {
    render(<Harness />);

    const firstTab = screen.getByRole("tab", { name: "Vue d’ensemble" });
    firstTab.focus();
    fireEvent.keyDown(firstTab, { key: "ArrowRight" });

    await waitFor(() => {
      expect(screen.getByRole("tab", { name: "Activité" })).toHaveFocus();
    });
    expect(screen.getByRole("tabpanel")).toHaveAttribute(
      "aria-labelledby",
      `${panelId}-tab-activity`,
    );
    expect(screen.getByText("Contenu de activity")).toBeInTheDocument();
  });

  it("propose un contrôle de défilement quand les onglets débordent", async () => {
    render(<Harness />);

    const tablist = screen.getByRole("tablist");
    const scrollBy = vi.fn();
    Object.defineProperties(tablist, {
      clientWidth: { configurable: true, get: () => 100 },
      scrollWidth: { configurable: true, get: () => 300 },
      scrollLeft: { configurable: true, get: () => 0 },
      scrollBy: { configurable: true, value: scrollBy },
    });

    fireEvent(window, new Event("resize"));

    const nextTabs = await screen.findByRole("button", { name: "Voir les onglets suivants" });
    expect(tablist).toHaveAttribute("aria-describedby", `${panelId}-scroll-hint`);
    fireEvent.click(nextTabs);
    expect(scrollBy).toHaveBeenCalledWith({ left: 160, behavior: "smooth" });
  });
});
