"""Enrichissement officiel ETF -> indice -> exposition économique.

Ce module ne consulte que les sites des émetteurs et fournisseurs d'indices.
Une réponse partielle (top 10), une page nécessitant une connexion ou le panier
de collatéral d'un fonds synthétique sont enregistrés comme tels, mais ne sont
jamais promus au rang de composition économique complète.
"""

from __future__ import annotations

import datetime as dt
import html
import io
import math
import re
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from .config import Config
from .etf_index_registry import (
    OFFICIAL_INDEX_COMPOSITION_SOURCES,
    cached_index_composition,
    canonical_index_id,
    canonical_index_name,
    load_registry,
    merge_registry_records,
    replication_method,
    save_registry,
    store_index_composition,
    valid_isin,
)

_TIMEOUT = 15.0
_USER_AGENT = "MissionControl/1.0 ETF metadata (+local portfolio analysis)"
_RETRY_DAYS = 7
_TEMPORARY_RETRY_DAYS = 1
_CONNECTOR_REVISIONS = {"hsbc": 1, "vanguard": 1}
_ISHARES_SEARCH = "https://www.ishares.com/varnish-api/core-search/search/products"
_ISHARES_PRODUCT_DATA = (
    "https://www.ishares.com/varnish-api/uk-retail01-product-data/"
    "product-data/api/v2/get-product-data"
)
_VANGUARD_GPX = "https://www.vanguard.co.uk/gpx/graphql"
_INVESCO_API = "https://dng-api.invesco.com/cache/v1/accounts/en_GB/shareclasses"
_BNP_RANGE_URLS = (
    # Catalogue officiel ETF & Index Funds, mai 2026. La fiche produit par ISIN
    # reste le repli si BNP renouvelle l'identifiant DocFinder.
    "https://docfinder.bnpparibas-am.com/api/files/"
    "a7d2d38d-12c5-4e0b-a77b-d493c83db951",
)
# API « push » qui alimente la fiche produit JS (en-offshore). La page HTML
# statique ne publie pas les répartitions pays/secteurs ; l'API les sert sous
# forme de ``breakdowns`` (COUNTRY / MSCI_SECTOR) avec des poids ``ptf_value``.
_BNP_PUSH_API = "https://api.bnpparibas-am.com/push"
_BNP_PUSH_PROFILE = "PV_LU-FSE"
_BNP_PUSH_LANG = "ENG"
_BNP_PUSH_COUNTRY = "LUX"
_UBS_RANGE_URLS = (
    "https://www.ubs.com/uk/en/assetmanagement/capabilities/etfs/core.html",
    "https://www.ubs.com/uk/en/assetmanagement/capabilities/etfs/active.html",
)
_FRANKLIN_PRODUCT_SITEMAP = (
    "https://www.franklintempleton.co.uk/binaries/content/assets/global/"
    "sitemaps/google/en-gb_product.xml"
)
# API GraphQL publique de la page « price-and-performance ». La page produit
# pré-rendue ne publie que le top 10 ; le panier intégral est servi par le champ
# ``Portfolio.portfolio.dailyholdings`` (ou ``fullholdings`` en repli).
_FRANKLIN_PDS_API = (
    "https://www.franklintempleton.co.uk/api/pds/price-and-performance"
)
_BNP_RANGE_CACHE: dict[str, object] = {}
_BNP_BENCHMARK_BY_ISIN: dict[str, tuple[str, str]] = {
    # Noms et codes publiés dans les fiches mensuelles officielles BNP AM.
    "LU1377381717": ("BNP Paribas Low Vol Europe (EUR) NR", "EU_BNPIFLVE"),
    "LU1481201025": ("BNP Paribas Low Vol Europe (EUR) NR", "EU_BNPIFLVE"),
    "LU1377382103": ("BNP Paribas Quality Europe (EUR) NR", "EU_BNPIFEQE"),
    "LU1481201611": ("BNP Paribas Quality Europe (EUR) NR", "EU_BNPIFEQE"),
    "LU1377382285": ("BNP Paribas Value Europe ESG (EUR) NR", "EU_BNPIFVE"),
    "LU1481201702": ("BNP Paribas Value Europe ESG (EUR) NR", "EU_BNPIFVE"),
    "LU1615090864": ("BNP Paribas High Dividend Europe (EUR) NR", "EU_BNPIHEUN"),
    "LU2244387887": ("BNP Paribas Growth Europe (EUR) RI", "EU_BNPIFEGE"),
}
_AMUNDI_BENCHMARK_BY_ISIN = {
    # La fiche anglaise tronque parfois ce nom à « MSCI USA ESG Selection ».
    # La fiche officielle courante et MSCI publient ce libellé complet.
    "LU1681042864": "MSCI USA ESG Selection P-Series 5% Issuer Capped Index",
    # Fonds physique servant de proxy strict au fonds synthétique ci-dessus.
    "IE000PEAJOT0": "MSCI USA ESG Selection P-Series 5% Issuer Capped Index",
}
_UBS_RANGE_CACHE: dict[str, object] = {}
_GLOBAL_X_CACHE: dict[str, object] = {}
_FRANKLIN_CACHE: dict[str, object] = {}
_VANGUARD_DIRECTORY_CACHE: dict[str, object] = {}
_VANGUARD_DIRECTORY_LOCK = threading.Lock()
_VANGUARD_EQUITY_TYPES = (
    "EQ.DRCPT", "EQ.ETF", "EQ.FSH", "EQ.PREF", "EQ.PSH", "EQ.REIT",
    "EQ.STOCK", "EQ.RIGHT", "EQ.WRT", "MF.MF",
)
_VANGUARD_DISCOVERY_QUERY = """
query DiscoverFunds($portIds: [String!]) {
  funds(portIds: $portIds) {
    portId
    profile {
      portId
      fundFullName
      assetClassificationLevel1
      benchMarkNameFromECS
      etfReplicationMethodology
      identifiers(altIds: ["ISIN"]) { altIdCode altIdValue }
    }
  }
}
"""
_VANGUARD_HOLDINGS_QUERY = """
query FundsHoldingsQuery(
  $portIds: [String!], $securityTypes: [String!], $lastItemKey: String
) {
  funds(portIds: $portIds) {
    profile {
      fundFullName
      fundCurrency
      assetClassificationLevel1
      benchMarkNameFromECS
      etfReplicationMethodology
    }
  }
  borHoldings(portIds: $portIds) {
    holdings(
      limit: 1500, securityTypes: $securityTypes, lastItemKey: $lastItemKey
    ) {
      items {
        issuerName
        securityLongDescription
        gicsSectorDescription
        marketValuePercentage
        ticker
        securityType
        effectiveDate
        bloombergIsoCountry
      }
      totalHoldings
      lastItemKey
    }
  }
}
"""


def _fee_rate(value) -> float | None:
    """Normalise un TER/OCF en fraction annuelle (0,20 % -> 0,002)."""
    if value is None:
        return None
    raw = str(value).strip().replace("\u00a0", " ").replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", raw)
    if not match:
        return None
    try:
        number = float(match.group())
    except ValueError:
        return None
    if number < 0:
        return None
    if "%" in raw or number > 0.02:
        number /= 100.0
    return number if number <= 0.05 else None


def _fee_from_text(text: str) -> float | None:
    compact = re.sub(r"\s+", " ", str(text or ""))
    labels = (
        "ongoing charges", "ongoing charge", "total expense ratio", "expense ratio",
        "all-in fee", "all in fee", "management fee", "frais courants",
        "frais de gestion", "coûts récurrents", "couts recurrents", "ter", "ocf",
    )
    alternatives = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?:{alternatives})[^%\d]{{0,100}}(\d+(?:[.,]\d+)?)\s*%",
        compact,
        flags=re.IGNORECASE,
    )
    return _fee_rate(f"{match.group(1)}%") if match else None


def _apply_official_fee(fund: dict, official: dict) -> None:
    """Persiste le coût émetteur et le fait qu'il a bien été recherché."""
    fund["management_fee_checked_at"] = dt.date.today().isoformat()
    rate = _fee_rate(official.get("management_fee_rate"))
    if rate is not None:
        fund["management_fee_rate"] = rate
        fund["management_fee_source"] = str(official.get("url") or "issuer")


def _issuer(name: str) -> str:
    value = str(name or "").strip().casefold()
    if "ishares" in value or "blackrock" in value:
        return "ishares"
    if "amundi" in value or "lyxor" in value:
        return "amundi"
    if "xtrackers" in value or re.search(r"\bxtr(?:\.|\s|$)", value):
        return "xtrackers"
    if "state street" in value or "spdr" in value:
        return "spdr"
    if "vaneck" in value:
        return "vaneck"
    if "kraneshares" in value:
        return "kraneshares"
    if "vanguard" in value:
        return "vanguard"
    if "invesco" in value:
        return "invesco"
    if "bnp paribas" in value:
        return "bnp"
    if re.search(r"\bubs\b", value):
        return "ubs"
    if "wisdomtree" in value:
        return "wisdomtree"
    if any(marker in value for marker in (
        "jpmorgan", "jp morgan", "j.p. morgan", "jpm ", "jpm etf",
    )):
        return "jpmorgan"
    if "legal & general" in value or re.search(r"\bl&g\b", value):
        return "legal_general"
    if "franklin" in value:
        return "franklin"
    if "hsbc" in value:
        return "hsbc"
    if "fidelity" in value:
        return "fidelity"
    if "first trust" in value or value.startswith(("ftgf-", "ftgt-")):
        return "first_trust"
    if "global x" in value:
        return "global_x"
    return ""


def _vanguard_graphql(
    http: httpx.Client,
    query: str,
    variables: dict,
) -> dict:
    response = http.post(
        _VANGUARD_GPX,
        headers={"X-Consumer-ID": "uk2"},
        json={"query": query, "variables": variables},
    )
    response.raise_for_status()
    payload = response.json() or {}
    if payload.get("errors"):
        raise ValueError(str(payload["errors"][:2]))
    return dict(payload.get("data") or {})


def _discover_vanguard_port_id(http: httpx.Client, isin: str) -> dict | None:
    """Résout l'ISIN dans l'annuaire officiel, y compris les nouveaux IDs E… ."""
    with _VANGUARD_DIRECTORY_LOCK:
        if time.monotonic() - float(_VANGUARD_DIRECTORY_CACHE.get("loaded_at", -1e9)) < 3600:
            return (_VANGUARD_DIRECTORY_CACHE.get("by_isin") or {}).get(isin.upper())
        response = http.get("https://www.vanguard.co.uk/professional/product")
        response.raise_for_status()
        ids = re.findall(r'"portIds"\s*:\s*"([A-Za-z0-9,]+)"', response.text)
        port_ids = list(dict.fromkeys(value for group in ids for value in group.split(",")))
        if not port_ids:
            raise ValueError("Annuaire Vanguard sans identifiants de fonds")
        by_isin = {}
        for start in range(0, len(port_ids), 200):
            data = _vanguard_graphql(http, _VANGUARD_DISCOVERY_QUERY, {"portIds": port_ids[start:start + 200]})
            for fund in data.get("funds") or []:
                profile = fund.get("profile") or {}
                for item in profile.get("identifiers") or []:
                    identifier = str(item.get("altIdValue") or "").strip().upper()
                    if valid_isin(identifier):
                        by_isin[identifier] = {
                            "port_id": str(fund.get("portId") or profile.get("portId") or ""),
                            "profile": profile,
                        }
        if by_isin:
            _VANGUARD_DIRECTORY_CACHE.update(by_isin=by_isin, loaded_at=time.monotonic())
        return by_isin.get(isin.upper())


def _fetch_vanguard(
    http: httpx.Client,
    isin: str,
    *,
    product_id: str = "",
) -> dict | None:
    discovery = None
    if product_id:
        discovery = {"port_id": str(product_id), "profile": {}}
    else:
        discovery = _discover_vanguard_port_id(http, isin)
    if not discovery or not discovery.get("port_id"):
        return None

    port_id = str(discovery["port_id"])
    profile = dict(discovery.get("profile") or {})
    holdings: list[dict] = []
    last_item_key = None
    total_holdings = 0
    while True:
        data = _vanguard_graphql(
            http,
            _VANGUARD_HOLDINGS_QUERY,
            {
                "portIds": [port_id],
                "securityTypes": None,
                "lastItemKey": last_item_key,
            },
        )
        funds = data.get("funds") or []
        if funds:
            profile.update(funds[0].get("profile") or {})
        bor_rows = data.get("borHoldings") or []
        if not bor_rows:
            break
        page = bor_rows[0].get("holdings") or {}
        total_holdings = int(page.get("totalHoldings") or total_holdings or 0)
        for row in page.get("items") or []:
            security_type = str(row.get("securityType") or "")
            if security_type not in _VANGUARD_EQUITY_TYPES and not security_type.startswith("FI."):
                continue
            try:
                weight = float(row.get("marketValuePercentage") or 0.0) / 100.0
            except (TypeError, ValueError):
                continue
            ticker = str(row.get("ticker") or "").strip().upper()
            name = str(
                row.get("securityLongDescription")
                or row.get("issuerName")
                or ticker
            ).strip()
            if not math.isfinite(weight) or weight <= 0 or not (ticker or name):
                continue
            holdings.append({
                "ticker": ticker,
                "isin": "",
                "name": name,
                "weight": weight,
                "country": str(row.get("bloombergIsoCountry") or "").strip(),
                "sector": str(row.get("gicsSectorDescription") or "").strip(),
                "asset_class": "Fixed Income" if security_type.startswith("FI.") else "Equity",
                "security_type": security_type,
                "as_of": str(row.get("effectiveDate") or ""),
            })
        next_key = page.get("lastItemKey")
        if not next_key or next_key == last_item_key:
            break
        last_item_key = next_key

    return {
        "product_id": port_id,
        "url": _VANGUARD_GPX,
        "index_name": canonical_index_name(profile.get("benchMarkNameFromECS")),
        "replication": replication_method(profile.get("etfReplicationMethodology")),
        "asset_class": str(profile.get("assetClassificationLevel1") or ""),
        "fund_name": str(profile.get("fundFullName") or ""),
        "holdings": holdings,
        "total_holdings": total_holdings,
        "management_fee_rate": None,
    }


def _pdf_text(content: bytes) -> str:
    """Extrait le texte d'une fiche officielle sans imposer pypdf au runtime web."""
    try:
        from pypdf import PdfReader

        return "\n".join(
            page.extract_text() or ""
            for page in PdfReader(io.BytesIO(content)).pages[:3]
        )
    except (ImportError, OSError, ValueError):
        return ""


def _official_marginal_exposures(text: str) -> dict[str, object]:
    """Extrait uniquement des répartitions officielles complètes en pourcentage.

    Les marges pays et secteurs sont conservées séparément. Cette fonction ne
    fabrique jamais une matrice pays × secteur et ignore explicitement les
    sections de collatéral/panier de substitution.
    """
    raw = str(text or "")
    folded = raw.casefold()
    if not raw:
        return {}

    section_heads = {
        "countries": (
            "country breakdown", "geographical breakdown", "geographic breakdown",
            "répartition géographique", "repartition geographique",
            "country allocation", "regional allocation",
        ),
        "sectors": (
            "sector breakdown", "sector allocation", "industry breakdown",
            "répartition sectorielle", "repartition sectorielle",
        ),
    }
    all_heads = tuple(value for values in section_heads.values() for value in values)

    def parse(kind: str) -> dict[str, float]:
        positions = [
            (folded.find(head), head)
            for head in section_heads[kind]
            if folded.find(head) >= 0
        ]
        if not positions:
            return {}
        start, head = min(positions)
        chunk_start = start + len(head)
        ends = [
            folded.find(other, chunk_start)
            for other in all_heads
            if folded.find(other, chunk_start) >= 0
        ]
        end = min(ends) if ends else min(len(raw), chunk_start + 3500)
        chunk = raw[chunk_start:end]
        if any(marker in chunk[:250].casefold() for marker in (
            "collateral", "substitute basket", "panier de substitution",
        )):
            return {}
        values: dict[str, float] = {}
        for line in chunk.splitlines():
            line = re.sub(r"\s+", " ", line).strip(" |;:-")
            percentages = re.findall(r"(?<!\d)(\d{1,3}(?:[.,]\d+)?)\s*%", line)
            if len(percentages) != 1:
                continue
            number = float(percentages[0].replace(",", ".")) / 100.0
            label = re.sub(r"(?<!\d)\d{1,3}(?:[.,]\d+)?\s*%", "", line)
            label = re.sub(r"\s+", " ", label).strip(" |;:-")
            if not label or len(label) > 80 or number <= 0 or number > 1:
                continue
            if any(marker in label.casefold() for marker in (
                "fund", "index", "benchmark", "portfolio", "difference",
            )):
                continue
            values[label] = values.get(label, 0.0) + number
        coverage = sum(values.values())
        if not 0.80 <= coverage <= 1.10:
            return {}
        if coverage > 1.0:
            values = {key: value / coverage for key, value in values.items()}
        return values

    countries = parse("countries")
    sectors = parse("sectors")
    if not countries and not sectors:
        return {}
    return {
        "countries": countries,
        "sectors": sectors,
        "country_coverage": min(sum(countries.values()), 1.0),
        "sector_coverage": min(sum(sectors.values()), 1.0),
        "scope": "economic_exposure",
    }


def _official_replication(text: str) -> str:
    """Détecte uniquement une méthode explicitement publiée par l'émetteur."""
    folded = re.sub(r"\s+", " ", str(text or "")).casefold()
    if folded.strip(" .:-") in {"synthetic", "indirect"} or re.search(
        r"replication(?: method)?\s*:\s*synthetic\b",
        folded,
    ):
        return "synthetic"
    if folded.strip(" .:-") in {"physical", "direct"} or re.search(
        r"replication(?: method)?\s*:\s*physical\b",
        folded,
    ):
        return "physical"
    if any(marker in folded for marker in (
        "synthetic replication", "synthetically replicated", "indirect replication",
        "replication synthétique", "réplication indirecte", "swap based",
        "swap-based", "total return swap", "funded swap", "unfunded swap",
    )):
        return "synthetic"
    if any(marker in folded for marker in (
        "physical replication", "physically replicated", "physically invested",
        "direct replication", "replication physique", "réplication directe",
        "physical sampling", "physical stratified sampling", "full replication",
    )):
        return "physical"
    return "unknown"


def _replications_from_text_pages(pages: list[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    for page in pages:
        lines = page.splitlines()

        def line_method(value: str) -> str:
            match = re.search(r"\b(?:Physical|Synthetic)\b", value, flags=re.IGNORECASE)
            if not match:
                return "unknown"
            return "physical" if match.group().casefold().startswith("physical") else "synthetic"

        for index, line in enumerate(lines):
            isins = re.findall(r"\b[A-Z]{2}[A-Z0-9]{10}\b", line)
            if not isins:
                continue
            method = line_method(line)
            if method == "unknown":
                # Une ligne longue est parfois coupée juste avant la cellule
                # « Replication Method ». Elle appartient au fonds courant tant
                # qu'aucun autre ISIN n'est rencontré.
                for following in lines[index + 1:index + 4]:
                    if re.search(r"\b[A-Z]{2}[A-Z0-9]{10}\b", following):
                        break
                    method = line_method(following)
                    if method != "unknown":
                        break
            if method == "unknown":
                # Les classes de parts supplémentaires ont une cellule fusionnée
                # vide : elles héritent de la dernière méthode explicitée.
                for previous in reversed(lines[max(0, index - 8):index]):
                    method = line_method(previous)
                    if method != "unknown":
                        break
            if method != "unknown":
                for isin in isins:
                    found[isin.upper()] = method
    return found


def _pdf_replications_by_isin(content: bytes) -> dict[str, str]:
    """Extrait les couples ISIN/méthode d'un catalogue tabulaire officiel.

    Les parts couvertes ou distribuantes héritent souvent d'une cellule de
    réplication fusionnée. L'analyse respecte les lignes et cellules fusionnées,
    sans supposer qu'une gamme entière utilise une seule méthode.
    """
    try:
        from pypdf import PdfReader

        pages = [page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages]
    except (ImportError, OSError, ValueError):
        return {}
    return _replications_from_text_pages(pages)


def _fetch_bnp_aggregate_exposure(
    http: httpx.Client, isin: str,
) -> dict[str, object]:
    """Construit l'exposition pays/secteurs depuis l'API push BNP AM.

    L'API expose les répartitions officielles complètes par pays (« COUNTRY »)
    et secteur (« MSCI_SECTOR »). Le panier économique suit ``bench_value`` (la
    pondération de l'indice) quand BNP le renseigne, sinon ``ptf_value`` ; cela
    évite que la poche de trésorerie/collatéral d'un fonds synthétique ou à
    futures ne dilue l'exposition réelle. Les lignes « Cash » et les poids non
    positifs sont ignorés. BNP ne publie pas les positions détaillées (seul le
    top 10 est servi), donc ce connecteur atteint « aggregate_complete », jamais
    « complete ».
    """
    try:
        fundsheet = http.get(
            f"{_BNP_PUSH_API}/fundsheet/{_BNP_PUSH_PROFILE}/"
            f"{_BNP_PUSH_LANG}/{_BNP_PUSH_COUNTRY}/{isin}"
        ).json()
    except (httpx.HTTPError, ValueError, TypeError):
        return {}
    fundshare_id = str(fundsheet.get("fundshare_id") or "")
    if not fundshare_id:
        return {}
    try:
        holdings = http.get(
            f"{_BNP_PUSH_API}/holdings/{_BNP_PUSH_LANG}/{fundshare_id}"
        ).json()
    except (httpx.HTTPError, ValueError, TypeError):
        return {}
    countries: dict[str, float] = {}
    sectors: dict[str, float] = {}
    for breakdown in holdings.get("breakdowns") or []:
        kind = str(breakdown.get("level_1_type_key") or "")
        if kind == "COUNTRY":
            target = countries
        elif kind == "MSCI_SECTOR":
            target = sectors
        else:
            continue
        rows = breakdown.get("level_1_breakdowns") or []
        bench_total = sum(
            float(row.get("bench_value") or 0.0)
            for row in rows
            if row.get("bench_value") is not None
        )
        use_bench = bench_total >= 0.80
        for row in rows:
            label = str(row.get("label") or "").strip()
            if not label or label.casefold() in {
                "cash", "cash and equivalents", "cash & equivalents",
            }:
                continue
            weight = (
                row.get("bench_value") if use_bench else row.get("ptf_value")
            )
            if weight is None:
                continue
            weight = float(weight)
            if weight <= 0:
                continue
            target[label] = target.get(label, 0.0) + weight
    if not countries and not sectors:
        return {}
    return {
        "countries": countries,
        "sectors": sectors,
        "country_coverage": min(sum(countries.values()), 1.0),
        "sector_coverage": min(sum(sectors.values()), 1.0),
        "scope": "economic_exposure",
    }


def _fetch_bnp_replication(http: httpx.Client, isin: str) -> dict | None:
    cache_key = "bnp-range"
    methods = _BNP_RANGE_CACHE.get(cache_key)
    source_url = ""
    if methods is None:
        methods = {}
        for url in _BNP_RANGE_URLS:
            response = http.get(url)
            if response.status_code == 404:
                continue
            response.raise_for_status()
            if response.content.startswith(b"%PDF"):
                methods = _pdf_replications_by_isin(response.content)
                source_url = str(response.url)
                if methods:
                    break
        _BNP_RANGE_CACHE[cache_key] = methods
        _BNP_RANGE_CACHE["source"] = {"url": source_url}
    source_url = str((_BNP_RANGE_CACHE.get("source") or {}).get("url") or source_url)
    method = methods.get(isin.upper(), "unknown")
    product_url = (
        "https://www.bnpparibas-am.com/en-offshore/fundsheet/equity/"
        f"{isin.casefold()}/"
    )
    response = http.get(product_url)
    if response.status_code != 404:
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        if isin.casefold() not in _text(soup).casefold() and method == "unknown":
            return None
    if method == "unknown":
        if response.status_code == 404:
            return None
        method = _official_replication(_text(soup))
        source_url = str(response.url)
    # L'exposition pays/secteurs n'apparaît pas dans le HTML statique (chargé en
    # JavaScript) : elle est récupérée via l'API push, une fois la fiche confirmée.
    aggregate_exposure = _fetch_bnp_aggregate_exposure(http, isin)
    benchmark_name, provider_index_id = _BNP_BENCHMARK_BY_ISIN.get(
        isin.upper(), ("", "")
    )
    return {
        "url": source_url or product_url,
        "replication": method,
        "management_fee_rate": None,
        "aggregate_exposure": aggregate_exposure,
        "index_name": benchmark_name,
        "provider_index_id": provider_index_id,
    }


def _fund_name_key(value: str) -> str:
    folded = str(value or "").casefold()
    folded = re.sub(r"\b(?:ubs|core|ucits|etf)\b", " ", folded)
    folded = re.sub(
        r"\b(?:eur|usd|gbp|chf|jpy|acc|dist|dis|hedged|unhedged|class|share|shares)\b",
        " ",
        folded,
    )
    return " ".join(re.findall(r"[a-z0-9]+", folded))


def _ubs_range_metadata(http: httpx.Client) -> tuple[dict[str, str], list[tuple[str, str]]]:
    cached = _UBS_RANGE_CACHE.get("metadata")
    if isinstance(cached, tuple):
        return cached
    by_isin: dict[str, str] = {}
    by_name: list[tuple[str, str]] = []
    for url in _UBS_RANGE_URLS:
        response = http.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for table in soup.find_all("table"):
            rows: dict[str, list[str]] = {}
            for row in table.find_all("tr"):
                cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
                if len(cells) >= 2:
                    rows[cells[0].strip().casefold()] = cells[1:]
            names = rows.get("etf name") or rows.get("fund name") or []
            isins = rows.get("isin") or []
            methods = rows.get("replication") or []
            for index, raw_method in enumerate(methods):
                method = _official_replication(raw_method)
                if method == "unknown":
                    method = replication_method(raw_method)
                if method == "unknown":
                    continue
                if index < len(isins) and re.fullmatch(r"[A-Z]{2}[A-Z0-9]{10}", isins[index].upper()):
                    by_isin[isins[index].upper()] = method
                if index < len(names):
                    key = _fund_name_key(names[index])
                    if key:
                        by_name.append((key, method))
    metadata = (by_isin, by_name)
    _UBS_RANGE_CACHE["metadata"] = metadata
    return metadata


def _fetch_ubs_replication(
    http: httpx.Client,
    isin: str,
    *,
    fund_name: str,
) -> dict | None:
    by_isin, by_name = _ubs_range_metadata(http)
    method = by_isin.get(isin.upper(), "unknown")
    if method == "unknown":
        key = _fund_name_key(fund_name)
        exact = [candidate_method for candidate, candidate_method in by_name if candidate == key]
        if len(set(exact)) == 1:
            method = exact[0]
    return {
        "url": _UBS_RANGE_URLS[0],
        "replication": method,
        "management_fee_rate": None,
    }


def _fetch_hsbc(http: httpx.Client, isin: str) -> dict | None:
    """Fiche identifiée par ISIN et export intégral officiels (Excel binaire)."""
    base = f"https://www.assetmanagement.hsbc.co.uk/api/v1/download/document/{isin.lower()}/gb/en"
    factsheet = http.get(f"{base}/factsheet")
    if factsheet.status_code == 404:
        return None
    factsheet.raise_for_status()
    if not factsheet.content.startswith(b"%PDF"):
        return None
    text = _pdf_text(factsheet.content)
    if not re.search(rf"\b{re.escape(isin)}\b", text, re.IGNORECASE):
        return None
    # La case dédiée prime sur une mention générale de swaps autorisés dans
    # le prospectus : Physical-Full n'est pas un ETF synthétique.
    method_match = re.search(
        r"Replication\s+method\s*[:\-]?\s*(Physical|Synthetic)\b", text, re.IGNORECASE,
    )
    method = method_match.group(1).lower() if method_match else "unknown"
    index_match = re.search(
        r"Index\s+name\s+(?:100\s*%\s*)?(.+?)\s+Index\s+currency", text,
        re.IGNORECASE | re.DOTALL,
    )
    index_name = canonical_index_name(re.sub(r"\s+", " ", index_match.group(1))) if index_match else ""
    holdings = []
    # Un export holdings de synthétique serait son collatéral. Seul le nom de
    # l'indice sera transmis à la résolution de l'exposition économique.
    if method == "physical":
        holdings = _download_table(http, f"{base}/holdings")
    return {
        "url": str(factsheet.url), "index_name": index_name,
        "replication": method, "holdings": holdings,
        "holdings_url": f"{base}/holdings",
        "management_fee_rate": _fee_from_text(text),
    }


def _jpmorgan_product_urls(fund_name: str, isin: str) -> list[str]:
    value = str(fund_name or "").casefold()
    value = re.sub(r"^jpmorgan\s+etfs?.*?icav\s*[-–—:]?\s*", "", value)
    value = re.sub(r"^jpmorgan\s+investment\s+funds?\s*[-–—:]?\s*", "", value)
    value = re.sub(r"\([^)]*ireland[^)]*\)", " ", value)
    words = re.findall(r"[a-z0-9]+", value)
    if not words:
        return []
    if words[0] != "jpm":
        words.insert(0, "jpm")
    slugs = ["-".join(words)]
    without_esg = [word for word in words if word != "esg"]
    if without_esg != words:
        slugs.append("-".join(without_esg))
    base = "https://am.jpmorgan.com/ch/en/asset-management/adv/products/"
    return [f"{base}{slug}-{isin.casefold()}" for slug in dict.fromkeys(slugs)]


def _fetch_jpmorgan(
    http: httpx.Client,
    isin: str,
    *,
    fund_name: str,
) -> dict | None:
    """Fiche et factsheet officielles J.P. Morgan, résolues par nom + ISIN."""
    for url in _jpmorgan_product_urls(fund_name, isin):
        response = http.get(url)
        if response.status_code == 404:
            continue
        response.raise_for_status()
        page = response.text
        if isin.casefold() not in page.casefold():
            continue
        text = _text(BeautifulSoup(page, "html.parser"))
        factsheet_match = re.search(
            r'"documentType"\s*:\s*"Fact Sheet[^"]*"\s*,\s*'
            r'"docURL"\s*:\s*"([^"]+)"',
            page,
            flags=re.IGNORECASE,
        )
        factsheet_url = ""
        if factsheet_match:
            factsheet_url = factsheet_match.group(1).replace(r"\/", "/")
            factsheet = http.get(factsheet_url)
            factsheet.raise_for_status()
            if factsheet.content.startswith(b"%PDF"):
                text = f"{text}\n{_pdf_text(factsheet.content)}"
        method = _official_replication(text)
        if (
            method == "unknown"
            and re.search(r"\bNumber of Holdings\b", text, flags=re.IGNORECASE)
            and re.search(
                r"actively investing primarily in a portfolio of (?:companies|securities|bonds)",
                text,
                flags=re.IGNORECASE,
            )
            and not re.search(
                r"\b(?:swap|synthetic replication|indirect replication)\b",
                text,
                flags=re.IGNORECASE,
            )
        ):
            # Les ETF actifs n'emploient pas toujours le mot « replication ».
            # J.P. Morgan publie toutefois explicitement un portefeuille de
            # titres et son nombre de positions : c'est une détention physique.
            method = "physical"
        benchmark = ""
        match = re.search(
            r"(?:Reference Index|Benchmark)\s*[:\-]?\s*(.+?)(?=\s{2,}|\n|TER|ISIN)",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            benchmark = canonical_index_name(match.group(1))
            if (
                len(benchmark) > 160
                or "benchmark" in benchmark.casefold()
                or ") by" in benchmark.casefold()
            ):
                benchmark = ""
        return {
            "url": str(response.url),
            "factsheet_url": factsheet_url,
            "index_name": benchmark,
            "replication": method,
            "management_fee_rate": _fee_from_text(text),
            "aggregate_exposure": _official_marginal_exposures(text),
        }
    return None


def _global_x_directory(http: httpx.Client) -> dict[str, str]:
    cached = _GLOBAL_X_CACHE.get("isins")
    if isinstance(cached, dict):
        return cached
    response = http.get("https://globalxetfs.eu/funds/")
    response.raise_for_status()
    # Le catalogue Next.js est rendu côté serveur dans des segments JSON
    # échappés. Les trois champs restent contigus et stables dans chaque ligne.
    page = response.text.replace(r'\"', '"').replace(r"\u0026", "&")
    directory: dict[str, str] = {}
    for match in re.finditer(
        r'"ETF_NAME"\s*:\s*"[^"]*"\s*,\s*'
        r'"PRIMARY_TICKER"\s*:\s*"([^"]+)"\s*,\s*'
        r'"PRIMARY_ISIN"\s*:\s*"([^"]+)"',
        page,
    ):
        ticker = match.group(1).strip().upper()
        isin = match.group(2).strip().upper()
        if ticker and re.fullmatch(r"[A-Z]{2}[A-Z0-9]{10}", isin):
            directory[isin] = ticker
    _GLOBAL_X_CACHE["isins"] = directory
    return directory


def _fetch_global_x(http: httpx.Client, isin: str) -> dict | None:
    ticker = _global_x_directory(http).get(isin.upper(), "")
    if not ticker:
        return None
    response = http.get(f"https://globalxetfs.eu/funds/{ticker.casefold()}/")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    text = _text(soup)
    if isin.casefold() not in text.casefold():
        return None
    method = _official_replication(text)
    index_name = canonical_index_name(_field(
        text,
        ("Underlying Index", "Benchmark Index", "Benchmark"),
    ))
    if not index_name:
        match = re.search(
            r"(?:Underlying|Benchmark) Index\s+(.{3,180}?)"
            r"(?=\s+(?:Total Expense|TER|Management Fee|Fund Facts|ISIN|"
            r"Replication|Holdings|Ticker|$))",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            index_name = canonical_index_name(match.group(1))
    index_download, fund_download = _download_holdings_links(
        soup,
        str(response.url),
        http,
    )
    table_holdings = _parse_holdings_table(soup)
    return {
        "url": str(response.url),
        "index_name": index_name,
        "replication": method,
        "management_fee_rate": _fee_from_text(text),
        "aggregate_exposure": _official_marginal_exposures(
            soup.get_text("\n", strip=True)
        ),
        "index_holdings": index_download[0],
        "index_holdings_url": index_download[1],
        "holdings": fund_download[0] or table_holdings,
        "holdings_url": fund_download[1] or str(response.url),
    }


def _franklin_directory(http: httpx.Client) -> dict[str, str]:
    """Annuaire officiel Franklin : une URL produit exacte par ISIN."""
    cached = _FRANKLIN_CACHE.get("isins")
    if isinstance(cached, dict):
        return cached
    response = http.get(_FRANKLIN_PRODUCT_SITEMAP)
    response.raise_for_status()
    directory: dict[str, str] = {}
    for url in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", response.text):
        if "/our-funds/etf/" not in url.casefold():
            continue
        match = re.search(r"/([A-Z]{2}[A-Z0-9]{10})(?:/)?$", url, flags=re.IGNORECASE)
        if match:
            directory[match.group(1).upper()] = url.strip()
    _FRANKLIN_CACHE["isins"] = directory
    return directory


def _franklin_holdings(http: httpx.Client, isin: str) -> list[dict]:
    """Positions complètes Franklin via l'API GraphQL PDS publique.

    ``ProductLookup`` résout l'ISIN vers le ``fundid`` et surtout le code pays
    d'enregistrement (``cntrycode``, ex. ``CH`` pour un ETF listé au SIX) : c'est
    lui, et non le pays du site, qui conditionne la requête ``Portfolio``.
    """
    lookup = http.post(
        _FRANKLIN_PDS_API,
        json={
            "query": (
                "query Lookup($isin: String!) { ProductLookup(isin: $isin) "
                "{ fundid shclcode cntrycode langcode isin } }"
            ),
            "variables": {"isin": isin},
        },
        headers={"Content-Type": "application/json"},
    )
    if lookup.status_code != 200:
        return []
    identifiers = (lookup.json().get("data") or {}).get("ProductLookup") or []
    match = next(
        (
            item
            for item in identifiers
            if str(item.get("isin") or "").upper() == isin.upper()
        ),
        identifiers[0] if identifiers else None,
    )
    if not match:
        return []
    fundid = str(match.get("fundid") or "")
    country = str(match.get("cntrycode") or "")
    language = str(match.get("langcode") or "") or "en"
    if not fundid or not country:
        return []
    response = http.post(
        _FRANKLIN_PDS_API,
        json={
            "query": (
                "query Portfolio($fundid: String!, $countrycode: String!, "
                "$languagecode: String!) { Portfolio(fundid: $fundid, "
                "countrycode: $countrycode, languagecode: $languagecode) { "
                "portfolio { dailyholdings { secticker isinsecnbr secname "
                "pctofnetassets assetclasscatg } fullholdings { secticker "
                "isinsecnbr secname pctofnetassets assetclasscatg } } } }"
            ),
            "variables": {
                "fundid": fundid,
                "countrycode": country,
                "languagecode": language,
            },
        },
        headers={"Content-Type": "application/json"},
    )
    if response.status_code != 200:
        return []
    portfolio = (
        ((response.json().get("data") or {}).get("Portfolio") or {}).get("portfolio")
        or {}
    )
    rows = portfolio.get("dailyholdings") or portfolio.get("fullholdings") or []
    holdings: list[dict] = []
    for row in rows:
        asset_class = str(row.get("assetclasscatg") or "").strip().upper()
        # Trésorerie et couvertures de change ne sont pas une exposition
        # économique et ne doivent jamais compter dans la couverture.
        if asset_class in {"CASH", "CURRENCY", "FUTURE", "FORWARD", "SWAP", "OPTION"}:
            continue
        try:
            weight = float(str(row.get("pctofnetassets") or "").replace(",", ".")) / 100.0
        except (TypeError, ValueError):
            continue
        ticker = str(row.get("secticker") or "").strip().upper()
        security_isin = str(row.get("isinsecnbr") or "").strip().upper()
        name = str(row.get("secname") or ticker).strip()
        if weight <= 0 or not (ticker or valid_isin(security_isin)):
            continue
        holdings.append({
            "ticker": ticker,
            "isin": security_isin,
            "name": name,
            "weight": weight,
            "asset_class": asset_class,
            "security_type": asset_class,
        })
    return holdings


def _fetch_franklin(http: httpx.Client, isin: str) -> dict | None:
    url = _franklin_directory(http).get(isin.upper(), "")
    if not url:
        return None
    candidates = [url]
    if "/SINGLCLASS/" in url:
        # Le sitemap Franklin publie parfois une classe générique tandis que
        # l'application utilise ETA (capitalisante) ou ETD (distribuante).
        candidates.extend([
            url.replace("/SINGLCLASS/", "/ETA/"),
            url.replace("/SINGLCLASS/", "/ETD/"),
        ])
    for candidate in dict.fromkeys(candidates):
        # La page Angular vide est servie aux clients classiques. Franklin
        # publie sa version officielle pré-rendue aux robots d'indexation.
        response = http.get(
            candidate,
            headers={"User-Agent": "Googlebot/2.1 (+http://www.google.com/bot.html)"},
        )
        if response.status_code == 404:
            continue
        response.raise_for_status()
        text = _text(BeautifulSoup(response.text, "html.parser"))
        if isin.casefold() not in text.casefold():
            continue
        method = _official_replication(text)
        if method == "unknown":
            structure = re.search(
                r"Product Structure(?:\s*\d+)?\s*(Physical|Synthetic)\b",
                text,
                flags=re.IGNORECASE,
            )
            if structure:
                method = (
                    "physical"
                    if structure.group(1).casefold() == "physical"
                    else "synthetic"
                )
        index_name = ""
        index_match = re.search(
            r"(?:Underlying Index|Benchmark)(?:\s*\d+)?\s+(.{3,180}?)"
            r"(?=\s+(?:Investment Universe|Domicile|UCITS|Methodology))",
            text,
            flags=re.IGNORECASE,
        )
        if index_match:
            index_name = canonical_index_name(
                re.sub(r"^\d+\s+", "", index_match.group(1))
            )
        fee = _fee_from_text(text)
        if fee is None:
            fee_match = re.search(
                r"Total Expense Ratio(?:\s*\d+)*\s+(\d+(?:[.,]\d+)?)\s*%",
                text,
                flags=re.IGNORECASE,
            )
            if fee_match:
                fee = _fee_rate(f"{fee_match.group(1)}%")
        result = {
            "url": str(response.url),
            "index_name": index_name,
            "replication": method,
            "management_fee_rate": fee,
        }
        break
    else:
        return None
    # Positions complètes publiées par l'API GraphQL PDS. La fiche pré-rendue
    # n'exposant que le top 10, ce second appel est nécessaire pour dépasser le
    # seuil de couverture de 90 % et promouvoir le fonds au statut « complete ».
    try:
        holdings = _franklin_holdings(http, isin)
    except (httpx.HTTPError, ValueError, TypeError):
        holdings = []
    if holdings:
        result["holdings"] = holdings
        result["holdings_url"] = result["url"]
    return result


def _amundi_index_name(text: str) -> str:
    compact = re.sub(r"\s+", " ", text)
    patterns = (
        # Les factsheets anglaises récentes publient ce champ avant le texte de
        # politique d'investissement (ex. « Benchmark :J.P. Morgan GBI... »).
        r"\bBenchmark\s*:\s*(.+?)(?=\s+(?:Key Information|Objective and Investment Policy|Risk & Reward|Net Asset Value|ISIN code))",
        r"Indice de r.f.rence\s*:\s*(?:100\s*%\s*)?(.+?)(?=Date de la premi.re VL|Donn.es cl.s)",
        r"performance of (?:the )?(.+? Index)(?=\s*\(|\s*,\s*(?:and|while|which|denominated))",
        r"performance de l.indice\s+(.+?)(?=\s*[\(«\"]|\s+quelle que)",
        r"performance de l.Indice\s+(.+?)(?=\s*[\(«\"]|\s+quelle que)",
    )
    for pattern in patterns:
        match = re.search(pattern, compact, flags=re.IGNORECASE)
        if match:
            candidate = canonical_index_name(match.group(1))
            # Une extraction de paragraphe entier ne doit jamais devenir un ID
            # d'indice. Continuer avec les motifs plus précis dans ce cas.
            if len(candidate) > 180:
                continue
            if not re.search(
                r"\b(?:MSCI|STOXX|S&P|FTSE|NASDAQ|TOPIX|KOSPI|SOLACTIVE|"
                r"MORNINGSTAR|BLOOMBERG|ICE|IBOXX|J\.?P\.?\s*MORGAN|"
                r"CAC\s*40|DAX)\b",
                candidate,
                flags=re.IGNORECASE,
            ):
                continue
            return candidate
    return ""


def _fetch_amundi_factsheet(http: httpx.Client, isin: str) -> dict | None:
    """Fiche officielle stable par ISIN, disponible une seule fois par fonds."""
    for language, country in (("ENG", "GBR"), ("ENG", "CHE"), ("FRA", "FRA")):
        url = (
            "https://www.amundietf.com/pdfDocuments/monthly-factsheet/"
            f"{isin}/{language}/{country}/INSTITUTIONNEL/ETF"
        )
        response = http.get(url)
        if response.status_code == 404:
            continue
        response.raise_for_status()
        if not response.content.startswith(b"%PDF"):
            continue
        text = _pdf_text(response.content)
        if isin.casefold() not in text.casefold() and len(text) < 100:
            continue
        folded = text.casefold()
        if any(value in folded for value in ("indirect replication", "réplication indirecte", "r?plication indirecte", "réplication synthétique", "r?plication synth?tique", "total return swap", "otc swaps")):
            method = "synthetic"
        elif any(value in folded for value in ("direct replication", "réplication directe", "r?plication directe", "direct investment", "full replication")):
            method = "physical"
        else:
            method = "unknown"
        first_line = re.sub(r"\s+", " ", text[:250]).casefold()
        if first_line.startswith(("obligataire", "fixed income", "bond")):
            asset_class = "fixed_income"
        elif first_line.startswith(("actions", "equity")):
            asset_class = "equity"
        else:
            asset_class = "unknown"
        return {
            "url": str(response.url),
            "index_name": _AMUNDI_BENCHMARK_BY_ISIN.get(
                isin.upper(), _amundi_index_name(text)
            ),
            "replication": method,
            "asset_class": asset_class,
            "management_fee_rate": _fee_from_text(text),
            "aggregate_exposure": _official_marginal_exposures(text),
        }
    return None


def _fetch_amundi_holdings(http: httpx.Client, isin: str) -> dict | None:
    """Positions complètes publiées par l'API de la page produit Amundi.

    Le téléchargement est réservé aux fonds physiques : pour un ETF
    synthétique, ce même tableau décrit le collatéral du swap et ne doit jamais
    être confondu avec les constituants de l'indice.
    """
    url = "https://www.amundietf.com/mapi/ProductAPI/getProductsData"
    payload = {
        "context": {
            "countryCode": "CHE",
            "countryName": "Switzerland",
            "languageCode": "en",
            "languageName": "English",
            "userProfileName": "INSTIT",
            "bcp47Code": "en-GB",
        },
        "productIds": [isin],
        "characteristics": [
            "ISIN",
            "SHARE_MARKETING_NAME",
            "FUND_REPLICATION_METHODOLOGY",
            "BENCHMARK_NAME",
            "POSITION_AS_OF_DATE",
        ],
        "historics": [],
        "metrics": [],
        "breakDown": {"aggregationFields": []},
        "productType": "PRODUCT",
        "composition": {
            "compositionFields": [
                "date", "type", "bbg", "isin", "name", "weight",
                "quantity", "currency", "sector", "country", "countryOfRisk",
            ],
        },
    }
    response = http.post(url, json=payload)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    products = response.json().get("products") or []
    if not products:
        return None
    product = products[0]
    characteristics = dict(product.get("characteristics") or {})
    if str(characteristics.get("ISIN") or "").upper() != isin.upper():
        return None
    method = replication_method(
        str(characteristics.get("FUND_REPLICATION_METHODOLOGY") or "")
    )
    # Protection fondamentale : le panier d'un synthétique est du collatéral.
    if method != "physical":
        return {
            "url": url,
            "replication": method,
            "index_name": str(characteristics.get("BENCHMARK_NAME") or ""),
            "holdings": [],
            "as_of": str(characteristics.get("POSITION_AS_OF_DATE") or ""),
        }
    holdings: list[dict] = []
    for row in (product.get("composition") or {}).get("compositionData") or []:
        item = dict(row.get("compositionCharacteristics") or {})
        security_type = str(item.get("type") or "").strip().upper()
        # Pour un fonds physique, les obligations sont elles aussi l'exposition
        # économique recherchée. L'ancien filtre EQUITY supprimait 100 % des
        # positions des ETF obligataires Amundi malgré leur ISIN et leur poids
        # officiels. Les instruments de gestion/collatéral restent exclus.
        if any(marker in security_type for marker in (
            "CASH", "FUTURE", "FORWARD", "SWAP", "OPTION", "COLLATERAL",
        )):
            continue
        try:
            weight = float(row.get("weight") or item.get("weight") or 0.0)
        except (TypeError, ValueError):
            continue
        bbg = str(item.get("bbg") or "").strip().upper()
        ticker = bbg.split()[0] if bbg else ""
        holding = {
            "ticker": ticker,
            "isin": str(item.get("isin") or "").strip().upper(),
            "name": str(item.get("name") or ticker).strip(),
            "weight": weight,
            "country": str(item.get("countryOfRisk") or item.get("country") or "").strip(),
            "sector": str(item.get("sector") or "").strip(),
            "security_type": security_type,
        }
        if weight > 0 and (holding["ticker"] or valid_isin(holding["isin"])):
            holdings.append(holding)
    return {
        "url": url,
        "replication": method,
        "index_name": _AMUNDI_BENCHMARK_BY_ISIN.get(
            isin.upper(), str(characteristics.get("BENCHMARK_NAME") or "")
        ),
        "holdings": holdings,
        "as_of": str(characteristics.get("POSITION_AS_OF_DATE") or ""),
    }


def _vaneck_slug(name: str) -> str:
    value = str(name or "").casefold()
    value = re.sub(r"\bvaneck(?: vectors)?\b", "", value)
    value = re.sub(r"\bj\.?p\.?\s*morgan\s+em\b", "emerging markets", value)
    value = re.sub(r"\bucits\b", "", value)
    value = re.sub(r"\bem\b", "emerging markets", value)
    words = re.findall(r"[a-z0-9]+", value)
    # Le nom officiel finit déjà presque toujours par ETF. Éviter etf-etf.
    return "-".join(words if words and words[-1] == "etf" else [*words, "etf"])


def _fetch_vaneck(
    http: httpx.Client,
    isin: str,
    *,
    fund_name: str,
) -> dict | None:
    """Positions publiées par le composant officiel des pages VanEck UCITS."""
    slug = _vaneck_slug(fund_name)
    url = f"https://www.vaneck.com/uk/en/investments/{slug}/holdings/"
    response = http.get(url)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    if isin.casefold() not in _text(soup).casefold():
        return None
    block = soup.find("ve-holdingsblock")
    ticker_node = soup.find("ve-fundticker")
    if block is None or ticker_node is None:
        return None
    block_id = str(block.get("data-blockid") or "")
    page_id = str(block.get("data-pageid") or "")
    internal_ticker = ticker_node.get_text(" ", strip=True)
    if not block_id or not page_id or not internal_ticker:
        return None
    dataset_url = "https://www.vaneck.com/Main/HoldingsBlock/GetDataset/"
    dataset = http.get(dataset_url, params={
        "blockId": block_id,
        "pageId": page_id,
        "ticker": internal_ticker,
        "reactlang": "en",
        "reactctr": "uk",
    })
    dataset.raise_for_status()
    payload = dataset.json() or {}
    rows = list(payload.get("Holdings") or [])
    holdings: list[dict] = []
    asset_classes: set[str] = set()
    for row in rows:
        asset_class = str(row.get("AssetClass") or "").strip()
        if asset_class:
            asset_classes.add(asset_class)
        if asset_class.casefold() in {"cash", "currency", "derivative", "futures"}:
            continue
        try:
            weight = float(str(row.get("Weight") or "").replace(",", ".")) / 100.0
        except ValueError:
            continue
        child_ticker = str(row.get("HoldingTicker") or row.get("Label") or "").strip().upper()
        name = str(row.get("HoldingName") or child_ticker).strip()
        if weight <= 0 or not (child_ticker or name):
            continue
        holdings.append({
            "ticker": child_ticker,
            "isin": str(row.get("ISIN") or "").strip().upper(),
            "name": name,
            "weight": weight,
            "country": str(row.get("Country") or "").strip(),
            "sector": str(row.get("Sector") or "").strip(),
            "asset_class": asset_class,
            "security_type": str(row.get("SecurityType") or row.get("Type") or "").strip(),
            "rating": str(row.get("Rating") or "").strip(),
            "maturity": str(row.get("MaturityDate") or row.get("Maturity") or "").strip(),
        })
    return {
        "url": str(response.url),
        "dataset_url": str(dataset.url),
        "holdings": holdings,
        "asset_classes": sorted(asset_classes),
        "replication": "physical",
        "management_fee_rate": _fee_from_text(_text(soup)),
    }


def _fetch_kraneshares(
    http: httpx.Client,
    isin: str,
    *,
    ticker: str,
) -> dict | None:
    """Composition complète des ETF UCITS publiée en CSV par KraneShares."""
    symbol = re.sub(r"[^A-Z0-9]", "", str(ticker).upper().split(".")[0])
    if not symbol:
        return None
    url = f"https://kraneshares.eu/etf/{symbol.casefold()}ln/"
    browser_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/127.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
    }
    response = http.get(url, headers=browser_headers)
    page_text = ""
    csv_url = ""
    if response.is_success:
        soup = BeautifulSoup(response.text, "html.parser")
        page_text = _text(soup)
        if isin.casefold() not in page_text.casefold():
            return None
        csv_url = next((
            urljoin(str(response.url), str(anchor.get("href") or ""))
            for anchor in soup.find_all("a", href=True)
            if "full holdings" in anchor.get_text(" ", strip=True).casefold()
            and str(anchor.get("href") or "").casefold().endswith(".csv")
        ), "")
    elif response.status_code not in {403, 404}:
        response.raise_for_status()

    # Le CDN CSV reste public lorsque WordPress refuse les clients automatisés.
    # Son nom est daté : rechercher les deux dernières semaines évite tout
    # mapping manuel et absorbe week-ends/jours fériés.
    candidates = [csv_url] if csv_url else []
    candidates.extend(
        "https://kraneshares.eu/csv/"
        f"{(dt.date.today() - dt.timedelta(days=offset)):%m_%d_%Y}_"
        f"{symbol.casefold()}ln_holdings.csv"
        for offset in range(15)
    )
    holdings: list[dict] = []
    for candidate_url in dict.fromkeys(candidates):
        request = urllib.request.Request(
            candidate_url,
            headers={**browser_headers, "Accept": "text/csv,*/*"},
        )
        try:
            timeout = http.budget.before_request() if hasattr(http, "budget") else _TIMEOUT
            with urllib.request.urlopen(request, timeout=timeout) as csv_response:
                content = csv_response.read()
        except urllib.error.HTTPError as exc:
            # Le CDN KraneShares répond parfois 403 plutôt que 404 pour une
            # date de fichier inexistante.
            if exc.code in {403, 404}:
                continue
            raise
        except urllib.error.URLError:
            continue
        frame = pd.read_csv(
            io.BytesIO(content), header=None, skiprows=1,
            encoding_errors="replace",
        )
        holdings = _holdings_from_frame(frame)
        if holdings:
            csv_url = candidate_url
            break
    if not page_text:
        factsheet_url = (
            "https://kraneshares.eu/resources/factsheet/"
            f"{symbol.casefold()}ln_factsheet.pdf"
        )
        try:
            request = urllib.request.Request(factsheet_url, headers=browser_headers)
            timeout = http.budget.before_request() if hasattr(http, "budget") else _TIMEOUT
            with urllib.request.urlopen(request, timeout=timeout) as factsheet:
                factsheet_text = _pdf_text(factsheet.read())
            if isin.casefold() in factsheet_text.casefold():
                page_text = re.sub(r"\s+", " ", factsheet_text)
        except (urllib.error.HTTPError, urllib.error.URLError):
            pass
    match = re.search(
        r"track(?:s|ing)? the performance of (?:the )?(.+? Index)",
        page_text,
        flags=re.IGNORECASE,
    )
    return {
        "url": str(response.url),
        "holdings_url": csv_url,
        "index_name": canonical_index_name(match.group(1)) if match else "",
        "replication": "physical",
        "holdings": holdings,
        "management_fee_rate": _fee_from_text(page_text),
    }


def _key_values(payload) -> list[tuple[str, object]]:
    found: list[tuple[str, object]] = []
    if isinstance(payload, dict):
        if "key" in payload and "value" in payload:
            found.append((str(payload.get("key") or ""), payload.get("value")))
        for value in payload.values():
            found.extend(_key_values(value))
    elif isinstance(payload, list):
        for value in payload:
            found.extend(_key_values(value))
    return found


def _fetch_xtrackers(http: httpx.Client, isin: str) -> dict | None:
    """API publique de la fiche produit Xtrackers, résolue uniquement par ISIN."""
    headers = {"client-id": "passive-frontend"}
    api = ""
    product_url = ""
    for culture in ("en-ch", "en-gb", "en-lu", "de-at", "de-de"):
        candidate_api = f"https://etf.dws.com/api/pdp/{culture}/etf/"
        settings = http.get(f"{candidate_api}{isin}-x/pdpSettings", headers=headers)
        if settings.status_code == 404:
            continue
        settings.raise_for_status()
        product_url = str((settings.json() or {}).get("pdpUrl") or "")
        if product_url:
            api = candidate_api
            break
    if not api or not product_url:
        return None
    identifier = product_url.strip("/").split("/")[-1]
    if not identifier or not identifier.upper().startswith(isin.upper()):
        return None
    meta_response = http.get(f"{api}{identifier}/pdpMetaTagsTealium", headers=headers)
    meta_response.raise_for_status()
    meta = meta_response.json() or {}
    fields = _key_values(meta)

    def field(*labels: str) -> str:
        wanted = {label.casefold() for label in labels}
        for key, value in fields:
            clean_key = BeautifulSoup(key, "html.parser").get_text(" ", strip=True).casefold()
            if clean_key in wanted:
                return BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True)
        return ""

    method = replication_method(field(
        "Product Methodology", "Portfolio Methodology", "Product method",
        "Investment methodology", "Produktmethode", "Portfoliomethode",
    ))
    index_name = canonical_index_name(field(
        "Index Name", "Reference Index", "Benchmark", "Indexname",
    ))
    management_fee = _fee_rate(field(
        "Total Expense Ratio", "All-in fee", "All in fee", "Ongoing Charges",
        "Management Fee", "Gesamtkostenquote", "Pauschalgebühr",
    ))
    holdings_response = http.get(f"{api}{identifier}/holdings", headers=headers)
    holdings_response.raise_for_status()
    tables = list((holdings_response.json() or {}).get("tables") or [])
    holdings: list[dict] = []
    asset_classes: set[str] = set()
    for table in tables:
        columns = {
            str(column.get("value") or "").strip().casefold(): str(column.get("key") or "")
            for column in table.get("columns") or []
        }

        def column(*markers: str, available=columns) -> str:
            return next((
                key for label, key in available.items()
                if any(marker in label for marker in markers)
            ), "")

        isin_col = column("isin")
        name_col = column("name")
        weight_col = column("weight", "gewichtung")
        country_col = column("country", "land")
        sector_col = column("industry", "sector", "industrie", "branche")
        asset_col = column("asset class", "anlageklasse")
        type_col = column("security type", "instrument type", "wertpapierart")
        rating_col = column("rating", "credit quality", "bonitat")
        maturity_col = column("maturity", "falligkeit")
        if not weight_col or not (isin_col or name_col):
            continue
        for row in table.get("values") or []:
            def cell(key: str, current=row):
                return (current.get(key) or {}) if key else {}

            asset_class = str(cell(asset_col).get("value") or "").strip()
            if asset_class:
                asset_classes.add(asset_class)
            if asset_class.casefold() in {
                "cash", "currencies", "currency", "derivatives", "derivative",
            }:
                continue
            raw_weight = cell(weight_col).get("sortValue")
            if raw_weight is None:
                raw_weight = str(cell(weight_col).get("value") or "").replace("%", "").replace(",", ".")
            try:
                weight = float(raw_weight) / 100.0
            except (TypeError, ValueError):
                continue
            child_isin = str(cell(isin_col).get("value") or "").strip().upper()
            name = str(cell(name_col).get("value") or child_isin).strip()
            if weight <= 0 or not (child_isin or name):
                continue
            holdings.append({
                "ticker": "",
                "isin": child_isin,
                "name": name,
                "weight": weight,
                "country": str(cell(country_col).get("value") or "").strip(),
                "sector": str(cell(sector_col).get("value") or "").strip(),
                "asset_class": asset_class,
                "security_type": str(cell(type_col).get("value") or "").strip(),
                "rating": str(cell(rating_col).get("value") or "").strip(),
                "maturity": str(cell(maturity_col).get("value") or "").strip(),
            })
    return {
        "url": f"https://etf.dws.com{product_url}",
        "holdings_url": str(holdings_response.url),
        "index_name": index_name,
        "replication": method,
        "holdings": holdings,
        "asset_classes": sorted(asset_classes),
        "management_fee_rate": management_fee,
    }


def _page_fact(soup: BeautifulSoup, label: str) -> str:
    """Lit une paire libellé/valeur sans dépendre du balisage du tableau."""
    wanted = label.casefold()
    for row in soup.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
        if len(cells) >= 2 and cells[0].strip().casefold() == wanted:
            return cells[1].strip()
    # Les tableaux State Street sont parfois rendus comme deux div/span.
    for node in soup.find_all(string=lambda value: bool(value and value.strip().casefold() == wanted)):
        parent = node.parent
        if parent is None:
            continue
        sibling = parent.find_next_sibling()
        if sibling is not None:
            value = sibling.get_text(" ", strip=True)
            if value:
                return value
    return ""


def _fetch_spdr(http: httpx.Client, isin: str) -> dict | None:
    """Résout un fonds State Street par ISIN puis télécharge toutes ses positions."""
    search = http.get(
        "https://www.ssga.com/public-api/aem/v2/suggest",
        params={
            "q": isin,
            "geoloc": "se:en_gb",
            "roleproduct": "institutional",
            "site": "ssga",
        },
    )
    if search.status_code == 404:
        return None
    search.raise_for_status()
    investments = ((search.json() or {}).get("suggests") or {}).get("Investments") or []
    product_url = next(
        (
            str(item.get("link") or "")
            for item in investments
            if "/etfs/" in str(item.get("link") or "")
        ),
        "",
    )
    if not product_url:
        return None
    response = http.get(product_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    if isin.casefold() not in _text(soup).casefold():
        return None

    index_name = canonical_index_name(_page_fact(soup, "Benchmark"))
    raw_method = _page_fact(soup, "Replication Method")
    method = "physical" if raw_method.casefold() == "replicated" else replication_method(raw_method)
    holdings: list[dict] = []
    holdings_url = ""
    for anchor in soup.find_all("a", href=True):
        label = anchor.get_text(" ", strip=True).casefold()
        href = urljoin(str(response.url), str(anchor["href"]))
        if "holding" not in label or not href.casefold().endswith((".xlsx", ".xls", ".csv")):
            continue
        try:
            holdings = _download_table(http, href)
        except (httpx.HTTPError, ValueError, OSError, pd.errors.ParserError):
            continue
        if holdings:
            holdings_url = href
            break
    return {
        "url": str(response.url),
        "holdings_url": holdings_url,
        "index_name": index_name,
        "replication": method,
        "holdings": holdings,
        "management_fee_rate": _fee_from_text(_text(soup)),
    }


def _invesco_holdings(payload: dict) -> list[dict]:
    """Normalise les constituants officiels Invesco (poids publiés en %)."""
    holdings: list[dict] = []
    for item in payload.get("holdings") or []:
        if not isinstance(item, dict):
            continue
        isin = str(item.get("isin") or "").strip().upper()
        ticker = str(item.get("ticker") or "").strip().upper()
        name = str(item.get("name") or ticker or isin).strip()
        try:
            weight = float(item.get("weight")) / 100.0
        except (TypeError, ValueError):
            continue
        if weight <= 0 or not (isin or ticker):
            continue
        holding = {
            "ticker": ticker,
            "isin": isin if valid_isin(isin) else "",
            "name": name,
            "weight": weight,
        }
        for source, target in (
            ("country", "country"),
            ("sector", "sector"),
            ("couponRate", "coupon_rate"),
            ("maturityDate", "maturity"),
        ):
            value = item.get(source)
            if value not in (None, ""):
                holding[target] = value
        holdings.append(holding)
    return holdings


def _fetch_invesco(http: httpx.Client, isin: str) -> dict | None:
    """Interroge le référentiel officiel Invesco par ISIN, sans page de recherche."""
    def get(url: str) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                fetched = http.get(url, params={"idType": "isin"}, timeout=45.0)
                if fetched.status_code not in {429, 500, 502, 503, 504}:
                    return fetched
                last_error = httpx.HTTPStatusError(
                    f"Invesco API returned {fetched.status_code}",
                    request=fetched.request,
                    response=fetched,
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
            if attempt < 2:
                time.sleep(float(attempt + 1))
        assert last_error is not None
        raise last_error

    base_url = f"{_INVESCO_API}/{isin}"
    response = get(base_url)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json() or {}
    published_isin = str((payload.get("aliases") or {}).get("isin") or "").upper()
    if published_isin != isin.upper():
        return None

    relationship = next(iter(payload.get("benchmarkRelationships") or []), {}) or {}
    index_name = canonical_index_name(html.unescape(str(
        relationship.get("benchmarkFullName") or ""
    )))
    method = replication_method(payload.get("replicationMethod"))
    strategy = payload.get("investmentStrategy") or {}
    account = payload.get("account") or {}
    asset_class = str(strategy.get("assetType") or account.get("fundFocus") or "").strip()
    charges = payload.get("shareclassCharges") or {}

    index_holdings: list[dict] = []
    fund_holdings: list[dict] = []
    index_url = f"{base_url}/holdings/index?idType=isin"
    fund_url = f"{base_url}/holdings/fund?idType=isin"
    try:
        index_response = get(f"{base_url}/holdings/index")
        if index_response.status_code not in {404, 501}:
            index_response.raise_for_status()
            index_holdings = _invesco_holdings(index_response.json() or {})
    except (httpx.HTTPError, ValueError, TypeError):
        pass
    if not index_holdings and method == "physical":
        try:
            fund_response = get(f"{base_url}/holdings/fund")
            if fund_response.status_code not in {404, 501}:
                fund_response.raise_for_status()
                fund_holdings = _invesco_holdings(fund_response.json() or {})
        except (httpx.HTTPError, ValueError, TypeError):
            pass

    return {
        "url": str(response.url),
        "index_url": index_url,
        "fund_url": fund_url,
        "index_name": index_name,
        "replication": method,
        "asset_class": asset_class,
        "management_fee_rate": _fee_rate(charges.get("fundManagementCharge")),
        "index_holdings": index_holdings,
        "fund_holdings": fund_holdings,
    }


def _product_urls(issuer: str, isin: str) -> list[str]:
    """Pages officielles déterministes ou recherches limitées au fournisseur."""
    if issuer == "amundi":
        return [
            f"https://www.amundietf.com/amundi/che/en/instit/{isin}",
            f"https://www.amundietf.fr/fr/particuliers/products/{isin}",
        ]
    if issuer == "ishares":
        return [
            "https://www.ishares.com/uk/individual/en/products/etf-investments"
            f"?search={isin}"
        ]
    if issuer == "xtrackers":
        return [f"https://etf.dws.com/en-gb/search-results/?q={isin}"]
    if issuer == "invesco":
        return []
    if issuer == "vaneck":
        return [f"https://www.vaneck.com/uk/en/search/?query={isin}"]
    if issuer == "spdr":
        return [f"https://www.ssga.com/uk/en_gb/intermediary/search?q={isin}"]
    if issuer == "bnp":
        return [
            "https://www.bnpparibas-am.com/en-offshore/fundsheet/equity/"
            f"{isin.casefold()}/",
        ]
    if issuer == "ubs":
        return [f"https://www.ubs.com/uk/en/assetmanagement/funds/etf.html?#search%3D{isin}"]
    if issuer == "wisdomtree":
        return [f"https://www.wisdomtree.eu/en-gb/search?query={isin}"]
    if issuer == "jpmorgan":
        return [f"https://am.jpmorgan.com/ch/en/asset-management/adv/search-results?query={isin}"]
    if issuer == "legal_general":
        return [f"https://fundcentres.lgim.com/en/uk/institutional/fund-centre/?isin={isin}"]
    if issuer == "franklin":
        return [f"https://www.franklintempleton.co.uk/search?query={isin}"]
    if issuer == "hsbc":
        return [f"https://www.assetmanagement.hsbc.co.uk/en/institutional-investor/funds?search={isin}"]
    if issuer == "fidelity":
        return [f"https://www.fidelityinternational.com/funds/search-results/?query={isin}"]
    if issuer == "first_trust":
        return [f"https://www.ftglobalportfolios.com/uk/Home/Search?search={isin}"]
    if issuer == "global_x":
        return [f"https://globalxetfs.eu/funds/?search={isin}"]
    return []


def _text(soup: BeautifulSoup) -> str:
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))


def _field(text: str, labels: tuple[str, ...]) -> str:
    alternatives = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?:{alternatives})\s*(?::|–|-)?\s*([^|]{{3,180}}?)"
        rf"(?=\s+(?:ISIN|Benchmark|Reference Index|Replication|Product Structure|$))",
        text,
        flags=re.IGNORECASE,
    )
    return canonical_index_name(match.group(1)) if match else ""


def _find_product_link(soup: BeautifulSoup, base_url: str, isin: str) -> str:
    for anchor in soup.find_all("a", href=True):
        haystack = f"{anchor.get_text(' ', strip=True)} {anchor['href']}".casefold()
        if isin.casefold() in haystack and any(
            marker in haystack for marker in ("product", "fund", "etf", "invest")
        ):
            return urljoin(base_url, anchor["href"])
    return ""


def _parse_holdings_table(soup: BeautifulSoup) -> list[dict]:
    """Lit seulement une table officielle contenant poids ET identifiant titre."""
    holdings: list[dict] = []
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        headers = [cell.get_text(" ", strip=True).casefold() for cell in rows[0].find_all(["th", "td"])]
        weight_col = next(
            (i for i, value in enumerate(headers) if "weight" in value or "poids" in value),
            None,
        )
        ticker_col = next(
            (i for i, value in enumerate(headers) if "ticker" in value or "symbol" in value),
            None,
        )
        isin_col = next((i for i, value in enumerate(headers) if value == "isin"), None)
        name_col = next(
            (i for i, value in enumerate(headers) if value in {"name", "nom", "company name"}),
            None,
        )
        if weight_col is None or (ticker_col is None and isin_col is None):
            continue
        for row in rows[1:]:
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
            if weight_col >= len(cells):
                continue
            raw_weight = cells[weight_col].replace("%", "").replace(",", ".")
            try:
                weight = float(raw_weight) / 100.0
            except ValueError:
                continue
            ticker = cells[ticker_col].strip().upper() if ticker_col is not None and ticker_col < len(cells) else ""
            isin = cells[isin_col].strip().upper() if isin_col is not None and isin_col < len(cells) else ""
            name = cells[name_col].strip() if name_col is not None and name_col < len(cells) else ticker or isin
            if weight > 0 and (ticker or isin):
                holdings.append({"ticker": ticker, "isin": isin, "name": name, "weight": weight})
        if holdings:
            break
    return holdings


def _holdings_from_frame(frame: pd.DataFrame) -> list[dict]:
    """Trouve la ligne d'en-tête dans les exports CSV/XLSX des émetteurs."""
    if frame.empty:
        return []
    header_row = None
    for index in range(min(len(frame), 30)):
        values = [str(value).strip().casefold() for value in frame.iloc[index].tolist()]
        has_weight = any(
            "weight" in value or "poids" in value or "percent of fund" in value
            or "net assets" in value
            for value in values
        )
        has_id = any(value == "isin" or "ticker" in value or "symbol" in value for value in values)
        if has_weight and has_id:
            header_row = index
            break
    if header_row is None:
        return []
    data = frame.iloc[header_row + 1:].copy()
    data.columns = [str(value).strip() for value in frame.iloc[header_row].tolist()]
    columns = {str(column).casefold(): column for column in data.columns}
    weight_col = next((
        column for key, column in columns.items()
        if "weight" in key or "poids" in key or "percent of fund" in key
        or "net assets" in key
    ), None)
    ticker_col = next((column for key, column in columns.items() if "ticker" in key or "symbol" in key), None)
    isin_col = next((column for key, column in columns.items() if key in {"isin", "identifier"}), None)
    name_col = next((
        column for key, column in columns.items()
        if key in {"name", "nom", "company name", "security name", "securityname"}
    ), None)
    country_col = next((column for key, column in columns.items() if "country" in key or "pays" in key), None)
    sector_col = next((column for key, column in columns.items() if "sector" in key or "secteur" in key or "industry" in key), None)
    asset_col = next((column for key, column in columns.items() if "asset class" in key or "classe d'actif" in key), None)
    type_col = next((column for key, column in columns.items() if "security type" in key or "instrument type" in key or key == "type"), None)
    rating_col = next((column for key, column in columns.items() if "rating" in key or "credit quality" in key), None)
    maturity_col = next((column for key, column in columns.items() if "maturity" in key or "echeance" in key or "échéance" in key), None)
    duration_col = next((column for key, column in columns.items() if "duration" in key), None)
    if weight_col is None or (ticker_col is None and isin_col is None):
        return []
    numeric_weights = pd.to_numeric(
        data[weight_col].astype(str).str.replace("%", "", regex=False)
        .str.replace(",", ".", regex=False).str.strip(), errors="coerce",
    )
    finite_weights = numeric_weights[numeric_weights.map(lambda value: math.isfinite(value))]
    # L'unité appartient à la colonne entière, jamais à chaque ligne : sinon
    # une position de 0,2 % devenait 20 % à côté d'une position de 8 %.
    percent_weights = (
        "%" in str(weight_col) or "percent" in str(weight_col).casefold()
        or str(weight_col).casefold() == "weighting"
        or finite_weights.abs().sum() > 1.5
    )

    def text_cell(value) -> str:
        return "" if pd.isna(value) else str(value).strip()

    holdings: list[dict] = []
    for _, row in data.iterrows():
        raw = str(row.get(weight_col, "")).replace("%", "").replace(",", ".").strip()
        try:
            weight = float(raw)
        except ValueError:
            continue
        if not math.isfinite(weight):
            continue
        if percent_weights:
            weight /= 100.0
        ticker = text_cell(row.get(ticker_col, "") if ticker_col else "").upper()
        isin = text_cell(row.get(isin_col, "") if isin_col else "").upper()
        ticker = re.sub(r"\.0$", "", ticker)
        if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", isin):
            isin = ""
        name = text_cell(row.get(name_col, "") if name_col else ticker or isin)
        if weight > 0 and (ticker or isin):
            holding = {
                "ticker": ticker,
                "isin": isin,
                "name": name,
                "weight": weight,
                "country": str(row.get(country_col, "") if country_col else "").strip(),
                "sector": str(row.get(sector_col, "") if sector_col else "").strip(),
                "asset_class": str(row.get(asset_col, "") if asset_col else "").strip(),
                "security_type": str(row.get(type_col, "") if type_col else "").strip(),
                "rating": str(row.get(rating_col, "") if rating_col else "").strip(),
                "maturity": str(row.get(maturity_col, "") if maturity_col else "").strip(),
                "duration": str(row.get(duration_col, "") if duration_col else "").strip(),
            }
            holdings.append({
                key: value
                for key, value in holding.items()
                if key in {"ticker", "isin", "name", "weight", "country", "sector"} or value
            })
    return holdings


def _download_table(http: httpx.Client, url: str) -> list[dict]:
    response = http.get(url)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").casefold()
    legacy_excel = response.content.startswith(b"\xd0\xcf\x11\xe0")
    if legacy_excel or response.content.startswith(b"PK\x03\x04") or "spreadsheet" in content_type or "ms-excel" in content_type or url.casefold().endswith((".xlsx", ".xls")):
        frames = pd.read_excel(
            io.BytesIO(response.content), sheet_name=None, header=None,
            engine="calamine" if legacy_excel else "openpyxl",
        )
        return next((parsed for frame in frames.values() if (parsed := _holdings_from_frame(frame))), [])
    # sep=None accepte les exports virgule/point-virgule/tabulation.
    frame = pd.read_csv(
        io.BytesIO(response.content), header=None, sep=None, engine="python",
        encoding_errors="replace",
    )
    return _holdings_from_frame(frame)


def _download_holdings_links(
    soup: BeautifulSoup,
    base_url: str,
    http: httpx.Client,
) -> tuple[tuple[list[dict], str], tuple[list[dict], str]]:
    """Renvoie (composition indice, positions fonds), sans confondre les deux."""
    index_result: tuple[list[dict], str] = ([], "")
    fund_result: tuple[list[dict], str] = ([], "")
    for anchor in soup.find_all("a", href=True):
        label = f"{anchor.get_text(' ', strip=True)} {anchor.get('title', '')}".casefold()
        href = urljoin(base_url, anchor["href"])
        if not any(marker in label for marker in ("holding", "constituent", "composition")):
            continue
        if href.casefold().endswith(".pdf"):
            continue
        try:
            parsed = _download_table(http, href)
        except (httpx.HTTPError, ValueError, OSError, pd.errors.ParserError):
            continue
        coverage = sum(item["weight"] for item in parsed)
        if coverage < 0.90:
            continue
        # « Fund constituents » désigne les positions du fonds, pas celles de
        # l'indice. Le mot constituents seul ne prouve jamais une exposition
        # indicielle (particulièrement dangereux pour les ETF synthétiques).
        if re.search(r"\b(?:index|indice|benchmark)\b", label):
            index_result = (parsed, href)
            break
        if not fund_result[0]:
            fund_result = (parsed, href)
    return index_result, fund_result


def _data_point(container: dict, name: str):
    return (
        (container.get("dataPointsByNameMap") or {}).get(name, {}) or {}
    ).get("value")


def _ishares_product_data(http: httpx.Client, product_id: str, component: str) -> dict:
    response = http.get(_ISHARES_PRODUCT_DATA, params={
        "appSubType": "ISHARES",
        "appType": "PRODUCT_PAGE",
        "component": component,
        "locale": "en_GB",
        "portfolioId": product_id,
        "targetSite": "ishares-uk",
        "userType": "individual",
        "excludeContent": "true",
    })
    response.raise_for_status()
    return response.json()


def _ishares_management_fee(http: httpx.Client, product_id: str) -> float | None:
    """Lit le TER dans la factsheet officielle BlackRock liée par iShares."""
    try:
        header = _ishares_product_data(http, product_id, "fundHeader")
    except (httpx.HTTPError, ValueError, TypeError):
        return None

    documents: list[dict] = []

    def collect(value) -> None:
        if isinstance(value, dict):
            if value.get("url") and value.get("label"):
                documents.append(value)
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(header)
    ordered = sorted(
        documents,
        key=lambda item: (
            "fact" not in str(item.get("label") or "").casefold(),
            "kiid" not in str(item.get("label") or "").casefold()
            and "kid" not in str(item.get("label") or "").casefold(),
        ),
    )
    for document in ordered:
        relative = str(document.get("url") or "").lstrip("/")
        if not relative.casefold().endswith(".pdf"):
            continue
        relative = re.sub(r"^documents/", "", relative, flags=re.IGNORECASE)
        url = f"https://www.blackrock.com/uk/literature/{relative}"
        try:
            response = http.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            continue
        if not response.content.startswith(b"%PDF"):
            continue
        fee = _fee_from_text(_pdf_text(response.content))
        if fee is not None:
            return fee
    return None


def _fetch_ishares_page(http: httpx.Client, match: dict, isin: str) -> dict | None:
    """Repli officiel pour les fonds d'un catalogue local non exposé par l'API UK."""
    product_path = str(match.get("url") or "")
    # Le moteur renvoie un identifiant interne (/ishares-ch/...) alors que la
    # route publique correspondante est /ch/...
    product_path = re.sub(r"^/ishares-([a-z]{2})/", r"/\1/", product_path)
    product_path = product_path.replace("/institutional/en/", "/professionals/en/")
    if re.search(r"/products/\d+/$", product_path):
        # iShares exige un segment SEO, mais sa valeur n'est pas utilisée pour
        # la résolution : l'identifiant numérique fait foi.
        product_path += "x"
    product_url = urljoin("https://www.ishares.com", product_path)
    if not product_url:
        return None
    response = http.get(product_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    if isin.casefold() not in _text(soup).casefold():
        return None

    def fact(column_class: str) -> str:
        item = soup.select_one(f".product-data-item.{column_class}")
        data = item.select_one(".data") if item else None
        return data.get_text(" ", strip=True) if data else ""

    holdings: list[dict] = []
    ajax = soup.select_one("#allHoldingsTab[data-ajaxuri]")
    if ajax is not None:
        holdings_response = http.get(urljoin(str(response.url), str(ajax.get("data-ajaxuri") or "")))
        holdings_response.raise_for_status()
        for row in (holdings_response.json() or {}).get("aaData") or []:
            if len(row) < 11:
                continue
            asset_class = str(row[3] or "").strip()
            if asset_class.casefold() in {"cash", "currency", "derivative"}:
                continue
            raw_weight = row[5].get("raw") if isinstance(row[5], dict) else row[5]
            try:
                weight = float(raw_weight) / 100.0
            except (TypeError, ValueError):
                continue
            child_isin = str(row[8] or "").strip().upper()
            ticker = str(row[0] or "").strip().upper()
            if weight <= 0 or not (ticker or child_isin):
                continue
            holdings.append({
                "ticker": ticker,
                "isin": "" if child_isin == "-" else child_isin,
                "name": str(row[1] or ticker or child_isin).strip(),
                "weight": weight,
                "country": str(row[10] or "").strip(),
                "sector": str(row[2] or "").strip(),
                "asset_class": asset_class,
            })
    return {
        "product_id": str(match.get("portfolioId") or ""),
        "url": str(response.url),
        "index_name": canonical_index_name(fact("col-indexSeriesName")),
        "replication": replication_method(fact("col-productStructure")),
        "holdings": holdings,
        "asset_classes": [fact("col-assetClass")],
        "management_fee_rate": (
            _fee_from_text(_text(soup))
            or _ishares_management_fee(
                http, str(match.get("portfolioId") or "")
            )
        ),
    }


def _fetch_ishares(
    http: httpx.Client,
    isin: str,
    *,
    ticker: str = "",
    fund_name: str = "",
) -> dict | None:
    """API officielle utilisée par le moteur de recherche iShares UK."""
    match = None
    page_match = None
    facts: dict = {}
    for site, locale, user_type in (
        ("ishares-uk", "en-gb", "individual"),
        ("ishares-ch", "en-ch", "individual"),
        ("ishares-ch", "en-ch", "institutional"),
        ("ishares-de", "de-de", "individual"),
        ("ishares-nl", "nl-nl", "individual"),
    ):
        for query in (isin, ticker, fund_name):
            if not str(query).strip():
                continue
            response = http.get(_ISHARES_SEARCH, params={
                "site": site, "locale": locale, "rows": "10",
                "userType": user_type, "query": str(query).strip(),
            })
            response.raise_for_status()
            matches = response.json().get("results") or []
            for candidate in matches:
                if (
                    str(candidate.get("portfolioType")) != "ISHARES_FUND_DATA"
                    or not candidate.get("portfolioId")
                ):
                    continue
                if str(query).strip().upper() == isin.upper() and page_match is None:
                    page_match = candidate
                try:
                    candidate_facts = _ishares_product_data(
                        http, str(candidate["portfolioId"]), "keyFundFacts",
                    )
                except httpx.HTTPError:
                    continue
                component = (
                    (candidate_facts.get("componentsByNameMap") or {})
                    .get("keyFundFacts", {})
                )
                container = (component.get("containersByNameMap") or {}).get("default", {})
                returned_isin = str(_data_point(container, "isin") or "").upper()
                if returned_isin == isin.upper():
                    match, facts = candidate, candidate_facts
                    break
            if match:
                break
        if match:
            break
        if page_match:
            return _fetch_ishares_page(http, page_match, isin)
    if not match and page_match:
        return _fetch_ishares_page(http, page_match, isin)
    if not match or not match.get("portfolioId") or not facts:
        return None
    product_id = str(match["portfolioId"])
    facts_component = (facts.get("componentsByNameMap") or {}).get("keyFundFacts", {})
    facts_container = (facts_component.get("containersByNameMap") or {}).get("default", {})
    index_name = canonical_index_name(_data_point(facts_container, "indexSeriesName"))
    management_fee = next(
        (
            rate
            for name in (
                "ongoingCharge", "ongoingCharges", "totalExpenseRatio",
                "expenseRatio", "managementFee",
            )
            if (rate := _fee_rate(_data_point(facts_container, name))) is not None
        ),
        None,
    )
    if management_fee is None:
        management_fee = _ishares_management_fee(http, product_id)
    replication = replication_method(
        " ".join(str(value or "") for value in (
            _data_point(facts_container, "productStructure"),
            _data_point(facts_container, "fundMethodologyTypeCode"),
        ))
    )
    holdings_payload = _ishares_product_data(http, product_id, "holdings")
    holdings_component = (holdings_payload.get("componentsByNameMap") or {}).get("holdings", {})
    container = (holdings_component.get("containersByNameMap") or {}).get("all", {})
    points = container.get("dataPointsByNameMap") or {}

    def values(name: str) -> list:
        value = (points.get(name) or {}).get("value") or []
        return value if isinstance(value, list) else []

    tickers = values("ticker")
    names = values("issueName")
    isins = values("isin")
    weights = values("holdingPercent")
    countries = values("countryOfRisk")
    sectors = values("sectorName")
    asset_classes = values("assetClass")
    security_types = values("securityType")
    ratings = values("rating") or values("creditRating")
    maturities = values("maturity") or values("maturityDate")
    durations = values("effectiveDuration") or values("duration")
    length = max(map(len, (tickers, names, isins, weights)), default=0)
    holdings: list[dict] = []
    for index in range(length):
        asset_class = str(asset_classes[index] if index < len(asset_classes) else "")
        if asset_class.casefold() in {"cash", "currency", "derivative"}:
            continue
        try:
            weight = float(weights[index]) / 100.0
        except (IndexError, TypeError, ValueError):
            continue
        ticker = str(tickers[index] if index < len(tickers) else "").strip().upper()
        child_isin = str(isins[index] if index < len(isins) else "").strip().upper()
        if weight <= 0 or not (ticker or child_isin):
            continue
        holdings.append({
            "ticker": ticker,
            "isin": "" if child_isin == "-" else child_isin,
            "name": str(names[index] if index < len(names) else ticker or child_isin).strip(),
            "weight": weight,
            "country": str(countries[index] if index < len(countries) else "").strip(),
            "sector": str(sectors[index] if index < len(sectors) else "").strip(),
            "asset_class": asset_class,
            "security_type": str(
                security_types[index] if index < len(security_types) else ""
            ).strip(),
            "rating": str(ratings[index] if index < len(ratings) else "").strip(),
            "maturity": str(maturities[index] if index < len(maturities) else "").strip(),
            "duration": str(durations[index] if index < len(durations) else "").strip(),
        })
    return {
        "product_id": product_id,
        "url": f"https://www.ishares.com/uk/individual/en/products/{product_id}/",
        "index_name": index_name,
        "replication": replication,
        "holdings": holdings,
        "asset_classes": list(match.get("assetClass") or []),
        "management_fee_rate": management_fee,
    }


def _status_record(*, status: str, url: str = "", error: str = "", coverage: float = 0.0) -> dict:
    return {
        "status": status,
        "source_url": url,
        "last_attempt_at": dt.date.today().isoformat(),
        "error": error[:500],
        "coverage": round(max(0.0, min(float(coverage), 1.0)), 6),
    }


def _attempt_due(record: dict, force: bool) -> bool:
    if force:
        return True
    enrichment = record.get("official_enrichment") or {}
    status = str(enrichment.get("status") or "")
    revision = _CONNECTOR_REVISIONS.get(_issuer(str(record.get("name") or "")), 0)
    if revision and status not in {"complete", "aggregate_complete", "non_equity"} and int(enrichment.get("connector_revision") or 0) < revision:
        return True
    # Dès qu'un ISIN absent lors d'une tentative précédente a été réparé depuis
    # un catalogue broker, la cause de l'échec a disparu. Ne pas conserver le
    # délai de retry de l'ancien statut, sinon la réplication resterait inconnue
    # plusieurs jours malgré une identité désormais exploitable.
    if status == "missing_catalog_isin" and valid_isin(record.get("isin")):
        return True
    # Un TER absent n'invalide pas une tentative récente : certains émetteurs
    # ne le publient pas sur la source utilisée. Le prochain rafraîchissement
    # normal pourra le compléter sans recommencer à chaque optimisation.
    # Un connecteur ajouté après une première analyse doit pouvoir reprendre
    # immédiatement les anciennes entrées ``unsupported_issuer``. Les vraies
    # références inconnues restent, elles, soumises au délai normal.
    if (
        status == "unsupported_issuer"
        and _issuer(str(record.get("name") or ""))
    ):
        return True
    try:
        attempted = dt.date.fromisoformat(str(enrichment.get("last_attempt_at", ""))[:10])
    except ValueError:
        return True
    temporary = status in {"temporary_error", "http_error", "parse_error"}
    refresh_days = (
        31 if status == "complete"
        else _TEMPORARY_RETRY_DAYS if temporary
        else _RETRY_DAYS
    )
    return (dt.date.today() - attempted).days >= refresh_days


def _enrich_official_etfs_serial(
    tickers: list[str] | set[str],
    *,
    broker_table=None,
    path=None,
    force: bool = False,
    client: httpx.Client | None = None,
    progress_cb=None,
    should_stop=None,
    _merge_persist: bool = False,
    _resolved: dict[str, dict] | None = None,
    budget=None,
) -> dict[str, dict]:
    """Résout et met en cache les ETF demandés pendant la préparation du run.

    Le téléchargement est fait une fois par ISIN. Pour un ETF physique, une
    table complète de positions publiée par l'émetteur constitue une exposition
    économique recevable. Pour un ETF synthétique, elle ne l'est jamais : il
    faut une composition officielle de l'indice, qui reste alors ``licensed`` ou
    ``unavailable`` tant qu'un connecteur fournisseur n'est pas disponible.
    """
    from .etf_index_registry import resolve_index_registry

    wanted = sorted({str(value).strip().upper() for value in tickers if str(value).strip()})
    resolved = _resolved or resolve_index_registry(
        wanted,
        broker_table=broker_table,
        path=path,
        persist=not _merge_persist,
    )
    # La file réseau porte sur les FONDS (ISIN), pas sur leurs cotations Yahoo.
    # On conserve un représentant et on propage ensuite son statut aux alias.
    representative_by_identity: dict[str, str] = {}
    aliases_by_identity: dict[str, list[str]] = {}
    for ticker in wanted:
        meta = resolved.get(ticker, {})
        identity = str(meta.get("identity_key") or f"TICKER:{ticker}")
        representative_by_identity.setdefault(identity, ticker)
        aliases_by_identity.setdefault(identity, []).append(ticker)
    worklist = sorted(representative_by_identity.values())
    registry = load_registry(path)
    owns_client = client is None
    http = client or httpx.Client(
        timeout=_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": _USER_AGENT, "Accept-Language": "en-GB,en;q=0.8"},
    )
    results: dict[str, dict] = {}
    from .etf_research_budget import BudgetClient, ResearchBudgetExceeded
    if budget is not None:
        http = BudgetClient(http, budget)
    processed_identities: set[str] = set()
    completed = 0
    try:
        for position, ticker in enumerate(worklist, start=1):
            if should_stop is not None and should_stop():
                # Chaque fonds traité est déjà dans ``registry``. Sauvegarder
                # immédiatement rend l'inventaire reprenable sans perdre le
                # travail accompli avant le clic Arrêt.
                if _merge_persist:
                    touched_funds = set(aliases_by_identity)
                    touched_indices = {
                        str(registry["funds"].get(identity, {}).get("index_id") or "")
                        for identity in touched_funds
                    } - {""}
                    merge_registry_records(
                        registry,
                        fund_ids=touched_funds,
                        index_ids=touched_indices,
                        path=path,
                    )
                else:
                    save_registry(registry, path)
                break
            completed = position
            # Une longue passe peut durer plusieurs dizaines de minutes. Un
            # checkpoint régulier évite de perdre tous les enrichissements si
            # le serveur est redémarré avant la fin.
            # Le registre réel fait plusieurs dizaines de Mo : un checkpoint
            # trop fréquent déplacerait le goulot d'étranglement vers le disque.
            if not _merge_persist and position > 1 and (position - 1) % 500 == 0:
                save_registry(registry, path)
            if progress_cb is not None:
                progress_cb(position - 1, len(worklist), ticker)
            meta = resolved.get(ticker, {})
            identity = str(meta.get("identity_key") or f"TICKER:{ticker}")
            fund = registry["funds"].setdefault(identity, dict(meta))
            # Plusieurs places de cotation peuvent partager le même ISIN. La
            # première résout le fonds; les alias réutilisent immédiatement le
            # résultat au lieu de rappeler deux fois la même page officielle.
            if identity in processed_identities:
                results[ticker] = dict(fund.get("official_enrichment") or {})
                continue
            processed_identities.add(identity)
            # Une composition appartient à l'INDICE, pas à l'ETF qui nous l'a
            # fournie. Ex. une seule source officielle CAC 40 dessert ensuite
            # Amundi, iShares, Xtrackers, BNP... sans nouvelle requête réseau.
            index_id = str(fund.get("index_id") or "")
            shared = cached_index_composition(index_id, path=path, registry=registry) if index_id else None
            if (
                index_id
                and shared
                and shared.get("holdings")
                and str(shared.get("source") or "") in OFFICIAL_INDEX_COMPOSITION_SOURCES
                and fund.get("management_fee_checked_at")
            ):
                status = _status_record(
                    status="complete_shared_index",
                    url=str(shared.get("source_url") or ""),
                    coverage=float(shared.get("coverage") or 0.0),
                )
                status["shared_index_id"] = index_id
                fund["official_enrichment"] = status
                results[ticker] = status
                continue
            if not _attempt_due(fund, force):
                results[ticker] = dict(fund.get("official_enrichment") or {})
                continue
            isin = str(fund.get("isin") or "")
            issuer = _issuer(str(fund.get("name") or ""))
            if not isin:
                status = _status_record(
                    status="missing_catalog_isin",
                    error="ISIN absent du catalogue broker; résolution officielle impossible",
                )
                fund["official_enrichment"] = status
                results[ticker] = status
                continue
            if not issuer:
                status = _status_record(
                    status="unsupported_issuer",
                    error="Émetteur officiel non reconnu ou instrument mal référencé",
                )
                fund["official_enrichment"] = status
                results[ticker] = status
                continue

            if budget is not None and not budget.claim("fund", identity):
                continue

            if issuer in {"bnp", "ubs", "jpmorgan", "global_x", "franklin", "hsbc"}:
                connector_error = ""
                try:
                    if issuer == "hsbc":
                        official = _fetch_hsbc(http, isin)
                    elif issuer == "bnp":
                        official = _fetch_bnp_replication(http, isin)
                    elif issuer == "ubs":
                        official = _fetch_ubs_replication(
                            http,
                            isin,
                            fund_name=str(fund.get("name") or ""),
                        )
                    elif issuer == "jpmorgan":
                        official = _fetch_jpmorgan(
                            http,
                            isin,
                            fund_name=str(fund.get("name") or ""),
                        )
                    elif issuer == "global_x":
                        official = _fetch_global_x(http, isin)
                    else:
                        official = _fetch_franklin(http, isin)
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    connector_error = f"{type(exc).__name__}: {exc}"
                    official = None
                if official:
                    _apply_official_fee(fund, official)
                    method = str(official.get("replication") or "unknown")
                    if method != "unknown":
                        fund["replication"] = method
                        fund["source"] = (
                            "issuer_range" if issuer in {"bnp", "ubs"}
                            else "issuer_product_page" if issuer in {"global_x", "franklin"}
                            else "issuer_factsheet"
                        )
                        fund["confidence"] = "high"
                        fund["verified_at"] = dt.date.today().isoformat()
                        exact_index = str(official.get("index_name") or "")
                        if exact_index:
                            fund["index_name"] = exact_index
                            fund["index_id"] = canonical_index_id(exact_index)
                            registry["indices"].setdefault(
                                fund["index_id"],
                                {"name": exact_index, "funds": []},
                            )
                            index_record = registry["indices"].setdefault(
                                fund["index_id"], {"name": exact_index, "funds": []}
                            )
                            provider_index_id = str(
                                official.get("provider_index_id") or ""
                            )
                            if provider_index_id:
                                fund["provider_index_id"] = provider_index_id
                                index_record["provider_index_id"] = provider_index_id
                            if issuer == "bnp":
                                index_record["provider"] = "bnp"
                        index_holdings = list(official.get("index_holdings") or [])
                        fund_holdings = list(official.get("holdings") or [])
                        if exact_index and index_holdings:
                            index_record = registry["indices"].setdefault(
                                fund["index_id"],
                                {"name": exact_index, "funds": []},
                            )
                            index_record["composition"] = {
                                "holdings": index_holdings,
                                "source": "issuer_index_constituents",
                                "source_url": str(
                                    official.get("index_holdings_url")
                                    or official.get("url")
                                    or ""
                                ),
                                "provider": "issuer",
                                "as_of": dt.date.today().isoformat(),
                                "fetched_at": dt.date.today().isoformat(),
                                "updated_at": dt.date.today().isoformat(),
                                "coverage": min(sum(
                                    float(item["weight"])
                                    for item in index_holdings
                                ), 1.0),
                                "partial": sum(
                                    float(item["weight"])
                                    for item in index_holdings
                                ) < 0.90,
                            }
                        elif method == "physical" and fund_holdings:
                            coverage = min(
                                sum(float(item["weight"]) for item in fund_holdings),
                                1.0,
                            )
                            fund["composition"] = {
                                "holdings": fund_holdings,
                                "source": "issuer_fund_holdings",
                                "source_url": str(
                                    official.get("holdings_url")
                                    or official.get("url")
                                    or ""
                                ),
                                "updated_at": dt.date.today().isoformat(),
                                "coverage": coverage,
                                "partial": coverage < 0.90,
                            }
                        aggregate = dict(official.get("aggregate_exposure") or {})
                        if aggregate:
                            fund["aggregate_exposure"] = {
                                **aggregate,
                                "source": "issuer_official_aggregate_exposure",
                                "source_url": str(official.get("url") or ""),
                                "updated_at": dt.date.today().isoformat(),
                            }
                        aggregate_complete = (
                            float(aggregate.get("country_coverage") or 0.0) >= 0.90
                            and float(aggregate.get("sector_coverage") or 0.0) >= 0.90
                        )
                        status = _status_record(
                            status=(
                                "complete" if sum(float(item["weight"]) for item in index_holdings) >= 0.90
                                or (method == "physical" and sum(float(item["weight"]) for item in fund_holdings) >= 0.90)
                                else "partial" if index_holdings or (method == "physical" and fund_holdings)
                                else "aggregate_complete" if aggregate_complete
                                else "metadata_complete"
                            ),
                            url=str(official.get("url") or ""),
                            coverage=min(sum(
                                float(item["weight"])
                                for item in (index_holdings or fund_holdings)
                            ), 1.0) if (index_holdings or fund_holdings) else min(
                                float(aggregate.get("country_coverage") or 0.0),
                                float(aggregate.get("sector_coverage") or 0.0),
                            ),
                        )
                        fund["official_enrichment"] = status
                        results[ticker] = status
                        continue
                    status = _status_record(
                        status="unavailable",
                        url=str(official.get("url") or ""),
                        error="Fiche officielle trouvée, méthode de réplication non publiée",
                    )
                else:
                    status = _status_record(
                        status="temporary_error",
                        error=connector_error or "Connecteur officiel sans fiche correspondant à cet ISIN",
                    )
                # Ces connecteurs ont déjà consulté leur annuaire et, selon
                # l'émetteur, leur fiche produit. Le repli générique pointerait
                # vers la même URL ou vers une recherche JS/404 et doublait les
                # requêtes sans apporter d'information supplémentaire.
                fund["official_enrichment"] = status
                results[ticker] = status
                continue

            if issuer == "ishares":
                try:
                    official = _fetch_ishares(
                        http, isin, ticker=ticker, fund_name=str(fund.get("name") or ""),
                    )
                except (httpx.HTTPError, ValueError, TypeError):
                    official = None
                if official:
                    _apply_official_fee(fund, official)
                    asset_class = str(official.get("asset_class") or "").strip()
                    if asset_class:
                        fund["asset_class"] = asset_class
                    exact_index = str(official.get("index_name") or "")
                    if exact_index:
                        fund["index_name"] = exact_index
                        fund["index_id"] = canonical_index_id(exact_index)
                        fund["source"] = "issuer_product_api"
                        fund["confidence"] = "high"
                        fund["verified_at"] = dt.date.today().isoformat()
                    method = str(official.get("replication") or "unknown")
                    if method != "unknown":
                        fund["replication"] = method
                    holdings = list(official.get("holdings") or [])
                    coverage = min(sum(float(item["weight"]) for item in holdings), 1.0)
                    if not any(
                        str(value).casefold() == "equity"
                        for value in official.get("asset_classes") or []
                    ):
                        if method == "physical" and holdings:
                            fund["composition"] = {
                                "holdings": holdings,
                                "source": "issuer_fund_holdings",
                                "source_url": official["url"],
                                "updated_at": dt.date.today().isoformat(),
                                "coverage": coverage,
                                "partial": coverage < 0.90,
                                "asset_class": "fixed_income",
                            }
                        status = _status_record(
                            status="non_equity", url=official["url"], coverage=coverage,
                        )
                        status["product_id"] = official["product_id"]
                        fund["official_enrichment"] = status
                        results[ticker] = status
                        continue
                    if method == "physical" and coverage >= 0.90:
                        fund["composition"] = {
                            "holdings": holdings,
                            "source": "issuer_fund_holdings",
                            "source_url": official["url"],
                            "updated_at": dt.date.today().isoformat(),
                            "coverage": coverage,
                            "partial": False,
                        }
                        status = _status_record(
                            status="complete", url=official["url"], coverage=coverage,
                        )
                        status["product_id"] = official["product_id"]
                        fund["official_enrichment"] = status
                        results[ticker] = status
                        continue
                    if method == "synthetic":
                        status = _status_record(
                            status="index_constituents_required", url=official["url"],
                            coverage=0.0,
                            error="Le panier iShares est du collatéral; composition de l'indice requise",
                        )
                        status["product_id"] = official["product_id"]
                        fund["official_enrichment"] = status
                        results[ticker] = status
                        continue

            if issuer == "amundi":
                try:
                    official = _fetch_amundi_factsheet(http, isin)
                except (httpx.HTTPError, ValueError, TypeError):
                    official = None
                if official:
                    _apply_official_fee(fund, official)
                    asset_class = str(official.get("asset_class") or "").strip()
                    if asset_class:
                        fund["asset_class"] = asset_class
                    exact_index = str(official.get("index_name") or "")
                    if exact_index:
                        fund["index_name"] = exact_index
                        fund["index_id"] = canonical_index_id(exact_index)
                    fund["source"] = "issuer_factsheet"
                    fund["confidence"] = "high"
                    fund["verified_at"] = dt.date.today().isoformat()
                    method = str(official.get("replication") or "unknown")
                    if method != "unknown":
                        fund["replication"] = method
                    amundi_holdings: dict | None = None
                    try:
                        amundi_holdings = _fetch_amundi_holdings(http, isin)
                    except (httpx.HTTPError, ValueError, TypeError):
                        amundi_holdings = None
                    api_method = str(
                        (amundi_holdings or {}).get("replication") or "unknown"
                    )
                    if api_method != "unknown":
                        method = api_method
                        fund["replication"] = api_method
                    holdings = list((amundi_holdings or {}).get("holdings") or [])
                    if not exact_index:
                        exact_index = canonical_index_name(
                            (amundi_holdings or {}).get("index_name") or ""
                        )
                        if exact_index:
                            fund["index_name"] = exact_index
                            fund["index_id"] = canonical_index_id(exact_index)
                    coverage = min(
                        sum(float(item["weight"]) for item in holdings), 1.0
                    )
                    if holdings and coverage >= 0.90:
                        fund["composition"] = {
                            "holdings": holdings,
                            "source": "issuer_fund_holdings",
                            "source_url": str(amundi_holdings.get("url") or official["url"]),
                            "as_of": str(amundi_holdings.get("as_of") or ""),
                            "updated_at": dt.date.today().isoformat(),
                            "coverage": coverage,
                            "partial": False,
                        }
                    aggregate = dict(official.get("aggregate_exposure") or {})
                    if aggregate:
                        fund["aggregate_exposure"] = {
                            **aggregate,
                            "source": "issuer_official_aggregate_exposure",
                            "source_url": str(official["url"]),
                            "updated_at": dt.date.today().isoformat(),
                        }
                    aggregate_complete = (
                        float(aggregate.get("country_coverage") or 0.0) >= 0.90
                        and float(aggregate.get("sector_coverage") or 0.0) >= 0.90
                    )
                    if official.get("asset_class") == "fixed_income":
                        status = _status_record(
                            status="non_equity", url=str(official["url"]), coverage=1.0,
                        )
                    elif holdings and coverage >= 0.90:
                        status = _status_record(
                            status="complete",
                            url=str(amundi_holdings.get("url") or official["url"]),
                            coverage=coverage,
                        )
                    elif aggregate_complete:
                        status = _status_record(
                            status="aggregate_complete",
                            url=str(official["url"]),
                            coverage=min(
                                float(aggregate.get("country_coverage") or 0.0),
                                float(aggregate.get("sector_coverage") or 0.0),
                            ),
                        )
                    elif method == "synthetic":
                        status = _status_record(
                            status="index_constituents_required",
                            url=str(official["url"]),
                            error=(
                                "Le panier Amundi est du collatéral; composition "
                                "officielle de l'indice requise"
                            ),
                        )
                    else:
                        status = _status_record(
                            status="metadata_complete",
                            url=str(official["url"]),
                            error=(
                                "Indice et réplication vérifiés; positions complètes "
                                "non publiées dans un format officiel exploitable"
                            ),
                        )
                    fund["official_enrichment"] = status
                    results[ticker] = status
                    continue

            if issuer == "vanguard":
                connector_error = ""
                try:
                    official = _fetch_vanguard(
                        http,
                        isin,
                        product_id=str(fund.get("product_id") or ""),
                    )
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    connector_error = f"{type(exc).__name__}: {exc}"
                    official = None
                if official:
                    _apply_official_fee(fund, official)
                    product_id = str(official.get("product_id") or "")
                    if product_id:
                        fund["product_id"] = product_id
                    exact_index = str(official.get("index_name") or "")
                    if exact_index:
                        fund["index_name"] = exact_index
                        fund["index_id"] = canonical_index_id(exact_index)
                    method = str(official.get("replication") or "unknown")
                    if method != "unknown":
                        fund["replication"] = method
                    fund["source"] = "issuer_product_api"
                    fund["confidence"] = "high"
                    fund["verified_at"] = dt.date.today().isoformat()
                    holdings = list(official.get("holdings") or [])
                    coverage = min(
                        sum(float(item["weight"]) for item in holdings), 1.0,
                    )
                    if method == "physical" and coverage >= 0.90:
                        fund["composition"] = {
                            "holdings": holdings,
                            "source": "issuer_fund_holdings",
                            "source_url": str(official["url"]),
                            "updated_at": dt.date.today().isoformat(),
                            "coverage": coverage,
                            "partial": False,
                        }
                        status = _status_record(
                            status="complete",
                            url=str(official["url"]),
                            coverage=coverage,
                        )
                    elif method == "synthetic":
                        status = _status_record(
                            status="index_constituents_required",
                            url=str(official["url"]),
                            error=(
                                "Le panier Vanguard est du collatéral; composition "
                                "officielle de l'indice requise"
                            ),
                        )
                    else:
                        status = _status_record(
                            status="partial",
                            url=str(official["url"]),
                            coverage=coverage,
                            error="Positions Vanguard officielles inférieures à 90 %",
                        )
                    status["product_id"] = product_id
                    status["total_holdings"] = int(
                        official.get("total_holdings") or len(holdings),
                    )
                    fund["official_enrichment"] = status
                    results[ticker] = status
                    continue

                status = _status_record(
                    status="temporary_error" if connector_error else "unavailable",
                    error=connector_error or "ISIN absent de l'annuaire officiel Vanguard Europe",
                )
                fund["official_enrichment"] = status
                results[ticker] = status
                continue

            if issuer == "vaneck":
                official = None
                for _attempt in range(2):
                    try:
                        official = _fetch_vaneck(
                            http, isin, fund_name=str(fund.get("name") or ""),
                        )
                    except (httpx.HTTPError, ValueError, TypeError):
                        continue
                    if official:
                        break
                if official:
                    _apply_official_fee(fund, official)
                    fund["replication"] = "physical"
                    fund["source"] = "issuer_product_api"
                    fund["confidence"] = "high"
                    fund["verified_at"] = dt.date.today().isoformat()
                    asset_classes = {
                        str(value).casefold()
                        for value in official.get("asset_classes") or []
                    }
                    if asset_classes and not asset_classes.intersection({"stock", "equity"}):
                        holdings = list(official.get("holdings") or [])
                        coverage = min(sum(float(item["weight"]) for item in holdings), 1.0)
                        if holdings:
                            fund["composition"] = {
                                "holdings": holdings,
                                "source": "issuer_fund_holdings",
                                "source_url": str(official["dataset_url"]),
                                "updated_at": dt.date.today().isoformat(),
                                "coverage": coverage,
                                "partial": coverage < 0.90,
                                "asset_class": "fixed_income",
                            }
                        status = _status_record(
                            status="non_equity", url=str(official["url"]), coverage=coverage,
                        )
                    else:
                        holdings = list(official.get("holdings") or [])
                        coverage = min(sum(float(item["weight"]) for item in holdings), 1.0)
                        if coverage >= 0.90:
                            fund["composition"] = {
                                "holdings": holdings,
                                "source": "issuer_fund_holdings",
                                "source_url": str(official["dataset_url"]),
                                "updated_at": dt.date.today().isoformat(),
                                "coverage": coverage,
                                "partial": False,
                            }
                            status = _status_record(
                                status="complete",
                                url=str(official["dataset_url"]),
                                coverage=coverage,
                            )
                        else:
                            status = _status_record(
                                status="partial", url=str(official["url"]),
                                coverage=coverage,
                                error="Dataset officiel VanEck inférieur à 90 %",
                            )
                    fund["official_enrichment"] = status
                    results[ticker] = status
                    continue

            if issuer == "kraneshares":
                try:
                    official = _fetch_kraneshares(http, isin, ticker=ticker)
                except (httpx.HTTPError, ValueError, TypeError):
                    official = None
                if official:
                    _apply_official_fee(fund, official)
                    exact_index = str(official.get("index_name") or "")
                    if exact_index:
                        fund["index_name"] = exact_index
                        fund["index_id"] = canonical_index_id(exact_index)
                    fund["replication"] = "physical"
                    fund["source"] = "issuer_product_page"
                    fund["confidence"] = "high"
                    fund["verified_at"] = dt.date.today().isoformat()
                    holdings = list(official.get("holdings") or [])
                    coverage = min(sum(float(item["weight"]) for item in holdings), 1.0)
                    if coverage >= 0.90:
                        fund["composition"] = {
                            "holdings": holdings,
                            "source": "issuer_fund_holdings",
                            "source_url": str(official.get("holdings_url") or official["url"]),
                            "updated_at": dt.date.today().isoformat(),
                            "coverage": coverage,
                            "partial": False,
                        }
                        status = _status_record(
                            status="complete",
                            url=str(official.get("holdings_url") or official["url"]),
                            coverage=coverage,
                        )
                    elif coverage > 0:
                        status = _status_record(
                            status="partial", url=str(official["url"]), coverage=coverage,
                            error="Composition KraneShares inférieure à 90 %",
                        )
                    else:
                        status = _status_record(
                            status="inactive_or_unavailable",
                            url=str(official["url"]),
                            error=(
                                "Aucun CSV officiel récent publié; référence "
                                "potentiellement inactive dans le catalogue broker"
                            ),
                        )
                    fund["official_enrichment"] = status
                    results[ticker] = status
                    continue

            if issuer == "xtrackers":
                try:
                    official = _fetch_xtrackers(http, isin)
                except (httpx.HTTPError, ValueError, TypeError):
                    official = None
                if official:
                    _apply_official_fee(fund, official)
                    exact_index = str(official.get("index_name") or "")
                    if exact_index:
                        fund["index_name"] = exact_index
                        fund["index_id"] = canonical_index_id(exact_index)
                    fund["source"] = "issuer_product_api"
                    fund["confidence"] = "high"
                    fund["verified_at"] = dt.date.today().isoformat()
                    method = str(official.get("replication") or "unknown")
                    if method != "unknown":
                        fund["replication"] = method
                    asset_classes = {
                        str(value).casefold()
                        for value in official.get("asset_classes") or []
                    }
                    if asset_classes and not asset_classes.intersection(
                        {"equities", "equity", "stocks", "stock", "aktien"}
                    ):
                        holdings = list(official.get("holdings") or [])
                        coverage = min(sum(float(item["weight"]) for item in holdings), 1.0)
                        if method == "physical" and holdings:
                            fund["composition"] = {
                                "holdings": holdings,
                                "source": "issuer_fund_holdings",
                                "source_url": str(official["holdings_url"]),
                                "updated_at": dt.date.today().isoformat(),
                                "coverage": coverage,
                                "partial": coverage < 0.90,
                                "asset_class": "fixed_income",
                            }
                        status = _status_record(
                            status="non_equity", url=str(official["url"]), coverage=coverage,
                        )
                    elif method == "synthetic":
                        status = _status_record(
                            status="index_constituents_required",
                            url=str(official["url"]),
                            error=(
                                "Le panier Xtrackers est du collatéral; composition "
                                "officielle de l'indice requise"
                            ),
                        )
                    else:
                        holdings = list(official.get("holdings") or [])
                        coverage = min(sum(float(item["weight"]) for item in holdings), 1.0)
                        if method == "physical" and coverage >= 0.90:
                            fund["composition"] = {
                                "holdings": holdings,
                                "source": "issuer_fund_holdings",
                                "source_url": str(official["holdings_url"]),
                                "updated_at": dt.date.today().isoformat(),
                                "coverage": coverage,
                                "partial": False,
                            }
                            status = _status_record(
                                status="complete",
                                url=str(official["holdings_url"]),
                                coverage=coverage,
                            )
                        else:
                            status = _status_record(
                                status="partial", url=str(official["url"]),
                                coverage=coverage,
                                error="Positions Xtrackers incomplètes ou réplication indéterminée",
                            )
                    fund["official_enrichment"] = status
                    results[ticker] = status
                    continue

            if issuer == "invesco":
                try:
                    official = _fetch_invesco(http, isin)
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    status = _status_record(
                        status="temporary_error",
                        url=f"{_INVESCO_API}/{isin}?idType=isin",
                        error=f"API officielle Invesco: {type(exc).__name__}: {exc}",
                    )
                    fund["official_enrichment"] = status
                    results[ticker] = status
                    continue
                if official is None:
                    status = _status_record(
                        status="inactive_or_unavailable",
                        url=f"{_INVESCO_API}/{isin}?idType=isin",
                        error="ISIN absent du référentiel officiel Invesco",
                    )
                    fund["official_enrichment"] = status
                    results[ticker] = status
                    continue
                if official:
                    _apply_official_fee(fund, official)
                    exact_index = str(official.get("index_name") or "")
                    if exact_index:
                        fund["index_name"] = exact_index
                        fund["index_id"] = canonical_index_id(exact_index)
                    fund["source"] = "issuer_product_api"
                    fund["confidence"] = "high"
                    fund["verified_at"] = dt.date.today().isoformat()
                    method = str(official.get("replication") or "unknown")
                    if method != "unknown":
                        fund["replication"] = method
                    asset_class = str(official.get("asset_class") or "").strip()
                    if asset_class:
                        fund["asset_class"] = asset_class

                    index_holdings = list(official.get("index_holdings") or [])
                    index_coverage = min(
                        sum(float(item["weight"]) for item in index_holdings), 1.0,
                    )
                    if index_coverage >= 0.90 and fund.get("index_id"):
                        store_index_composition(
                            str(fund["index_id"]), index_holdings,
                            source="issuer_index_constituents", reference_ticker=ticker,
                            index_name=str(fund.get("index_name") or ""),
                            source_url=str(official["index_url"]), path=path,
                            registry=registry, persist=False,
                        )

                    asset_key = re.sub(r"[^a-z]", "", asset_class.casefold())
                    non_equity = bool(asset_key) and not any(
                        marker in asset_key for marker in ("equity", "equities", "stock")
                    )
                    fund_holdings = list(official.get("fund_holdings") or [])
                    fund_coverage = min(
                        sum(float(item["weight"]) for item in fund_holdings), 1.0,
                    )
                    if method == "physical" and fund_coverage >= 0.90:
                        fund["composition"] = {
                            "holdings": fund_holdings,
                            "source": "issuer_fund_holdings",
                            "source_url": str(official["fund_url"]),
                            "updated_at": dt.date.today().isoformat(),
                            "coverage": fund_coverage,
                            "partial": False,
                            **({"asset_class": asset_class} if non_equity else {}),
                        }

                    if non_equity:
                        status = _status_record(
                            status="non_equity", url=str(official["url"]),
                            coverage=max(index_coverage, fund_coverage),
                        )
                    elif index_coverage >= 0.90 and fund.get("index_id"):
                        status = _status_record(
                            status="complete", url=str(official["index_url"]),
                            coverage=index_coverage,
                        )
                        status["shared_index_id"] = str(fund["index_id"])
                    elif method == "physical" and fund_coverage >= 0.90:
                        status = _status_record(
                            status="complete", url=str(official["fund_url"]),
                            coverage=fund_coverage,
                        )
                    elif method == "synthetic":
                        status = _status_record(
                            status="index_constituents_required", url=str(official["url"]),
                            error=(
                                "Le panier Invesco est du collatéral; composition "
                                "officielle de l'indice requise"
                            ),
                        )
                    else:
                        status = _status_record(
                            status="metadata_complete", url=str(official["url"]),
                            coverage=max(index_coverage, fund_coverage),
                            error="Métadonnées officielles obtenues; composition complète indisponible",
                        )
                    fund["official_enrichment"] = status
                    results[ticker] = status
                    continue

            if issuer == "spdr":
                try:
                    official = _fetch_spdr(http, isin)
                except (httpx.HTTPError, ValueError, TypeError):
                    official = None
                if official:
                    _apply_official_fee(fund, official)
                    exact_index = str(official.get("index_name") or "")
                    if exact_index:
                        fund["index_name"] = exact_index
                        fund["index_id"] = canonical_index_id(exact_index)
                    fund["source"] = "issuer_product_page"
                    fund["confidence"] = "high"
                    fund["verified_at"] = dt.date.today().isoformat()
                    method = str(official.get("replication") or "unknown")
                    if method != "unknown":
                        fund["replication"] = method
                    holdings = list(official.get("holdings") or [])
                    coverage = min(sum(float(item["weight"]) for item in holdings), 1.0)
                    if method == "physical" and coverage >= 0.90:
                        fund["composition"] = {
                            "holdings": holdings,
                            "source": "issuer_fund_holdings",
                            "source_url": str(official.get("holdings_url") or official["url"]),
                            "updated_at": dt.date.today().isoformat(),
                            "coverage": coverage,
                            "partial": False,
                        }
                        status = _status_record(
                            status="complete",
                            url=str(official.get("holdings_url") or official["url"]),
                            coverage=coverage,
                        )
                    else:
                        status = _status_record(
                            status="partial" if holdings else "unavailable",
                            url=str(official["url"]),
                            coverage=coverage,
                            error="Positions State Street incomplètes ou réplication indéterminée",
                        )
                    fund["official_enrichment"] = status
                    results[ticker] = status
                    continue

            final_url = ""
            soup = None
            error = ""
            for url in _product_urls(issuer, isin):
                try:
                    response = http.get(url)
                    response.raise_for_status()
                    candidate = BeautifulSoup(response.text, "html.parser")
                    product_link = _find_product_link(candidate, str(response.url), isin)
                    if product_link and product_link != str(response.url):
                        response = http.get(product_link)
                        response.raise_for_status()
                        candidate = BeautifulSoup(response.text, "html.parser")
                    if isin.casefold() in _text(candidate).casefold():
                        soup, final_url = candidate, str(response.url)
                        break
                except (httpx.HTTPError, ValueError) as exc:
                    error = str(exc)
            if soup is None:
                status = _status_record(status="temporary_error", url=final_url, error=error or "Page produit officielle introuvable")
                fund["official_enrichment"] = status
                results[ticker] = status
                continue

            page_text = _text(soup)
            aggregate = _official_marginal_exposures(
                soup.get_text("\n", strip=True)
            )
            if aggregate:
                fund["aggregate_exposure"] = {
                    **aggregate,
                    "source": "issuer_official_aggregate_exposure",
                    "source_url": final_url,
                    "updated_at": dt.date.today().isoformat(),
                }
            fund["management_fee_checked_at"] = dt.date.today().isoformat()
            page_fee = _fee_from_text(page_text)
            if page_fee is not None:
                fund["management_fee_rate"] = page_fee
                fund["management_fee_source"] = final_url
            exact_index = _field(page_text, ("Benchmark Index", "Benchmark", "Reference Index", "Underlying Index"))
            if exact_index:
                fund["index_name"] = exact_index
                fund["index_id"] = canonical_index_id(exact_index)
                fund["source"] = "issuer_product_page"
                fund["confidence"] = "high"
                fund["verified_at"] = dt.date.today().isoformat()
            raw_replication = _field(page_text, ("Product Structure", "Replication Method", "Replication"))
            method = replication_method(raw_replication)
            if method != "unknown":
                fund["replication"] = method

            (index_holdings, index_url), (downloaded_fund, fund_url) = (
                _download_holdings_links(soup, final_url, http)
            )
            index_coverage = min(sum(item["weight"] for item in index_holdings), 1.0)
            if index_holdings and index_coverage >= 0.90 and fund.get("index_id"):
                store_index_composition(
                    str(fund["index_id"]), index_holdings,
                    source="issuer_index_constituents", reference_ticker=ticker,
                    index_name=str(fund.get("index_name") or ""),
                    source_url=index_url, path=path, registry=registry, persist=False,
                )
                status = _status_record(status="complete", url=index_url, coverage=index_coverage)
                status["shared_index_id"] = str(fund["index_id"])
                fund["official_enrichment"] = status
                results[ticker] = status
                continue

            holdings = downloaded_fund or _parse_holdings_table(soup)
            coverage = min(sum(item["weight"] for item in holdings), 1.0)
            complete = coverage >= 0.90
            if fund.get("replication") == "physical" and complete and fund.get("index_id"):
                # Des positions de fonds physiques sont économiques, mais ne
                # sont pas nécessairement la composition exacte de l'indice
                # (sampling, liquidités). Elles restent donc attachées à l'ISIN.
                fund["composition"] = {
                    "holdings": holdings,
                    "source": "issuer_fund_holdings",
                    "source_url": fund_url or final_url,
                    "updated_at": dt.date.today().isoformat(),
                    "coverage": coverage,
                    "partial": False,
                }
                status = _status_record(status="complete", url=fund_url or final_url, coverage=coverage)
            elif holdings and not complete:
                status = _status_record(status="partial", url=final_url, coverage=coverage, error="Composition officielle inférieure à 90 %")
            elif (
                float(aggregate.get("country_coverage") or 0.0) >= 0.90
                and float(aggregate.get("sector_coverage") or 0.0) >= 0.90
            ):
                status = _status_record(
                    status="aggregate_complete",
                    url=final_url,
                    coverage=min(
                        float(aggregate.get("country_coverage") or 0.0),
                        float(aggregate.get("sector_coverage") or 0.0),
                    ),
                )
            elif fund.get("replication") == "synthetic":
                status = _status_record(status="index_constituents_required", url=final_url, error="Le panier du fonds est du collatéral; composition officielle de l'indice requise")
            else:
                status = _status_record(status="unavailable", url=final_url, error="Composition complète non publiée dans la page officielle")
            fund["official_enrichment"] = status
            results[ticker] = status
    except ResearchBudgetExceeded:
        pass  # Keep successes; never persist a budget limit as an issuer failure.
    finally:
        if owns_client:
            http.close()
        if progress_cb is not None:
            progress_cb(completed, len(worklist), "")
    for identity, aliases in aliases_by_identity.items():
        representative = representative_by_identity[identity]
        status = dict(results.get(representative) or {})
        fund = registry["funds"].get(identity, {})
        revision = _CONNECTOR_REVISIONS.get(_issuer(str(fund.get("name") or "")), 0)
        if status and revision:
            status["connector_revision"] = revision
            fund["official_enrichment"] = status
        for ticker in aliases:
            results[ticker] = status
    if _merge_persist:
        touched_funds = set(aliases_by_identity)
        touched_indices = {
            str(registry["funds"].get(identity, {}).get("index_id") or "")
            for identity in touched_funds
        } - {""}
        merge_registry_records(
            registry,
            fund_ids=touched_funds,
            index_ids=touched_indices,
            path=path,
        )
    else:
        save_registry(registry, path)
    return results


def enrich_official_etfs(
    tickers: list[str] | set[str],
    *,
    broker_table=None,
    path=None,
    force: bool = False,
    client: httpx.Client | None = None,
    progress_cb=None,
    should_stop=None,
    budget=None,
) -> dict[str, dict]:
    """Résout les fonds avec une concurrence bornée et une persistance sérialisée."""
    from .etf_index_registry import resolve_index_registry

    wanted = sorted({str(value).strip().upper() for value in tickers if str(value).strip()})
    max_workers = max(1, int(Config.ETF_ENRICHMENT_MAX_WORKERS))
    if not wanted:
        return {}
    if client is not None or len(wanted) <= 1 or max_workers <= 1:
        return _enrich_official_etfs_serial(
            wanted,
            broker_table=broker_table,
            path=path,
            force=force,
            client=client,
            progress_cb=progress_cb,
            should_stop=should_stop,
            budget=budget,
        )

    resolved = resolve_index_registry(wanted, broker_table=broker_table, path=path)
    aliases_by_identity: dict[str, list[str]] = {}
    representative_by_identity: dict[str, str] = {}
    provider_by_ticker: dict[str, str] = {}
    for ticker in wanted:
        meta = resolved.get(ticker, {})
        identity = str(meta.get("identity_key") or f"TICKER:{ticker}")
        aliases_by_identity.setdefault(identity, []).append(ticker)
        representative_by_identity.setdefault(identity, ticker)
        provider_by_ticker[ticker] = _issuer(str(meta.get("name") or "")) or "unknown"

    representatives = sorted(representative_by_identity.values())
    per_provider = max(1, int(Config.ETF_ENRICHMENT_MAX_WORKERS_PER_PROVIDER))
    # Deux files au plus par fournisseur. Chaque file conserve son client HTTP,
    # sa copie du registre et ne fusionne qu'une seule fois en fin de lot. On
    # évite ainsi le précédent anti-pattern : rescanner le catalogue complet et
    # réécrire le registre pour chacun des 185 ETF.
    by_provider: dict[str, list[str]] = {}
    for ticker in representatives:
        by_provider.setdefault(provider_by_ticker.get(ticker, "unknown"), []).append(ticker)
    work_batches: list[list[str]] = []
    for provider_tickers in by_provider.values():
        lanes = [
            [] for _ in range(min(per_provider, len(provider_tickers)))
        ]
        for position, ticker in enumerate(provider_tickers):
            lanes[position % len(lanes)].append(ticker)
        work_batches.extend(lane for lane in lanes if lane)

    progress_lock = threading.Lock()
    completed = 0

    def run_batch(batch: list[str]) -> dict[str, dict]:
        nonlocal completed
        if should_stop is not None and should_stop():
            return {}
        local_done = 0

        def report_batch(done: int, _total: int, ticker: str) -> None:
            nonlocal completed, local_done
            delta = max(0, done - local_done)
            local_done = max(local_done, done)
            with progress_lock:
                completed += delta
                global_done = completed
            if progress_cb is not None:
                progress_cb(global_done, len(representatives), ticker)

        return _enrich_official_etfs_serial(
            batch,
            path=path,
            force=force,
            progress_cb=report_batch,
            should_stop=should_stop,
            _merge_persist=True,
            budget=budget,
            _resolved={ticker: resolved[ticker] for ticker in batch},
        )

    results: dict[str, dict] = {}
    if progress_cb is not None:
        progress_cb(0, len(representatives), representatives[0] if representatives else "")
    with ThreadPoolExecutor(max_workers=min(max_workers, len(work_batches))) as executor:
        futures = {executor.submit(run_batch, batch): batch for batch in work_batches}
        for future in as_completed(futures):
            batch = futures[future]
            try:
                results.update(future.result())
            except Exception:  # conserver un statut réessayable, pas un rejet permanent
                # Une seule référence atypique ne doit pas invalider toute la
                # file du fournisseur. Rejouer isolément permet de persister
                # les succès et d'attacher l'erreur au seul ISIN fautif.
                for ticker in batch:
                    try:
                        recovered = _enrich_official_etfs_serial(
                            [ticker], path=path, force=force,
                            should_stop=should_stop, _merge_persist=True,
                            budget=budget,
                            _resolved={ticker: resolved[ticker]},
                        )
                        results.update(recovered)
                    except Exception as item_exc:
                        results[ticker] = _status_record(
                            status="temporary_error",
                            error=f"{type(item_exc).__name__}: {item_exc}",
                        )
                if progress_cb is not None:
                    with progress_lock:
                        global_done = completed
                    progress_cb(global_done, len(representatives), batch[-1])

    for identity, aliases in aliases_by_identity.items():
        representative = representative_by_identity[identity]
        status = dict(results.get(representative) or {})
        for ticker in aliases:
            results[ticker] = status
    return results


def enrich_unknown_etf_replications(
    tickers,
    *,
    broker_table=None,
    path=None,
    progress_cb=None,
    should_stop=None,
    allow_network: bool = True,
) -> dict[str, object]:
    """Tente les réplications inconnues achetables chez les brokers actifs.

    La résolution locale (catalogue, cache et marqueurs explicites dans le nom)
    précède les connecteurs officiels. Les échecs sont datés par
    :func:`enrich_official_etfs`, qui évite ensuite de répéter une requête avant
    son délai de retry. Cette fonction peut donc être appelée à chaque lancement
    sans retélécharger les milliers de fonds déjà connus. Bourse Direct 2 est
    traité avant Trading 212.
    """
    from collections import Counter

    from .etf_index_registry import resolve_index_registry

    universe = sorted({str(value).strip().upper() for value in tickers if str(value).strip()})
    if not universe:
        return {
            "total": 0,
            "known_before": 0,
            "unknown_before": 0,
            "resolved_now": 0,
            "unknown_after": 0,
            "broker_priority": {
                "available_unknown": 0,
                "available_resolved_now": 0,
            },
            "statuses": {},
        }

    before = resolve_index_registry(universe, broker_table=broker_table, path=path)
    unknown = [
        ticker
        for ticker in universe
        if str(before.get(ticker, {}).get("replication") or "unknown") == "unknown"
    ]

    # Les ETF réellement achetables avec un budget actif passent avant le reste
    # du catalogue. Une interruption manuelle de la préparation laisse ainsi en
    # cache les résultats les plus utiles au portefeuille de l'utilisateur.
    broker_available: set[str] = set()
    bourse_direct_available: set[str] = set()
    if broker_table is not None and not getattr(broker_table, "empty", True):
        try:
            from .broker_availability import (
                _cell_state,
                _find_ticker_col,
                _match_broker_column,
            )

            ticker_column = _find_ticker_col(
                broker_table.columns,
                "Ticker Yahoo Finance",
            )
            active_columns = [
                column
                for broker, budget in Config.BUDGET_BROKERS.items()
                if float(budget or 0) > 0
                if (column := _match_broker_column(broker, broker_table.columns))
                is not None
            ]
            bourse_direct_column = _match_broker_column(
                "BoursDirect2", broker_table.columns,
            )
            if ticker_column is not None and active_columns:
                for _, row in broker_table.iterrows():
                    if any(_cell_state(row.get(column)) is True for column in active_columns):
                        ticker = str(row.get(ticker_column) or "").strip().upper()
                        if ticker:
                            broker_available.add(ticker)
                            if (
                                bourse_direct_column is not None
                                and _cell_state(row.get(bourse_direct_column)) is True
                            ):
                                bourse_direct_available.add(ticker)
        except (AttributeError, TypeError, ValueError):
            broker_available = set()

    unknown.sort(key=lambda ticker: (
        ticker not in broker_available,
        ticker not in bourse_direct_available,
        not bool(_issuer(str(before.get(ticker, {}).get("name") or ""))),
        ticker,
    ))
    scoped_universe = (
        sorted(set(universe) & broker_available)
        if broker_available
        else universe
    )
    scoped_unknown = [ticker for ticker in unknown if ticker in set(scoped_universe)]
    # Ne pas envoyer les milliers d'échecs récents à ``enrich_official_etfs`` :
    # cette fonction vérifie elle aussi le délai, mais seulement APRÈS avoir
    # parcouru et signalé chaque fonds. Sur une optimisation rapprochée, l'UI
    # affichait donc à nouveau 0/2157...2157/2157 sans aucune requête utile.
    # Le registre est déjà chargé ici pour les diagnostics : filtrer avant la
    # boucle rend une relance réellement instantanée pour les ETF inchangés.
    registry_before = load_registry(path)
    due_unknown: list[str] = []
    for ticker in scoped_unknown:
        identity = str(before.get(ticker, {}).get("identity_key") or "")
        fund = registry_before.get("funds", {}).get(identity, {})
        if _attempt_due(fund, False):
            due_unknown.append(ticker)

    def report(done: int, total: int, ticker: str) -> None:
        if progress_cb is not None and (done == 0 or done == total or done % 25 == 0):
            progress_cb(done, total, ticker)

    if due_unknown and allow_network:
        enrichment_kwargs = {
            "broker_table": broker_table,
            "path": path,
            "progress_cb": report,
        }
        if should_stop is not None:
            enrichment_kwargs["should_stop"] = should_stop
        enrich_official_etfs(due_unknown, **enrichment_kwargs)

    after = resolve_index_registry(universe, broker_table=broker_table, path=path)
    remaining = [
        ticker
        for ticker in scoped_unknown
        if str(after.get(ticker, {}).get("replication") or "unknown") == "unknown"
    ]
    registry = load_registry(path)
    statuses = Counter()
    for ticker in remaining:
        identity = str(after.get(ticker, {}).get("identity_key") or "")
        fund = registry.get("funds", {}).get(identity, {})
        status = str((fund.get("official_enrichment") or {}).get("status") or "non_tente")
        statuses[status] += 1
    return {
        "total": len(scoped_universe),
        "known_before": len(scoped_universe) - len(scoped_unknown),
        "unknown_before": len(scoped_unknown),
        "due_now": len(due_unknown),
        "cached_recent": len(scoped_unknown) - len(due_unknown),
        "resolved_now": len(scoped_unknown) - len(remaining),
        "unknown_after": len(remaining),
        "ignored_outside_active_brokers": len(universe) - len(scoped_universe),
        "broker_priority": {
            "available_unknown": len(scoped_unknown),
            "available_resolved_now": sum(
                ticker in broker_available and ticker not in remaining
                for ticker in scoped_unknown
            ),
        },
        "statuses": dict(statuses),
    }
