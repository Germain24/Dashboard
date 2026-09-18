"""Résolution officielle indice -> constituants économiques.

Il n'existe pas de source gratuite universelle. Ce module fournit donc une
interface unique et des connecteurs publics conservateurs. Une source qui ne
publie que le top 10, des quantités sans poids, une page sous licence ou un
résultat ambigu n'est jamais promue au rang de composition économique.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import re
import ssl
from collections.abc import Iterable
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from pypdf import PdfReader

from .etf_index_registry import (
    cached_index_composition,
    canonical_constituent_set_id,
    canonical_index_id,
    canonical_index_name,
    load_registry,
    save_registry,
    store_index_composition,
)

_TIMEOUT = 20.0
_USER_AGENT = "MissionControl/1.0 official index constituents"
_TEMPORARY_RETRY_DAYS = 1
_PERMANENT_RETRY_DAYS = 7
_JPX_TOPIX_URL = "https://www.jpx.co.jp/english/markets/indices/topix/"
_NIKKEI_225_WEIGHTS_URL = (
    "https://indexes.nikkei.co.jp/nkave/archives/file/"
    "nikkei_stock_average_weight_en.csv"
)
_STOXX_CATALOG_URL = "https://www.stoxx.com/data-vendor-codes"
_SOLACTIVE_SEARCH_URL = "https://www.solactive.com/"
_FTSE_RUSSELL_CATALOG_URL = (
    "https://www.lseg.com/en/ftse-russell/index-resources/constituent-weights"
)
_FTSE_RUSSELL_CATALOG_API = (
    "https://www.lseg.com/content/lseg/en_us/ftse-russell/index-resources/"
    "constituent-weights/jcr:content/root/container/page_content_region/"
    "page-content-region/section/section-fw/data_table.constituentsandweights.json"
)
_BNP_INDEX_API = "https://indx.bnpparibas.com/api/bnpp-indx/index"

_LICENSED_PROVIDERS = {
    "msci", "spdj", "nasdaq", "bloomberg", "ice", "iboxx",
    "jpmorgan", "morningstar",
}
_LICENSED_PROVIDER_URLS = {
    "msci": "https://www.msci.com/indexes",
    "spdj": "https://www.spglobal.com/spdji/en/indices/",
    "nasdaq": "https://indexes.nasdaqomx.com/",
    "bloomberg": "https://www.bloomberg.com/professional/products/indices/",
    "ice": "https://www.ice.com/market-data/indices",
    "iboxx": "https://www.spglobal.com/spdji/en/index-family/fixed-income/iboxx/",
    "jpmorgan": "https://www.jpmorgan.com/insights/global-research/index-research/composition-docs",
    "morningstar": "https://indexes.morningstar.com/",
}


def detect_index_provider(name: str) -> str:
    """Identifie l'administrateur sans confondre le nom d'un ETF et l'indice."""
    upper = canonical_index_name(name).upper()
    if "MSCI" in upper:
        return "msci"
    if any(marker in upper for marker in ("STOXX", "TECDAX", "MDAX", "SDAX", "DAX")):
        return "stoxx"
    if any(marker in upper for marker in ("S&P", "STANDARD & POOR", "DOW JONES")):
        return "spdj"
    if any(marker in upper for marker in ("FTSE", "RUSSELL")):
        return "ftse_russell"
    if "NASDAQ" in upper:
        return "nasdaq"
    if any(marker in upper for marker in ("TOPIX", "JPX")):
        return "jpx"
    if "NIKKEI" in upper:
        return "nikkei"
    if "SOLACTIVE" in upper:
        return "solactive"
    if "BLOOMBERG" in upper:
        return "bloomberg"
    if "IBOXX" in upper or "MARKIT IBOXX" in upper:
        return "iboxx"
    if "ICE " in upper or upper.startswith("ICE-"):
        return "ice"
    if re.search(r"\bJ\.?P\.?\s*MORGAN\b|\bJPM\b", upper):
        return "jpmorgan"
    if "MORNINGSTAR" in upper:
        return "morningstar"
    if "BNP PARIBAS" in upper:
        return "bnp"
    return "unknown"


def _status(
    status: str,
    *,
    provider: str,
    source_url: str = "",
    error: str = "",
    coverage: float = 0.0,
) -> dict[str, Any]:
    return {
        "status": status,
        "provider": provider,
        "source_url": source_url,
        "error": error,
        "coverage": min(max(float(coverage), 0.0), 1.0),
        "last_attempt_at": dt.date.today().isoformat(),
    }


def _attempt_due(record: dict, *, force: bool) -> bool:
    if force:
        return True
    enrichment = record.get("official_enrichment") or {}
    try:
        attempted = dt.date.fromisoformat(str(enrichment.get("last_attempt_at", ""))[:10])
    except ValueError:
        return True
    temporary = str(enrichment.get("status") or "") in {
        "temporary_error", "source_unavailable",
    }
    retry = _TEMPORARY_RETRY_DAYS if temporary else _PERMANENT_RETRY_DAYS
    return (dt.date.today() - attempted).days >= retry


def _response_bytes(response: Any) -> bytes:
    content = getattr(response, "content", None)
    if isinstance(content, bytes):
        return content
    return str(getattr(response, "text", "")).encode("utf-8")


def _response_json(response: Any) -> Any:
    """Décode les catalogues officiels même lorsque leur charset est erroné.

    LSEG sert parfois son catalogue FTSE avec un en-tête UTF-8 alors que des
    espaces insécables Windows-1252 subsistent dans le corps. ``httpx.json()``
    lève alors UnicodeDecodeError avant même que le JSON puisse être analysé.
    """
    payload = _response_bytes(response)
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return json.loads(payload.decode(encoding))
        except UnicodeDecodeError:
            continue
    # Si le texte est bien décodable mais que le JSON est invalide, conserver
    # l'erreur JSON précise au lieu de la masquer comme une panne d'encodage.
    return json.loads(payload.decode("utf-8-sig", errors="replace"))


def _read_table(response: Any, url: str) -> pd.DataFrame:
    payload = _response_bytes(response)
    content_type = str(getattr(response, "headers", {}).get("content-type", "")).casefold()
    if url.casefold().endswith((".xlsx", ".xls")) or "spreadsheet" in content_type:
        return pd.read_excel(io.BytesIO(payload))
    text = payload.decode("utf-8-sig", errors="replace")
    for separator in (";", ",", "\t"):
        try:
            # low_memory=False évite le DtypeWarning des colonnes mixtes
            # (ex. « Close P002 », « Other Report ») sans changer la sémantique.
            frame = pd.read_csv(io.StringIO(text), sep=separator, low_memory=False)
        except (ValueError, pd.errors.ParserError):
            continue
        if len(frame.columns) > 1:
            return frame
    raise ValueError("format tabulaire officiel non reconnu")


def _column(frame: pd.DataFrame, *markers: str) -> Any | None:
    columns = {str(value).strip().casefold(): value for value in frame.columns}
    for marker in markers:
        folded = marker.casefold()
        if folded in columns:
            return columns[folded]
    for marker in markers:
        folded = marker.casefold()
        for key, value in columns.items():
            if folded in key:
                return value
    return None


def _float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    raw = str(value).strip().replace("\u00a0", "").replace("%", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def holdings_from_weight_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Normalise un fichier officiel, mais exige une colonne de poids explicite."""
    weight_col = _column(
        frame, "weight", "index weight", "component weight", "closing weight",
        "weighting", "poids",
    )
    name_col = _column(frame, "instrument_name", "constituent name", "company name", "name")
    isin_col = _column(frame, "isin", "component isin")
    ticker_col = _column(frame, "ticker", "ric", "local code", "code", "symbol")
    country_col = _column(frame, "country", "country code", "country of risk")
    sector_col = _column(frame, "sector", "industry", "icb", "gics")
    if weight_col is None or (name_col is None and isin_col is None and ticker_col is None):
        return []
    rows: list[dict[str, Any]] = []
    for _, raw in frame.iterrows():
        weight = _float(raw.get(weight_col))
        if weight is None or weight <= 0:
            continue
        item = {
            "ticker": str(raw.get(ticker_col) or "").strip().upper() if ticker_col else "",
            "isin": str(raw.get(isin_col) or "").strip().upper() if isin_col else "",
            "name": str(raw.get(name_col) or "").strip() if name_col else "",
            "country": str(raw.get(country_col) or "").strip() if country_col else "",
            "sector": str(raw.get(sector_col) or "").strip() if sector_col else "",
            "weight": weight,
        }
        if item["ticker"] or item["isin"] or item["name"]:
            rows.append(item)
    total = sum(float(item["weight"]) for item in rows)
    if total > 2.0:
        for item in rows:
            item["weight"] = float(item["weight"]) / 100.0
        total /= 100.0
    # Refuse les top-N et les fichiers dont l'unité n'a pas pu être identifiée.
    if total < 0.90 or total > 1.05:
        return []
    if total > 1.0:
        for item in rows:
            item["weight"] = float(item["weight"]) / total
    return rows


def _exact_catalog_row(frame: pd.DataFrame, index_name: str) -> pd.Series | None:
    name_col = _column(frame, "index full name", "index name", "name")
    if name_col is None:
        return None
    target = canonical_constituent_set_id(index_name)
    matches = frame[
        frame[name_col].map(lambda value: canonical_constituent_set_id(value) == target)
    ]
    if len(matches) == 1:
        return matches.iloc[0]
    if matches.empty:
        return None

    # STOXX publie souvent le même panier sous plusieurs devises et conventions
    # de rendement. Ce ne sont pas des indices économiques distincts : la ligne
    # dont le symbole est le « Main Symbol » désigne le panier de référence.
    symbol_col = _column(frame, "symbol")
    main_symbol_col = _column(frame, "main symbol")
    if symbol_col is not None and main_symbol_col is not None:
        main = matches[
            matches.apply(
                lambda row: str(row.get(symbol_col) or "").strip().upper()
                == str(row.get(main_symbol_col) or "").strip().upper(),
                axis=1,
            )
        ]
        if len(main) == 1:
            return main.iloc[0]

    # Certains catalogues dupliquent encore Price EUR/Price USD avec un même
    # Main Symbol. On accepte uniquement si toutes les lignes pointent vers le
    # même panier de constituants ; sinon la correspondance reste ambiguë.
    components_col = _column(frame, "components p000")
    if components_col is not None:
        component_sets = {
            re.sub(r"_[a-z0-9]+_YYYYMMDD", "_SET_YYYYMMDD", str(value), flags=re.I)
            for value in matches[components_col].dropna()
            if str(value).strip()
        }
        if len(component_sets) == 1:
            return matches.iloc[0]
    return None


def _official_ssl_context() -> ssl.SSLContext:
    """Ajoute les autorités Windows au bundle Python/certifi.

    Certains diffuseurs officiels (notamment STOXX) présentent une chaîne que
    Windows valide mais que le bundle certifi embarqué ne connaît pas encore.
    La vérification TLS reste active : aucun ``verify=False`` n'est utilisé.
    """
    context = ssl.create_default_context()
    enum_certificates = getattr(ssl, "enum_certificates", None)
    if enum_certificates is None:
        return context
    for store in ("ROOT", "CA"):
        try:
            certificates = enum_certificates(store)
        except OSError:
            continue
        for certificate, encoding, _trust in certificates:
            if encoding != "x509_asn":
                continue
            try:
                context.load_verify_locations(
                    cadata=ssl.DER_cert_to_PEM_cert(certificate)
                )
            except ssl.SSLError:
                continue
    return context


def _holdings_from_ftse_text(text: str) -> list[dict[str, Any]]:
    """Lit les tableaux texte des PDF publics FTSE sans inventer les poids <0,005 %."""
    holdings: list[dict[str, Any]] = []
    pending: list[str] = []
    row_pattern = re.compile(
        r"^(?:(.*?)\s+)?(<\s*0\.0+\s*5|\d+\.\d{1,3})\s+([A-Z][A-Z ]+)$"
    )
    ignored = (
        "source:", "ftse russell publications", "indicative index weight",
        "constituent", "weight (%)", "corporate", "of ",
    )
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        folded = line.casefold()
        if any(folded.startswith(marker) for marker in ignored):
            pending.clear()
            continue
        match = row_pattern.match(line)
        if match is None:
            # Les noms longs sont parfois renvoyés sur la ligne précédant le poids.
            if not re.fullmatch(r"\d{1,2}\s+\w+\s+\d{4}", line):
                pending.append(line)
            continue
        prefix, raw_weight, country = match.groups()
        name = " ".join([*pending, prefix or ""]).strip()
        pending.clear()
        # Une valeur « <0,005 % » n'a pas de poids exact. Elle reste documentée
        # dans le PDF, mais n'entre pas dans le panier numérique.
        if raw_weight.lstrip().startswith("<") or not name:
            continue
        holdings.append(
            {
                "ticker": "",
                "isin": "",
                "name": name,
                "country": country.title(),
                "sector": "",
                "weight": float(raw_weight) / 100.0,
            }
        )
    total = sum(float(item["weight"]) for item in holdings)
    return holdings if 0.90 <= total <= 1.05 else []


def _holdings_from_ftse_pdf(payload: bytes) -> list[dict[str, Any]]:
    reader = PdfReader(io.BytesIO(payload))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return _holdings_from_ftse_text(text)


def _fetch_ftse_russell(http: httpx.Client, index_name: str) -> dict[str, Any]:
    """Résout uniquement les indices publiés dans le catalogue public LSEG."""
    catalog_response = http.get(_FTSE_RUSSELL_CATALOG_API)
    catalog_response.raise_for_status()
    payload = _response_json(catalog_response)
    rows = payload.get("Data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return _status(
            "source_unavailable", provider="ftse_russell",
            source_url=_FTSE_RUSSELL_CATALOG_URL,
            error="catalogue public FTSE Russell non reconnu",
        )
    target = canonical_constituent_set_id(index_name)
    matches = [
        row for row in rows
        if isinstance(row, dict)
        and canonical_constituent_set_id(row.get("IndexName")) == target
    ]
    unique = {
        (str(row.get("IndexId") or ""), str(row.get("Url") or "")): row
        for row in matches
    }
    if len(unique) != 1:
        return _status(
            "index_not_found", provider="ftse_russell",
            source_url=_FTSE_RUSSELL_CATALOG_URL,
            error=(
                "indice absent du catalogue public FTSE Russell"
                if not unique
                else "plusieurs publications FTSE Russell distinctes correspondent au nom"
            ),
        )
    row = next(iter(unique.values()))
    source_url = str(row.get("Url") or "").strip()
    if not source_url:
        return _status(
            "composition_unavailable", provider="ftse_russell",
            source_url=_FTSE_RUSSELL_CATALOG_URL,
            error="publication trouvée sans lien de constituants",
        )
    response = http.get(source_url)
    response.raise_for_status()
    content = _response_bytes(response)
    if content.startswith(b"%PDF"):
        holdings = _holdings_from_ftse_pdf(content)
    else:
        holdings = holdings_from_weight_frame(_read_table(response, source_url))
    if not holdings:
        return _status(
            "incomplete", provider="ftse_russell", source_url=source_url,
            error=(
                "la publication officielle ne fournit pas au moins 90 % de poids "
                "numériques exploitables"
            ),
        )
    coverage = sum(float(item["weight"]) for item in holdings)
    return {
        **_status(
            "complete", provider="ftse_russell", source_url=source_url,
            coverage=coverage,
        ),
        "holdings": holdings,
        "provider_index_id": str(row.get("IndexId") or "").strip(),
    }


def _fetch_stoxx(http: httpx.Client, index_name: str) -> dict[str, Any]:
    landing = http.get(_STOXX_CATALOG_URL)
    landing.raise_for_status()
    soup = BeautifulSoup(landing.text, "html.parser")
    catalog_url = next(
        (
            urljoin(str(landing.url), str(link.get("href") or ""))
            for link in soup.find_all("a", href=True)
            if (
                "index report" in link.get_text(" ", strip=True).casefold()
                or "index_reports_links" in str(link.get("href") or "").casefold()
            )
            and ".csv" in str(link.get("href") or "").casefold()
        ),
        "",
    )
    if not catalog_url:
        return _status(
            "source_unavailable", provider="stoxx", source_url=str(landing.url),
            error="catalogue officiel des liens de rapports introuvable",
        )
    catalog_response = http.get(catalog_url)
    catalog_response.raise_for_status()
    catalog = _read_table(catalog_response, catalog_url)
    row = _exact_catalog_row(catalog, index_name)
    if row is None:
        return _status(
            "index_not_found", provider="stoxx", source_url=catalog_url,
            error="aucune correspondance exacte et non ambiguë dans le catalogue STOXX",
        )
    close_col = _column(catalog, "close composition", "close")
    symbol_col = _column(catalog, "symbol")
    index_isin_col = _column(catalog, "isin")
    composition_url = str(row.get(close_col) or "").strip() if close_col else ""
    if not composition_url:
        return _status(
            "composition_unavailable", provider="stoxx", source_url=catalog_url,
            error="fichier de composition absent du catalogue officiel",
        )
    composition_url = urljoin(catalog_url, composition_url)
    candidate_urls = [composition_url]
    if "YYYYMMDD" in composition_url:
        candidate_urls = [
            composition_url.replace(
                "YYYYMMDD", (dt.date.today() - dt.timedelta(days=offset)).strftime("%Y%m%d")
            )
            for offset in range(8)
        ]
    response = None
    for candidate_url in candidate_urls:
        candidate_response = http.get(candidate_url)
        status_code = int(getattr(candidate_response, "status_code", 200) or 200)
        if status_code in {401, 403}:
            return {
                **_status(
                    "licence_required",
                    provider="stoxx",
                    source_url=candidate_url,
                    error="le fichier de composition STOXX exige une autorisation",
                ),
                "provider_index_id": (
                    str(row.get(symbol_col) or "").strip() if symbol_col else ""
                ),
                "index_isin": (
                    str(row.get(index_isin_col) or "").strip()
                    if index_isin_col
                    else ""
                ),
            }
        if status_code == 404 and len(candidate_urls) > 1:
            continue
        candidate_response.raise_for_status()
        response = candidate_response
        composition_url = candidate_url
        break
    if response is None:
        return _status(
            "composition_unavailable",
            provider="stoxx",
            source_url=composition_url,
            error="aucun fichier de composition daté publié sur les huit derniers jours",
        )
    # Un téléchargement authentifié manquant renvoie parfois une page HTML 200.
    if "<html" in response.text[:500].casefold():
        return _status(
            "licence_required", provider="stoxx", source_url=composition_url,
            error="le fichier de composition STOXX exige une autorisation",
        )
    holdings = holdings_from_weight_frame(_read_table(response, composition_url))
    if not holdings:
        return _status(
            "incomplete", provider="stoxx", source_url=composition_url,
            error="poids complets absents ou couverture inférieure à 90 %",
        )
    return {
        **_status("complete", provider="stoxx", source_url=composition_url, coverage=1.0),
        "holdings": holdings,
        "provider_index_id": str(row.get(symbol_col) or "").strip() if symbol_col else "",
        "index_isin": str(row.get(index_isin_col) or "").strip() if index_isin_col else "",
    }


def _fetch_jpx(http: httpx.Client, index_name: str) -> dict[str, Any]:
    exact = canonical_index_id(index_name)
    if exact not in {"TOPIX", "TOPIX-INDEX", "TOKYO-STOCK-PRICE-INDEX-TOPIX"}:
        return _status(
            "index_not_supported", provider="jpx",
            error="seul le TOPIX large est résolu automatiquement sans catalogue licencié",
        )
    landing = http.get(_JPX_TOPIX_URL)
    landing.raise_for_status()
    soup = BeautifulSoup(landing.text, "html.parser")
    candidates: list[str] = []
    for link in soup.find_all("a", href=True):
        href = str(link.get("href") or "")
        text = link.get_text(" ", strip=True).casefold()
        if href.casefold().endswith((".xls", ".xlsx", ".csv")) and (
            "component" in text and "weight" in text
            or "topix" in href.casefold() and "weight" in href.casefold()
        ):
            candidates.append(urljoin(str(landing.url), href))
    if len(set(candidates)) != 1:
        return _status(
            "source_unavailable", provider="jpx", source_url=str(landing.url),
            error="fichier officiel TOPIX absent ou ambigu",
        )
    source_url = candidates[0]
    response = http.get(source_url)
    response.raise_for_status()
    holdings = holdings_from_weight_frame(_read_table(response, source_url))
    for item in holdings:
        item["country"] = item.get("country") or "Japan"
        ticker = str(item.get("ticker") or "").strip()
        if re.fullmatch(r"\d{4,5}", ticker):
            item["ticker"] = f"{ticker}.T"
    if not holdings:
        return _status(
            "incomplete", provider="jpx", source_url=source_url,
            error="poids TOPIX complets non reconnus",
        )
    return {
        **_status("complete", provider="jpx", source_url=source_url, coverage=1.0),
        "holdings": holdings,
        "provider_index_id": "TOPIX",
    }


def _fetch_nikkei(http: httpx.Client, index_name: str) -> dict[str, Any]:
    """Charge le fichier mensuel public du Nikkei 225, sans extrapolation."""
    exact = canonical_index_id(index_name)
    if exact not in {
        "NIKKEI-225",
        "NIKKEI-STOCK-AVERAGE",
        "NIKKEI-STOCK-AVERAGE-NIKKEI-225",
    }:
        return _status(
            "index_not_supported",
            provider="nikkei",
            error="seul le Nikkei 225 est publié avec ses poids complets gratuits",
        )
    response = http.get(_NIKKEI_225_WEIGHTS_URL)
    response.raise_for_status()
    holdings = holdings_from_weight_frame(_read_table(response, _NIKKEI_225_WEIGHTS_URL))
    for item in holdings:
        item["country"] = item.get("country") or "Japan"
        ticker = str(item.get("ticker") or "").strip()
        if re.fullmatch(r"\d{4,5}", ticker):
            item["ticker"] = f"{ticker}.T"
    if not holdings:
        return _status(
            "incomplete",
            provider="nikkei",
            source_url=_NIKKEI_225_WEIGHTS_URL,
            error="poids mensuels complets du Nikkei 225 non reconnus",
        )
    return {
        **_status(
            "complete",
            provider="nikkei",
            source_url=_NIKKEI_225_WEIGHTS_URL,
            coverage=1.0,
        ),
        "holdings": holdings,
        "provider_index_id": "NIKKEI-225",
    }


def _solactive_id_from_url(url: str) -> str:
    values = parse_qs(urlparse(url).query)
    return str((values.get("index") or values.get("Index") or [""])[0]).strip()


def _fetch_solactive(http: httpx.Client, index_name: str, provider_id: str = "") -> dict[str, Any]:
    candidate_id = str(provider_id).strip()
    if not candidate_id:
        response = http.get(_SOLACTIVE_SEARCH_URL, params={"s": index_name})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        exact: list[str] = []
        target = canonical_index_id(index_name)
        for link in soup.find_all("a", href=True):
            found = _solactive_id_from_url(str(link.get("href") or ""))
            if found and canonical_index_id(link.get_text(" ", strip=True)) == target:
                exact.append(found)
        if len(set(exact)) != 1:
            return _status(
                "index_not_found", provider="solactive", source_url=str(response.url),
                error="identifiant Solactive exact absent ou ambigu",
            )
        candidate_id = exact[0]
    source_url = f"https://www.solactive.com/Indices/?index={candidate_id}"
    response = http.get(source_url)
    response.raise_for_status()
    try:
        tables = pd.read_html(io.StringIO(response.text))
    except ValueError:
        tables = []
    holdings = next((rows for table in tables if (rows := holdings_from_weight_frame(table))), [])
    if not holdings:
        return _status(
            "weights_unavailable", provider="solactive", source_url=source_url,
            error="la page publie des quantités mais pas des poids économiques exacts",
        )
    return {
        **_status("complete", provider="solactive", source_url=source_url, coverage=1.0),
        "holdings": holdings,
        "provider_index_id": candidate_id,
        "index_isin": candidate_id if re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", candidate_id) else "",
    }


def _bnp_public_index_id(index_name: str) -> str:
    """Codes MDS publiés par le portail Indx de BNP Paribas."""
    upper = canonical_index_name(index_name).upper()
    if "BNP PARIBAS" not in upper or "EUROPE" not in upper:
        return ""
    if "HIGH DIVIDEND" in upper:
        return "EU_BNPIHEUN"
    if "GROWTH" in upper:
        return "EU_BNPIFEGE"
    if "QUALITY" in upper:
        return "EU_BNPIFEQE"
    if "VALUE" in upper:
        return "EU_BNPIFVE"
    if "LOW VOL" in upper:
        return "EU_BNPIFLVE"
    return ""


def _fetch_bnp_index(http: httpx.Client, index_name: str) -> dict[str, Any]:
    """Charge la composition publique utilisée par le portail officiel Indx."""
    provider_id = _bnp_public_index_id(index_name)
    if not provider_id:
        return _status(
            "index_not_found",
            provider="bnp",
            source_url="https://indx.bnpparibas.com/",
            error="indice propriétaire absent du catalogue public BNP Indx pris en charge",
        )
    source_url = f"{_BNP_INDEX_API}/composition/{provider_id}"
    response = http.get(source_url)
    response.raise_for_status()
    payload = response.json() if _response_bytes(response).strip() else []
    if not isinstance(payload, list) or not payload:
        return {
            **_status(
                "composition_unavailable",
                provider="bnp",
                source_url=source_url,
                error="indice identifié, mais composition courante non publiée par BNP Indx",
            ),
            "provider_index_id": provider_id,
        }
    frame = pd.DataFrame(
        {
            "Name": [row.get("Underlying") for row in payload],
            "Ticker": [
                re.sub(r"\s+Equity$", "", str(row.get("BbgCode") or ""), flags=re.I)
                for row in payload
            ],
            "Weight": [row.get("Weight") for row in payload],
        }
    )
    holdings = holdings_from_weight_frame(frame)
    if not holdings:
        return {
            **_status(
                "incomplete",
                provider="bnp",
                source_url=source_url,
                error="composition BNP publiée sans au moins 90 % de poids exploitables",
            ),
            "provider_index_id": provider_id,
        }
    dates = {
        str(row.get("formattedCompDate") or "").strip()
        for row in payload
        if str(row.get("formattedCompDate") or "").strip()
    }
    return {
        **_status(
            "complete",
            provider="bnp",
            source_url=source_url,
            coverage=sum(float(item["weight"]) for item in holdings),
        ),
        "holdings": holdings,
        "provider_index_id": provider_id,
        "as_of": next(iter(dates)) if len(dates) == 1 else "",
    }


def _fetch_index(http: httpx.Client, record: dict) -> dict[str, Any]:
    name = str(record.get("name") or "")
    stored_provider = str(record.get("provider") or "").strip()
    provider = (
        detect_index_provider(name)
        if stored_provider.casefold() in {"", "unknown"}
        else stored_provider
    )
    if provider in _LICENSED_PROVIDERS:
        provider_id = str(record.get("provider_index_id") or "").strip()
        source_url = _LICENSED_PROVIDER_URLS.get(provider, "")
        if provider == "msci" and provider_id:
            source_url = f"https://www.msci.com/indexes/index/{provider_id}"
        return _status(
            "licence_required", provider=provider, source_url=source_url,
            error="composition complète disponible uniquement via un flux officiel autorisé",
        )
    if provider == "stoxx":
        return _fetch_stoxx(http, name)
    if provider == "jpx":
        return _fetch_jpx(http, name)
    if provider == "nikkei":
        return _fetch_nikkei(http, name)
    if provider == "solactive":
        return _fetch_solactive(http, name, str(record.get("provider_index_id") or ""))
    if provider == "ftse_russell":
        return _fetch_ftse_russell(http, name)
    if provider == "bnp":
        return _fetch_bnp_index(http, name)
    return _status(
        "provider_unsupported", provider=provider,
        error="aucun connecteur officiel public disponible",
    )


def enrich_official_indices(
    index_ids: Iterable[str],
    *,
    path=None,
    force: bool = False,
    client: httpx.Client | None = None,
    progress_cb=None,
    should_stop=None,
    budget=None,
) -> dict[str, dict[str, Any]]:
    """Cherche chaque indice manquant une fois, puis persiste résultat et échec."""
    wanted = sorted({str(value).strip() for value in index_ids if str(value).strip()})
    if not wanted:
        return {}
    owns_client = client is None
    http = client or httpx.Client(
        timeout=_TIMEOUT,
        follow_redirects=True,
        verify=_official_ssl_context(),
        headers={"User-Agent": _USER_AGENT, "Accept-Language": "en-GB,en;q=0.8"},
    )
    output: dict[str, dict[str, Any]] = {}
    from .etf_research_budget import BudgetClient, ResearchBudgetExceeded
    from .etf_index_registry import canonical_constituent_set_id
    if budget is not None:
        http = BudgetClient(http, budget)
    try:
        registry = load_registry(path)
        # Externalise dès l'entrée les anciens paniers inline. Sans ce point de
        # migration, chaque vérification de cache relisait encore le registre
        # historique de plusieurs centaines de Mo jusqu'au premier checkpoint.
        save_registry(registry, path)
        for position, index_id in enumerate(wanted, start=1):
            if should_stop is not None and should_stop():
                break
            if progress_cb is not None:
                progress_cb(position - 1, len(wanted), index_id)
            record = registry["indices"].get(index_id)
            if not isinstance(record, dict):
                output[index_id] = _status(
                    "index_unresolved", provider="unknown", error="indice absent du registre",
                )
                continue
            record["provider"] = str(record.get("provider") or detect_index_provider(record.get("name", "")))
            cached = cached_index_composition(index_id, path=path, registry=registry)
            if cached and not force:
                output[index_id] = _status(
                    "complete_cached",
                    provider=record["provider"],
                    source_url=str(cached.get("source_url") or ""),
                    coverage=float(cached.get("coverage") or 0.0),
                )
                continue
            if not _attempt_due(record, force=force):
                output[index_id] = dict(record.get("official_enrichment") or {})
                continue
            if budget is not None and not budget.claim(
                "index", canonical_constituent_set_id(record.get("name") or index_id),
            ):
                continue
            try:
                result = _fetch_index(http, record)
            except ResearchBudgetExceeded:
                break
            except (httpx.HTTPError, ValueError, TypeError, OSError, ImportError) as exc:
                result = _status(
                    "temporary_error", provider=record["provider"], error=str(exc),
                )
            record["official_enrichment"] = {
                key: value for key, value in result.items() if key != "holdings"
            }
            if result.get("provider_index_id"):
                record["provider_index_id"] = str(result["provider_index_id"])
            if result.get("index_isin"):
                record["index_isin"] = str(result["index_isin"])
            holdings = list(result.get("holdings") or [])
            if result.get("status") == "complete" and holdings:
                store_index_composition(
                    index_id,
                    holdings,
                    source="official_index_constituents",
                    index_name=str(record.get("name") or ""),
                    source_url=str(result.get("source_url") or ""),
                    path=path,
                    provider=str(result.get("provider") or ""),
                    provider_index_id=str(result.get("provider_index_id") or ""),
                    as_of=str(result.get("as_of") or ""),
                    registry=registry,
                    persist=False,
                )
            output[index_id] = {
                key: value for key, value in result.items() if key != "holdings"
            }
            # Point de reprise sans réécrire un registre géant à chaque indice.
            if position % 25 == 0:
                save_registry(registry, path)
    finally:
        try:
            if "registry" in locals():
                save_registry(registry, path)
        finally:
            if progress_cb is not None:
                progress_cb(len(output), len(wanted), "")
            if owns_client:
                http.close()
    return output
