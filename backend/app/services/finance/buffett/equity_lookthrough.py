"""Décomposition d'une allocation ETF en actions sous-jacentes.

La composition publiée par Yahoo est généralement limitée aux principales
positions. Le résidu n'est jamais redistribué artificiellement : il est porté
par une ligne unique ``AUTRES`` afin de conserver exactement le poids du
portefeuille source.
"""

from __future__ import annotations

import datetime as dt
import math
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .country_normalization import canonical_country, canonicalize_exposure

_NON_EQUITY_MARKERS = (
    "commodity", "commodities", "matiere premiere", "matières premières",
    "gold", "silver", "platinum", "palladium", "physical", "bond", "obligation", "treasury", "money market",
    "monetaire", "monétaire", "overnight", "court terme",
    # Libellés fréquents des obligations britanniques/européennes. Sans ces
    # variantes, IGLT et des ETF « government gilts » entraient à tort dans
    # l'univers actions et déclenchaient le filtre sectoriel/pays.
    "gilt", "gilts", "sovereign", "government bond", "government bonds",
    "fixed income", "fixed_income", "corporate debt", "credit bond",
    "bitcoin", "ethereum", "crypto", "cryptocurrency", "digital asset",
    "exchange traded product", "exchange-traded product", " etp",
)


def _is_non_equity_etf(row: Any) -> bool:
    # pandas.Series est le type réellement fourni par le runner. Il expose
    # ``get``/``items`` mais n'est pas un dict et ses attributs sont sensibles à
    # la casse : chercher ``nom`` via getattr ne trouvait donc jamais ``Nom``.
    # Cela envoyait obligations, métaux et crypto dans le contrôle des actions.
    if hasattr(row, "items"):
        lowered = {str(key).casefold(): value for key, value in row.items()}

        def getter(field, default=""):
            return lowered.get(field.casefold(), default)
    else:

        def getter(field, default=""):
            return getattr(row, field, default)
    # ToutBroker porte fréquemment la classe d'actif dans ``Secteur 2`` tandis
    # que l'émetteur l'ajoute au payload officiel. Se limiter à ``Secteur``
    # envoyait donc des obligations dans le contrôle secteur+pays des actions.
    fields = (
        "nom", "name", "secteur", "secteur 1", "secteur 2", "secteur 3",
        "pays", "asset_class", "asset class", "legal_type", "legal type",
        "index", "index_name",
    )
    text = " ".join(_clean_text(getter(field, "")) for field in fields).casefold()
    # « Gold miners » désigne des actions de sociétés minières, pas de l'or
    # physique. Le mot gold seul ne doit pas faire contourner le look-through.
    if any(marker in text for marker in ("gold miner", "gold mining", "silver miner", "silver mining")):
        return False
    return any(marker in text for marker in _NON_EQUITY_MARKERS)


def _composition_payload(value: Any) -> tuple[list[dict], dict]:
    """Accepte l'ancien ``list[holding]`` et le nouveau payload documenté."""
    if isinstance(value, dict):
        holdings = value.get("holdings") or []
        meta = {key: item for key, item in value.items() if key != "holdings"}
        return list(holdings), meta
    return list(value or []), {"source": "yahoo_top_holdings", "partial": True}


def _remaining_maturity_years(value: Any) -> float | None:
    """Convertit les dates émetteurs (ISO ou YYYYMMDD) en années restantes."""
    raw = _clean_text(value)
    if not raw:
        return None
    for pattern, candidate in (("%Y-%m-%d", raw[:10]), ("%Y%m%d", raw[:8])):
        try:
            maturity = dt.datetime.strptime(candidate, pattern).date()
            return max((maturity - dt.date.today()).days / 365.25, 0.0)
        except ValueError:
            continue
    return None


def _bond_maturity_bucket(holding: dict) -> str:
    """Tranche lisible et stable utilisée par la décomposition du portefeuille."""
    years = _remaining_maturity_years(holding.get("maturity"))
    if years is None:
        years = _number(holding.get("duration"))
    if years is None:
        return "Échéance inconnue"
    for upper, label in (
        (1.0, "0–1 an"), (3.0, "1–3 ans"), (5.0, "3–5 ans"),
        (7.0, "5–7 ans"), (10.0, "7–10 ans"),
        (15.0, "10–15 ans"), (20.0, "15–20 ans"),
    ):
        if years <= upper:
            return label
    return "20 ans et plus"


def _identifier_slug(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]+", "_", folded.upper()).strip("_") or "INCONNU"


def economic_exposure_from_payload(
    value: Any,
    *,
    minimum_coverage: float,
) -> tuple[dict[str, float], float, dict, bool]:
    """Normalise une composition et indique si elle est exploitable.

    Le seuil porte sur la somme réellement identifiée. Pour un ETF synthétique,
    seule la feuille de constituants économiques est recevable : les principales
    positions Yahoo pourraient décrire le collatéral du swap.
    """
    holdings, meta = _composition_payload(value)
    exposure: defaultdict[str, float] = defaultdict(float)
    for item in holdings:
        ticker = _clean_text(item.get("ticker")).upper()
        isin = _clean_text(item.get("isin")).upper()
        identity = ticker or (f"ISIN:{isin}" if isin else "")
        weight = _number(item.get("weight"))
        if identity and weight is not None:
            exposure[identity] += max(float(weight), 0.0)
    raw_coverage = sum(exposure.values())
    if raw_coverage > 1.0:
        exposure = defaultdict(
            float,
            {ticker: weight / raw_coverage for ticker, weight in exposure.items()},
        )
    coverage = min(raw_coverage, 1.0)
    source = str(meta.get("source") or "")
    economic_source = source in {
        "index_composition_cache",
        "official_index_constituents",
        "issuer_index_constituents",
        "manual_official_index_constituents",
        "issuer_fund_holdings",
        "physical_tracker_proxy",
        "manual_physical_tracker_proxy",
    }
    usable = economic_source and coverage >= min(max(float(minimum_coverage), 0.0), 1.0)
    return dict(exposure), coverage, meta, usable


def etf_composition_quality(
    value: Any,
    row: Any,
    *,
    minimum_coverage: float,
    constituent_metadata: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Décide si la connaissance économique d'un ETF autorise son achat.

    Actions : au moins ``minimum_coverage`` de positions économiques ET de
    couples secteur+pays classifiés. Un synthétique n'est recevable que depuis
    la composition officielle de l'indice ou, à défaut, les positions officielles
    d'un tracker physique du même panier clairement signalées comme proxy. Les
    non-actions utilisent une preuve adaptée : positions obligataires documentées,
    indice monétaire identifié ou matière physique identifiée.
    """
    from .breakdown import _canon_sector, is_economic_risk_sector

    holdings, meta = _composition_payload(value)
    threshold = min(max(float(minimum_coverage), 0.0), 1.0)
    source = str(meta.get("source") or "")
    replication = str(meta.get("replication") or "unknown").casefold()
    official_index = source in {
        "index_composition_cache",
        "official_index_constituents",
        "issuer_index_constituents",
        "manual_official_index_constituents",
    }
    official_fund = source == "issuer_fund_holdings" and replication != "synthetic"
    proxy_index = source in {
        "physical_tracker_proxy", "manual_physical_tracker_proxy",
    }
    official_aggregate = source == "issuer_official_aggregate_exposure"
    economic_source = official_index or official_fund or proxy_index
    metadata = {
        str(key).strip().upper(): info
        for key, info in (constituent_metadata or {}).items()
    }
    raw_total = 0.0
    classified_joint = 0.0
    for item in holdings:
        weight = _number(item.get("weight"))
        if weight is None:
            continue
        weight = max(float(weight), 0.0)
        raw_total += weight
        symbol = _clean_text(item.get("ticker")).upper()
        isin = _clean_text(item.get("isin")).upper()
        info = metadata.get(symbol) or metadata.get(f"ISIN:{isin}") or {}
        country = canonical_country(_clean_text(
            item.get("country") or info.get("country") or info.get("Pays")
        ))
        sector = _canon_sector(
            _clean_text(item.get("sector") or info.get("sector") or info.get("Secteur"))
        )
        if (
            country
            and country.casefold() not in {"inconnu", "unknown"}
            and sector != "Inconnu"
            and is_economic_risk_sector(sector)
        ):
            classified_joint += weight
    scale = 1.0 / raw_total if raw_total > 1.0 else 1.0
    coverage = min(raw_total * scale, 1.0)
    joint_coverage = min(classified_joint * scale, 1.0)
    country_coverage = float(meta.get("country_coverage") or 0.0)
    sector_coverage = float(meta.get("sector_coverage") or 0.0)
    aggregate_complete = (
        official_aggregate
        and str(meta.get("scope") or "") == "economic_exposure"
        and country_coverage >= threshold
        and sector_coverage >= threshold
        and bool(meta.get("countries"))
        and bool(meta.get("sectors"))
    )

    # La fiche émetteur peut corriger une classification catalogue trop vague
    # (souvent ``Secteur 2 = Actions`` même pour un ETF obligataire). Les deux
    # sources descriptives sont donc examinées, l'une ne masquant pas l'autre.
    if _is_non_equity_etf(row) or _is_non_equity_etf(meta):
        fixed_income = _fixed_income_risk_profile(value, holdings)
        if isinstance(row, dict):
            lowered_row = {str(key).casefold(): item for key, item in row.items()}
            row_text = " ".join(
                _clean_text(lowered_row.get(key, ""))
                for key in ("nom", "name", "secteur", "pays")
            )
        else:
            row_text = " ".join(
                _clean_text(getattr(row, key, ""))
                for key in ("nom", "name", "secteur", "pays")
            )
        text = " ".join(
            _clean_text(meta.get(key)) for key in ("name", "nom", "index", "index_name")
        ) + " " + row_text
        text = text.casefold()
        is_crypto_etp = any(marker in text for marker in (
            "bitcoin", "ethereum", "crypto", "digital asset",
            "exchange traded product", "exchange-traded product", " etp",
        ))
        physical_commodity = (
            not is_crypto_etp
            and
            replication == "physical"
            and any(marker in text for marker in (
                "gold", "silver", "platinum", "palladium", "commodity",
                "matiere premiere", "matières premières",
            ))
        )
        money_index = bool(
            fixed_income
            and fixed_income[0] == "Monetaire"
            and any(marker in text for marker in ("overnight", "estr", "€str", "sonia", "money market"))
        )
        documented_bonds = bool(fixed_income and economic_source and coverage >= threshold)
        accepted = not is_crypto_etp and (
            physical_commodity or money_index or documented_bonds or aggregate_complete
        )
        reason = (
            "official_aggregate_exposure" if aggregate_complete
            else "adapted_non_equity"
            if accepted
            else "crypto_etp_excluded" if is_crypto_etp
            else "non_equity_economic_description_insufficient"
        )
        return {
            "eligible": accepted,
            "reason": reason,
            "coverage": coverage,
            "joint_coverage": joint_coverage,
            "source": source,
            "replication": replication,
            "provider": str(meta.get("provider") or ""),
            "index": str(meta.get("index") or meta.get("index_name") or ""),
            "index_id": str(meta.get("index_id") or ""),
            "provider_index_id": str(meta.get("provider_index_id") or ""),
            "index_source_url": str(meta.get("index_source_url") or ""),
            "as_of": str(meta.get("as_of") or meta.get("updated_at") or ""),
            "index_status": str(meta.get("index_status") or ""),
            "index_error": str(meta.get("index_error") or ""),
            "enrichment_errors": list(meta.get("enrichment_errors") or []),
            "proxy_ticker": str(meta.get("proxy_ticker") or ""),
            "proxy_isin": str(meta.get("proxy_isin") or ""),
            "proxy_source_url": str(meta.get("proxy_source_url") or ""),
            "proxy_warning": str(meta.get("proxy_warning") or ""),
        }

    if aggregate_complete:
        reason = "official_aggregate_exposure"
        accepted = True
    elif replication == "synthetic" and not (official_index or proxy_index):
        reason = (
            "synthetic_index_unresolved"
            if not str(meta.get("index_id") or "").strip()
            else "synthetic_index_constituents_required"
        )
        accepted = False
    elif not economic_source:
        reason = "unofficial_or_collateral_composition"
        accepted = False
    elif coverage < threshold:
        reason = "economic_coverage_below_threshold"
        accepted = False
    elif joint_coverage < threshold:
        reason = "sector_country_coverage_below_threshold"
        accepted = False
    else:
        reason = "physical_tracker_proxy" if proxy_index else "complete"
        accepted = True
    return {
        "eligible": accepted,
        "reason": reason,
        "coverage": coverage,
        "joint_coverage": joint_coverage,
        "source": source,
        "replication": replication,
        "provider": str(meta.get("provider") or ""),
        "index": str(meta.get("index") or meta.get("index_name") or ""),
        "index_id": str(meta.get("index_id") or ""),
        "provider_index_id": str(meta.get("provider_index_id") or ""),
        "index_source_url": str(meta.get("index_source_url") or ""),
        "as_of": str(meta.get("as_of") or meta.get("updated_at") or ""),
        "index_status": str(meta.get("index_status") or ""),
        "index_error": str(meta.get("index_error") or ""),
        "enrichment_errors": list(meta.get("enrichment_errors") or []),
        "proxy_ticker": str(meta.get("proxy_ticker") or ""),
        "proxy_isin": str(meta.get("proxy_isin") or ""),
        "proxy_source_url": str(meta.get("proxy_source_url") or ""),
        "proxy_warning": str(meta.get("proxy_warning") or ""),
    }


def index_sector_country_lookthrough(
    compositions: dict[str, Any],
    constituent_metadata: dict[str, dict[str, Any]],
) -> dict[str, dict[str, dict[str, float]]]:
    """Table exacte ``ETF -> secteur -> pays -> poids`` issue des positions."""
    from .breakdown import _canon_sector, is_economic_risk_sector

    metadata = {
        str(key).strip().upper(): value
        for key, value in constituent_metadata.items()
    }
    output: dict[str, dict[str, dict[str, float]]] = {}
    for raw_ticker, payload in compositions.items():
        ticker = str(raw_ticker).strip().upper()
        holdings, meta = _composition_payload(payload)
        if (
            str(meta.get("source") or "")
            == "issuer_official_aggregate_exposure"
        ):
            # Deux marges ne définissent pas une distribution conjointe.
            output[ticker] = {}
            continue
        buckets: defaultdict[str, defaultdict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        total = 0.0
        for holding in holdings:
            weight = _number(holding.get("weight"))
            if weight is None:
                continue
            weight = max(float(weight), 0.0)
            total += weight
            symbol = _clean_text(holding.get("ticker")).upper()
            isin = _clean_text(holding.get("isin")).upper()
            info = metadata.get(symbol) or metadata.get(f"ISIN:{isin}") or {}
            raw_sector = _clean_text(
                holding.get("sector") or info.get("sector") or info.get("Secteur")
            )
            sector = _canon_sector(raw_sector)
            if sector == "Inconnu" or not is_economic_risk_sector(sector):
                sector = "Inconnu"
            country = canonical_country(_clean_text(
                holding.get("country") or info.get("country") or info.get("Pays")
            ) or "Inconnu")
            if country.casefold() in {"unknown", "inconnu"}:
                country = "Inconnu"
            buckets[sector][country] += weight
        scale = 1.0 / total if total > 1.0 else 1.0
        normalized = {
            sector: {country: value * scale for country, value in countries.items()}
            for sector, countries in buckets.items()
        }
        residue = max(0.0, 1.0 - total * scale)
        if residue > 1e-12:
            normalized.setdefault("Inconnu", {})["Inconnu"] = (
                normalized.get("Inconnu", {}).get("Inconnu", 0.0) + residue
            )
        output[ticker] = normalized
    return output


def _fixed_income_risk_profile(payload: Any, holdings: list[dict]) -> tuple[str, float] | None:
    """Classe le risque de taux/crédit sans appeler toute obligation défensive."""
    _, meta = _composition_payload(payload)
    text = " ".join(
        _clean_text(meta.get(key))
        for key in ("name", "nom", "index", "index_name", "asset_class")
    )
    text += " " + " ".join(
        " ".join(
            _clean_text(item.get(key))
            for key in ("asset_class", "security_type", "name", "rating")
        )
        for item in holdings[:200]
    )
    folded = text.casefold()
    fixed_markers = (
        "bond", "fixed income", "fixed_income", "obligation", "treasury", "gilt",
        "money market", "monetaire", "monétaire", "overnight", "€str", "estr",
        "sonia", "t-bill", "court terme",
    )
    if not any(marker in folded for marker in fixed_markers):
        return None

    money = any(marker in folded for marker in (
        "money market", "monetaire", "monétaire", "overnight", "€str", "estr", "sonia", "fed funds",
        "0-1 year", "ultrashort", "ultra short",
    ))
    high_yield = any(marker in folded for marker in (
        "high yield", "sub-investment", "below investment grade", "junk bond",
    ))
    sovereign = any(marker in folded for marker in (
        "government", "sovereign", "treasury", "gilt", "bund", "govt",
    ))
    corporate = any(marker in folded for marker in (
        "corporate", "corp bond", "entreprise", "investment grade credit",
    ))

    rating_weights = 0.0
    rating_quality = 0.0
    duration_weights = 0.0
    duration_total = 0.0
    today = dt.date.today()
    rating_scores = {
        "AAA": 1.00, "AA+": 0.95, "AA": 0.92, "AA-": 0.88,
        "A+": 0.82, "A": 0.78, "A-": 0.73,
        "BBB+": 0.66, "BBB": 0.60, "BBB-": 0.52,
        "BB+": 0.34, "BB": 0.28, "BB-": 0.22,
        "B+": 0.16, "B": 0.12, "B-": 0.09, "CCC": 0.04,
    }
    for item in holdings:
        weight = _number(item.get("weight")) or 0.0
        rating = _clean_text(item.get("rating")).upper().replace(" ", "")
        score = next((value for key, value in rating_scores.items() if rating.startswith(key)), None)
        if score is not None:
            rating_quality += weight * score
            rating_weights += weight
            if score < rating_scores["BBB-"]:
                high_yield = True
        raw_duration = _number(item.get("duration"))
        years = raw_duration
        if years is None:
            raw_maturity = _clean_text(item.get("maturity"))[:10]
            try:
                maturity = dt.date.fromisoformat(raw_maturity)
                years = max((maturity - today).days / 365.25, 0.0)
            except ValueError:
                years = None
        if years is not None:
            duration_total += weight * min(float(years), 30.0)
            duration_weights += weight

    duration = duration_total / duration_weights if duration_weights else None
    credit = rating_quality / rating_weights if rating_weights else None
    if money:
        return "Monetaire", 0.95
    if high_yield:
        bucket, base = "Obligations high yield", 0.18
    elif sovereign:
        bucket, base = "Obligations souveraines", 0.82
    elif corporate or (credit is not None and credit >= 0.52):
        bucket, base = "Obligations entreprises IG", 0.62
    else:
        bucket, base = "Obligations diversifiees", 0.45
    # Une maturité longue accroît fortement la sensibilité aux taux. À qualité
    # identique elle ne reçoit donc pas le même caractère défensif qu'un 1-3 ans.
    if duration is not None:
        duration_factor = 1.0 if duration <= 3 else 0.82 if duration <= 7 else 0.58
        base *= duration_factor
    if credit is not None:
        base *= 0.75 + 0.35 * credit
    return bucket, min(max(base, 0.0), 1.0)


def index_risk_lookthrough(
    compositions: dict[str, Any],
    constituent_metadata: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]], dict[str, float]]:
    """Dérive pays, secteurs et défensif des mêmes constituants d'indice.

    Le reliquat non publié ou non classifié reste ``Inconnu``. Aucun champ pays,
    secteur ou défensif porté par la ligne ETF de ToutBroker n'est consulté.
    """
    from .breakdown import _canon_sector, is_economic_risk_sector
    from .sector_lookthrough import DEFENSIVE_SECTORS

    countries_by_etf: dict[str, dict[str, float]] = {}
    sectors_by_etf: dict[str, dict[str, float]] = {}
    defensive_by_etf: dict[str, float] = {}
    metadata = {str(key).strip().upper(): value for key, value in constituent_metadata.items()}

    for raw_ticker, payload in compositions.items():
        ticker = str(raw_ticker).strip().upper()
        holdings, aggregate_meta = _composition_payload(payload)
        if (
            str(aggregate_meta.get("source") or "")
            == "issuer_official_aggregate_exposure"
        ):
            countries_by_etf[ticker] = canonicalize_exposure({
                str(key): float(value)
                for key, value in (aggregate_meta.get("countries") or {}).items()
            })
            sectors_by_etf[ticker] = {
                str(key): float(value)
                for key, value in (aggregate_meta.get("sectors") or {}).items()
            }
            # Sans matrice officielle conjointe, aucun bonus pays × secteur et
            # aucune déduction supplémentaire du caractère défensif.
            defensive_by_etf[ticker] = 0.0
            continue
        fixed_income = _fixed_income_risk_profile(payload, holdings)
        countries: defaultdict[str, float] = defaultdict(float)
        sectors: defaultdict[str, float] = defaultdict(float)
        classified_country = 0.0
        defensive = 0.0
        total = 0.0
        for holding in holdings:
            symbol = _clean_text(holding.get("ticker")).upper()
            isin = _clean_text(holding.get("isin")).upper()
            weight = _number(holding.get("weight"))
            if not (symbol or isin) or weight is None:
                continue
            weight = max(float(weight), 0.0)
            info = metadata.get(symbol) or metadata.get(f"ISIN:{isin}", {})
            country = canonical_country(
                _clean_text(holding.get("country") or info.get("country") or info.get("Pays"))
            )
            raw_sector = _clean_text(holding.get("sector") or info.get("sector") or info.get("Secteur"))
            sector = _canon_sector(raw_sector)
            total += weight
            if country and country.casefold() not in {"inconnu", "unknown"}:
                countries[country] += weight
                classified_country += weight
            if fixed_income is None and sector and sector != "Inconnu" and is_economic_risk_sector(sector):
                sectors[sector] += weight
                if sector in DEFENSIVE_SECTORS:
                    defensive += weight

        # Un indice ne peut représenter plus de 100 % malgré les arrondis.
        scale = 1.0 / total if total > 1.0 else 1.0
        countries = defaultdict(float, {key: value * scale for key, value in countries.items()})
        sectors = defaultdict(float, {key: value * scale for key, value in sectors.items()})
        defensive *= scale
        if fixed_income is not None:
            bucket, defensive = fixed_income
            sectors = defaultdict(float, {bucket: 1.0})
        unknown_country = max(0.0, 1.0 - classified_country * scale)
        if fixed_income is not None and not holdings:
            # Un indice monétaire représente un taux, pas l'émetteur du panier
            # de collatéral d'un swap. Il n'a donc volontairement aucun pays.
            if fixed_income[0] == "Monetaire":
                countries = defaultdict(float, {"Sans pays": 1.0})
                unknown_country = 0.0
        if unknown_country > 1e-12:
            countries["Inconnu"] += unknown_country
        countries_by_etf[ticker] = canonicalize_exposure(dict(countries)) or {"Inconnu": 1.0}
        sectors_by_etf[ticker] = dict(sectors)
        defensive_by_etf[ticker] = min(max(defensive, 0.0), 1.0)
    return countries_by_etf, sectors_by_etf, defensive_by_etf


def load_etf_replication_metadata(tickers: Iterable[str]) -> dict[str, dict]:
    """Lit les métadonnées déclarées sans supposer que le collatéral est l'indice."""
    wanted = {str(value).strip().upper() for value in tickers}
    if not wanted:
        return {}
    try:
        from .broker_availability import _find_ticker_col, load_broker_table

        frame = load_broker_table()
        ticker_column = _find_ticker_col(frame.columns, "Ticker Yahoo Finance")
    except Exception:
        return {}
    columns = {str(column).strip().casefold(): column for column in frame.columns}
    replication_column = next(
        (
            columns[name]
            for name in (
                "replication", "réplication", "methode de replication",
                "méthode de réplication", "replication method",
            )
            if name in columns
        ),
        None,
    )
    index_column = next(
        (columns[name] for name in ("indice", "index", "benchmark") if name in columns),
        None,
    )
    result: dict[str, dict] = {}
    if ticker_column is None:
        return result
    for _, row in frame.iterrows():
        ticker = _clean_text(row.get(ticker_column)).upper()
        if ticker not in wanted:
            continue
        raw_replication = _clean_text(row.get(replication_column)).casefold() if replication_column else ""
        replication = (
            "synthetic"
            if any(marker in raw_replication for marker in ("synt", "swap"))
            else "physical" if any(marker in raw_replication for marker in ("phys", "direct"))
            else "unknown"
        )
        result[ticker] = {
            "replication": replication,
            "index": _clean_text(row.get(index_column)) if index_column else "",
        }
    return result


def load_cached_economic_constituents(tickers: Iterable[str]) -> dict[str, dict]:
    """Charge l'éventuelle feuille ``ETF_Constituants`` du catalogue.

    Pour un fonds synthétique cette feuille doit contenir l'indice économique,
    jamais les titres remis en collatéral par la contrepartie du swap.
    """
    wanted = {str(value).strip().upper() for value in tickers}
    if not wanted:
        return {}
    try:
        import pandas as pd

        from .broker_availability import find_broker_file

        path = find_broker_file()
        frame = pd.read_excel(path, sheet_name="ETF_Constituants") if path else None
    except Exception:
        return {}
    if frame is None or frame.empty:
        return {}
    columns = {str(column).strip().casefold(): column for column in frame.columns}
    etf_col = next((columns[key] for key in ("etf_ticker", "ticker etf", "etf") if key in columns), None)
    child_col = next((columns[key] for key in ("ticker", "constituent_ticker", "ticker constituant") if key in columns), None)
    weight_col = next((columns[key] for key in ("weight_pct", "poids_pct", "poids", "weight") if key in columns), None)
    name_col = next((columns[key] for key in ("nom", "name") if key in columns), None)
    if etf_col is None or child_col is None or weight_col is None:
        return {}
    grouped: dict[str, list[dict]] = {}
    for _, row in frame.iterrows():
        etf = _clean_text(row.get(etf_col)).upper()
        child = _clean_text(row.get(child_col)).upper()
        weight = _number(row.get(weight_col))
        if etf not in wanted or not child or weight is None:
            continue
        grouped.setdefault(etf, []).append({
            "ticker": child,
            "name": _clean_text(row.get(name_col)) if name_col else child,
            "weight": weight,
        })
    result = {}
    for etf, holdings in grouped.items():
        if holdings and (max(item["weight"] for item in holdings) > 1 or sum(item["weight"] for item in holdings) > 2):
            for item in holdings:
                item["weight"] /= 100.0
        result[etf] = {
            "holdings": holdings,
            "source": "catalog_etf_constituents",
            "partial": sum(item["weight"] for item in holdings) < 0.90,
        }
    return result


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.casefold() in {"", "nan", "none", "-"} else text


def _number(value: Any) -> float | None:
    try:
        if isinstance(value, str):
            value = value.strip().replace("%", "").replace(",", ".")
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def holdings_from_yahoo(frame: Any) -> list[dict]:
    """Normalise ``funds_data.top_holdings`` sans dépendre de sa casse exacte."""
    if frame is None or getattr(frame, "empty", True):
        return []
    columns = {str(column).strip().casefold(): column for column in frame.columns}
    weight_column = next(
        (
            columns[name]
            for name in ("holding percent", "holdingpercent", "% assets", "weight")
            if name in columns
        ),
        None,
    )
    if weight_column is None:
        return []
    name_column = next(
        (columns[name] for name in ("name", "holding name", "description") if name in columns),
        None,
    )
    symbol_column = next(
        (columns[name] for name in ("symbol", "ticker", "holding symbol") if name in columns),
        None,
    )

    parsed: list[dict] = []
    for index, row in frame.iterrows():
        symbol = _clean_text(row.get(symbol_column) if symbol_column is not None else index).upper()
        weight = _number(row.get(weight_column))
        if not symbol or weight is None:
            continue
        parsed.append(
            {
                "ticker": symbol,
                "name": _clean_text(row.get(name_column)) if name_column is not None else symbol,
                "weight": weight,
            }
        )
    # Yahoo renvoie habituellement des fractions, mais certains fournisseurs
    # exposent les mêmes valeurs en pourcentages.
    if parsed and (max(item["weight"] for item in parsed) > 1.0 or sum(item["weight"] for item in parsed) > 2.0):
        for item in parsed:
            item["weight"] /= 100.0
    return parsed


def fetch_etf_holdings(
    tickers: Iterable[str],
    *,
    refresh_indices: bool = False,
    force_refresh: bool = False,
    progress_cb=None,
    should_stop=None,
    budget=None,
) -> dict[str, dict]:
    """Charge les constituants officiels, mutualisés par indice exact.

    Yahoo et les anciennes feuilles ``ETF_Constituants``/``ETF_Pays`` ne sont
    pas des replis. À défaut de composition officielle de l'indice, seules les
    positions officielles récentes d'un tracker physique du même panier peuvent
    servir de proxy économique explicite; sinon le résultat reste indisponible.

    ``refresh_indices`` reste compatible avec les anciens appelants : la
    fraîcheur et les délais de reprise sont toujours respectés. Seul
    ``force_refresh`` permet une relance réseau forcée de maintenance.
    """
    from .broker_availability import load_broker_table
    from .etf_index_registry import (
        OFFICIAL_INDEX_COMPOSITION_SOURCES,
        canonical_constituent_set_id,
        cached_fund_composition,
        cached_index_composition,
        cached_physical_index_proxy,
        load_registry,
        resolve_index_registry,
    )

    unique = sorted({str(ticker).strip().upper() for ticker in tickers if ticker})
    if not unique:
        return {}

    def report(stage: str):
        if progress_cb is None:
            return None
        return lambda done, total, item: progress_cb(stage, done, total, item)

    table = load_broker_table()
    # Le registre complet reste disponible pour les proxies, mais les
    # métadonnées des milliers d'autres ETF ne doivent pas être reconstruites
    # à chaque vague de remplacement.
    universe = unique
    pipeline_errors: list[dict[str, str]] = []
    # L'enrichissement réseau est volontairement limité aux ETF effectivement
    # demandés par la présélection. Les correspondances sont ensuite partagées
    # par ISIN/indice avec toutes leurs autres cotations.
    from .config import Config
    from .etf_research_budget import EtfResearchBudget
    if budget is None:
        budget = EtfResearchBudget()

    # Cache first, including exact physical trackers of synthetic benchmarks.
    # Snapshot reuse avoids rereading the entire registry for every ETF.
    initial_meta = resolve_index_registry(universe, broker_table=table)
    initial_registry = load_registry()
    full_registry = initial_registry
    proxy_cache: dict[str, dict | None] = {}

    def physical_proxy(index_id: str):
        if index_id not in proxy_cache:
            proxy_cache[index_id] = cached_physical_index_proxy(index_id, registry=full_registry)
        return proxy_cache[index_id]
    reusable: set[str] = set()
    wanted_baskets: set[str] = set()
    for ticker in unique:
        meta = initial_meta.get(ticker, {})
        index_id = str(meta.get("index_id") or "")
        composition = cached_index_composition(index_id, registry=initial_registry) if index_id else None
        if not composition and str(meta.get("replication") or "").casefold() != "synthetic":
            composition = cached_fund_composition(str(meta.get("identity_key") or ""), registry=initial_registry)
        if not composition and index_id:
            composition = physical_proxy(index_id)
        if composition and float(composition.get("coverage") or sum(
            float(row.get("weight") or 0) for row in composition.get("holdings", [])
        )) >= 0.90:
            reusable.add(ticker)
        elif index_id:
            wanted_baskets.add(canonical_constituent_set_id(meta.get("index_name") or index_id))

    # A known physical tracker can publish holdings even when the benchmark
    # administrator licenses its constituents. Try ONE donor per exact basket.
    donors: dict[str, str] = {}
    for fund in initial_registry.get("funds", {}).values():
        if str(fund.get("replication") or "").casefold() != "physical":
            continue
        basket = canonical_constituent_set_id(fund.get("index_name") or fund.get("index_id"))
        aliases = fund.get("tickers") or []
        if basket in wanted_baskets and aliases:
            donors.setdefault(basket, str(aliases[0]).upper())
    network_tickers = sorted(set(unique if force_refresh else set(unique) - reusable) | set(donors.values()))

    if Config.ETF_OFFICIAL_ENRICHMENT_ENABLED:
        try:
            from .official_etf_enrichment import enrich_official_etfs
            # Une préparation ordinaire respecte fraîcheur et cache d'échecs.
            # Seule une demande explicite de maintenance contourne les délais.
            enrich_official_etfs(
                network_tickers, broker_table=table, progress_cb=report("fonds"),
                **({"force": True} if force_refresh else {}),
                **({"should_stop": should_stop} if should_stop is not None else {}),
                budget=budget,
            )
        except Exception as exc:
            # L'analyse peut continuer, mais l'échec doit rester visible dans les
            # diagnostics de chaque ETF concerné et dans le détail de la run.
            error = {
                "stage": "issuer_fund_enrichment",
                "type": type(exc).__name__,
                "message": str(exc),
            }
            pipeline_errors.append(error)
            print(f"[ETF] enrichissement émetteur impossible: {type(exc).__name__}: {exc}")
    declared = load_etf_replication_metadata(universe)
    registry = resolve_index_registry(universe, broker_table=table)
    from .manual_etf_sources import prepare_manual_official_sources
    manual_routes = prepare_manual_official_sources(unique, registry, budget=budget)
    if manual_routes:
        # Une source manuelle officielle peut avoir complété le registre partagé.
        registry = resolve_index_registry(universe, broker_table=table)
    full_registry = load_registry()
    proxy_cache.clear()

    def needs_index_download(ticker: str) -> bool:
        if force_refresh:
            return True
        meta = registry.get(ticker, {})
        declared_meta = declared.get(ticker, {})
        replication = str(
            meta.get("replication")
            if str(meta.get("source") or "").startswith("issuer_")
            else declared_meta.get("replication") or meta.get("replication") or "unknown"
        ).strip().casefold()
        if replication != "synthetic" and cached_fund_composition(str(meta.get("identity_key") or ""), registry=full_registry):
            return False
        index_id = str(meta.get("index_id") or "")
        if index_id and physical_proxy(index_id):
            return False
        return True

    # Deuxième étage : l'émetteur a identifié l'indice exact; si sa composition
    # n'est pas encore en cache, interroger automatiquement son administrateur
    # officiel avant de décider d'exclure le fonds synthétique.
    if Config.ETF_OFFICIAL_INDEX_ENRICHMENT_ENABLED:
        selected_index_ids = {
            str(value.get("index_id") or "")
            for ticker in unique
            for value in [registry.get(ticker, {})]
            if str(value.get("index_id") or "")
            and needs_index_download(ticker)
        }
        manual_index_ids = {
            str(registry.get(ticker, {}).get("index_id") or "")
            for ticker, route in manual_routes.items()
            if route.get("Mode_Composition") == "SOURCE_OFFICIELLE"
        }
        index_ids_to_check = {
            index_id for index_id in selected_index_ids
            if index_id not in manual_index_ids
            and (force_refresh or not cached_index_composition(index_id, registry=full_registry))
        }
        if index_ids_to_check:
            try:
                from .official_index_enrichment import enrich_official_indices

                enrich_official_indices(
                    index_ids_to_check,
                    **({"force": True} if force_refresh else {}),
                    **({"progress_cb": report("indices")} if progress_cb else {}),
                    **({"should_stop": should_stop} if should_stop is not None else {}),
                    budget=budget,
                )
                registry = resolve_index_registry(universe, broker_table=table)
            except Exception as exc:
                # Ne jamais transformer silencieusement une panne du connecteur
                # en preuve que l'indice n'existe pas.
                error = {
                    "stage": "official_index_enrichment",
                    "type": type(exc).__name__,
                    "message": str(exc),
                }
                pipeline_errors.append(error)
                print(f"[ETF] enrichissement indices impossible: {type(exc).__name__}: {exc}")
    full_registry = load_registry()
    if progress_cb is not None:
        progress_cb("assemblage", 0, len(unique), "")
    metadata: dict[str, dict] = {}
    for ticker in universe:
        declared_meta = declared.get(ticker, {})
        registry_meta = registry.get(ticker, {})
        registry_is_official = str(registry_meta.get("source") or "").startswith("issuer_")
        replication = str(
            registry_meta.get("replication") if registry_is_official
            else declared_meta.get("replication")
            or "unknown"
        )
        if replication == "unknown":
            replication = str(registry_meta.get("replication") or "unknown")
        index_record = full_registry.get("indices", {}).get(
            str(registry_meta.get("index_id") or ""), {}
        )
        index_status = index_record.get("official_enrichment") or {}
        metadata[ticker] = {
            **registry_meta,
            **declared_meta,
            "replication": replication,
            "index": str(
                registry_meta.get("index_name") if registry_is_official
                else declared_meta.get("index") or registry_meta.get("index_name")
                or ""
            ),
            "provider": str(index_record.get("provider") or ""),
            "provider_index_id": str(index_record.get("provider_index_id") or ""),
            "index_status": str(index_status.get("status") or ""),
            "index_error": str(index_status.get("error") or ""),
            "index_source_url": str(index_status.get("source_url") or ""),
            "enrichment_errors": [dict(value) for value in pipeline_errors],
        }

    def load(ticker: str) -> dict:
        meta = metadata.get(ticker, {})
        index_id = str(meta.get("index_id") or "")
        manual_route = manual_routes.get(ticker)
        if manual_route and manual_route.get("Mode_Composition") == "PROXY_PHYSIQUE":
            from .manual_etf_sources import manual_physical_proxy
            return manual_physical_proxy(
                ticker, meta, full_registry, manual_route,
            ) or {
                **meta, "holdings": [], "source": "manual_route_invalid",
                "index_status": "manual_route_invalid",
            }
        if manual_route and manual_route.get("_error"):
            return {
                **meta, "holdings": [], "source": "manual_route_invalid",
                "index_status": "manual_route_invalid",
                "index_error": str(manual_route["_error"]),
            }
        cached_index = cached_index_composition(index_id, registry=full_registry) if index_id else None
        source = str((cached_index or {}).get("source") or "")
        if cached_index and source in OFFICIAL_INDEX_COMPOSITION_SOURCES:
            return {
                **meta,
                **cached_index,
                "source": (
                    "manual_official_index_constituents"
                    if manual_route
                    and manual_route.get("Mode_Composition") == "SOURCE_OFFICIELLE"
                    else "index_composition_cache"
                ),
            }
        cached_fund = cached_fund_composition(str(meta.get("identity_key") or ""), registry=full_registry)
        # ``cached_fund_composition`` n'accepte que ``issuer_fund_holdings``, la
        # preuve autoritaire d'un fonds physique (un synthétique publie du
        # collatéral). Le champ ``replication`` peut rester ``unknown`` sans
        # invalider la composition : seul un synthétique déclaré reste exclu.
        if cached_fund and str(meta.get("replication") or "").strip().casefold() != "synthetic":
            return {**meta, **cached_fund, "source": "issuer_fund_holdings"}
        proxy = (
            physical_proxy(index_id)
            if index_id else None
        )
        if proxy:
            return {
                **meta,
                **proxy,
                "source": "physical_tracker_proxy",
                "index_status": "physical_tracker_proxy",
                "index_source_url": str(proxy.get("proxy_source_url") or ""),
            }
        identity_key = str(meta.get("identity_key") or "")
        aggregate = (
            full_registry.get("funds", {}).get(identity_key, {}).get(
                "aggregate_exposure"
            )
            or {}
        )
        if (
            str(aggregate.get("source") or "")
            == "issuer_official_aggregate_exposure"
        ):
            return {
                **meta,
                **aggregate,
                "holdings": [],
                "source": "issuer_official_aggregate_exposure",
                "partial": False,
            }
        # Aucun proxy suffisamment couvert et récent : conserver l'échec
        # explicite, sans utiliser le collatéral du fonds synthétique.
        return {
            **meta,
            "holdings": [],
            "source": "official_index_constituents_required",
            "partial": True,
        }

    results: dict[str, dict] = {}
    assembled = 0
    with ThreadPoolExecutor(max_workers=min(6, len(unique))) as executor:
        futures = {executor.submit(load, ticker): ticker for ticker in unique}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                results[ticker] = future.result()
            except Exception:
                results[ticker] = {
                    "holdings": [], "source": "unavailable", "partial": True,
                    "replication": "unknown", "index": "",
                }
            assembled += 1
            if progress_cb is not None:
                progress_cb("assemblage", assembled, len(unique), ticker)
    return results


def build_equity_lookthrough(allocation_rows: Iterable[Any], compositions: dict[str, Any]) -> dict:
    """Décompose les ETF en actions et en obligations pays × échéance."""
    rows = [row for row in allocation_rows if _number(getattr(row, "allocation_pct", None))]
    input_total = sum(float(row.allocation_pct) for row in rows)
    weights: defaultdict[str, float] = defaultdict(float)
    names: dict[str, str] = {}
    sources: defaultdict[str, set[str]] = defaultdict(set)
    bond_weights: defaultdict[tuple[str, str], float] = defaultdict(float)
    bond_sources: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    etfs: list[dict] = []
    other_equities_weight = 0.0
    unknown_weight = 0.0
    non_equity_weight = 0.0
    known_bonds_weight = 0.0
    other_non_equity_weight = 0.0

    for row in rows:
        ticker = _clean_text(getattr(row, "ticker", "")).upper()
        portfolio_weight = max(float(row.allocation_pct), 0.0)
        is_etf = _clean_text(getattr(row, "secteur", "")).upper() == "ETF"
        if not is_etf:
            weights[ticker] += portfolio_weight
            names.setdefault(ticker, _clean_text(getattr(row, "nom", "")) or ticker)
            sources[ticker].add("Action directe")
            continue

        if _is_non_equity_etf(row):
            non_equity_weight += portfolio_weight
            holdings, meta = _composition_payload(compositions.get(ticker, []))
            fixed_income = _fixed_income_risk_profile(compositions.get(ticker, {}), holdings)
            valid_bonds: list[tuple[str, str, float]] = []
            if fixed_income is not None:
                for holding in holdings:
                    asset_class = _clean_text(holding.get("asset_class")).casefold()
                    if asset_class in {"cash", "currency", "derivative", "futures"}:
                        continue
                    fraction = max(float(_number(holding.get("weight")) or 0.0), 0.0)
                    if fraction <= 0:
                        continue
                    country = canonical_country(_clean_text(holding.get("country"))) or "Inconnu"
                    if country.casefold() in {"unknown", "inconnu"}:
                        country = "Inconnu"
                    valid_bonds.append((country, _bond_maturity_bucket(holding), fraction))
            raw_coverage = sum(fraction for _, _, fraction in valid_bonds)
            scale = 1.0 / raw_coverage if raw_coverage > 1.0 else 1.0
            coverage = min(raw_coverage, 1.0)
            for country, maturity_bucket, raw_fraction in valid_bonds:
                key = (country, maturity_bucket)
                amount = portfolio_weight * raw_fraction * scale
                bond_weights[key] += amount
                bond_sources[key].add(ticker)
                known_bonds_weight += amount
            residual = portfolio_weight * (1.0 - coverage)
            other_non_equity_weight += residual
            etfs.append({
                "ticker": ticker,
                "name": _clean_text(getattr(row, "nom", "")) or ticker,
                "portfolio_weight_pct": portfolio_weight,
                "holdings_coverage_pct": coverage * 100.0,
                "known_holdings": len(valid_bonds),
                "residual_pct": residual,
                "source": str(meta.get("source") or "asset_class"),
                "replication": str(meta.get("replication") or "not_applicable"),
                "index": str(meta.get("index") or meta.get("index_name") or ""),
                "status": "non_equity",
            })
            continue

        holdings, meta = _composition_payload(compositions.get(ticker, []))
        valid_holdings: list[tuple[str, str, float]] = []
        for holding in holdings:
            child = _clean_text(holding.get("ticker")).upper()
            isin = _clean_text(holding.get("isin")).upper()
            identity = child or (f"ISIN:{isin}" if isin else "")
            fraction = max(float(holding.get("weight", 0.0)), 0.0)
            if identity and fraction > 0:
                valid_holdings.append(
                    (
                        identity,
                        _clean_text(holding.get("name")) or identity,
                        fraction,
                    )
                )
        raw_coverage = sum(fraction for _, _, fraction in valid_holdings)
        # Une composition légèrement supérieure à 100 % à cause des arrondis
        # est ramenée à 100 % ; elle ne doit jamais créer du capital.
        scale = 1.0 / raw_coverage if raw_coverage > 1.0 else 1.0
        coverage = min(raw_coverage, 1.0)
        for child, child_name, raw_fraction in valid_holdings:
            fraction = raw_fraction * scale
            weights[child] += portfolio_weight * fraction
            names.setdefault(child, child_name)
            sources[child].add(ticker)
        residual = portfolio_weight * (1.0 - coverage)
        if valid_holdings:
            other_equities_weight += residual
            status = "complete" if coverage >= 0.90 else "partial"
        else:
            unknown_weight += portfolio_weight
            status = "unavailable"
        etfs.append(
            {
                "ticker": ticker,
                "name": _clean_text(getattr(row, "nom", "")) or ticker,
                "portfolio_weight_pct": portfolio_weight,
                "holdings_coverage_pct": coverage * 100.0,
                "known_holdings": len(valid_holdings),
                "residual_pct": residual,
                "source": str(meta.get("source") or "unknown"),
                "replication": str(meta.get("replication") or "unknown"),
                "index": str(meta.get("index") or ""),
                "status": status,
            }
        )

    output = [
        {
            "ticker": ticker,
            "name": names.get(ticker, ticker),
            "weight_pct": weight,
            "sources": sorted(sources[ticker]),
            "is_other": False,
            "asset_type": "action",
            "country": "",
            "maturity_bucket": "",
        }
        for ticker, weight in weights.items()
        if weight > 1e-10
    ]
    for (country, maturity_bucket), weight in bond_weights.items():
        if weight <= 1e-10:
            continue
        output.append({
            "ticker": f"OBLIGATION_{_identifier_slug(country)}_{_identifier_slug(maturity_bucket)}",
            "name": f"Obligation — {country} — {maturity_bucket}",
            "weight_pct": weight,
            "sources": sorted(bond_sources[(country, maturity_bucket)]),
            "is_other": False,
            "asset_type": "obligation",
            "country": country,
            "maturity_bucket": maturity_bucket,
        })
    if other_equities_weight > 1e-10:
        output.append(
            {
                "ticker": "AUTRES_ACTIONS",
                "name": "Autres actions non détaillées",
                "weight_pct": other_equities_weight,
                "sources": sorted(item["ticker"] for item in etfs if item["residual_pct"] > 1e-10),
                "is_other": True,
                "asset_type": "other",
            }
        )
    if unknown_weight > 1e-10:
        output.append({
            "ticker": "COMPOSITION_INDISPONIBLE",
            "name": "Composition économique indisponible",
            "weight_pct": unknown_weight,
            "sources": sorted(item["ticker"] for item in etfs if item["status"] == "unavailable"),
            "is_other": True,
            "asset_type": "other",
        })
    if other_non_equity_weight > 1e-10:
        output.append({
            "ticker": "NON_ACTIONS",
            "name": "Autres expositions non-actions non détaillées",
            "weight_pct": other_non_equity_weight,
            "sources": sorted(
                item["ticker"] for item in etfs
                if item["status"] == "non_equity" and item["residual_pct"] > 1e-10
            ),
            "is_other": True,
            "asset_type": "other",
        })
    output.sort(key=lambda item: (-item["weight_pct"], item["ticker"]))
    known_equities = max(input_total - other_equities_weight - unknown_weight - non_equity_weight, 0.0)
    equity_total = max(input_total - non_equity_weight, 0.0)
    unresolved = other_equities_weight + unknown_weight
    return {
        "version": 3,
        "total_pct": input_total,
        "known_pct": known_equities,
        "other_pct": unresolved,
        "coverage_pct": (known_equities / equity_total * 100.0) if equity_total > 0 else 100.0,
        "equity_coverage_pct": (known_equities / equity_total * 100.0) if equity_total > 0 else 100.0,
        "known_equities_pct": known_equities,
        "other_equities_pct": other_equities_weight,
        "unknown_pct": unknown_weight,
        "non_equity_pct": non_equity_weight,
        "known_bonds_pct": known_bonds_weight,
        "other_non_equity_pct": other_non_equity_weight,
        "rows": output,
        "etfs": sorted(etfs, key=lambda item: -item["portfolio_weight_pct"]),
    }
