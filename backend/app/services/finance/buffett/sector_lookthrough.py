"""Look-through sectoriel des ETF, mis en cache dans ``ETF_Secteurs``.

Les poids sont toujours manipulés en fractions (0..1). La feuille Excel reste en
pourcentages afin d'être lisible et modifiable à la main, comme ``ETF_Pays``.
"""
from __future__ import annotations

import datetime as dt
import math

import numpy as np

from .breakdown import _canon_sector, is_economic_risk_sector

META = (
    "Ticker", "Nom", "Source", "Date_analyse", "ISIN", "Indice",
    "Couverture_pct",
)
DEFENSIVE_SECTORS = {"Sante", "Services aux collectivites", "Conso. de base"}


def _text(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    value = str(value).strip()
    return "" if value.casefold() in {"", "nan", "none", "-"} else value


def _normalise(values: dict, *, percent: bool = False) -> dict[str, float]:
    clean: dict[str, float] = {}
    for raw_sector, raw_value in (values or {}).items():
        try:
            value = max(float(raw_value), 0.0)
        except (TypeError, ValueError):
            continue
        sector = _canon_sector(_text(raw_sector).replace("_", " "))
        if not sector or sector == "Inconnu" or value <= 0 or not is_economic_risk_sector(sector):
            continue
        value = value / 100.0 if percent else value
        clean[sector] = clean.get(sector, 0.0) + value
    total = sum(clean.values())
    return {sector: value / total for sector, value in clean.items()} if total else {}


def sectors_from_yahoo(value) -> dict[str, float]:
    """Normalise ``funds_data.sector_weightings`` (dict, Series ou DataFrame)."""
    if value is None:
        return {}
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if isinstance(value, dict):
        # Certaines versions de yfinance renvoient un DataFrame transposé.
        if len(value) == 1 and isinstance(next(iter(value.values()), None), dict):
            value = next(iter(value.values()))
        elif value and all(isinstance(item, dict) for item in value.values()):
            flattened: dict = {}
            for item in value.values():
                flattened.update(item)
            value = flattened
        return _normalise(value)
    return {}


def fetch_yahoo_fund_composition(ticker: str) -> dict | None:
    """Charge l'objet fonds Yahoo une seule fois pour secteurs et positions."""
    import yfinance as yf

    from app.services.finance.yf_session import yf_session

    try:
        data = yf.Ticker(ticker, session=yf_session()).funds_data
        return {
            "top_holdings": data.top_holdings,
            "sectors": sectors_from_yahoo(data.sector_weightings),
            "asset_classes": getattr(data, "asset_classes", None),
        }
    except Exception:
        return None


def _read_sheet(path: str, name: str):
    import pandas as pd

    try:
        return pd.read_excel(path, sheet_name=name)
    except Exception:
        return None


def load_sector_lookthrough(path: str | None = None) -> tuple[dict, dict]:
    """Retourne ``(poids_par_ticker, dates_par_ticker)`` depuis ToutBroker."""
    from .broker_availability import find_broker_file

    path = path or find_broker_file()
    frame = _read_sheet(path, "ETF_Secteurs") if path else None
    exposures: dict[str, dict[str, float]] = {}
    dates: dict[str, str] = {}
    if frame is None or getattr(frame, "empty", True):
        return exposures, dates
    for _, row in frame.iterrows():
        ticker = _text(row.get("Ticker")).upper()
        if not ticker:
            continue
        weights = _normalise(
            {column: row.get(column) for column in frame.columns if column not in META},
            percent=True,
        )
        if weights:
            exposures[ticker] = weights
        date = _text(row.get("Date_analyse"))[:10]
        if date:
            dates[ticker] = date
    return exposures, dates


def _stale(value: str, max_age_days: int) -> bool:
    try:
        analysed = dt.date.fromisoformat(_text(value)[:10])
    except ValueError:
        return True
    return (dt.date.today() - analysed).days > max(0, int(max_age_days))


def resolve_sector_exposures(
    tickers: list[str],
    *,
    etf_tickers: set[str],
    fallback_sectors: dict[str, str],
    max_age_days: int = 365,
    path: str | None = None,
) -> tuple[dict[str, dict[str, float]], dict]:
    """Construit les expositions, avec un one-hot provisoire si nécessaire."""
    stored, dates = load_sector_lookthrough(path)
    etfs = {str(value).strip().upper() for value in etf_tickers}
    result: dict[str, dict[str, float]] = {}
    refresh: list[str] = []
    for raw_ticker in tickers:
        ticker = str(raw_ticker).strip().upper()
        if ticker in etfs and stored.get(ticker):
            result[ticker] = stored[ticker]
            if _stale(dates.get(ticker, ""), max_age_days):
                refresh.append(ticker)
            continue
        fallback = _canon_sector(fallback_sectors.get(ticker, "Inconnu"))
        if fallback != "Inconnu" and is_economic_risk_sector(fallback):
            result[ticker] = {fallback: 1.0}
        if ticker in etfs:
            refresh.append(ticker)
    return result, {"refresh_tickers": sorted(set(refresh)), "stored": len(stored)}


def sector_matrix(
    tickers: list[str],
    exposures: dict[str, dict[str, float]],
    fallback_labels: list[str | None] | None = None,
) -> tuple[np.ndarray, list[str]]:
    """Matrice [ticker x secteur]. Une ligne DÉCRITE somme à un, sinon à zéro.

    La ligne nulle est volontaire : un ETF « Monde » ou « USA » sans composition
    sectorielle connue ne doit pas se voir attribuer un pseudo-secteur portant un
    nom de pays. Elle a longtemps eu un effet de bord non voulu — l'ETF sortait
    de tous les termes du bonus de diversification et n'obtenait rien, malgré des
    pays parfaitement connus. Ce n'est plus le cas : `with_unassigned_sector`
    (`sector_constraints.py`) rattrape cette part côté bonus, sans lui prêter de
    secteur. La matrice rendue ici reste, elle, strictement descriptive, car elle
    alimente aussi les plafonds de risque sectoriel.
    """
    rows: list[dict[str, float]] = []
    for index, raw_ticker in enumerate(tickers):
        ticker = str(raw_ticker).strip().upper()
        weights = _normalise(exposures.get(ticker, {}))
        if not weights and fallback_labels and fallback_labels[index]:
            # Repli sur l'étiquette du fonds UNIQUEMENT si elle décrit un
            # secteur. Un ETF « USA » ou « Monde » sans composition sectorielle
            # connue reste sans ligne : il apparaissait sinon comme un pseudo
            # secteur portant un nom de pays dans la contribution au risque.
            from .sector_constraints import is_geographic_label

            if (
                not is_geographic_label(fallback_labels[index])
                and is_economic_risk_sector(fallback_labels[index])
            ):
                weights = {_canon_sector(fallback_labels[index]): 1.0}
        rows.append(weights)
    sectors = sorted({sector for row in rows for sector in row})
    matrix = np.zeros((len(rows), len(sectors)), dtype=float)
    positions = {sector: index for index, sector in enumerate(sectors)}
    for row_index, row in enumerate(rows):
        for sector, value in row.items():
            matrix[row_index, positions[sector]] = value
    return matrix, sectors


def defensive_from_sectors(sectors: dict[str, float]) -> float:
    """Part défensive d'un ETF actions dérivée de sa composition sectorielle."""
    weights = _normalise(sectors)
    return sum(value for sector, value in weights.items() if sector in DEFENSIVE_SECTORS)


def load_defensive_lookthrough(path: str | None = None) -> tuple[dict, dict]:
    from .broker_availability import find_broker_file

    path = path or find_broker_file()
    frame = _read_sheet(path, "ETF_Defensif") if path else None
    values: dict[str, float] = {}
    dates: dict[str, str] = {}
    if frame is None or getattr(frame, "empty", True):
        return values, dates
    for _, row in frame.iterrows():
        ticker = _text(row.get("Ticker")).upper()
        if not ticker:
            continue
        try:
            values[ticker] = min(max(float(row.get("Defensif_pct") or 0) / 100.0, 0.0), 1.0)
        except (TypeError, ValueError):
            pass
        date = _text(row.get("Date_analyse"))[:10]
        if date:
            dates[ticker] = date
    return values, dates


def stale_defensive_tickers(
    tickers: list[str], *, etf_tickers: set[str], max_age_days: int = 365,
    path: str | None = None,
) -> list[str]:
    values, dates = load_defensive_lookthrough(path)
    etfs = {str(value).strip().upper() for value in etf_tickers}
    return sorted({
        str(ticker).strip().upper()
        for ticker in tickers
        if str(ticker).strip().upper() in etfs
        and (
            str(ticker).strip().upper() not in values
            or _stale(dates.get(str(ticker).strip().upper(), ""), max_age_days)
        )
    })


def merge_sector_rows(frame, updates: list[dict], today: str | None = None):
    import pandas as pd

    today = today or dt.date.today().isoformat()
    rows: dict[str, dict] = {}
    if frame is not None and not getattr(frame, "empty", True):
        for _, row in frame.iterrows():
            ticker = _text(row.get("Ticker")).upper()
            if ticker:
                rows[ticker] = {str(column): row.get(column) for column in frame.columns}
    for update in updates:
        sectors = _normalise(update.get("secteurs", {}))
        if not sectors:
            continue
        ticker = _text(update.get("Ticker")).upper()
        rows[ticker] = {
            **{name: update.get(name, "") for name in META},
            "Ticker": ticker,
            "Date_analyse": _text(update.get("Date_analyse")) or today,
            **{sector: value * 100.0 for sector, value in sectors.items()},
        }
    sectors = sorted({key for row in rows.values() for key in row if key not in META})
    data = []
    for ticker, values in rows.items():
        item = {"Ticker": ticker}
        item.update({name: values.get(name, "") for name in META if name != "Ticker"})
        item.update({sector: values.get(sector, 0) or 0 for sector in sectors})
        data.append(item)
    return pd.DataFrame(data, columns=[*META, *sectors])


def write_sector_lookthrough(updates: list[dict], path: str | None = None) -> int:
    import pandas as pd

    from .broker_availability import find_broker_file

    path = path or find_broker_file()
    if not path or not updates:
        return 0
    frame = _read_sheet(path, "ETF_Secteurs")
    merged = merge_sector_rows(frame, updates)
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        merged.to_excel(writer, sheet_name="ETF_Secteurs", index=False)
    return sum(bool(update.get("secteurs")) for update in updates)


def merge_defensive_rows(frame, updates: list[dict]):
    import pandas as pd
    rows: dict[str, dict] = {}
    if frame is not None and not getattr(frame, "empty", True):
        for _, row in frame.iterrows():
            ticker = _text(row.get("Ticker")).upper()
            if ticker:
                rows[ticker] = {str(column): row.get(column) for column in frame.columns}
    written = 0
    for update in updates:
        if "defensif" not in update:
            continue
        ticker = _text(update.get("Ticker")).upper()
        previous = rows.get(ticker, {})
        rows[ticker] = {
            **previous,
            "Ticker": ticker,
            "Nom": _text(update.get("Nom")) or previous.get("Nom", ""),
            "Defensif_pct": min(max(float(update["defensif"]), 0.0), 1.0) * 100.0,
            "Source": _text(update.get("Source")) or "yahoo_sector_weightings",
            "Date_analyse": _text(update.get("Date_analyse")) or dt.date.today().isoformat(),
        }
        written += 1
    if not written:
        return frame, 0
    columns = list(frame.columns) if frame is not None else []
    for column in ("Ticker", "Nom", "Defensif_pct", "Source", "Date_analyse"):
        if column not in columns:
            columns.append(column)
    return pd.DataFrame(rows.values(), columns=columns), written


def write_defensive_lookthrough(updates: list[dict], path: str | None = None) -> int:
    """Upsert annuel de ``ETF_Defensif`` sans toucher aux autres feuilles."""
    import pandas as pd

    from .broker_availability import find_broker_file

    path = path or find_broker_file()
    if not path or not updates:
        return 0
    frame = _read_sheet(path, "ETF_Defensif")
    merged, written = merge_defensive_rows(frame, updates)
    if not written:
        return 0
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        merged.to_excel(writer, sheet_name="ETF_Defensif", index=False)
    return written


def write_composition_lookthrough(updates: list[dict], path: str | None = None) -> dict:
    """Écrit pays, secteurs et défensif en une seule ouverture de ToutBroker."""
    import pandas as pd

    from .broker_availability import find_broker_file
    from .etf_lookthrough import merge_pays

    path = path or find_broker_file()
    if not path or not updates:
        return {"pays": 0, "secteurs": 0, "defensif": 0}
    pays = merge_pays(_read_sheet(path, "ETF_Pays"), updates)
    secteurs = merge_sector_rows(_read_sheet(path, "ETF_Secteurs"), updates)
    defensif, defensive_count = merge_defensive_rows(
        _read_sheet(path, "ETF_Defensif"), updates
    )
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        if any(update.get("pays") for update in updates):
            pays.to_excel(writer, sheet_name="ETF_Pays", index=False)
        if any(update.get("secteurs") for update in updates):
            secteurs.to_excel(writer, sheet_name="ETF_Secteurs", index=False)
        if defensive_count:
            defensif.to_excel(writer, sheet_name="ETF_Defensif", index=False)
    return {
        "pays": sum(bool(update.get("pays")) for update in updates),
        "secteurs": sum(bool(update.get("secteurs")) for update in updates),
        "defensif": defensive_count,
    }
