"""yf_session() était un singleton PROCESS-WIDE : une seule instance
curl_cffi.requests.Session partagée par les 10 workers du ThreadPoolExecutor
de l'analyse Buffett. curl_cffi (bindings natifs autour de libcurl) n'est pas
garanti thread-safe pour un usage concurrent du même objet Session -> crash
natif intermittent du process (aucune trace Python, cf. job_monthly_buffett
qui catch déjà toute Exception avec exc_info=True : si un traceback avait été
loggable, on l'aurait vu). Chaque thread doit avoir SA PROPRE session."""

import threading

from app.services.finance import yf_session as yfs


def setup_function(_):
    yfs.reset_sessions()


def test_meme_thread_reutilise_la_meme_session():
    a = yfs.yf_session()
    b = yfs.yf_session()
    assert a is b


def test_threads_differents_ont_des_sessions_differentes():
    captured: dict[str, object] = {}

    def capture(key: str) -> None:
        captured[key] = yfs.yf_session()

    t1 = threading.Thread(target=capture, args=("t1",))
    t2 = threading.Thread(target=capture, args=("t2",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    main_session = yfs.yf_session()
    assert captured["t1"] is not captured["t2"]
    assert captured["t1"] is not main_session
    assert captured["t2"] is not main_session


def test_rotate_session_ne_change_que_le_thread_courant():
    before = yfs.yf_session()
    other_before: dict[str, object] = {}

    def capture_other() -> None:
        other_before["session"] = yfs.yf_session()

    t = threading.Thread(target=capture_other)
    t.start()
    t.join()

    yfs.rotate_session()
    after = yfs.yf_session()

    assert after is not before  # le thread courant a bien une nouvelle session
    # l'autre thread (déjà terminé) n'est pas affecté rétroactivement ; on
    # vérifie juste qu'un NOUVEL appel depuis un autre thread reste indépendant
    other_after: dict[str, object] = {}

    def capture_other_after() -> None:
        other_after["session"] = yfs.yf_session()

    t2 = threading.Thread(target=capture_other_after)
    t2.start()
    t2.join()
    assert other_after["session"] is not after


def test_session_has_a_default_timeout():
    """Sans timeout, une connexion qui ne répond jamais bloque le thread
    indéfiniment (#run Buffett resté bloqué à quelques tickers de la fin,
    process actif mais aucune progression pendant plusieurs minutes)."""
    session = yfs.yf_session()
    assert session is not None  # curl_cffi doit être installé en test
    assert session.timeout == yfs.DEFAULT_TIMEOUT_S
    assert session.timeout > 0
