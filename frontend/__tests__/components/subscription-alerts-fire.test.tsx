import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SubscriptionAlerts } from "@/components/budget/SubscriptionAlerts";
import { FireCard } from "@/components/finance/FireCard";
import type { SubscriptionAlerts as Alerts, FireReport } from "@/lib/budget";

const NO_ALERTS: Alerts = { hausses: [], doublons: [], nb_alertes: 0, surcout_mensuel: 0 };

const hausse = {
  marchand: "NETFLIX.COM", montant_precedent: 15.99, montant_actuel: 18.99,
  delta: 3, delta_pct: 18.8, date: "2026-04-05", occurrences: 4, category_id: null,
};

const FIRE: FireReport = {
  patrimoine_net: 100000, revenus_annuels: 48000, epargne_annuelle: 20000,
  depenses_annuelles: 28000, objectif_fi: 700000, taux_epargne_pct: 41.7,
  taux_retrait_pct: 4, rendement_reel_pct: 5, progression_pct: 14.3,
  annees_restantes: 17.1, annee_cible: 2043, atteint: false, horizon_max: 60,
  mois_analyses: 12, devise: "EUR",
};

describe("SubscriptionAlerts (#260)", () => {
  it("n'affiche rien sans alerte", () => {
    const { container } = render(<SubscriptionAlerts alerts={NO_ALERTS} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("affiche une hausse avec l'ancien et le nouveau prix", () => {
    render(<SubscriptionAlerts alerts={{ ...NO_ALERTS, hausses: [hausse], nb_alertes: 1, surcout_mensuel: 3 }} />);
    expect(screen.getByText(/NETFLIX\.COM/)).toBeInTheDocument();
    expect(screen.getByText(/15,99/)).toBeInTheDocument();
    expect(screen.getByText(/18,99/)).toBeInTheDocument();
    expect(screen.getByText(/\+18,8\s*%/)).toBeInTheDocument();
  });

  it("affiche un doublon de service avec les deux libellés", () => {
    const doublon = {
      type: "meme_service" as const, service: "SPOTIFY",
      marchands: ["SPOTIFY AB", "SPOTIFY P34X"], mois: "2026-04",
      occurrences: 4, montant_redondant: 11.99,
    };
    render(<SubscriptionAlerts alerts={{ ...NO_ALERTS, doublons: [doublon], nb_alertes: 1, surcout_mensuel: 11.99 }} />);
    expect(screen.getByText(/SPOTIFY AB/)).toBeInTheDocument();
    expect(screen.getByText(/SPOTIFY P34X/)).toBeInTheDocument();
  });

  it("affiche un double prélèvement avec son mois", () => {
    const doublon = {
      type: "double_prelevement" as const, service: "GYM",
      marchands: ["GYM PLUS"], mois: "2026-03", occurrences: 2, montant_redondant: 40,
    };
    render(<SubscriptionAlerts alerts={{ ...NO_ALERTS, doublons: [doublon], nb_alertes: 1, surcout_mensuel: 40 }} />);
    expect(screen.getByText(/GYM PLUS/)).toBeInTheDocument();
    expect(screen.getByText(/2026-03/)).toBeInTheDocument();
  });

  it("résume le surcoût mensuel dans l'en-tête", () => {
    render(<SubscriptionAlerts alerts={{ ...NO_ALERTS, hausses: [hausse], nb_alertes: 1, surcout_mensuel: 3 }} />);
    expect(screen.getByText(/1 alerte/)).toBeInTheDocument();
  });
});

describe("FireCard (#268)", () => {
  it("affiche le taux d'épargne et les années restantes", () => {
    render(<FireCard fire={FIRE} />);
    expect(screen.getByText("41,7 %")).toBeInTheDocument();
    expect(screen.getByText("17,1 ans")).toBeInTheDocument();
    expect(screen.getByText(/2043/)).toBeInTheDocument();
  });

  it("signale une indépendance déjà atteinte", () => {
    render(<FireCard fire={{ ...FIRE, atteint: true, annees_restantes: 0, progression_pct: 120 }} />);
    expect(screen.getByText(/Atteinte/i)).toBeInTheDocument();
  });

  it("signale un objectif hors d'atteinte quand l'épargne ne suffit pas", () => {
    render(<FireCard fire={{ ...FIRE, annees_restantes: null, annee_cible: null, taux_epargne_pct: -5 }} />);
    expect(screen.getByText(/Hors d'atteinte/i)).toBeInTheDocument();
    expect(screen.getByText(/60 ans/)).toBeInTheDocument();
  });

  it("n'affiche rien tant que le rapport n'est pas chargé", () => {
    const { container } = render(<FireCard fire={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });
});
