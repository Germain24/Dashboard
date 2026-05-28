"""Cache JSON local pour éviter de re-télécharger des données récentes."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import Config

SUFFIX_MAP: dict[str, str] = {
    ".PA": "France", ".DE": "Germany", ".F": "Germany", ".VI": "Austria",
    ".MC": "Spain", ".MI": "Italy", ".AS": "Netherlands", ".L": "United Kingdom",
    ".CO": "Denmark", ".ST": "Sweden", ".OL": "Norway", ".HE": "Finland",
    ".SW": "Switzerland", ".LS": "Portugal", ".BR": "Belgium", ".HK": "Hong Kong",
    ".SS": "China", ".SZ": "China", ".NS": "India", ".BO": "India",
    ".KS": "South Korea", ".KQ": "South Korea", ".T": "Japan", ".TW": "Taiwan",
    ".AX": "Australia", ".MX": "Mexico", ".SA": "Brazil", ".JO": "South Africa",
    ".JK": "Indonesia", ".IS": "Turkey", ".TO": "Canada", ".IL": "Israel",
    ".BK": "Thailand", ".KL": "Malaysia", ".SG": "Singapore",
}


def infer_country(symbol: str) -> str:
    """Devine le pays depuis le suffixe du ticker."""
    for suffix, country in SUFFIX_MAP.items():
        if symbol.upper().endswith(suffix):
            return country
    return "United States" if "." not in symbol else "Inconnu"


class CacheManager:
    """Gère le fichier cache_status.json (thread-safe)."""

    def __init__(self, cache_file: str = Config.CACHE_FILE) -> None:
        self.cache_file = cache_file
        self.lock = threading.Lock()
        self.cache: dict = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save(self) -> None:
        with self.lock:
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f, indent=2)

    def update(
        self, ticker: str, latest_year: int, score: float, metrics: dict
    ) -> None:
        with self.lock:
            self.cache[ticker] = {
                "last_update": datetime.now().isoformat(),
                "latest_year": latest_year,
                "score": score,
                "metrics": metrics,
                "status": "success",
            }

    def get_cached_result(self, ticker: str) -> Optional[tuple[float, dict]]:
        """Retourne (score, metrics) si l'analyse est récente, sinon None."""
        with self.lock:
            info = self.cache.get(ticker, {})
            if not info or info.get("status") != "success":
                return None
            try:
                last_update = datetime.fromisoformat(info["last_update"])
                age_days = (datetime.now() - last_update).days
                cached_year = info.get("latest_year", 0)
                age_fin = datetime.now().year - cached_year
                if age_days < 60 and age_fin <= Config.MAX_AGE_YEARS and info.get("metrics"):
                    score = float(info.get("score") or 0.0)
                    metrics = dict(info.get("metrics", {}))
                    if metrics.get("Pays") == "Inconnu":
                        metrics["Pays"] = infer_country(ticker)
                    return score, metrics
            except Exception:
                pass
            return None

    def get_status(self, ticker: str, file_path: Path) -> str:
        """Retourne 'local_ok' | 'update' | 'download' | 'too_old'."""
        with self.lock:
            cached_year = self.cache.get(ticker, {}).get("latest_year", 0)

        latest_year = cached_year
        if latest_year == 0 and file_path.exists():
            try:
                import pandas as pd
                idx = pd.read_excel(file_path, sheet_name="income", usecols=[0], index_col=0).index
                latest_year = pd.to_datetime(idx).year.max()
            except Exception:
                return "download"

        if latest_year == 0:
            return "download"
        age = datetime.now().year - latest_year
        if age > Config.MAX_AGE_YEARS:
            return "too_old"
        if age <= 1:
            return "local_ok"
        return "update"
