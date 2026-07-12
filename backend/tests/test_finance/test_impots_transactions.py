"""Plus/moins-values réalisées FIFO depuis le grand livre des transactions."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401
from app.models.finance import Transaction
from app.services.finance.impots_transactions import (
    compute_realized_gains_fifo, compute_realized_sales_fifo, compute_tax_summary, realized_sales_detail,
)


@dataclass
class FakeTx:
    date: dt.datetime
    ticker: str
    type: str
    quantite: float
    prix_unitaire: float
    devise: str = "EUR"
    frais: float = 0.0


def test_simple_buy_then_sell_same_year():
    txs = [
        FakeTx(dt.datetime(2025, 1, 1), "AAA", "achat", 10, 100.0),
        FakeTx(dt.datetime(2025, 6, 1), "AAA", "vente", 10, 150.0),
    ]
    assert compute_realized_gains_fifo(txs) == {2025: 500.0}


def test_fifo_order_across_two_lots():
    # Achète 5@100 puis 5@120 ; vend 8 -> consomme les 5@100 (moins cher,
    # achetés en premier) puis 3@120, PAS une moyenne pondérée.
    txs = [
        FakeTx(dt.datetime(2025, 1, 1), "AAA", "achat", 5, 100.0),
        FakeTx(dt.datetime(2025, 2, 1), "AAA", "achat", 5, 120.0),
        FakeTx(dt.datetime(2025, 6, 1), "AAA", "vente", 8, 150.0),
    ]
    # 5*(150-100) + 3*(150-120) = 250 + 90 = 340
    assert compute_realized_gains_fifo(txs) == {2025: 340.0}


def test_gain_attributed_to_sale_year_not_purchase_year():
    txs = [
        FakeTx(dt.datetime(2024, 1, 1), "AAA", "achat", 10, 100.0),
        FakeTx(dt.datetime(2025, 1, 1), "AAA", "vente", 10, 150.0),
    ]
    out = compute_realized_gains_fifo(txs)
    assert out == {2025: 500.0}
    assert 2024 not in out


def test_loss_produces_negative_gain():
    txs = [
        FakeTx(dt.datetime(2025, 1, 1), "AAA", "achat", 10, 100.0),
        FakeTx(dt.datetime(2025, 6, 1), "AAA", "vente", 10, 60.0),
    ]
    assert compute_realized_gains_fifo(txs) == {2025: -400.0}


def test_dividends_and_fees_are_ignored():
    txs = [
        FakeTx(dt.datetime(2025, 1, 1), "AAA", "achat", 10, 100.0),
        FakeTx(dt.datetime(2025, 3, 1), "AAA", "dividende", 0, 5.0),
        FakeTx(dt.datetime(2025, 6, 1), "AAA", "vente", 10, 150.0),
    ]
    assert compute_realized_gains_fifo(txs) == {2025: 500.0}


def test_partial_sell_leaves_remaining_lot_for_next_sale():
    txs = [
        FakeTx(dt.datetime(2025, 1, 1), "AAA", "achat", 10, 100.0),
        FakeTx(dt.datetime(2025, 3, 1), "AAA", "vente", 4, 150.0),   # 4*(150-100)=200
        FakeTx(dt.datetime(2025, 6, 1), "AAA", "vente", 6, 130.0),   # 6*(130-100)=180
    ]
    assert compute_realized_gains_fifo(txs) == {2025: 380.0}


def test_multiple_tickers_summed_per_year():
    txs = [
        FakeTx(dt.datetime(2025, 1, 1), "AAA", "achat", 10, 100.0),
        FakeTx(dt.datetime(2025, 6, 1), "AAA", "vente", 10, 150.0),   # +500
        FakeTx(dt.datetime(2025, 1, 1), "BBB", "achat", 5, 50.0),
        FakeTx(dt.datetime(2025, 6, 1), "BBB", "vente", 5, 40.0),     # -50
    ]
    assert compute_realized_gains_fifo(txs) == {2025: 450.0}


def test_gbx_pence_converted_via_gbp(monkeypatch):
    import app.services.finance.impots_transactions as mod

    def fake_convert(amount, base, quote, **kw):
        assert base == "GBP" and quote == "EUR"
        return round(amount * 1.15, 4)  # taux GBP->EUR fictif

    monkeypatch.setattr("app.services.finance.fx.convert", fake_convert)
    txs = [
        FakeTx(dt.datetime(2025, 1, 1), "BAG", "achat", 10, 60_000.0, devise="GBX"),  # 600 GBP
        FakeTx(dt.datetime(2025, 6, 1), "BAG", "vente", 10, 70_000.0, devise="GBX"),  # 700 GBP
    ]
    out = compute_realized_gains_fifo(txs)
    # (700-600) GBP * 10... non : prix_unitaire est DEJA par action en pence ;
    # cout = 60000/100=600 GBP/action *1.15=690 EUR/action ; vente = 700/100=7 GBP...
    # -> valeurs choisies pour un calcul lisible : 10 actions, cout unitaire 690 EUR, vente unitaire 805 EUR.
    assert out == {2025: round(10 * (805.0 - 690.0), 2)}


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _add_tx(session, date, ticker, type_, qty, prix, devise="EUR", broker="trading212"):
    session.add(Transaction(date=date, ticker=ticker, broker=broker, type=type_,
                             quantite=qty, prix_unitaire=prix, devise=devise))
    session.commit()


def test_compute_tax_summary_no_carryforward(session):
    _add_tx(session, dt.datetime(2025, 1, 1), "AAA", "achat", 10, 100.0)
    _add_tx(session, dt.datetime(2025, 6, 1), "AAA", "vente", 10, 150.0)

    out = compute_tax_summary(session, annee=2025, autres_revenus=0.0)
    assert out["gain_brut"] == 500.0
    assert out["gain_net_imposable"] == 500.0
    assert out["report_moins_values_restant"] == 0.0
    assert out["pfu"]["total"] == 150.0  # 500*30%
    assert out["recommande"] == "bareme"  # revenu 0 -> barème (0% jusqu'à 11 600)


def test_compute_tax_summary_carries_loss_from_prior_year(session):
    # 2024 : perte de 1000. 2025 : gain de 700 -> entièrement absorbé par le report.
    _add_tx(session, dt.datetime(2024, 1, 1), "AAA", "achat", 10, 200.0)
    _add_tx(session, dt.datetime(2024, 6, 1), "AAA", "vente", 10, 100.0)   # -1000
    _add_tx(session, dt.datetime(2025, 1, 1), "BBB", "achat", 10, 100.0)
    _add_tx(session, dt.datetime(2025, 6, 1), "BBB", "vente", 10, 170.0)  # +700

    out = compute_tax_summary(session, annee=2025, autres_revenus=0.0)
    assert out["historique_par_annee"][2024]["report_apres"] == 1000.0
    assert out["gain_brut"] == 700.0
    assert out["gain_net_imposable"] == 0.0   # absorbé par le report de 2024
    assert out["report_moins_values_restant"] == 300.0
    assert out["pfu"]["total"] == 0.0


def test_compute_tax_summary_pre_ledger_carryforward_input(session):
    # Perte antérieure à l'historique du grand livre (saisie manuelle) : 2000 €.
    _add_tx(session, dt.datetime(2025, 1, 1), "AAA", "achat", 10, 100.0)
    _add_tx(session, dt.datetime(2025, 6, 1), "AAA", "vente", 10, 250.0)  # +1500

    out = compute_tax_summary(session, annee=2025, moins_values_anterieures=2000.0)
    assert out["gain_net_imposable"] == 0.0
    assert out["report_moins_values_restant"] == 500.0  # 2000-1500


def test_compute_tax_summary_loss_expires_after_10_years(session):
    # Perte en 2014, gain 11 ans plus tard en 2025 (2025-2014=11 > 10) : le
    # report a expire, le gain de 2025 est donc entierement imposable.
    _add_tx(session, dt.datetime(2014, 1, 1), "AAA", "achat", 10, 200.0)
    _add_tx(session, dt.datetime(2014, 6, 1), "AAA", "vente", 10, 100.0)   # -1000
    _add_tx(session, dt.datetime(2025, 1, 1), "BBB", "achat", 10, 100.0)
    _add_tx(session, dt.datetime(2025, 6, 1), "BBB", "vente", 10, 170.0)  # +700

    out = compute_tax_summary(session, annee=2025, autres_revenus=0.0)
    assert out["gain_net_imposable"] == 700.0  # report expire, rien a imputer
    assert out["report_moins_values_restant"] == 0.0
    assert out["pfu"]["total"] == 210.0  # 700*30%


def test_compute_tax_summary_loss_still_usable_at_exactly_10_years(session):
    # Perte en 2015, gain exactement 10 ans plus tard en 2025 (2025-2015=10) :
    # "reporte sur les 10 annees suivantes" -> encore valide a la borne.
    _add_tx(session, dt.datetime(2015, 1, 1), "AAA", "achat", 10, 200.0)
    _add_tx(session, dt.datetime(2015, 6, 1), "AAA", "vente", 10, 100.0)   # -1000
    _add_tx(session, dt.datetime(2025, 1, 1), "BBB", "achat", 10, 100.0)
    _add_tx(session, dt.datetime(2025, 6, 1), "BBB", "vente", 10, 170.0)  # +700

    out = compute_tax_summary(session, annee=2025, autres_revenus=0.0)
    assert out["gain_net_imposable"] == 0.0  # encore utilisable a la borne des 10 ans
    assert out["report_moins_values_restant"] == 300.0  # 1000-700
    assert out["pfu"]["total"] == 0.0


def test_compute_tax_summary_oldest_vintage_consumed_first(session):
    # Vintage ancien (perte 2010, 500) plus petit, vintage recent (perte
    # 2015, 2000) plus grand. Un gain en 2016 (700) ne consomme que
    # partiellement les deux : l'ordre d'imputation (plus ancien d'abord)
    # doit epuiser ENTIEREMENT le vintage 2010 avant d'entamer celui de 2015.
    #
    # La somme agregee des reports restants est la meme quel que soit l'ordre
    # d'imputation (500+2000-700=1800 dans tous les cas) -- donc on ne peut
    # PAS prouver l'ordre en regardant juste ce total juste apres 2016. La
    # preuve vient de l'expiration differentielle : si l'imputation avait ete
    # a l'envers (le plus recent d'abord), le vintage 2010 resterait a 500 et
    # expirerait a l'interrogation de 2021 (2021-2010=11>10), faisant tomber
    # le report total a 1300 au lieu de 1800. Avec l'ordre correct
    # (plus-ancien-d'abord), le vintage 2010 est deja epuise a 0 des 2016 (et
    # donc absent de la liste), seul le vintage 2015 (1800) survit et reste
    # valide en 2021 (2021-2015=6<=10) -> report = 1800.
    _add_tx(session, dt.datetime(2010, 1, 1), "AAA", "achat", 10, 150.0)
    _add_tx(session, dt.datetime(2010, 6, 1), "AAA", "vente", 10, 100.0)   # -500 (2010)
    _add_tx(session, dt.datetime(2015, 1, 1), "BBB", "achat", 10, 300.0)
    _add_tx(session, dt.datetime(2015, 6, 1), "BBB", "vente", 10, 100.0)   # -2000 (2015)
    _add_tx(session, dt.datetime(2016, 1, 1), "CCC", "achat", 10, 100.0)
    _add_tx(session, dt.datetime(2016, 6, 1), "CCC", "vente", 10, 170.0)   # +700 (2016)

    out = compute_tax_summary(session, annee=2021, autres_revenus=0.0)
    assert out["report_moins_values_restant"] == 1800.0


def test_short_sale_without_matching_lot_is_ignored():
    """Vente sans lot d'achat correspondant (position à découvert, non
    modélisée) : aucune cession réelle -> pas d'entrée pour cette année,
    plutôt qu'un gain fictif calculé sur un coût de base inexistant."""
    txs = [FakeTx(dt.datetime(2025, 1, 1), "AAA", "vente", 10, 150.0)]
    assert compute_realized_gains_fifo(txs) == {}


# ── Détail vente par vente (tableau cliquable) ────────────────────────────────

def test_sales_fifo_returns_one_line_per_sale_with_avg_buy_price():
    txs = [
        FakeTx(dt.datetime(2025, 1, 1), "AAA", "achat", 5, 100.0),
        FakeTx(dt.datetime(2025, 2, 1), "AAA", "achat", 5, 120.0),
        FakeTx(dt.datetime(2025, 6, 1), "AAA", "vente", 8, 150.0),
    ]
    sales = compute_realized_sales_fifo(txs)
    assert len(sales) == 1
    s = sales[0]
    assert s["ticker"] == "AAA"
    assert s["quantite"] == 8.0
    assert s["prix_vente"] == 150.0
    # moyenne pondérée des lots consommés : 5@100 + 3@120 -> (500+360)/8 = 107.5
    assert s["prix_achat_moyen"] == 107.5
    assert s["plus_value"] == 340.0  # matches test_fifo_order_across_two_lots


def test_sales_fifo_estimated_tax_zero_on_loss():
    txs = [
        FakeTx(dt.datetime(2025, 1, 1), "AAA", "achat", 10, 100.0),
        FakeTx(dt.datetime(2025, 6, 1), "AAA", "vente", 10, 60.0),
    ]
    sales = compute_realized_sales_fifo(txs)
    assert sales[0]["plus_value"] == -400.0
    assert sales[0]["impot_estime_pfu"] == 0.0


def test_sales_fifo_estimated_tax_pfu_30_pct_on_gain():
    txs = [
        FakeTx(dt.datetime(2025, 1, 1), "AAA", "achat", 10, 100.0),
        FakeTx(dt.datetime(2025, 6, 1), "AAA", "vente", 10, 150.0),  # +500
    ]
    sales = compute_realized_sales_fifo(txs)
    assert sales[0]["plus_value"] == 500.0
    assert sales[0]["impot_estime_pfu"] == 150.0  # 500 * 0.30


def test_sales_fifo_two_separate_sales_produce_two_lines():
    txs = [
        FakeTx(dt.datetime(2025, 1, 1), "AAA", "achat", 10, 100.0),
        FakeTx(dt.datetime(2025, 3, 1), "AAA", "vente", 4, 150.0),
        FakeTx(dt.datetime(2025, 6, 1), "AAA", "vente", 6, 130.0),
    ]
    sales = compute_realized_sales_fifo(txs)
    assert len(sales) == 2
    assert [s["quantite"] for s in sales] == [4.0, 6.0]
    assert [s["plus_value"] for s in sales] == [200.0, 180.0]


def test_sales_fifo_purchase_fee_increases_cost_basis():
    # Achat 10@100 + frais 10 -> cout unitaire = 100 + 10/10 = 101. Vente 10@150, frais 5.
    # plus_value = 10*(150-101) - 5 = 490 - 5 = 485.
    txs = [
        FakeTx(dt.datetime(2025, 1, 1), "AAA", "achat", 10, 100.0, frais=10.0),
        FakeTx(dt.datetime(2025, 6, 1), "AAA", "vente", 10, 150.0, frais=5.0),
    ]
    sales = compute_realized_sales_fifo(txs)
    assert len(sales) == 1
    assert sales[0]["plus_value"] == 485.0


def test_gains_fifo_purchase_and_sale_fees_reduce_gain():
    txs = [
        FakeTx(dt.datetime(2025, 1, 1), "AAA", "achat", 10, 100.0, frais=10.0),
        FakeTx(dt.datetime(2025, 6, 1), "AAA", "vente", 10, 150.0, frais=5.0),
    ]
    assert compute_realized_gains_fifo(txs) == {2025: 485.0}


def test_sale_fee_only_applied_once_per_sale_not_per_lot():
    # Vente qui consomme deux lots differents : le frais de vente ne doit
    # etre soustrait qu'une seule fois (pas une fois par lot consomme).
    txs = [
        FakeTx(dt.datetime(2025, 1, 1), "AAA", "achat", 5, 100.0),
        FakeTx(dt.datetime(2025, 2, 1), "AAA", "achat", 5, 120.0),
        FakeTx(dt.datetime(2025, 6, 1), "AAA", "vente", 8, 150.0, frais=8.0),
    ]
    # 5*(150-100) + 3*(150-120) = 250 + 90 = 340, moins 8 de frais = 332.
    sales = compute_realized_sales_fifo(txs)
    assert len(sales) == 1
    assert sales[0]["plus_value"] == 332.0


def test_realized_sales_detail_filters_by_broker_and_year_most_recent_first(session):
    _add_tx(session, dt.datetime(2024, 1, 1), "AAA", "achat", 10, 100.0, broker="trading212")
    _add_tx(session, dt.datetime(2024, 6, 1), "AAA", "vente", 10, 150.0, broker="trading212")
    _add_tx(session, dt.datetime(2025, 1, 1), "BBB", "achat", 5, 50.0, broker="trading212")
    _add_tx(session, dt.datetime(2025, 6, 1), "BBB", "vente", 5, 80.0, broker="trading212")
    _add_tx(session, dt.datetime(2025, 1, 1), "CCC", "achat", 1, 10.0, broker="boursedirect")
    _add_tx(session, dt.datetime(2025, 6, 1), "CCC", "vente", 1, 20.0, broker="boursedirect")

    detail = realized_sales_detail(session, broker="trading212")
    assert [d["ticker"] for d in detail] == ["BBB", "AAA"]  # plus récent en premier

    detail_2025 = realized_sales_detail(session, broker="trading212", annee=2025)
    assert [d["ticker"] for d in detail_2025] == ["BBB"]
