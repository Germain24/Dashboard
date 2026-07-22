"""Cache JSON local pour eviter de re-telecharger des donnees recentes."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from .config import Config
from .scoring_pure import SCORING_MODEL_VERSION

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
    for suffix, country in SUFFIX_MAP.items():
        if symbol.upper().endswith(suffix):
            return country
    return "United States" if "." not in symbol else "Inconnu"


def json_default(o):
    """Encodeur JSON tolérant aux types non natifs (numpy, pandas, datetime).

    Pandas/NumPy produisent des scalaires (`numpy.int32`, `numpy.float64`,
    `numpy.bool_`) que `json.dump` ne sait pas sérialiser. On les convertit en
    types Python natifs avant l'écriture du cache.
    """
    # Scalaires/arrays NumPy (np.generic expose .item(), np.ndarray .tolist()).
    item = getattr(o, "item", None)
    if callable(item):
        try:
            return o.item()
        except Exception:
            pass
    tolist = getattr(o, "tolist", None)
    if callable(tolist):
        try:
            return o.tolist()
        except Exception:
            pass
    if isinstance(o, (set, frozenset)):
        return list(o)
    iso = getattr(o, "isoformat", None)
    if callable(iso):
        return o.isoformat()
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")


def _atomic_json_dump(data: dict, destination: str | Path) -> None:
    """Écrit un JSON sans jamais exposer un fichier cible partiel.

    Le fichier temporaire est créé dans le même répertoire que la cible afin
    que ``os.replace`` reste une opération atomique, y compris sous Windows.
    """
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, indent=2, default=json_default)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def purge_misclassified_etf_cache(
    cache_file: str | None = None, output_dir: str | None = None,
    etf_tickers: set | None = None,
) -> dict:
    """Purge du cache les titres classés ETF (``score >= 200``) qui ne sont PLUS
    des ETF selon ToutBroker.xlsx (ticker absent de la colonne 'Secteur 1' == 'ETF').

    Ces titres restaient figés Score=200 et n'étaient jamais réanalysés. On retire
    l'entrée du cache ET son fichier financier local, pour forcer leur réanalyse au
    prochain run. ``etf_tickers`` : ensemble autoritaire (si None, lu depuis ToutBroker).

    Retourne {removed, tickers, files_deleted}.
    """
    if etf_tickers is None:
        from .broker_availability import load_etf_tickers
        etf_tickers = load_etf_tickers()

    cache_file = cache_file or Config.CACHE_FILE
    out = Path(output_dir) if output_dir else Config.output_dir()

    if not os.path.exists(cache_file):
        return {"removed": 0, "tickers": [], "files_deleted": 0}
    try:
        with open(cache_file) as f:
            cache = json.load(f)
    except Exception:
        return {"removed": 0, "tickers": [], "files_deleted": 0}

    victims = [
        t for t, info in cache.items()
        if float((info or {}).get("score") or 0) >= 200
        and t.upper() not in etf_tickers
    ]

    files_deleted = 0
    for t in victims:
        cache.pop(t, None)
        fp = out / f"{t.replace(':', '_')}.xlsx"
        try:
            if fp.exists():
                fp.unlink()
                files_deleted += 1
        except Exception:
            pass

    if victims:
        _atomic_json_dump(cache, cache_file)

    return {"removed": len(victims), "tickers": sorted(victims), "files_deleted": files_deleted}


class CacheManager:
    """Gere le fichier cache_status.json (thread-safe)."""

    def __init__(self, cache_file: str = Config.CACHE_FILE) -> None:
        self.cache_file = cache_file
        self.lock = threading.Lock()
        self.cache: dict = self._load()
        self._dirty = False

    def _load(self) -> dict:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save(self) -> None:
        with self.lock:
            _atomic_json_dump(self.cache, self.cache_file)
            self._dirty = False

    def save_if_dirty(self) -> bool:
        """Persiste seulement si une mise à jour n'est pas encore sur disque."""
        with self.lock:
            if not self._dirty:
                return False
            _atomic_json_dump(self.cache, self.cache_file)
            self._dirty = False
            return True

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
                "score_model_version": SCORING_MODEL_VERSION,
            }
            self._dirty = True

    def replace_cached_metrics(self, ticker: str, score: float, metrics: dict) -> None:
        """Remplace seulement le résultat scoré, sans rajeunir les données.

        Utilisé après la calibration secteur/région : ``latest_year`` et
        ``last_update`` décrivent le téléchargement des comptes et ne doivent pas
        changer pendant ce second passage purement transversal.
        """
        with self.lock:
            info = self.cache.get(ticker)
            if not info or info.get("status") != "success":
                return
            # Le rechargement DB utilisé par le second passage ne contient
            # qu'un sous-ensemble des métriques. Une substitution complète
            # perdrait notamment VolumeDevise, Industrie et les ratios bruts,
            # puis convertirait Volume une seconde fois au prochain cache hit.
            merged_metrics = dict(info.get("metrics") or {})
            merged_metrics.update(metrics)
            info["score"] = score
            info["metrics"] = merged_metrics
            info["score_model_version"] = SCORING_MODEL_VERSION
            self._dirty = True

    def get_cached_result(self, ticker: str) -> tuple[float, dict] | None:
        """Retourne (score, metrics) si le cache est valide, sinon None.

        Regles :
        - ETF (score >= 200) : retourne toujours si cache < 60 jours, sans
          restriction d'age financier (les ETF n'ont pas de comptes annuels).
        - Action normale : retourne si cache < 60 jours ET age financier dans
          [MIN_AGE_YEARS, MAX_AGE_YEARS].
        """
        with self.lock:
            info = self.cache.get(ticker, {})
            if not info or info.get("status") != "success":
                return None
            try:
                if not info.get("metrics"):
                    return None
                score = float(info.get("score") or 0.0)
                metrics = dict(info.get("metrics", {}))
                if metrics.get("Pays") == "Inconnu":
                    metrics["Pays"] = infer_country(ticker)
                # ETF (score=200) : cache permanent, AUCUNE restriction d'age
                # (ni TTL 60 jours, ni fenetre d'age financier) -- un ETF n'a
                # pas de fondamentaux qui changent d'un run a l'autre. La
                # reclassification (ETF -> action) est geree en amont par
                # purge_misclassified_etf_cache, appele a chaque run.
                if score >= 200:
                    return score, metrics
                # Une action doit être recalculée dès que les formules MOAT
                # changent. Les anciennes entrées sans version sont invalides.
                if info.get("score_model_version") != SCORING_MODEL_VERSION:
                    return None
                last_update = datetime.fromisoformat(info["last_update"])
                age_days = (datetime.now() - last_update).days
                if age_days >= 60:
                    return None
                # Action normale : verifier la fenetre d'age
                cached_year = info.get("latest_year", 0)
                age_fin = datetime.now().year - cached_year
                if Config.MIN_AGE_YEARS <= age_fin <= Config.MAX_AGE_YEARS:
                    return score, metrics
            except Exception:
                pass
            return None

    def get_status(self, ticker: str, file_path: Path) -> str:
        """Retourne le statut du ticker selon l'age de ses donnees.

        Statuts possibles :
        - too_fresh : age < MIN_AGE_YEARS (pas de nouveau rapport annuel possible)
        - local_ok  : age == MIN_AGE_YEARS (fichier local suffisant, pas de dl)
        - update    : MIN_AGE_YEARS < age <= MAX_AGE_YEARS (tenter mise a jour)
        - too_old   : age > MAX_AGE_YEARS (probablement deliste - tenter quand meme)
        - download  : aucun fichier local
        """
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
        if age < Config.MIN_AGE_YEARS:
            return "too_fresh"
        if age > Config.MAX_AGE_YEARS:
            return "too_old"
        if age == Config.MIN_AGE_YEARS:
            return "local_ok"
        return "update"
