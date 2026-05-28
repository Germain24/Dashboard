"""Configuration Buffett — paramètres chargés depuis params.json + valeurs par défaut."""

from __future__ import annotations

import json
import os
from pathlib import Path


class Config:
    # Chemins
    DATA_DIR: str = "data"
    FOLDER_PATH: str = os.path.join("data", "financials_by_company")
    TICKERS_CSV: str = "tickers.csv"
    CACHE_FILE: str = os.path.join("data", "cache_status.json")
    PARAMS_FILE: str = "params.json"

    # Limites analyse
    MAX_AGE_YEARS: int = 1
    SCORE_THRESHOLD: float = 80.0
    MAX_REQUESTS_PER_HOUR: int = 2000
    REQUESTS_PER_TICKER: int = 4

    # Filtres valorisation
    PER_MAX: float = 40.0
    PEG_MAX: float = 1.0
    TAUX_DEFAUT: float = 0.04

    TAUX_OBLIGATAIRES: dict = {
        "United States": 0.042, "France": 0.029, "Germany": 0.024,
        "United Kingdom": 0.040, "Switzerland": 0.007, "Canada": 0.035,
        "Japan": 0.008, "China": 0.023, "India": 0.067,
        "South Korea": 0.030, "Australia": 0.043, "Hong Kong": 0.038,
        "Taiwan": 0.015, "Brazil": 0.135, "Mexico": 0.095,
        "Sweden": 0.020, "Netherlands": 0.027, "Belgium": 0.030,
        "Denmark": 0.025, "Norway": 0.035, "Israel": 0.045,
        "Singapore": 0.030, "South Africa": 0.095, "Indonesia": 0.068,
        "Turkey": 0.280,
    }

    # Optimiseur
    SHARPE_TARGET_PERCENT: float = 0.90
    MIN_ALLOCATION_THRESHOLD: float = 0.01
    N_MULTISTART: int = 5
    USE_BROKER_CONSTRAINTS: bool = True
    BUDGET_BROKERS: dict = {
        "Trading212": 733.70,
        "BoursDirect": 0.0,
        "BoursDirect2": 24472.0,
    }

    # Copule
    VINE_TRUNC_HIGH: float = 20.0
    VINE_FAMILY: str = "auto"

    # Déduplication
    DEDUP_FUZZY_THRESHOLD: float = 0.80

    # Tickers forcés (ex: ETF)
    FORCED_BUY_TICKERS: list = []

    @classmethod
    def load_params(cls) -> None:
        """Surcharge les valeurs depuis params.json s'il existe."""
        if not os.path.exists(cls.PARAMS_FILE):
            return
        try:
            with open(cls.PARAMS_FILE, "r", encoding="utf-8") as f:
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
