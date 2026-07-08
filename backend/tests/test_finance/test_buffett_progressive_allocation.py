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


def test_on_new_best_async_write_does_not_block(monkeypatch):
    """Reproduit le pattern _on_new_best de runner.py : l'appel doit revenir
    immediatement meme si l'ecriture DB sous-jacente est lente, et une 2e
    ecriture pendant que la 1ere tourne encore doit etre ignoree sans erreur
    (pas d'empilement de threads)."""
    import threading
    import time

    write_started = threading.Event()
    write_can_finish = threading.Event()
    write_count = {"n": 0}

    def slow_write() -> None:
        write_count["n"] += 1
        write_started.set()
        write_can_finish.wait(timeout=2)

    _write_lock = threading.Lock()

    def on_new_best(_w_matrix) -> None:
        if not _write_lock.acquire(blocking=False):
            return

        def _write() -> None:
            try:
                slow_write()
            finally:
                _write_lock.release()

        threading.Thread(target=_write, daemon=True).start()

    t0 = time.monotonic()
    on_new_best(object())          # 1ere ecriture : demarre un thread, revient tout de suite
    elapsed = time.monotonic() - t0
    assert elapsed < 0.5           # n'a PAS attendu la fin de l'ecriture (qui bloque sur l'Event)

    assert write_started.wait(timeout=1)
    on_new_best(object())          # 2e ecriture pendant que la 1ere tourne encore -> ignoree
    write_can_finish.set()
    time.sleep(0.2)                # laisse le thread de la 1ere ecriture se terminer
    assert write_count["n"] == 1   # la 2e a bien ete ignoree, pas d'empilement
