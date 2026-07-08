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


def test_final_write_blocks_on_lock_and_wins_race(monkeypatch):
    """Reproduit la course corrigee dans runner.py : une ecriture progressive
    lente (non-bloquante, skip-if-busy, comme _on_new_best) est encore en vol
    quand l'ecriture finale (bloquante) est tentee. Avant le correctif,
    l'ecriture finale n'attendait pas le verrou et pouvait se terminer AVANT
    la progressive, qui ecrasait alors le resultat final avec une allocation
    plus ancienne. Apres le correctif, l'ecriture finale attend le meme verrou
    (acquisition bloquante) et est donc garantie d'etre la DERNIERE a ecrire,
    quelle que soit la lenteur de l'ecriture progressive en cours."""
    import threading
    import time

    _write_lock = threading.Lock()
    last_written = {"value": None}
    progressive_can_finish = threading.Event()
    progressive_started = threading.Event()

    def _progressive_write(value) -> None:
        """Pattern _on_new_best : skip-if-busy, ecriture async dans un thread."""
        if not _write_lock.acquire(blocking=False):
            return

        def _write() -> None:
            try:
                progressive_started.set()
                # Simule une ecriture DB lente (WAL degrade) : ne se termine
                # qu'apres que le test l'y autorise explicitement.
                progressive_can_finish.wait(timeout=2)
                last_written["value"] = value
            finally:
                _write_lock.release()

        threading.Thread(target=_write, daemon=True).start()

    def _final_write(value) -> None:
        """Pattern corrige de l'ecriture finale dans runner.py : acquisition
        BLOQUANTE du meme verrou -- attend la fin de toute ecriture progressive
        en vol avant d'ecrire, garantissant qu'elle est la derniere."""
        with _write_lock:
            last_written["value"] = value

    # 1) Une ecriture progressive (ancienne allocation) demarre et reste en vol.
    _progressive_write("allocation_intermediaire_ancienne")
    assert progressive_started.wait(timeout=1)

    # 2) L'ecriture finale (vraie allocation finale) est tentee pendant que la
    #    progressive tourne encore. Elle doit BLOQUER (pas etre ignoree, pas
    #    racer) jusqu'a la liberation du verrou par la progressive.
    final_write_returned = threading.Event()

    def _run_final() -> None:
        _final_write("allocation_finale_correcte")
        final_write_returned.set()

    final_thread = threading.Thread(target=_run_final, daemon=True)
    t0 = time.monotonic()
    final_thread.start()

    # Le thread final doit rester bloque tant que la progressive n'a pas fini.
    time.sleep(0.3)
    assert not final_write_returned.is_set()
    assert last_written["value"] is None  # la progressive n'a pas encore ecrit

    # 3) La progressive lente se termine enfin (et ecrit son ancienne valeur)...
    progressive_can_finish.set()
    # ...puis l'ecriture finale, qui attendait le verrou, doit s'executer APRES
    # et donc etre la derniere a ecrire.
    assert final_write_returned.wait(timeout=2)
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.2  # a bien attendu le verrou, pas couru en parallele

    # L'ecriture finale doit gagner : jamais ecrasee par l'ancienne allocation
    # progressive, meme si celle-ci s'est terminee "en dernier" en temps reel
    # par rapport au moment ou l'ecriture finale a ete DEMANDEE.
    assert last_written["value"] == "allocation_finale_correcte"
