"""La session doit rester cohérente avec le singleton YfData de yfinance."""

import threading

from app.services.finance import yf_session as yfs


def setup_function(_):
    yfs.reset_sessions()


def test_meme_thread_reutilise_la_meme_session():
    assert yfs.yf_session() is yfs.yf_session()


def test_threads_recoivent_la_meme_session_process_wide():
    captured: list[object] = []

    def capture() -> None:
        captured.append(yfs.yf_session())

    threads = [threading.Thread(target=capture) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert captured[0] is captured[1] is yfs.yf_session()


def test_rotate_session_remplace_la_session_globale():
    before = yfs.yf_session()
    yfs.rotate_session()
    after = yfs.yf_session()
    assert after is not before


def test_session_has_a_default_timeout():
    session = yfs.yf_session()
    assert session is not None
    assert session.timeout == yfs.DEFAULT_TIMEOUT_S
    assert session.timeout > 0
