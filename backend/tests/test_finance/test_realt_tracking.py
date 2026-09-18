"""Suivi du coût total investi et du P&L incluant crypto/RealT.

Les RealTokens (immobilier tokenisé) sont en liquidation : leur cours est
volontairement fixé à 0, mais leur coût de revient doit rester compté dans le
total investi et leur perte dans le P&L latent.
"""

from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

from app.services.finance.portfolio_state import _attach_invested_totals


def test_attach_invested_totals_sums_cost_basis_and_pnl():
    state = {
        "positions": [
            {"acb": 50.0, "quantite": 1.0},   # RealT (prix 0, base de coût conservée)
            {"acb": 100.0, "quantite": 2.0},  # titre classique
        ],
        "pl_realise": 200.0,
        "pl_latent_total": -50.0,
    }
    out = _attach_invested_totals(state)
    assert out["investi_total"] == 250.0   # 50*1 + 100*2
    assert out["pl_total"] == 150.0        # 200 + (-50)


def test_take_snapshot_now_skips_realt_zero_price(monkeypatch):
    """Un RealT à prix 0 ne bloque plus le snapshot ; son coût reste investi."""
    import app.services.finance.portfolio as portfolio_mod
    from app.services.finance.snapshots import take_snapshot_now

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    monkeypatch.setattr(
        portfolio_mod,
        "get_positions",
        lambda session: [
            {
                "ticker": "REALTOKEN-1945-BOURBON-ST",
                "broker": "MetaMask · Gnosis",
                "quantite": 1.0,
                "pmu": 50.0,
                "prix_actuel": 0.0,
                "valeur_actuelle": 0.0,
            },
            {
                "ticker": "AAPL",
                "broker": "Trading212",
                "quantite": 2.0,
                "pmu": 100.0,
                "prix_actuel": 120.0,
                "valeur_actuelle": 240.0,
            },
        ],
    )

    snap = take_snapshot_now(session)
    assert snap is not None
    assert snap.valeur == 240.0
    assert snap.investit == 250.0  # 50 (RealT) + 200 (AAPL)


def test_take_snapshot_now_still_blocks_non_realt_zero_price(monkeypatch):
    """Une position non-RealT à prix 0 doit continuer de bloquer le snapshot."""
    import app.services.finance.portfolio as portfolio_mod
    from app.services.finance.snapshots import take_snapshot_now

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    monkeypatch.setattr(
        portfolio_mod,
        "get_positions",
        lambda session: [
            {
                "ticker": "XYZ",
                "broker": "Trading212",
                "quantite": 1.0,
                "pmu": 10.0,
                "prix_actuel": 0.0,
                "valeur_actuelle": 0.0,
            },
        ],
    )

    assert take_snapshot_now(session) is None
