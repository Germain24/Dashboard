import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RiskMetricsRow } from "@/components/finance/RiskMetricsRow";

describe("RiskMetricsRow", () => {
  it("affiche Sharpe et Sortino cote a cote", () => {
    render(<RiskMetricsRow metrics={{ sharpe: 1.23, sortino: 2.05, max_drawdown_pct: 12.5 }} />);
    expect(screen.getByText("Sharpe")).toBeInTheDocument();
    expect(screen.getByText("1,23")).toBeInTheDocument();
    expect(screen.getByText("Sortino")).toBeInTheDocument();
    expect(screen.getByText("2,05")).toBeInTheDocument();
  });

  it("affiche un tiret quand Sortino est non defini (aucune baisse sur la periode)", () => {
    render(<RiskMetricsRow metrics={{ sharpe: 1.23, sortino: null, max_drawdown_pct: 0 }} />);
    const sortino = screen.getByTitle(/aucun rendement baissier/i);
    expect(sortino).toHaveTextContent("—");
  });

  it("ne rend rien sans metrique exploitable", () => {
    const { container } = render(<RiskMetricsRow metrics={{}} />);
    expect(container).toBeEmptyDOMElement();
  });

  // Volatilite et concentration sortaient toujours vides de l'API : le schema
  // declarait `volatilite_annuelle_pct`/`hhi_label` la ou le service produisait
  // `volatilite_annualisee_pct`/`concentration`. Noms realignes -> ces deux
  // champs vivent enfin, d'ou leur affichage ici.
  it("affiche volatilite et concentration", () => {
    render(
      <RiskMetricsRow
        metrics={{ sharpe: 1.2, sortino: 1.8, max_drawdown_pct: 8, volatilite_annualisee_pct: 14.37, concentration: "élevée" }}
      />,
    );
    expect(screen.getByText("Volatilité")).toBeInTheDocument();
    expect(screen.getByText("14,37 %")).toBeInTheDocument();
    expect(screen.getByText("Concentration")).toBeInTheDocument();
    expect(screen.getByText("élevée")).toBeInTheDocument();
  });

  it("masque la concentration tant qu'elle est inconnue", () => {
    render(<RiskMetricsRow metrics={{ sharpe: 1.2, concentration: "inconnu" }} />);
    expect(screen.queryByText("Concentration")).not.toBeInTheDocument();
  });
});
