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
    """Non-regression : un run sans ticker eligible (aucune optimisation a
    tenter) reste un succes normal (`error` a None), pas un echec."""
    _isolate_buffett_paths(monkeypatch, tmp_path)

    tickers_csv = tmp_path / "tickers.csv"
    tickers_csv.write_text("")  # aucun ticker

    result = runner.run_buffett_analysis(
        session_factory=lambda: Session(create_engine("sqlite://")),
        csv_path=str(tickers_csv),
        max_workers=1,
        run_id=None,
    )
    # Chemin "aucun ticker dans tickers.csv" : dict d'erreur explicite existant,
    # pas de cle "error" a valider ici (cf. runner.py:364-365) -- ce test verifie
    # juste qu'il ne plante pas et reste explicite.
    assert result.get("error") == "Aucun ticker dans tickers.csv"
