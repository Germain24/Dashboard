"""Une exception pendant la phase d'optimisation DE (bug reseau, erreur de
calcul...) ne doit plus etre avalee silencieusement : avant ce correctif,
`run_buffett_analysis` renvoyait un dict "de succes" (sans cle 'error') meme
si l'optimisation avait plante, et `job_monthly_buffett` marquait alors le
run "termine" sans portefeuille et sans aucune erreur visible (#bug rapporte
: "l'analyse DE s'est arretee seule, sans graphique, sans erreur").

Tous les chemins reels (cache, ToutBroker.xlsx, params.json) sont isoles vers
tmp_path : ce test ne doit JAMAIS lire/ecrire les vraies donnees financieres
de l'utilisateur ni risquer une course avec le serveur dev reellement lance
(meme process CWD == backend/, memes chemins relatifs par defaut)."""

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.services.finance.buffett import broker_availability, broker_budgets, runner
from app.services.finance.buffett.cache_manager import CacheManager as RealCacheManager
from app.services.finance.buffett.config import Config


def _isolate_buffett_paths(monkeypatch, tmp_path):
    """Redirige tous les chemins reels de Config vers tmp_path, et neutralise
    tout acces reseau/fichier best-effort (bond yields, ToutBroker.xlsx)."""
    monkeypatch.setattr(Config, "CACHE_FILE", str(tmp_path / "cache_status.json"))
    monkeypatch.setattr(Config, "FOLDER_PATH", str(tmp_path / "financials_by_company"))
    monkeypatch.setattr(Config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(Config, "PARAMS_FILE", str(tmp_path / "absent_params.json"))
    # CacheManager() est appele SANS argument dans runner.py -- son parametre
    # par defaut est lie a l'import du module (pas au Config courant), donc le
    # patch Config.CACHE_FILE ci-dessus ne suffit pas a le rediriger : on
    # remplace directement le nom utilise dans le namespace de runner.py.
    monkeypatch.setattr(
        runner, "CacheManager", lambda: RealCacheManager(str(tmp_path / "cache_status.json"))
    )
    # Jamais de vrai ToutBroker.xlsx (find_broker_file() essaie plusieurs
    # chemins de repli, dont des relatifs -- un simple Config.BROKER_FILE ne
    # suffirait pas a l'empecher de trouver le vrai fichier de l'utilisateur).
    monkeypatch.setattr(broker_availability, "load_broker_table", lambda: None)
    monkeypatch.setattr(runner, "_refresh_bond_yields", lambda: None)


def test_run_buffett_analysis_surfaces_optimization_exception(tmp_path, monkeypatch):
    _isolate_buffett_paths(monkeypatch, tmp_path)

    tickers_csv = tmp_path / "tickers.csv"
    tickers_csv.write_text("AAPL;Apple;NASDAQ;Action\n")

    # Le scoring du ticker echoue proprement (pas de reseau dans le test) --
    # on ne teste pas le scoring ici, seulement la phase d'optimisation.
    monkeypatch.setattr(runner, "_internet_available", lambda timeout=4.0: True)
    monkeypatch.setattr(runner, "fetch_data", lambda ticker, rl: None)

    def _boom():
        raise RuntimeError("boom - simulated DE crash")

    monkeypatch.setattr(broker_budgets, "apply_live_broker_budgets", _boom)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    result = runner.run_buffett_analysis(
        session_factory=lambda: Session(engine),
        csv_path=str(tickers_csv),
        max_workers=1,
        run_id=None,
    )

    assert result.get("error") is not None
    assert "boom" in result["error"]


def test_run_buffett_analysis_error_is_none_on_success(tmp_path, monkeypatch):
    """Non-regression : quand aucune exception ne survient dans le bloc
    d'optimisation (ici parce qu'aucun ticker n'est finalement eligible apres
    le scoring), le retour final reste un succes explicite (`error` a None) --
    ce test exerce reellement le `return` final modifie par ce correctif,
    contrairement a l'ancien test qui ne passait jamais par le bloc
    d'optimisation (chemin "aucun ticker dans tickers.csv", inchange)."""
    _isolate_buffett_paths(monkeypatch, tmp_path)

    tickers_csv = tmp_path / "tickers.csv"
    tickers_csv.write_text("AAPL;Apple;NASDAQ;Action\n")

    # Le ticker existe mais echoue a etre score (pas de cache, pas de reseau)
    # -> results reste vide -> aucun ticker eligible -> t_list vide -> le bloc
    # d'optimisation ne leve aucune exception (apply_live_broker_budgets reste
    # mocke pour ne jamais toucher les vrais soldes de comptes).
    monkeypatch.setattr(runner, "_internet_available", lambda timeout=4.0: True)
    monkeypatch.setattr(runner, "fetch_data", lambda ticker, rl: None)
    monkeypatch.setattr(broker_budgets, "apply_live_broker_budgets", lambda: {"IBKR": 1000.0})

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    result = runner.run_buffett_analysis(
        session_factory=lambda: Session(engine),
        csv_path=str(tickers_csv),
        max_workers=1,
        run_id=None,
    )

    assert result.get("error") is None
    assert result.get("n_analyzed") == 0


def test_run_buffett_analysis_no_tickers_returns_explicit_error(tmp_path, monkeypatch):
    """Non-regression du chemin existant (inchange par ce correctif) : un
    tickers.csv vide retourne un dict d'erreur explicite AVANT meme d'atteindre
    le bloc d'optimisation -- ce chemin garde son propre message, distinct de
    la cle 'error' generique introduite par ce correctif."""
    _isolate_buffett_paths(monkeypatch, tmp_path)

    tickers_csv = tmp_path / "tickers.csv"
    tickers_csv.write_text("")  # aucun ticker

    result = runner.run_buffett_analysis(
        session_factory=lambda: Session(create_engine("sqlite://")),
        csv_path=str(tickers_csv),
        max_workers=1,
        run_id=None,
    )
    assert result.get("error") == "Aucun ticker dans tickers.csv"


def test_run_buffett_analysis_empty_download_surfaces_error(tmp_path, monkeypatch):
    """Si le telechargement groupe des cours revient vide (timeout ou echec de
    download_with_timeout), le run ne doit PAS etre rapporte comme un succes
    silencieux -- avant ce correctif, opt_error restait None sur cette branche
    et job_monthly_buffett marquait le run "termine" sans aucun portefeuille
    calcule et sans erreur visible (meme bug que Task 1, chemin different :
    un DataFrame vide n'est pas une exception, donc le try/except seul ne
    suffisait pas a le detecter)."""
    import pandas as pd
    from app.services.finance import yf_session as yf_session_module
    from app.services.finance.buffett.cache_manager import CacheManager as RealCacheManager

    _isolate_buffett_paths(monkeypatch, tmp_path)

    tickers_csv = tmp_path / "tickers.csv"
    tickers_csv.write_text("AAPL;Apple;NASDAQ;Action\n")

    # Le ticker est "score" via un cache-hit canned (pas de reseau) avec un
    # score eligible (> SCORE_THRESHOLD, Achat=True, liquide) -> t_list non
    # vide -> le code atteint bien l'appel de telechargement groupe.
    cache_path = tmp_path / "cache_status.json"
    isolated_cache = RealCacheManager(str(cache_path))
    monkeypatch.setattr(
        isolated_cache, "get_cached_result",
        lambda ticker: (95.0, {"Nom": "Apple", "Achat": True, "Volume": 1e9, "Prix": 100.0}),
    )
    monkeypatch.setattr(runner, "CacheManager", lambda: isolated_cache)
    monkeypatch.setattr(broker_budgets, "apply_live_broker_budgets", lambda: {"IBKR": 1000.0})
    monkeypatch.setattr(yf_session_module, "download_with_timeout", lambda **kwargs: pd.DataFrame())

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    result = runner.run_buffett_analysis(
        session_factory=lambda: Session(engine),
        csv_path=str(tickers_csv),
        max_workers=1,
        run_id=None,
    )

    assert result.get("error") is not None
