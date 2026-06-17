"""Configuration Buffett — paramètres chargés depuis params.json + valeurs par défaut."""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.core.config import settings
from app.services.finance.buffett.bond_yields import STATIC_BOND_YIELDS


class Config:
    # Chemins. Les fichiers FOURNIS par l'utilisateur sont rangés sous
    # data/imports/<Catégorie>/<Type>/ (cf. #6). Les fichiers de cache/runtime
    # restent sous data/ (non fournis par l'utilisateur).
    _IMPORTS_FIN = settings.imports_dir / "Finances"
    DATA_DIR: str = str(settings.data_dir)
    FOLDER_PATH: str = os.path.join("data", "financials_by_company")  # cache runtime
    CACHE_FILE: str = os.path.join("data", "cache_status.json")        # cache runtime
    # Fichiers d'entrée (Finances) — rangés data/imports/Finances/<type>/
    TICKERS_CSV: str = str(_IMPORTS_FIN / "variables" / "tickers.csv")
    PARAMS_FILE: str = str(_IMPORTS_FIN / "variables" / "params.json")
    # Disponibilite par broker + scores + Poids (colonnes Tradding 212, Bourse
    # Direct, Bourse Direct 2, IBKR... + Chance MOAT). find_broker_file teste
    # plusieurs emplacements au chargement.
    BROKER_FILE: str = str(_IMPORTS_FIN / "tableur" / "ToutBroker.xlsx")

    # Limites analyse -- fenetre cible : MIN_AGE_YEARS <= age <= MAX_AGE_YEARS
    MIN_AGE_YEARS: int = 1   # < 1 an : pas de nouveau rapport annuel possible
    MAX_AGE_YEARS: int = 2   # > 2 ans : probablement deliste
    # Réglages pilotables par .env (cf. app.core.config.Settings).
    SCORE_THRESHOLD: float = settings.buffett_score_threshold
    MAX_REQUESTS_PER_HOUR: int = settings.buffett_max_requests_per_hour
    REQUESTS_PER_TICKER: int = settings.buffett_requests_per_ticker
    # Pause max (s) quand le quota horaire est atteint (borne anti-attente longue).
    RATE_LIMIT_MAX_PAUSE_SEC: float = settings.buffett_rate_limit_max_pause_sec

    # Filtres valorisation
    PER_MAX: float = settings.buffett_per_max
    PEG_MAX: float = settings.buffett_peg_max
    TAUX_DEFAUT: float = settings.buffett_taux_defaut

    # Valeurs de repli ; rafraîchies en direct au lancement du run (cf.
    # bond_yields.get_bond_yields appelé dans runner.run_buffett_analysis).
    TAUX_OBLIGATAIRES: dict = dict(STATIC_BOND_YIELDS)

    # Optimiseur
    SHARPE_TARGET_PERCENT: float = settings.buffett_sharpe_target_percent
    MIN_ALLOCATION_THRESHOLD: float = settings.buffett_min_allocation_threshold
    N_MULTISTART: int = settings.buffett_n_multistart
    USE_BROKER_CONSTRAINTS: bool = True
    BUDGET_BROKERS: dict = {
        "Trading212": 733.70,
        "BoursDirect": 0.0,
        "BoursDirect2": 24472.0,
    }

    # Copule
    VINE_TRUNC_HIGH: float = 20.0
    VINE_FAMILY: str = "auto"

    # Deduplication
    DEDUP_FUZZY_THRESHOLD: float = settings.buffett_dedup_fuzzy_threshold

    # Tickers forces (ex: ETF)
    FORCED_BUY_TICKERS: list = []

    @classmethod
    def load_params(cls) -> None:
        """Surcharge les valeurs depuis params.json s'il existe."""
        if not os.path.exists(cls.PARAMS_FILE):
            return
        try:
            with open(cls.PARAMS_FILE, encoding="utf-8") as f:
                params = json.load(f)
            for k, v in params.items():
                if hasattr(cls, k):
                    setattr(cls, k, v)
        except Exception as e:
            print(f"[Config] Erreur chargement {cls.PARAMS_FILE}: {e}")

    @classmethod
    def output_dir(cls) -> Path:
        return Path(cls.FOLDER_PATH)

    @classmethod
    def ensure_dirs(cls) -> None:
        os.makedirs(cls.DATA_DIR, exist_ok=True)
        os.makedirs(cls.FOLDER_PATH, exist_ok=True)
