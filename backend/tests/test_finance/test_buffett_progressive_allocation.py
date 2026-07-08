"""update_allocations(reset=True, par defaut) doit remplacer entierement
l'allocation d'un run a chaque appel -- c'est ce qui permet d'afficher le
meilleur portefeuille trouve jusqu'ici pendant l'optimisation DE (qui peut
durer des heures) sans laisser de residu de l'appel precedent."""

from sqlmodel import select

from app.models.finance import BuffettRunResult
from app.services.finance.buffett.reporting import update_allocations


def test_update_allocations_replaces_previous_progressive_snapshot(mem_session):
    for t in ["AAPL", "MSFT", "GOOG"]:
        mem_session.add(BuffettRunResult(run_id=1, ticker=t, chance_moat=90.0))
    mem_session.commit()

    # Premiere estimation "meilleur jusqu'ici" : AAPL + MSFT
    update_allocations(mem_session, 1, [
        {"Ticker": "AAPL", "Broker": "IBKR", "Poids total (%)": 60.0},
        {"Ticker": "MSFT", "Broker": "IBKR", "Poids total (%)": 40.0},
    ])
    rows = {r.ticker: r.allocation_pct for r in mem_session.exec(
        select(BuffettRunResult).where(BuffettRunResult.run_id == 1)
    ).all()}
    assert rows["AAPL"] == 60.0
    assert rows["MSFT"] == 40.0
    assert rows["GOOG"] is None

    # Le DE trouve un meilleur portefeuille (GOOG remplace MSFT) : le nouvel appel
    # doit effacer l'ancienne allocation de MSFT, pas seulement ajouter GOOG.
    update_allocations(mem_session, 1, [
        {"Ticker": "AAPL", "Broker": "IBKR", "Poids total (%)": 55.0},
        {"Ticker": "GOOG", "Broker": "IBKR", "Poids total (%)": 45.0},
    ])
    rows2 = {r.ticker: r.allocation_pct for r in mem_session.exec(
        select(BuffettRunResult).where(BuffettRunResult.run_id == 1)
    ).all()}
    assert rows2["AAPL"] == 55.0
    assert rows2["GOOG"] == 45.0
    assert rows2["MSFT"] is None  # résidu du run précédent effacé
