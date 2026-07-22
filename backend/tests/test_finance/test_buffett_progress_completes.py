"""La barre de progression du scoring doit toujours atteindre le total.

#bug rapporte : "quand le programme supprime un ticker car donnees non
disponibles, ca ne fait pas avancer la barre -> on ne sait jamais quand ca
finit". Cause reelle : `task()` incrementait `n_done` APRES `_analyze_one`,
donc toute exception non prevue (I/O cache, parsing local, yfinance) sautait
l'increment -- et `as_completed` n'appelant jamais `.result()`, l'echec etait
totalement muet. Le compteur perdait definitivement ces tickers.

Meme isolation stricte des chemins reels que
test_buffett_optimization_error_surfacing (aucune donnee utilisateur touchee).
"""

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.services.finance.buffett import broker_availability, broker_budgets, runner
from app.services.finance.buffett.cache_manager import CacheManager as RealCacheManager
from app.services.finance.buffett.config import Config


def _isolate_buffett_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "CACHE_FILE", str(tmp_path / "cache_status.json"))
    monkeypatch.setattr(Config, "FOLDER_PATH", str(tmp_path / "financials_by_company"))
    monkeypatch.setattr(Config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(Config, "PARAMS_FILE", str(tmp_path / "absent_params.json"))
    monkeypatch.setattr(
        runner, "CacheManager", lambda: RealCacheManager(str(tmp_path / "cache_status.json"))
    )
    monkeypatch.setattr(broker_availability, "load_broker_table", lambda: None)
    monkeypatch.setattr(runner, "_refresh_bond_yields", lambda: None)


def test_progress_reaches_total_even_when_analysis_raises(tmp_path, monkeypatch):
    _isolate_buffett_paths(monkeypatch, tmp_path)

    tickers = ["AAA", "BBB", "CCC", "DDD"]
    tickers_csv = tmp_path / "tickers.csv"
    tickers_csv.write_text("".join(f"{t};{t} Corp;NASDAQ;Action\n" for t in tickers))

    monkeypatch.setattr(runner, "_internet_available", lambda timeout=4.0: True)
    monkeypatch.setattr(broker_budgets, "apply_live_broker_budgets", lambda: {"IBKR": 1000.0})

    def _analyze(ticker, *a, **kw):
        if ticker in ("BBB", "DDD"):
            raise RuntimeError(f"crash simule sur {ticker}")
        return False  # abandon propre (donnees indisponibles)

    monkeypatch.setattr(runner, "_analyze_one", _analyze)

    seen: list[tuple[int, int]] = []
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    runner.run_buffett_analysis(
        session_factory=lambda: Session(engine),
        csv_path=str(tickers_csv),
        max_workers=2,
        on_progress=lambda done, total: seen.append((done, total)),
        run_id=None,
    )

    assert seen, "aucune mise a jour de progression emise"
    n_done, n_total = seen[-1]
    assert n_total == len(tickers)
    assert n_done == n_total, (
        f"le scoring s'arrete a {n_done}/{n_total} : les tickers en echec ne "
        f"font pas avancer la barre"
    )
