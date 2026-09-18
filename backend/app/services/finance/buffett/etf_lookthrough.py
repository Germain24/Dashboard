"""Résolution et persistance du look-through pays des ETF.

justETF ne fournit PAS la composition des ETF **synthétiques** (swap) — or toute la
gamme PEA Amundi/BNP l'est. Le look-through pays est donc rempli **par indice**
(copie d'un ETF physique du même indice / mono-pays), pas scrapé. Ces helpers
fusionnent ces données dans ``ETF_Pays`` sans écraser l'existant.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import unicodedata
from pathlib import Path

# Colonnes NON-pays de ETF_Pays (alignées sur lookthrough._META : Region/Source
# sont des métadonnées de la feuille curée, pas des pays).
_META = (
    "Ticker", "Nom", "Region", "Source", "Date_analyse", "ISIN", "Indice",
    "Couverture_pct",
)

# Fallbacks d'indice. Ils ne prétendent pas remplacer une composition publiée :
# ils empêchent seulement qu'un ETF régional connu soit attribué à son pays de
# cotation (un MSCI World coté à Paris n'est pas 100 % France).
REGION_COUNTRIES: dict[str, dict[str, float]] = {
    "Monde": {"United States": 70, "Japan": 6, "United Kingdom": 4, "Canada": 3,
              "France": 3, "Switzerland": 3, "Germany": 2.5, "Australia": 2,
              "Netherlands": 1.5, "Other": 4.5},
    "USA": {"United States": 100},
    "Zone euro": {"France": 36, "Germany": 27, "Netherlands": 14, "Italy": 8,
                  "Spain": 7, "Finland": 3, "Belgium": 3, "Ireland": 2},
    "Europe": {"United Kingdom": 23, "France": 17, "Switzerland": 15, "Germany": 14,
               "Netherlands": 7, "Sweden": 5, "Italy": 5, "Spain": 5, "Denmark": 5,
               "Other": 4},
    "Émergents": {"China": 28, "India": 18, "Taiwan": 18, "South Korea": 12,
                  "Brazil": 5, "Saudi Arabia": 4, "South Africa": 3, "Mexico": 2,
                  "Other": 10},
    "Asie émergente": {"China": 38, "India": 22, "Taiwan": 22, "South Korea": 14,
                       "Other": 4},
    "Émergents EMEA": {"Saudi Arabia": 30, "South Africa": 22,
                       "United Arab Emirates": 12, "Poland": 10, "Qatar": 8,
                       "Other": 18},
    "Amérique latine": {"Brazil": 58, "Mexico": 27, "Chile": 7, "Other": 8},
    "Asie-Pacifique": {"Australia": 33, "Taiwan": 22, "South Korea": 15,
                       "Hong Kong": 12, "Singapore": 9, "Other": 9},
    "France": {"France": 100}, "Allemagne": {"Germany": 100},
    "Italie": {"Italy": 100}, "Espagne": {"Spain": 100},
    "Autriche": {"Austria": 100}, "Japon": {"Japan": 100},
    "Inde": {"India": 100}, "Chine": {"China": 100},
    "Brésil": {"Brazil": 100}, "Grèce": {"Greece": 100},
    "Pologne": {"Poland": 100}, "Royaume-Uni": {"United Kingdom": 100},
}

_REGION_ALIASES = {
    "world": "Monde", "global": "Monde", "msci world": "Monde",
    "united states": "USA", "etats-unis": "USA", "us": "USA",
    "eurozone": "Zone euro", "euro area": "Zone euro",
    "emerging markets": "Émergents", "emergents": "Émergents",
    "latin america": "Amérique latine", "bresil": "Brésil", "brazil": "Brésil",
    "greece": "Grèce", "grece": "Grèce", "germany": "Allemagne",
    "italy": "Italie", "spain": "Espagne", "japan": "Japon",
    "india": "Inde", "china": "Chine", "poland": "Pologne",
    "united kingdom": "Royaume-Uni", "uk": "Royaume-Uni",
}

_NO_COUNTRY_ASSET_PREFIXES = (
    "matiere", "commodity", "commodities", "or", "gold", "argent", "silver",
)


def _text(value) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    value = str(value).strip()
    return "" if value.casefold() in {"", "nan", "none", "-"} else value


def _key(value) -> str:
    return unicodedata.normalize("NFKD", _text(value)).encode("ascii", "ignore").decode().casefold()


def _normalise_weights(values: dict, *, percent: bool = False) -> dict[str, float]:
    clean: dict[str, float] = {}
    for country, value in (values or {}).items():
        try:
            number = max(float(value), 0.0)
        except (TypeError, ValueError):
            continue
        if number > 0 and _text(country):
            clean[_text(country)] = number / 100.0 if percent else number
    total = sum(clean.values())
    if total <= 0:
        return {}
    # Les sources en pourcentage comportent souvent 99.99/100.01 à cause des
    # arrondis. La matrice de contraintes doit toujours représenter exactement 1.
    return {country: value / total for country, value in clean.items()}


def countries_from_top_holdings(
    holdings,
    country_by_symbol: dict[str, str],
    *,
    min_coverage: float = 0.90,
) -> tuple[dict[str, float], float]:
    """Reconstruit les pays lorsque Yahoo expose presque tout le fonds.

    ``top_holdings`` est souvent limité aux dix premières positions. On refuse
    donc toute reconstruction sous 90 % plutôt que de normaliser un petit
    échantillon et de créer une fausse précision.
    """
    if holdings is None or getattr(holdings, "empty", True):
        return {}, 0.0
    columns = {str(column).strip().casefold(): column for column in holdings.columns}
    weight_col = next(
        (columns[name] for name in ("holding percent", "holdingpercent", "% assets", "weight")
         if name in columns),
        None,
    )
    if weight_col is None:
        return {}, 0.0
    aggregate: dict[str, float] = {}
    covered = 0.0
    for symbol, row in holdings.iterrows():
        ticker = _text(row.get(columns.get("symbol"))) or _text(symbol)
        country = _text(country_by_symbol.get(ticker.upper()))
        try:
            weight = max(float(row.get(weight_col) or 0), 0.0)
        except (TypeError, ValueError):
            continue
        if weight > 1.0 + 1e-9:
            weight /= 100.0
        if country and weight > 0:
            aggregate[country] = aggregate.get(country, 0.0) + weight
            covered += weight
    if covered + 1e-9 < min_coverage:
        return {}, covered
    unknown = max(0.0, 1.0 - covered)
    if unknown > 1e-9:
        aggregate["Inconnu"] = unknown
    return _normalise_weights(aggregate), covered


def fetch_yahoo_top_holdings(ticker: str):
    """Best effort : un seul appel fonds Yahoo, jamais les cours historiques."""
    import yfinance as yf

    from app.services.finance.yf_session import yf_session

    try:
        return yf.Ticker(ticker, session=yf_session()).funds_data.top_holdings
    except Exception:
        return None


def _done_pays_tickers(pays_df) -> set[str]:
    """Tickers déjà renseignés en pays (au moins un pays > 0) dans ``ETF_Pays``."""
    import pandas as pd
    done: set[str] = set()
    if pays_df is None or getattr(pays_df, "empty", True):
        return done
    ccols = [c for c in pays_df.columns if c not in _META]
    for _, r in pays_df.iterrows():
        t = str(r.get("Ticker", "") or "").strip()
        if not t:
            continue
        if any((pd.notna(r[c]) and float(r[c] or 0) > 0) for c in ccols):
            done.add(t)
    return done


def _etf_dates(pays_df) -> dict[str, str]:
    """ticker -> Date_analyse (YYYY-MM-DD) depuis ``ETF_Pays``, si la colonne existe."""
    import pandas as pd
    out: dict[str, str] = {}
    if pays_df is None or getattr(pays_df, "empty", True) or "Date_analyse" not in pays_df.columns:
        return out
    for _, r in pays_df.iterrows():
        t = str(r.get("Ticker", "") or "").strip()
        v = r.get("Date_analyse")
        if t and pd.notna(v) and str(v).strip():
            out[t] = str(v).strip()[:10]
    return out


def merge_pays(pays_df, results: list[dict], today: str | None = None):
    """Fusionne les nouveaux pays dans ``ETF_Pays`` (upsert par ticker, union des
    colonnes pays). Préserve lignes/colonnes existantes ; estampille ``Date_analyse``
    = ``today`` pour les ETF (re)remplis, conserve l'ancienne date pour les autres.

    ``results`` : [{Ticker, Nom, pays: {pays: %}}, ...]."""
    import pandas as pd
    today = today or dt.date.today().isoformat()
    rows: dict[str, dict] = {}
    if pays_df is not None and not getattr(pays_df, "empty", True):
        ccols = [c for c in pays_df.columns if c not in _META]
        for _, r in pays_df.iterrows():
            t = str(r.get("Ticker", "") or "").strip()
            if not t:
                continue
            d = r.get("Date_analyse")
            rows[t] = {
                name: r.get(name, "")
                for name in _META
                if name != "Ticker" and name in pays_df.columns
            }
            rows[t]["Nom"] = r.get("Nom", "")
            rows[t]["Date_analyse"] = (
                str(d)[:10] if pd.notna(d) and str(d).strip() else None
            )
            for c in ccols:
                if pd.notna(r[c]) and float(r[c] or 0):
                    rows[t][c] = float(r[c])
    for res in results:
        if not res.get("pays"):
            continue
        rows[res["Ticker"]] = {
            **{
                name: res.get(name, "")
                for name in _META
                if name not in {"Ticker", "Date_analyse"}
            },
            "Date_analyse": str(res.get("Date_analyse") or today)[:10],
            **{k: float(v) for k, v in res["pays"].items()},
        }
    countries = sorted({c for v in rows.values() for c in v if c not in _META})
    data = []
    for t, v in rows.items():
        row = {"Ticker": t}
        for name in _META:
            if name != "Ticker":
                row[name] = v.get(name, "")
        for c in countries:
            row[c] = v.get(c, 0) or 0
        data.append(row)
    df = pd.DataFrame(data)
    if countries and not df.empty:
        order = sorted(countries, key=lambda c: df[c].sum(), reverse=True)
        df = df[list(_META) + order]
    return df


def _read_sheet(path: str, name: str):
    import pandas as pd
    try:
        return pd.read_excel(path, sheet_name=name)
    except Exception:
        return None


def _load_cached_compositions() -> dict:
    """Cache historique justETF, facultatif et strictement local."""
    path = Path(__file__).resolve().parents[4] / "scripts" / ".etf_lookthrough_cache.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


def _country_rows(frame) -> dict[str, dict]:
    if frame is None or getattr(frame, "empty", True):
        return {}
    result: dict[str, dict] = {}
    for _, row in frame.iterrows():
        ticker = _text(row.get("Ticker")).upper()
        if not ticker:
            continue
        countries = {
            str(column): row.get(column)
            for column in frame.columns
            if str(column) not in _META
        }
        weights = _normalise_weights(countries, percent=True)
        if weights:
            result[ticker] = {
                "weights": weights,
                "source": _text(row.get("Source")) or "ETF_Pays",
                "date": _text(row.get("Date_analyse")),
                "isin": _text(row.get("ISIN")),
                "index": _text(row.get("Indice")),
            }
    return result


def _manual_region(row: dict) -> tuple[str, dict[str, float]]:
    for column in ("Secteur 4", "Secteur 5", "Region"):
        value = _text(row.get(column))
        canonical = _REGION_ALIASES.get(_key(value), value)
        if canonical in REGION_COUNTRIES:
            return canonical, _normalise_weights(REGION_COUNTRIES[canonical], percent=True)
    return "", {}


def _older_than(date_value: str, max_age_days: int) -> bool:
    try:
        analysed = dt.date.fromisoformat(_text(date_value)[:10])
    except (TypeError, ValueError):
        return True
    return (dt.date.today() - analysed).days > max(0, int(max_age_days))


def resolve_country_exposures(
    tickers: list[str],
    *,
    etf_tickers: set[str],
    yahoo_countries: dict[str, str] | None = None,
    broker_table=None,
    pays_table=None,
    cached_compositions: dict | None = None,
    holdings_fetcher=None,
    max_live_fetches: int = 20,
    min_holdings_coverage: float = 0.90,
    max_age_days: int = 365,
    include_unresolved: bool = False,
) -> tuple[dict[str, dict[str, float]], dict, list[dict]]:
    """Résout les expositions pays avant les historiques/corrélations.

    Priorité ETF : feuille existante, cache justETF, autre cotation du même ISIN,
    positions Yahoo suffisamment complètes, puis mandat/indice régional. Les ETF
    actions/taux encore inconnus sont signalés pour exclusion. Les matières
    premières physiques n'ont pas de risque-pays d'entreprise et reçoivent le
    compartiment explicite ``Sans pays``.
    """
    from .broker_availability import _find_ticker_col, find_broker_file, load_broker_table

    normalized = [str(ticker).strip().upper() for ticker in tickers if str(ticker).strip()]
    etfs = {str(ticker).strip().upper() for ticker in etf_tickers}
    table = broker_table if broker_table is not None else load_broker_table()
    if pays_table is None:
        path = find_broker_file()
        pays_table = _read_sheet(path, "ETF_Pays") if path else None
    existing = _country_rows(pays_table)
    cached = cached_compositions if cached_compositions is not None else _load_cached_compositions()
    from .etf_index_registry import canonical_index_id, resolve_index_registry

    index_metadata = resolve_index_registry(
        etfs,
        broker_table=table,
        # Le registre autoritaire est écrit une seule fois dans la phase de
        # déduplication. Ici on ne fait que le consulter/calculer en mémoire.
        persist=False,
    )

    rows: dict[str, dict] = {}
    country_by_symbol = {
        str(ticker).strip().upper(): _text(country)
        for ticker, country in (yahoo_countries or {}).items()
    }
    if table is not None and not getattr(table, "empty", True):
        ticker_col = _find_ticker_col(table.columns, "Ticker Yahoo Finance")
        if ticker_col is not None:
            for _, raw in table.iterrows():
                ticker = _text(raw.get(ticker_col)).upper()
                if not ticker:
                    continue
                row = {str(column).strip(): raw.get(column) for column in table.columns}
                rows[ticker] = row
                if not country_by_symbol.get(ticker):
                    country_by_symbol[ticker] = _text(row.get("Pays"))

    # L'ISIN de la feuille principale complète celui des anciennes lignes
    # ETF_Pays qui ne possédaient pas encore cette métadonnée.
    by_isin: dict[str, dict] = {}
    for ticker, data in existing.items():
        isin = data.get("isin") or _text(rows.get(ticker, {}).get("ISIN"))
        if isin:
            by_isin[isin.upper()] = data
    for ticker, data in cached.items():
        weights = _normalise_weights((data or {}).get("pays", {}), percent=True)
        isin = _text((data or {}).get("isin")) or _text(rows.get(ticker.upper(), {}).get("ISIN"))
        if weights and isin:
            by_isin.setdefault(isin.upper(), {"weights": weights, "source": "justETF-cache"})

    # Une composition économique fiable appartient à l'INDICE, pas au ticker.
    # Elle peut donc servir à un ETF synthétique dès lors qu'un fonds physique du
    # même indice a déjà été documenté.
    by_index: dict[str, dict] = {}
    for ticker, data in existing.items():
        index_id = canonical_index_id(
            data.get("index") or index_metadata.get(ticker, {}).get("index_name")
        )
        source = str(data.get("source") or "")
        if index_id and source not in {"provisional_unknown", "index_region_fallback"}:
            by_index.setdefault(index_id, data)
    for ticker, data in cached.items():
        weights = _normalise_weights((data or {}).get("pays", {}), percent=True)
        index_id = canonical_index_id(
            (data or {}).get("indice")
            or index_metadata.get(str(ticker).upper(), {}).get("index_name")
        )
        if weights and index_id:
            by_index.setdefault(index_id, {"weights": weights, "source": "index_cache"})

    resolved: dict[str, dict[str, float]] = {}
    sources: dict[str, int] = {}
    unresolved_etfs: list[str] = []
    updates: list[dict] = []
    refresh_tickers: list[str] = []
    live_fetches = 0
    fetcher = holdings_fetcher or fetch_yahoo_top_holdings

    for ticker in normalized:
        if ticker not in etfs:
            country = country_by_symbol.get(ticker)
            resolved[ticker] = {country: 1.0} if country else {"Inconnu": 1.0}
            sources["yahoo_action" if country else "unknown_action"] = (
                sources.get("yahoo_action" if country else "unknown_action", 0) + 1
            )
            continue

        row = rows.get(ticker, {})
        weights: dict[str, float] = {}
        source = ""
        coverage = 1.0
        replace_legacy_row = False
        cache_data = cached.get(ticker) or {}
        cached_weights = _normalise_weights(cache_data.get("pays", {}), percent=True)
        if ticker in existing:
            weights = existing[ticker]["weights"]
            source = existing[ticker].get("source") or "ETF_Pays"
            # Les anciennes feuilles n'avaient ni Source ni Date_analyse. Une
            # composition locale explicitement sourcée/datée est plus fiable que
            # ce fallback historique (ex. GRE.PA autrefois forcé à 100 % Grèce).
            if (
                source == "ETF_Pays"
                and not existing[ticker].get("date")
                and cached_weights
                and _text(cache_data.get("source"))
            ):
                weights = cached_weights
                source = _text(cache_data.get("source"))
                replace_legacy_row = True
        if not weights and cached_weights:
            weights = cached_weights
            source = _text(cache_data.get("source")) or "justETF-cache"
        isin = _text(row.get("ISIN")) or _text(cache_data.get("isin"))
        if not weights and isin and isin.upper() in by_isin:
            weights = by_isin[isin.upper()]["weights"]
            source = "same_isin"
        index_id = index_metadata.get(ticker, {}).get("index_id", "")
        if not weights and index_id and index_id in by_index:
            weights = by_index[index_id]["weights"]
            source = "same_economic_index"

        region, regional_weights = _manual_region(row)
        asset_class = _key(row.get("Secteur 2"))
        has_no_country = any(asset_class.startswith(prefix) for prefix in _NO_COUNTRY_ASSET_PREFIXES)
        if not weights and has_no_country:
            weights = {"Sans pays": 1.0}
            source = "non_geographic_asset"

        # Yahoo est réservé aux cas encore inconnus. Le plafond empêche qu'une
        # analyse avec beaucoup d'ETF exotiques ajoute des heures de requêtes.
        is_synthetic = index_metadata.get(ticker, {}).get("replication") == "synthetic"
        if (
            not weights
            and not is_synthetic
            and live_fetches < max(0, int(max_live_fetches))
        ):
            live_fetches += 1
            holdings = fetcher(ticker)
            weights, coverage = countries_from_top_holdings(
                holdings,
                country_by_symbol,
                min_coverage=min_holdings_coverage,
            )
            source = "yahoo_top_holdings" if weights else ""
        if not weights and regional_weights:
            weights = regional_weights
            source = "index_region_fallback"
            coverage = 1.0

        if not weights:
            if include_unresolved:
                weights = {"Inconnu": 1.0}
                source = "provisional_unknown"
            else:
                unresolved_etfs.append(ticker)
                continue
        resolved[ticker] = weights
        sources[source] = sources.get(source, 0) + 1
        source_date = (
            _text(cache_data.get("date_analyse"))
            if replace_legacy_row or source == _text(cache_data.get("source"))
            else _text(existing.get(ticker, {}).get("date"))
        )
        reliable_source = source not in {
            "ETF_Pays", "index_region_fallback", "provisional_unknown",
        }
        if (
            source not in {"non_geographic_asset"}
            and (not reliable_source or _older_than(source_date, max_age_days))
        ):
            refresh_tickers.append(ticker)
        # Les fallbacks servent à la première passe mais ne sont pas écrits comme
        # s'ils constituaient une analyse fraîche. Ils resteront donc candidats à
        # l'enrichissement paresseux lorsqu'ils entreront réellement au portefeuille.
        if (
            (ticker not in existing or replace_legacy_row)
            and source not in {"index_region_fallback", "provisional_unknown"}
        ):
            updates.append({
                "Ticker": ticker,
                "Nom": _text(row.get("Nom")),
                "Region": region,
                "Source": source,
                "Date_analyse": _text(cache_data.get("date_analyse")) or dt.date.today().isoformat(),
                "ISIN": isin,
                "Indice": (
                    _text(row.get("Indice"))
                    or _text(row.get("Index"))
                    or _text(cache_data.get("indice"))
                ),
                "Couverture_pct": coverage * 100.0,
                "pays": {country: value * 100.0 for country, value in weights.items()},
            })

    return resolved, {
        "method": "etf_pays_then_cache_isin_holdings_index",
        "requested": len(normalized),
        "classified": len(resolved),
        "excluded": len(unresolved_etfs),
        "excluded_tickers": unresolved_etfs,
        "sources": sources,
        "live_fetches": live_fetches,
        "refresh_tickers": refresh_tickers,
    }, updates


def refresh_country_exposure(
    ticker: str,
    *,
    country_by_symbol: dict[str, str],
    holdings_fetcher=None,
    min_holdings_coverage: float = 0.90,
    metadata: dict | None = None,
    fallback_countries: dict[str, float] | None = None,
) -> dict | None:
    """Actualise un seul ETF sélectionné ; ``None`` garde l'ancienne donnée."""
    from .etf_index_registry import replication_method

    info = metadata or {}
    replication = replication_method(
        info.get("Réplication")
        or info.get("Replication")
        or info.get("Méthode de réplication")
        or info.get("Replication Method")
    )
    # Les positions Yahoo d'un fonds synthétique peuvent être le collatéral du
    # swap. Elles ne décrivent ni les pays ni les entreprises économiques.
    if replication == "synthetic":
        return None
    fetcher = holdings_fetcher or fetch_yahoo_top_holdings
    holdings = fetcher(str(ticker).strip().upper())
    # ``None`` signifie échec réseau/API : ne surtout pas dater le fallback,
    # afin qu'une coupure temporaire ne repousse pas la prochaine tentative d'un an.
    if holdings is None:
        return None
    countries, coverage = countries_from_top_holdings(
        holdings,
        {str(symbol).strip().upper(): country for symbol, country in country_by_symbol.items()},
        min_coverage=min_holdings_coverage,
    )
    source = "yahoo_top_holdings"
    if not countries:
        fallback = {
            country: max(float(value), 0.0)
            for country, value in (fallback_countries or {}).items()
            if country not in {"Inconnu"} and float(value) > 0
        }
        total = sum(fallback.values())
        if total <= 0:
            return None
        countries = {country: value / total for country, value in fallback.items()}
        coverage = 0.0
        source = "fallback_verified_no_complete_yahoo_holdings"
    return {
        "Ticker": str(ticker).strip().upper(),
        "Nom": _text(info.get("Nom")),
        "Region": _text(info.get("Secteur 4")) or _text(info.get("Secteur 5")),
        "Source": source,
        "Date_analyse": dt.date.today().isoformat(),
        "ISIN": _text(info.get("ISIN")),
        "Indice": _text(info.get("Indice")) or _text(info.get("Index")),
        "Couverture_pct": coverage * 100.0,
        "pays": {country: value * 100.0 for country, value in countries.items()},
    }


def write_pays_lookthrough(results: list[dict], path: str | None = None) -> int:
    """Fusionne ``results`` ([{Ticker, Nom, pays}]) dans la feuille ``ETF_Pays`` de
    ToutBroker en préservant les autres feuilles. Retourne le nombre d'ETF écrits."""
    import pandas as pd

    from .broker_availability import find_broker_file

    path = path or find_broker_file()
    if not path or not results:
        return 0
    pays_df = _read_sheet(path, "ETF_Pays")
    new_pays = merge_pays(pays_df, results)
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
        new_pays.to_excel(w, sheet_name="ETF_Pays", index=False)
    return len(results)
