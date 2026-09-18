"""Registre persistant ETF -> indice économique exact.

L'identité d'un fonds (ISIN) et celle de son sous-jacent sont deux choses
différentes.  Ce module résout le sous-jacent une fois par ISIN et partage cette
identité entre toutes les cotations du fonds.  Il ne confond jamais le panier de
collatéral d'un ETF synthétique avec l'indice répliqué.

Le registre est volontairement conservateur : un nom générique ("World ETF",
"Water ETF"...) ne suffit pas.  En l'absence d'un fournisseur/nom d'indice
explicite, le fonds reste non résolu et la déduplication par corrélation demeure
le filet de sécurité.
"""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import html
import json
import os
import re
import tempfile
import threading
import unicodedata
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .config import Config

REGISTRY_VERSION = 2
DEFAULT_REGISTRY_PATH = Path(Config.DATA_DIR) / "cache" / "etf_index_registry.json"
_EXTERNAL_HOLDINGS_MIN_COUNT = 25
_registry_io_lock = threading.RLock()
ETF_INDEX_SHEET = "ETF_Indices"
INDEX_CONSTITUENTS_SHEET = "Indices_Constituants"
OFFICIAL_INDEX_COMPOSITION_SOURCES = {
    "official_index_constituents",
    "issuer_index_constituents",
    "manual_official_index_constituents",
}
OFFICIAL_ECONOMIC_COMPOSITION_SOURCES = {
    *OFFICIAL_INDEX_COMPOSITION_SOURCES,
    "issuer_fund_holdings",
}

_INDEX_MARKERS = (
    "MSCI", "STOXX", "S&P", "STANDARD & POOR", "FTSE", "NASDAQ", "TOPIX",
    "SOLACTIVE", "MORNINGSTAR", "BLOOMBERG", "ICE", "MARKIT", "IBOXX",
    "CAC 40", "DAX", "TECDAX", "MDAX", "SDAX", "FTSE MIB", "EURO STOXX",
)
_ISSUER_PREFIX = re.compile(
    r"^(?:AMUNDI(?: INDEX SOLUTIONS)?|ISHARES|XTRACKERS|VANECK|FIRST TRUST|"
    r"STATE STREET SPDR|SPDR|BNP PARIBAS EASY|LYXOR|INVESCO|VANGUARD|WISDOMTREE)\s+",
    re.IGNORECASE,
)
_FUND_SUFFIX = re.compile(
    r"\s+(?:UCITS\s+)?ETF(?:\s*\([^)]*\))?(?:\s*[-–—:]?\s*"
    r"(?:EUR|USD|GBP|CHF)?\s*(?:HEDGED)?\s*(?:ACC|DIST|C|D)?)?.*$",
    re.IGNORECASE,
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    value = str(value).strip()
    return "" if value.casefold() in {"", "nan", "none", "-"} else value


def _norm_isin(value: Any) -> str:
    value = re.sub(r"[^A-Z0-9]", "", _text(value).upper())
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", value):
        return ""
    expanded = "".join(
        str(ord(char) - ord("A") + 10) if char.isalpha() else char
        for char in value
    )
    total = 0
    for position, char in enumerate(reversed(expanded)):
        number = int(char) * (2 if position % 2 else 1)
        total += number // 10 + number % 10
    return value if total % 10 == 0 else ""


def valid_isin(value: Any) -> str:
    """Renvoie l'ISIN normalisé uniquement si son chiffre de contrôle est valide."""
    return _norm_isin(value)


def _cusip_check_digit(base: str) -> str:
    """Chiffre de contrôle CUSIP (9e caractère), calculé sur les 8 premiers.

    Pondération alternée depuis la gauche : les positions paires (2e, 4e, 6e, 8e
    en comptage 1-indexé, donc les index impairs 0-indexé) sont multipliées par
    2, les autres par 1 ; les lettres A-Z valent 10-35. Ce checksum CUSIP est
    distinct du checksum ISIN appliqué ensuite par ``_norm_isin``.
    """
    total = 0
    for position, char in enumerate(base):
        value = ord(char) - ord("A") + 10 if char.isalpha() else int(char)
        weight = 2 if position % 2 else 1
        product = value * weight
        total += product // 10 + product % 10
    return str((10 - total % 10) % 10)


def cusip_to_isin(cusip: Any) -> str:
    """ISIN US d'un titre coté aux États-Unis, dérivé de son CUSIP (9 caractères).

    L'ISIN d'une valeur US vaut « US » + CUSIP + 1 chiffre de contrôle Luhn.
    La reconstitution est refusée (renvoie "") si le CUSIP n'a pas exactement
    9 caractères, si son propre chiffre de contrôle (9e caractère) est invalide,
    ou si aucun chiffre de contrôle ISIN valide n'existe — jamais de valeur
    inventée. Le chiffre de contrôle ISIN est déterminé par force brute sur les
    10 candidats via ``_norm_isin`` (le validateur Luhn partagé) : le préfixe
    fait 11 caractères alors que ``_norm_isin`` en attend 12 (chiffre de contrôle
    compris), donc réimplémenter sa pondération décalerait les positions et
    inverserait le poids Luhn. Passer par le validateur garantit la cohérence
    avec la validation des autres ISIN sans recoder ce décalage.
    """
    cusip = re.sub(r"[^A-Z0-9]", "", _text(cusip).upper())
    if len(cusip) != 9:
        return ""
    if _cusip_check_digit(cusip[:8]) != cusip[8]:
        return ""
    prefix = "US" + cusip
    for digit in "0123456789":
        candidate = _norm_isin(prefix + digit)
        if candidate:
            return candidate
    return ""


def _registry_isins_by_ticker(funds: dict[str, dict]) -> dict[str, str]:
    """Réutilise l'ISIN déjà vérifié d'une autre cotation du même fonds."""
    candidates: dict[str, set[str]] = {}
    for record in funds.values():
        if not isinstance(record, dict):
            continue
        isin = _norm_isin(record.get("isin"))
        if not isin:
            continue
        for alias in record.get("tickers", []):
            ticker = _text(alias).upper()
            if ticker:
                candidates.setdefault(ticker, set()).add(isin)
    return {
        ticker: next(iter(values))
        for ticker, values in candidates.items()
        if len(values) == 1
    }


def _local_broker_isins() -> tuple[dict[str, str], dict[str, str]]:
    """ISIN locaux Trading212/Bourse Direct, sans aucune requête réseau.

    Les symboles courts ambigus sont volontairement ignorés. Le cache Bourse
    Direct est produit par ``scripts/import_boursedirect_pea.py --scrape-etfs``.
    """
    variables = Path(Config.TICKERS_CSV).parent
    sources = (
        (variables / "trading212_instruments.json", "shortName"),
        (variables / "boursedirect_pea_etfs.json", "yahoo"),
    )
    schedule_names: dict[int, str] = {}
    try:
        exchanges = json.loads(
            (variables / "trading212_exchanges.json").read_text(encoding="utf-8")
        )
        for exchange in exchanges:
            for schedule in exchange.get("workingSchedules") or []:
                schedule_names[int(schedule["id"])] = str(exchange["name"])
    except (OSError, ValueError, TypeError, KeyError):
        pass
    maps: list[dict[str, str]] = []
    for source, symbol_field in sources:
        candidates: dict[str, set[str]] = {}
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
            rows = payload.get("instruments", []) if isinstance(payload, dict) else payload
        except (OSError, ValueError, TypeError):
            rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            isin = _norm_isin(row.get("isin"))
            symbol = _text(row.get(symbol_field)).upper()
            if source.name == "trading212_instruments.json" and schedule_names:
                try:
                    from app.services.finance.trading212_api import yahoo_symbol

                    symbol = _text(yahoo_symbol(row, schedule_names)).upper()
                except Exception:
                    symbol = ""
            if isin and symbol:
                candidates.setdefault(symbol, set()).add(isin)
        maps.append({
            symbol: next(iter(values))
            for symbol, values in candidates.items()
            if len(values) == 1
        })
    return maps[0], maps[1]


def _read_us_isins_file(filename: str) -> dict[str, str]:
    """Lit un fichier de mapping ticker US -> ISIN (format ``{"etfs": {...}}`` ou nu).

    Chaque ISIN est revalidé via ``_norm_isin`` : une valeur invalide n'est jamais
    propagée. Un fichier absent renvoie simplement ``{}``.
    """
    source = Path(Config.TICKERS_CSV).parent / filename
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    if isinstance(payload, dict) and "etfs" in payload and isinstance(payload["etfs"], dict):
        payload = payload["etfs"]
    if not isinstance(payload, dict):
        return {}
    result: dict[str, str] = {}
    for symbol, value in payload.items():
        ticker = _text(symbol).upper().rsplit(".", 1)[0]
        isin = _norm_isin(value)
        if ticker and isin:
            result[ticker] = isin
    return result


def _us_etf_isins() -> dict[str, str]:
    """ISIN US dérivés de CUSIP, pour les ETF US cotés sans suffixe de place.

    Deux sources, dans l'ordre de priorité croissante :
    1. ``us_etf_isins_yf.json`` — repli yfinance (``scripts/import_us_etf_isins_yf.py``),
       pour les tickers absents de la source bulk ;
    2. ``us_etf_isins.json`` — source bulk ``free-ticker-database``
       (``scripts/import_us_etf_isins.py``), ISIN 100 % validés Luhn.

    La source bulk prime : elle est plus autoritaire que le repli yfinance.
    """
    result = _read_us_isins_file("us_etf_isins_yf.json")
    result.update(_read_us_isins_file("us_etf_isins.json"))
    return result


def _read_nonus_isins_file(filename: str) -> dict[str, str]:
    """Lit un mapping ticker Yahoo COMPLET -> ISIN (format ``{"etfs": {...}}`` ou nu).

    Contrairement à ``_read_us_isins_file`` (ETF US sans suffixe de place), la clé
    est ici le symbole Yahoo complet, suffixe compris (ex. ``"1329.T"``), car un
    même nom court peut exister sur plusieurs places avec des ISIN distincts. Une
    valeur invalide n'est jamais propagée ; un fichier absent renvoie ``{}``.
    """
    source = Path(Config.TICKERS_CSV).parent / filename
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    if isinstance(payload, dict) and "etfs" in payload and isinstance(payload["etfs"], dict):
        payload = payload["etfs"]
    if not isinstance(payload, dict):
        return {}
    result: dict[str, str] = {}
    for symbol, value in payload.items():
        ticker = _text(symbol).upper()
        isin = _norm_isin(value)
        if ticker and isin:
            result[ticker] = isin
    return result


def _nonus_etf_isins() -> dict[str, str]:
    """ISIN des ETF non-US (Europe + Asie), dérivés de la source bulk.

    ``scripts/import_nonus_etf_isins.py`` produit ``nonus_etf_isins.json`` à partir
    de ``core_listings.csv`` (filtre ``asset_type == ETF`` + ``country_code != US``),
    en ne retenant que le couple ``(exchange, ticker)`` exact — jamais de
    correspondance par nom (collisions cross-marché). La clé est le symbole Yahoo
    complet, suffixe compris.
    """
    return _read_nonus_isins_file("nonus_etf_isins.json")


def _fee_rate(value: Any) -> float | None:
    raw = _text(value).replace("\u00a0", " ").replace(",", ".")
    match = re.search(r"\d+(?:\.\d+)?", raw)
    if not match:
        return None
    number = float(match.group())
    if "%" in raw or number > 0.02:
        number /= 100.0
    return number if 0 <= number <= 0.05 else None


def _column(columns: Iterable[Any], *names: str):
    available = {str(column).strip().casefold(): column for column in columns}
    return next((available[name.casefold()] for name in names if name.casefold() in available), None)


def replication_method(value: Any) -> str:
    value = _text(value).casefold()
    if any(marker in value for marker in ("synt", "swap", "indirect")):
        return "synthetic"
    if any(
        marker in value
        for marker in (
            "phys", "direct", "sampling", "replication complete",
            "optimised", "optimized", "replicated",
        )
    ):
        return "physical"
    return "unknown"


def infer_replication_from_fund_name(value: Any) -> str:
    """Déduit uniquement les mentions de réplication explicites du nom du fonds.

    Un nom générique d'ETF ne permet pas de conclure qu'il est physique. En
    revanche, ``Swap``/``Synthetic`` et les formulations complètes de réplication
    physique sont des preuves suffisamment fortes pour éviter une requête réseau.
    """
    name = _text(value).casefold()
    if re.search(r"\b(?:swap|synthetic|synthetical|synthétique)\b", name):
        return "synthetic"
    if re.search(
        r"\b(?:physically replicated|physical replication|physical|"
        r"direct replication|full replication|optimized sampling|"
        r"optimised sampling|representative sampling)\b",
        name,
    ):
        return "physical"
    return "unknown"


def canonical_index_name(value: Any) -> str:
    """Normalise l'orthographe sans effacer les variantes économiques.

    ESG, Screened, Capped, Equal Weight, Net/Total Return et la couverture de
    change sont donc conservés dans la clé : deux variantes proches ne seront
    jamais fusionnées par accident.
    """
    value = _text(value)
    if not value:
        return ""
    # Certains catalogues stockent les entités HTML échappées (« S&amp;P »).
    value = html.unescape(value)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.replace("®", "").replace("™", "")
    value = re.sub(r"\s+", " ", value).strip(" -–—:;,.()")
    # Des concaténations de catalogues répètent parfois un même suffixe
    # (« MSCI Pacific ex Japan Min TE Min TE »). Un doublon adjacent n'est
    # jamais une variante économique : on le réduit à une seule occurrence.
    value = re.sub(
        r"\b((?:[A-Za-z0-9&+]){1,8}(?:\s+[A-Za-z0-9&+]{1,8})?)(?:\s+\1)+\b",
        r"\1",
        value,
    )
    return value


_PLACEHOLDER_INDEX_NAMES = {
    "the index", "l'indice", "indice", "index", "benchmark",
    "the benchmark", "reference index", "indice de reference",
    "indice de référence",
}


def reject_placeholder_index(value: Any) -> str:
    """Ignore un « nom d'indice » qui n'en est pas un.

    Certains catalogues renseignent le benchmark avec une valeur factice
    (« the index ») ou laissent le ticker du fonds fuiter dans la colonne
    indice (« SICE.F »). Ces valeurs ne décrivent pas un panier économique.
    """
    name = canonical_index_name(value)
    folded = name.casefold()
    if folded in _PLACEHOLDER_INDEX_NAMES:
        return ""
    if re.fullmatch(r"[A-Z0-9.-]+\.[A-Z]{1,2}", name):
        return ""
    return name


def canonical_index_id(value: Any) -> str:
    name = canonical_index_name(value)
    if not name:
        return ""
    key = name.upper().replace("STANDARD & POOR'S", "S&P").replace("STANDARD AND POOR'S", "S&P")
    key = re.sub(r"[^A-Z0-9&+]+", "-", key).strip("-")
    aliases = {
        "TOPIX-INDEX": "TOPIX",
        "TOKYO-STOCK-PRICE-INDEX-TOPIX": "TOPIX",
    }
    return aliases.get(key, key)


def canonical_constituent_set_id(
    value: Any, *, strip_hedging: bool = True,
) -> str:
    """Identité du panier, indépendante de la convention de rendement.

    Price/Net/Gross Return, la devise, le hedging et les attributs de part
    changent la série ou le fonds, pas ses actions. Les variantes ESG, capped,
    screened, equal weight, momentum, leveraged/inverse, etc. restent distinctes.
    """
    name = canonical_index_name(value).upper()
    if not name:
        return ""
    # Closed vocabulary, not fuzzy similarity: preserve all strategy qualifiers.
    name = re.sub(r"[-–—]+", " ", name)
    name = re.sub(r"\bSTANDARD (?:&|AND) POOR'?S\b|\bS\s*&\s*P\b", "S&P", name)
    for pattern, replacement in (
        (r"\bINDICE\b|\bINDIZES\b", "INDEX"),
        (r"\bRENDEMENT (?:TOTAL )?NET\b", "NET RETURN"),
        (r"\bRENDEMENT (?:TOTAL )?BRUT\b", "GROSS RETURN"),
        (r"\bMSCI MONDE\b", "MSCI WORLD"),
        (r"\bMARCHES EMERGENTS\b", "EMERGING MARKETS"),
        (r"\bMSCI EM\b", "MSCI EMERGING MARKETS"),
        (r"\bMSCI ALL COUNTRY WORLD\b", "MSCI ACWI"),
        (r"\bETATS UNIS\b|\bUNITED STATES\b", "USA"),
        (r"\bPETITES CAPITALISATIONS\b|\bSMALL CAPS\b", "SMALL CAP"),
        (r"\bPONDERATION EGALE\b|\bEQUAL WEIGHTED\b", "EQUAL WEIGHT"),
        (r"\bCOUVERT (?:EN )?(EUR|USD|GBP|CHF|JPY)\b", r"\1 HEDGED"),
    ):
        name = re.sub(pattern, replacement, name)
    # Le nom du fonds ou de sa part se glisse souvent dans le champ benchmark.
    # Ces attributs ne changent pas les actions du panier économique.
    marker = re.search(
        r"\b(?:MSCI|STOXX|S&P|FTSE|NASDAQ|TOPIX|KOSPI|SOLACTIVE|"
        r"MORNINGSTAR|BLOOMBERG|ICE|IBOXX|CAC\s*40|DAX)\b",
        name,
    )
    if marker and marker.start() > 0:
        name = name[marker.start():]
    # ``UCI`` apparaît dans certains libellés tronqués (« MSCI World UCI »).
    name = re.sub(r"\b(?:UCITS|UCI|ETF)\b", " ", name)
    name = re.sub(r"\b(?:SWAP|SYNTHETIC|SYNTHETICAL|PHYSICAL)\b", " ", name)
    name = re.sub(
        r"\b(?:ACC(?:UMULATING|UMULATION)?|DIST(?:RIBUTING|RIBUTION)?)\b",
        " ",
        name,
    )
    if strip_hedging:
        name = re.sub(r"\b(?:EUR|USD|GBP|CHF|JPY)\s+HEDGED\b", " ", name)
    name = re.sub(r"\b(?:SHARE\s+)?CLASS\s+[A-Z0-9]+\b", " ", name)
    # « II » après Swap/nom de part est une génération de fonds, contrairement
    # à 2x/Inverse/Equal Weight qui doivent impérativement rester distincts.
    name = re.sub(r"\bII\s*$", " ", name)
    name = re.sub(r"\b(?:NET|GROSS)\s*(?:TOTAL\s*)?RETURN\b", " ", name)
    name = re.sub(r"\b(?:NET|GROSS)\s+TR\b", " ", name)
    name = re.sub(r"\bNTR\b|\bGTR\b", " ", name)
    name = re.sub(r"\bTR\b", " ", name)
    # Certaines API tronquent la parenthèse finale (« MSCI World Index (Net »).
    # Ce suffixe décrit la convention de rendement, pas un panier différent.
    name = re.sub(r"[\s(\-]+(?:NET|GROSS)\s*$", " ", name)
    name = re.sub(r"\bINDEX\s*$", " ", name)
    name = re.sub(r"\bPRICE(?:\s+RETURN)?\b", " ", name)
    # Price/Performance change le traitement des dividendes, pas les titres.
    name = re.sub(r"\bPERFORMANCE(?:\s+INDEX)?\b", " ", name)
    name = re.sub(r"\bIN\s+(?:EUR|USD|GBP|CHF|JPY)\b", " ", name)
    name = re.sub(r"\(?(?:EUR|USD|GBP|CHF|JPY)\)?\s*$", " ", name)
    name = re.sub(r"\bII\s*$", " ", name)
    name = re.sub(r"\s+", " ", name).strip(" -–—:;,.")
    key = canonical_index_id(name)
    # Liste fermée de supersecteurs STOXX dont les pages émetteurs abrègent le
    # nom en omettant « Capped ». Ne jamais supprimer ce marqueur globalement.
    stoxx_supersectors = {
        "BANKS", "BASIC-RESOURCES", "HEALTH-CARE", "HEALTHCARE",
        "INSURANCE", "TECHNOLOGY", "TELECOMMUNICATIONS", "UTILITIES",
    }
    for sector in stoxx_supersectors:
        if key == f"STOXX-EUROPE-600-{sector}-CAPPED":
            normalized = sector.replace("HEALTHCARE", "HEALTH-CARE")
            return f"STOXX-EUROPE-600-{normalized}"
    if key == "STOXX-EUROPE-600-HEALTHCARE":
        return "STOXX-EUROPE-600-HEALTH-CARE"
    return key


def _looks_like_index(value: str) -> bool:
    upper = value.upper()
    return any(marker in upper for marker in _INDEX_MARKERS)


def infer_index_from_fund_name(value: Any) -> str:
    """Extrait seulement les noms de fonds contenant un marqueur d'indice sûr."""
    name = canonical_index_name(value)
    if not name:
        return ""
    # Le contenu parenthétique est souvent le benchmark exact (ex. TOPIX ou
    # MSCI Emerging Asia), mais seulement s'il ressemble réellement à un indice.
    for candidate in re.findall(r"\(([^)]+)\)", name):
        if _looks_like_index(candidate):
            return canonical_index_name(candidate)
    candidate = name
    # Les noms Yahoo contiennent souvent la coquille juridique avant un tiret :
    # « Amundi Index Solutions - Amundi MSCI World ... ».
    parts = re.split(r"\s+[-–—]\s+", candidate)
    if len(parts) > 1 and _looks_like_index(parts[-1]):
        candidate = parts[-1]
    candidate = _ISSUER_PREFIX.sub("", candidate).lstrip(" -–—")
    candidate = _FUND_SUFFIX.sub("", candidate)
    candidate = re.sub(r"^(?:PEA|CORE)\s+", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(
        r"\s+(?:SWAP|SYNTHETIC|PHYSICAL|PEA)(?:\s+(?:EUR|USD|GBP))?$",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    if not _looks_like_index(candidate):
        return ""
    # La couverture est parfois une propriété de la part et non du nom officiel
    # de l'indice. Elle modifie néanmoins les rendements : elle appartient donc à
    # l'identité économique utilisée pour la déduplication.
    hedge = re.search(r"\b(EUR|USD|GBP|CHF|JPY)\s+HEDGED\b", name, re.IGNORECASE)
    if hedge and "HEDGED" not in candidate.upper():
        candidate = f"{candidate} {hedge.group(1).upper()} Hedged"
    return canonical_index_name(candidate)


def _empty_registry() -> dict:
    return {"version": REGISTRY_VERSION, "funds": {}, "indices": {}}


def _registry_target(path: str | Path | None = None) -> Path:
    return Path(path) if path else DEFAULT_REGISTRY_PATH


def _holdings_file(target: Path, kind: str, identity: str) -> Path:
    digest = hashlib.sha256(f"{kind}:{identity}".encode()).hexdigest()
    return target.with_name(f"{target.stem}_compositions") / f"{kind}-{digest}.json.gz"


def _write_external_holdings(
    target: Path,
    *,
    kind: str,
    identity: str,
    holdings: list[dict],
    previous: dict | None = None,
) -> dict:
    payload = json.dumps(
        holdings, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    content_hash = hashlib.sha256(payload).hexdigest()
    destination = _holdings_file(target, kind, identity)
    previous = previous or {}
    if previous.get("sha256") != content_hash or not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(
            prefix=destination.name, suffix=".tmp", dir=destination.parent,
        )
        try:
            with os.fdopen(handle, "wb") as raw:
                with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as stream:
                    stream.write(payload)
            os.replace(temporary, destination)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise
    return {
        "format": "json.gz",
        "file": os.path.relpath(destination, target.parent).replace("\\", "/"),
        "count": len(holdings),
        "sha256": content_hash,
    }


def _externalize_compositions(registry: dict, target: Path) -> None:
    """Sort les gros paniers du registre avant sa sérialisation."""
    for kind, section in (("fund", "funds"), ("index", "indices")):
        for identity, record in registry.get(section, {}).items():
            if not isinstance(record, dict):
                continue
            composition = record.get("composition")
            if not isinstance(composition, dict):
                continue
            holdings = composition.get("holdings")
            if not isinstance(holdings, list) or len(holdings) < _EXTERNAL_HOLDINGS_MIN_COUNT:
                continue
            composition["holdings_ref"] = _write_external_holdings(
                target,
                kind=kind,
                identity=str(identity),
                holdings=holdings,
                previous=composition.get("holdings_ref"),
            )
            composition["holdings_count"] = len(holdings)
            composition.pop("holdings", None)


def _composition_with_holdings(composition: Any, target: Path) -> dict:
    if not isinstance(composition, dict):
        return {}
    result = dict(composition)
    if isinstance(result.get("holdings"), list):
        return result
    reference = result.get("holdings_ref")
    if not isinstance(reference, dict) or reference.get("format") != "json.gz":
        return result
    relative = str(reference.get("file") or "")
    try:
        source = (target.parent / relative).resolve()
        root = target.parent.resolve()
        if source != root and root not in source.parents:
            return result
        with gzip.open(source, "rt", encoding="utf-8") as stream:
            holdings = json.load(stream)
        if isinstance(holdings, list):
            result["holdings"] = holdings
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    return result


def load_registry(path: str | Path | None = None) -> dict:
    target = _registry_target(path)
    with _registry_io_lock:
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            data = _empty_registry()
    if not isinstance(data, dict):
        data = _empty_registry()
    data.setdefault("funds", {})
    data.setdefault("indices", {})
    # Anciennes versions créaient deux paniers identiques pour TOPIX et
    # TOPIX-INDEX. La migration est volontairement limitée à ces alias sûrs.
    for old_id in ("TOPIX-INDEX", "TOKYO-STOCK-PRICE-INDEX-TOPIX"):
        old = data["indices"].pop(old_id, None)
        if not isinstance(old, dict):
            continue
        current = data["indices"].setdefault("TOPIX", {})
        merged_funds = sorted(set(current.get("funds", [])) | set(old.get("funds", [])))
        merged = {**old, **current, "funds": merged_funds}
        if not merged.get("composition") and old.get("composition"):
            merged["composition"] = old["composition"]
        data["indices"]["TOPIX"] = merged
    for fund in data["funds"].values():
        if isinstance(fund, dict) and fund.get("index_id") in {
            "TOPIX-INDEX", "TOKYO-STOCK-PRICE-INDEX-TOPIX",
        }:
            fund["index_id"] = "TOPIX"
    data["version"] = REGISTRY_VERSION
    data["_storage_path"] = str(target)
    return data


def save_registry(registry: dict, path: str | Path | None = None) -> None:
    """Écriture atomique : une interruption ne peut pas tronquer le cache."""
    target = _registry_target(path or registry.get("_storage_path"))
    with _registry_io_lock:
        _externalize_compositions(registry, target)
        serializable = {
            "version": REGISTRY_VERSION,
            "funds": registry.get("funds", {}),
            "indices": registry.get("indices", {}),
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=target.name, suffix=".tmp", dir=target.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(serializable, stream, ensure_ascii=False, separators=(",", ":"))
            os.replace(temporary, target)
            registry["_storage_path"] = str(target)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise


def merge_registry_records(
    updates: dict,
    *,
    fund_ids: Iterable[str] = (),
    index_ids: Iterable[str] = (),
    path: str | Path | None = None,
) -> None:
    """Fusionne atomiquement les enregistrements produits par des workers réseau.

    Chaque worker enrichit des fonds distincts dans sa copie du registre. La
    fusion sous le verrou d'E/S empêche qu'un worker terminant plus tard écrase
    les résultats déjà sauvegardés par un autre.
    """
    target = _registry_target(path or updates.get("_storage_path"))
    with _registry_io_lock:
        latest = load_registry(target)
        for identity in fund_ids:
            record = updates.get("funds", {}).get(identity)
            if isinstance(record, dict):
                latest["funds"][identity] = record
        for index_id in index_ids:
            record = updates.get("indices", {}).get(index_id)
            if not isinstance(record, dict):
                continue
            current = latest["indices"].get(index_id)
            if isinstance(current, dict):
                merged = {**current, **record}
                merged["funds"] = sorted(
                    set(current.get("funds", [])) | set(record.get("funds", []))
                )
                latest["indices"][index_id] = merged
            else:
                latest["indices"][index_id] = record
        save_registry(latest, target)


def resolve_index_registry(
    tickers: Iterable[str],
    *,
    broker_table=None,
    path: str | Path | None = None,
    persist: bool = True,
) -> dict[str, dict]:
    """Résout les indices demandés et renvoie un dictionnaire par ticker.

    Priorité : valeur explicite ``Indice/Index/Benchmark`` du catalogue, puis
    inférence conservatrice depuis le nom complet. Une résolution déjà enregistrée
    par ISIN est réutilisée : elle n'est pas recalculée à chaque run.
    """
    wanted = {str(ticker).strip().upper() for ticker in tickers if _text(ticker)}
    if not wanted:
        return {}
    if broker_table is None:
        try:
            from .broker_availability import load_broker_table

            broker_table = load_broker_table()
        except Exception:
            broker_table = None

    rows: dict[str, dict] = {}
    if broker_table is not None and not getattr(broker_table, "empty", True):
        ticker_col = _column(broker_table.columns, "Ticker Yahoo Finance", "Ticker")
        if ticker_col is not None:
            selected_rows = broker_table[
                broker_table[ticker_col].map(_text).str.upper().isin(wanted)
            ]
            for _, raw in selected_rows.iterrows():
                ticker = _text(raw.get(ticker_col)).upper()
                if ticker in wanted:
                    rows[ticker] = {str(column).strip(): raw.get(column) for column in broker_table.columns}

    registry = load_registry(path)
    funds = registry["funds"]
    indices = registry["indices"]
    registry_isins = _registry_isins_by_ticker(funds)
    trading212_isins, bourse_direct_isins = _local_broker_isins()
    us_isins = _us_etf_isins()
    nonus_isins = _nonus_etf_isins()
    result: dict[str, dict] = {}
    changed = False
    today = dt.date.today().isoformat()

    from .etf_reference import reference_for

    for ticker in sorted(wanted):
        row = rows.get(ticker, {})
        isin_col = _column(row, "ISIN")
        name_col = _column(row, "Nom", "Name")
        index_col = _column(row, "Indice", "Index", "Benchmark", "Underlying Index")
        replication_col = _column(
            row,
            "Réplication", "Replication", "Méthode de réplication", "Replication Method",
        )
        fee_col = _column(
            row,
            "TER", "Frais de gestion", "Frais courants", "Ongoing Charges",
            "Expense Ratio", "Management Fee",
        )
        raw_catalog_isin = _text(row.get(isin_col)).upper() if isin_col else ""
        catalog_isin = _norm_isin(raw_catalog_isin)
        reference = reference_for(isin=catalog_isin, ticker=ticker)
        reference_isin = _norm_isin(reference.get("isin"))
        base_symbol = ticker.rsplit(".", 1)[0]
        # L'identité d'un fonds ne dépend pas de son drapeau de disponibilité.
        # Exiger ce drapeau créait une dépendance circulaire pour les lignes ETF
        # mal classées. Les maps locales ont déjà écarté tout symbole ambigu.
        local_bd_isin = bourse_direct_isins.get(ticker, "")
        # `trading212_isins` est indexé par le symbole Yahoo COMPLET (court nom +
        # suffixe de place, cf. `_local_broker_isins`) dès qu'un fichier
        # `trading212_exchanges.json` est présent. Chercher seulement le nom court
        # amputé du suffixe ne correspondait donc jamais pour les cotations non-US
        # (ex. "CSPX.L" -> clé "CSPX.L" mais requête "CSPX"), laissant l'ISIN vide.
        # On tente d'abord le symbole complet, puis le nom court en repli (cas des
        # environnements sans fichier de places, où la clé reste le nom court).
        local_t212_isin = trading212_isins.get(ticker, "") or trading212_isins.get(base_symbol, "")
        known_alias_isin = registry_isins.get(ticker, "")
        # Un ISIN peut être lisible directement dans le ticker (ex. "IE00BN4Q1675.SG" :
        # la base EST l'ISIN). Fiable, il comble les fonds dont le catalogue est muet.
        ticker_embedded_isin = _norm_isin(base_symbol)
        # ISIN US dérivé de CUSIP, réservé aux cotations SANS suffixe de place :
        # un ticker européen homonyme ("SPY.L") ne doit jamais hériter de l'ISIN US
        # de son court nom (collision cross-marché).
        us_isin = us_isins.get(base_symbol, "") if "." not in ticker else ""
        # ISIN non-US dérivé de la source bulk (``core_listings.csv``), indexé par
        # le symbole Yahoo COMPLET. Le couple (exchange, ticker) exact de la source
        # est autoritaire pour les ETF européens/asiatiques ; il ne corrige qu'un
        # catalogue broker muet (jamais d'écrasement d'un ISIN catalogue existant).
        nonus_isin = nonus_isins.get(ticker, "")
        local_values = {value for value in (local_bd_isin, local_t212_isin) if value}
        agreed_local_isin = next(iter(local_values)) if len(local_values) == 1 else ""
        # ``us_isin`` (ISIN US dérivé de CUSIP) ne doit corriger qu'un ISIN
        # ABSENT ou NON-US du catalogue broker (collision cross-marché). Il ne
        # doit JAMAIS écraser un ISIN US déjà valide du catalogue : pour SQQQ le
        # catalogue porte US74350P6759 (correct selon yfinance) alors que la
        # source bulk propose US74347G1922 (erroné) — même situation pour IAU.
        catalog_is_us = bool(catalog_isin and catalog_isin.startswith("US"))
        us_isin_corrects = bool(us_isin and not catalog_is_us)
        isin = (
            reference_isin
            or (us_isin if us_isin_corrects else "")
            or catalog_isin
            or nonus_isin
            or ticker_embedded_isin
            or known_alias_isin
            or agreed_local_isin
        )
        isin_source = (
            "manual_reference" if reference_isin
            else "us_cusip" if us_isin_corrects
            else "broker_catalog" if catalog_isin
            else "nonus_bulk" if nonus_isin
            else "ticker_embedded_isin" if ticker_embedded_isin
            else "registry_alias" if known_alias_isin
            else "bourse_direct_api" if agreed_local_isin and local_bd_isin
            else "trading212_api" if agreed_local_isin and local_t212_isin
            else ""
        )
        identity_key = f"ISIN:{isin}" if isin else f"TICKER:{ticker}"
        cached = funds.get(identity_key, {})

        # Purge uniquement cet alias des anciennes identités. Cela répare les
        # associations historiques ticker/ISIN sans effacer les autres places
        # de cotation légitimes du fonds concerné.
        # Une cotation US sans suffixe de place ne doit jamais rester rattachée à
        # un ISIN non-US : une fois l'ISIN US résolu (source CUSIP ou catalogue
        # broker US), ce ticker est purgé des anciens enregistrements (collision
        # cross-marché). Le cas GDX est couvert ici : le catalogue porte déjà
        # US92189F1066, donc ``us_isin_corrects`` est faux, mais l'ISIN US reste
        # autoritaire et doit purger l'ancien IE00BQQP9F84.
        resolved_us_isin = isin if (isin.startswith("US") and "." not in ticker) else ""
        authoritative_isin = reference_isin or resolved_us_isin
        if authoritative_isin:
            for old_key, old_record in list(funds.items()):
                if old_key == identity_key or not isinstance(old_record, dict):
                    continue
                aliases = [str(value).strip().upper() for value in old_record.get("tickers", [])]
                if ticker not in aliases:
                    continue
                old_record["tickers"] = [value for value in aliases if value != ticker]
                old_record.setdefault("identity_conflicts", []).append({
                    "ticker": ticker,
                    "authoritative_isin": authoritative_isin,
                    "detected_at": today,
                })
                changed = True

        explicit = reject_placeholder_index(row.get(index_col)) if index_col else ""
        fund_name = _text(row.get(name_col)) if name_col else ""
        if reference:
            explicit = reject_placeholder_index(reference.get("index_name")) or explicit
            fund_name = _text(reference.get("official_name")) or fund_name
        hedge = re.search(r"\b(EUR|USD|GBP|CHF|JPY)\s+HEDGED\b", fund_name, re.IGNORECASE)
        if explicit and hedge and "HEDGED" not in explicit.upper():
            explicit = f"{explicit} {hedge.group(1).upper()} Hedged"
        inferred = infer_index_from_fund_name(fund_name)
        cached_is_official = _text(cached.get("source")).startswith("issuer_")
        # Une donnée vérifiée chez l'émetteur reste prioritaire sur le catalogue
        # local lors des runs suivantes. Le catalogue explicite peut en revanche
        # corriger une ancienne simple inférence de nom.
        if reference and explicit:
            index_name, source, confidence = explicit, "manual_reference", "high"
        elif cached_is_official and cached.get("index_id"):
            index_name = _text(cached.get("index_name"))
            source = _text(cached.get("source"))
            confidence = _text(cached.get("confidence")) or "high"
        elif explicit:
            index_name, source, confidence = explicit, "catalog_explicit", "high"
        elif cached.get("index_id"):
            index_name = _text(cached.get("index_name"))
            source = _text(cached.get("source")) or "registry_cache"
            confidence = _text(cached.get("confidence")) or "medium"
        elif inferred:
            index_name, source, confidence = inferred, "fund_name_inference", "medium"
        else:
            index_name, source, confidence = "", "unresolved", "low"

        index_id = canonical_index_id(index_name)
        replication = replication_method(reference.get("replication")) if reference else "unknown"
        if replication == "unknown":
            replication = replication_method(row.get(replication_col)) if replication_col else "unknown"
        if replication == "unknown":
            replication = _text(cached.get("replication")) or "unknown"
        if replication == "unknown":
            replication = infer_replication_from_fund_name(fund_name)
        catalog_fee = _fee_rate(row.get(fee_col)) if fee_col else None
        aliases = sorted(set(cached.get("tickers", [])) | {ticker})
        # Conserver les données enrichies attachées à l'ISIN (composition
        # officielle, statut, identifiant produit). Une résolution ultérieure
        # ETF -> indice ne doit mettre à jour que le mapping et surtout pas
        # effacer le panier que le connecteur vient de télécharger.
        record = {
            **cached,
            "isin": isin,
            "isin_source": isin_source or _text(cached.get("isin_source")),
            "tickers": aliases,
            "name": _text(row.get(name_col)) if name_col else _text(cached.get("name")),
            "index_id": index_id,
            "index_name": index_name,
            "replication": replication,
            "source": source,
            "confidence": confidence,
            # La date décrit la résolution ETF -> indice. Elle ne sert pas à
            # dater la composition, laquelle évolue indépendamment.
            "verified_at": cached.get("verified_at") or today,
        }
        if reference:
            record.update({
                "name": fund_name,
                "issuer": _text(reference.get("issuer")),
                "legal_type": _text(reference.get("legal_type")),
                "asset_class": _text(reference.get("asset_class")),
                "official_product_url": _text(reference.get("official_product_url")),
                "evidence_url": _text(reference.get("evidence_url")),
                "verification_status": "manual_verified",
                "verified_at": _text(reference.get("verified_at")) or today,
                "catalog_isin_conflict": catalog_isin if catalog_isin and catalog_isin != isin else "",
            })
        source_candidates = {
            source: candidate
            for source, candidate in {
                "catalog": catalog_isin,
                "us_cusip": us_isin,
                "nonus_bulk": nonus_isin,
                "ticker_embedded_isin": ticker_embedded_isin,
                "registry_alias": known_alias_isin,
                "bourse_direct_api": local_bd_isin,
                "trading212_api": local_t212_isin,
                "manual_reference": reference_isin,
            }.items()
            if candidate
        }
        conflicting = sorted(set(source_candidates.values()) - ({isin} if isin else set()))
        if raw_catalog_isin and not catalog_isin:
            record["invalid_catalog_isin"] = raw_catalog_isin
        elif "invalid_catalog_isin" in record:
            record.pop("invalid_catalog_isin", None)
        if conflicting:
            record["isin_conflicts"] = {
                source: candidate
                for source, candidate in source_candidates.items()
                if candidate != isin
            }
        elif "isin_conflicts" in record:
            record.pop("isin_conflicts", None)
        if catalog_fee is not None and record.get("management_fee_rate") is None:
            record["management_fee_rate"] = catalog_fee
            record["management_fee_source"] = "catalog"
            record["management_fee_checked_at"] = today
        if record != cached:
            funds[identity_key] = record
            changed = True
        if index_id:
            index_record = indices.setdefault(index_id, {"name": index_name, "funds": []})
            index_record["constituent_set_id"] = canonical_constituent_set_id(index_name)
            member = isin or ticker
            new_members = sorted(set(index_record.get("funds", [])) | {member})
            if new_members != index_record.get("funds", []):
                index_record["funds"] = new_members
                changed = True
        result[ticker] = {**record, "identity_key": identity_key}

    if persist and changed:
        save_registry(registry, path)
    return result


def sync_registry_isins_to_broker_workbook(
    broker_table=None,
    *,
    path: str | Path | None = None,
    workbook_path: str | Path | None = None,
) -> dict[str, Any]:
    """Complète et contrôle la colonne ISIN de tous les ETF du classeur broker.

    Les cellules vides ou dotées d'un checksum invalide sont réparées depuis le
    registre. Un conflit entre deux ISIN valides est signalé et conservé, sauf
    lorsqu'une référence manuelle explicitement vérifiée corrige le catalogue.
    """
    from .broker_availability import (
        _find_ticker_col,
        _save_main_sheet,
        find_broker_file,
        load_broker_table,
        reset_etf_cache,
    )

    table = broker_table if broker_table is not None else load_broker_table()
    if table is None or getattr(table, "empty", True):
        return {"rows": 0, "filled": 0, "corrected": 0, "invalid": 0, "conflicts": []}
    ticker_col = _find_ticker_col(table.columns, "Ticker Yahoo Finance")
    isin_col = _column(table.columns, "ISIN")
    etf_col = _column(table.columns, "Secteur 1")
    if ticker_col is None or isin_col is None or etf_col is None:
        return {
            "rows": len(table), "filled": 0, "corrected": 0, "invalid": 0,
            "conflicts": [], "error": "Colonnes Ticker/ISIN/Secteur 1 absentes",
        }

    registry = load_registry(path)
    by_ticker: dict[str, tuple[str, dict]] = {}
    ambiguous: set[str] = set()
    for record in registry.get("funds", {}).values():
        if not isinstance(record, dict):
            continue
        isin = _norm_isin(record.get("isin"))
        if not isin:
            continue
        for alias in record.get("tickers", []):
            ticker = _text(alias).upper()
            previous = by_ticker.get(ticker)
            if previous and previous[0] != isin:
                ambiguous.add(ticker)
            elif ticker:
                by_ticker[ticker] = (isin, record)

    filled = corrected = invalid = 0
    conflicts: list[dict[str, str]] = []
    changed = False
    for index, row in table.iterrows():
        if _text(row.get(etf_col)).upper() != "ETF":
            continue
        ticker = _text(row.get(ticker_col)).upper()
        if not ticker or ticker in ambiguous or ticker not in by_ticker:
            continue
        registry_isin, record = by_ticker[ticker]
        raw = _text(row.get(isin_col)).upper()
        current = _norm_isin(raw)
        manual = str(record.get("verification_status") or "") == "manual_verified"
        if not current:
            table.at[index, isin_col] = registry_isin
            invalid += bool(raw)
            filled += not bool(raw)
            changed = True
        elif current != registry_isin:
            conflicts.append({
                "ticker": ticker, "catalog": current, "registry": registry_isin,
                "registry_source": str(record.get("isin_source") or record.get("source") or ""),
            })
            if manual:
                table.at[index, isin_col] = registry_isin
                corrected += 1
                changed = True

    target = Path(workbook_path or find_broker_file() or "")
    if changed and str(target):
        _save_main_sheet(table, str(target))
        reset_etf_cache()
    return {
        "rows": len(table),
        "filled": filled,
        "corrected": corrected,
        "invalid": invalid,
        "ambiguous": len(ambiguous),
        "conflicts": conflicts,
    }


def index_groups(metadata: dict[str, dict], *, minimum_confidence: str = "medium") -> dict[str, list[str]]:
    order = {"low": 0, "medium": 1, "high": 2}
    minimum = order.get(minimum_confidence, 1)
    groups: dict[str, list[str]] = {}
    for ticker, value in metadata.items():
        index_id = _text(value.get("index_id"))
        constituent_set_id = canonical_constituent_set_id(
            value.get("index_name") or value.get("index"),
            strip_hedging=False,
        )
        confidence = order.get(_text(value.get("confidence")), 0)
        group_id = constituent_set_id or index_id
        if group_id and confidence >= minimum:
            groups.setdefault(group_id, []).append(ticker)
    return groups


def cached_index_composition(
    index_id: str,
    *,
    path: str | Path | None = None,
    max_age_days: int | None = None,
    registry: dict | None = None,
) -> dict | None:
    """Composition mutualisée d'un indice, si elle est encore fraîche."""
    target = _registry_target(path)
    indices = (registry if registry is not None else load_registry(target)).get("indices", {})
    record = indices.get(index_id, {})
    composition = _composition_with_holdings(record.get("composition"), target)
    if not isinstance(composition, dict) or not composition.get("holdings"):
        # Prefer the administrator's authoritative basket identifier.
        provider = str(record.get("provider") or "")
        provider_index_id = str(record.get("provider_index_id") or "")
        composition = next(
            (
                _composition_with_holdings(candidate.get("composition"), target)
                for candidate in indices.values()
                if provider
                and provider_index_id
                and str(candidate.get("provider") or "") == provider
                and str(candidate.get("provider_index_id") or "")
                == provider_index_id
                and isinstance(candidate.get("composition"), dict)
                and (
                    candidate["composition"].get("holdings")
                    or candidate["composition"].get("holdings_ref")
                )
                and str(candidate["composition"].get("source") or "")
                in OFFICIAL_INDEX_COMPOSITION_SOURCES
            ),
            None,
        )
    if not isinstance(composition, dict) or not composition.get("holdings"):
        # Exact closed-vocabulary aliases are also usable, never fuzzy matches.
        # Conflicting official provider IDs always override a name match.
        basket = canonical_constituent_set_id(record.get("name") or index_id)
        for candidate_id, candidate in indices.items():
            if candidate_id == index_id or not candidate.get("composition"):
                continue
            if canonical_constituent_set_id(candidate.get("name") or candidate_id) != basket:
                continue
            if any(record.get(field) and candidate.get(field)
                   and record[field] != candidate[field]
                   for field in ("provider", "provider_index_id")):
                continue
            cached = cached_index_composition(
                candidate_id, path=target, max_age_days=max_age_days,
                registry={"indices": {candidate_id: candidate}},
            )
            if cached and str(cached.get("source") or "") in OFFICIAL_INDEX_COMPOSITION_SOURCES:
                return cached
    if not isinstance(composition, dict) or not composition.get("holdings"):
        return None
    try:
        updated = dt.date.fromisoformat(str(composition.get("updated_at", ""))[:10])
    except ValueError:
        return None
    if max_age_days is None:
        provider = str(composition.get("provider") or record.get("provider") or "")
        source = str(composition.get("source") or "")
        if provider in {"jpx", "nikkei"}:
            max_age_days = int(Config.ETF_INDEX_MONTHLY_MAX_AGE_DAYS)
        elif source == "issuer_index_constituents":
            max_age_days = int(Config.ETF_INDEX_ISSUER_MAX_AGE_DAYS)
        else:
            max_age_days = int(Config.ETF_INDEX_DAILY_MAX_AGE_DAYS)
    if (dt.date.today() - updated).days > max(0, int(max_age_days)):
        return None
    return composition


def cached_fund_composition(
    identity_key: str,
    *,
    path: str | Path | None = None,
    max_age_days: int = 31,
    registry: dict | None = None,
) -> dict | None:
    """Positions économiques propres à un ETF physique.

    Elles ne sont pas mutualisées : un fonds à réplication optimisée peut
    détenir un échantillon différent de l'indice et d'un autre ETF associé.
    """
    target = _registry_target(path)
    record = (registry if registry is not None else load_registry(target)).get("funds", {}).get(identity_key, {})
    composition = _composition_with_holdings(record.get("composition"), target)
    if not isinstance(composition, dict) or not composition.get("holdings"):
        return None
    if str(composition.get("source") or "") != "issuer_fund_holdings":
        return None
    try:
        updated = dt.date.fromisoformat(str(composition.get("updated_at", ""))[:10])
    except ValueError:
        return None
    if (dt.date.today() - updated).days > max(0, int(max_age_days)):
        return None
    return composition


def cached_physical_index_proxy(
    index_id: str,
    *,
    path: str | Path | None = None,
    max_age_days: int = 31,
    minimum_coverage: float = 0.90,
    registry: dict | None = None,
) -> dict | None:
    """Meilleur tracker physique officiel du même panier d'indice.

    Ce repli n'est jamais enregistré comme composition officielle de l'indice :
    un fonds physique peut échantillonner le panier et garder un peu de cash.
    Il fournit néanmoins un proxy économique transparent quand les constituants
    propriétaires sont sous licence. Les variantes ESG/hedged/capped restent
    distinctes; seules les conventions Price/Net/Gross Return sont rapprochées.
    """
    target = _registry_target(path)
    registry_data = registry if registry is not None else load_registry(target)
    index_record = registry_data.get("indices", {}).get(index_id, {})
    target_name = str(index_record.get("name") or index_id)
    target_set = canonical_constituent_set_id(target_name)
    if not target_set:
        return None
    candidates: list[tuple[float, int, str, dict, dict]] = []
    from .leverage_filter import is_leveraged_product

    for identity, fund in registry_data.get("funds", {}).items():
        if is_leveraged_product(str(fund.get("name") or "")):
            continue
        # La preuve autoritaire qu'un fonds est physique est la présence de
        # positions ``issuer_fund_holdings`` (vérifiée plus bas) : un synthétique
        # publie du collatéral, jamais ce libellé. Le champ ``replication`` peut
        # rester ``unknown`` sans invalider la composition ; on n'écarte donc que
        # les synthétiques déclarés.
        if str(fund.get("replication") or "").strip().casefold() == "synthetic":
            continue
        if canonical_constituent_set_id(fund.get("index_name") or "") != target_set:
            continue
        composition = _composition_with_holdings(fund.get("composition"), target)
        if (
            not isinstance(composition, dict)
            or not composition.get("holdings")
            or str(composition.get("source") or "") != "issuer_fund_holdings"
        ):
            continue
        coverage = float(composition.get("coverage") or 0.0)
        if coverage < min(max(float(minimum_coverage), 0.0), 1.0):
            continue
        try:
            updated = dt.date.fromisoformat(str(composition.get("updated_at", ""))[:10])
        except ValueError:
            continue
        if (dt.date.today() - updated).days > max(0, int(max_age_days)):
            continue
        candidates.append((
            coverage,
            len(composition.get("holdings") or []),
            str(updated),
            fund,
            composition,
        ))
    if not candidates:
        return None
    coverage, _count, _updated, fund, composition = max(
        candidates, key=lambda item: (item[0], item[1], item[2])
    )
    tickers = [str(value).strip().upper() for value in fund.get("tickers") or []]
    return {
        **composition,
        "source": "physical_tracker_proxy",
        "coverage": coverage,
        "partial": coverage < 0.999,
        "proxy_ticker": tickers[0] if tickers else "",
        "proxy_isin": str(fund.get("isin") or ""),
        "proxy_index_id": str(fund.get("index_id") or ""),
        "proxy_index_name": str(fund.get("index_name") or ""),
        "proxy_source_url": str(composition.get("source_url") or ""),
        "proxy_warning": (
            "Positions officielles d'un tracker physique du même panier; "
            "proxy économique, pas composition officielle de l'indice."
        ),
    }


def store_index_composition(
    index_id: str,
    holdings: list[dict],
    *,
    source: str,
    reference_ticker: str = "",
    index_name: str = "",
    source_url: str = "",
    provider: str = "",
    provider_index_id: str = "",
    index_isin: str = "",
    as_of: str = "",
    path: str | Path | None = None,
    registry: dict | None = None,
    persist: bool = True,
) -> None:
    """Enregistre une composition une seule fois pour tous les ETF de l'indice."""
    if not index_id or not holdings:
        return
    registry = registry if registry is not None else load_registry(path)
    record = registry["indices"].setdefault(
        index_id,
        {"name": canonical_index_name(index_name), "funds": []},
    )
    record["constituent_set_id"] = canonical_constituent_set_id(
        index_name or record.get("name")
    )
    if provider:
        record["provider"] = str(provider).strip()
    if provider_index_id:
        record["provider_index_id"] = str(provider_index_id).strip()
    if index_isin:
        record["index_isin"] = str(index_isin).strip().upper()
    today = dt.date.today().isoformat()
    record["composition"] = {
        "holdings": holdings,
        "source": source,
        "reference_ticker": str(reference_ticker).strip().upper(),
        "source_url": str(source_url).strip(),
        "provider": str(provider or record.get("provider") or ""),
        "provider_index_id": str(
            provider_index_id or record.get("provider_index_id") or ""
        ),
        "as_of": str(as_of or today),
        "fetched_at": today,
        "updated_at": today,
        "coverage": min(sum(max(float(item.get("weight", 0)), 0.0) for item in holdings), 1.0),
        "partial": sum(max(float(item.get("weight", 0)), 0.0) for item in holdings) < 0.90,
    }
    if persist:
        save_registry(registry, path)


def registry_workbook_frames(registry: dict | None = None):
    """Construit les deux tables auditables du registre d'indices.

    ``ETF_Indices`` décrit la correspondance fonds/indice. Pour éviter toute
    absence silencieuse, ``Indices_Constituants`` contient aussi une ligne de
    statut pour chaque indice synthétique sans composition. Les positions d'un
    tracker physique exact y sont publiées comme ``PROXY_PHYSIQUE`` et jamais
    comme constituants officiels de l'administrateur d'indice.
    """
    import pandas as pd

    data = registry or load_registry()
    registry_target = _registry_target(data.get("_storage_path"))
    from .leverage_filter import is_leveraged_product

    active_funds = {
        identity: fund
        for identity, fund in data.get("funds", {}).items()
        if not is_leveraged_product(str(fund.get("name") or ""))
    }
    # Le pipeline d'exécution accepte aussi un proxy physique exact lorsque la
    # réplication du fonds est encore inconnue (ex. UET5.DE). L'export couvre
    # donc synthétiques + inconnus. Un fonds déjà physique utilise directement
    # ses positions officielles : le recopier comme proxy de lui-même gonflerait
    # inutilement `Indices_Constituants`.
    proxy_candidate_index_ids = {
        str(fund.get("index_id") or "")
        for fund in active_funds.values()
        if str(fund.get("index_id") or "").strip()
        and str(fund.get("replication") or "unknown").strip().lower()
        != "physical"
    }
    # Construire l'index des trackers physiques UNE seule fois. Appeler
    # ``cached_physical_index_proxy`` pour chaque indice rescannait tous les fonds
    # à chaque appel (O(indices × fonds)) et rendait l'export presque interminable.
    proxy_by_constituent_set: dict[str, tuple[tuple[float, int, str], dict]] = {}
    today = dt.date.today()
    for fund in active_funds.values():
        if str(fund.get("replication") or "").strip().casefold() == "synthetic":
            continue
        constituent_set = canonical_constituent_set_id(fund.get("index_name") or "")
        if not constituent_set:
            continue
        composition = _composition_with_holdings(fund.get("composition"), registry_target)
        if (
            not isinstance(composition, dict)
            or not composition.get("holdings")
            or str(composition.get("source") or "") != "issuer_fund_holdings"
        ):
            continue
        coverage = float(composition.get("coverage") or 0.0)
        if coverage < 0.90:
            continue
        try:
            updated = dt.date.fromisoformat(str(composition.get("updated_at") or "")[:10])
        except ValueError:
            continue
        if (today - updated).days > 31:
            continue
        tickers = [str(value).strip().upper() for value in fund.get("tickers") or []]
        proxy = {
            **composition,
            "source": "physical_tracker_proxy",
            "coverage": coverage,
            "partial": coverage < 0.999,
            "proxy_ticker": tickers[0] if tickers else "",
            "proxy_isin": str(fund.get("isin") or ""),
            "proxy_index_id": str(fund.get("index_id") or ""),
            "proxy_index_name": str(fund.get("index_name") or ""),
            "proxy_source_url": str(composition.get("source_url") or ""),
            "proxy_warning": (
                "Positions officielles d'un tracker physique du même panier; "
                "proxy économique, pas composition officielle de l'indice."
            ),
        }
        rank = (coverage, len(composition.get("holdings") or []), str(updated))
        previous = proxy_by_constituent_set.get(constituent_set)
        if previous is None or rank > previous[0]:
            proxy_by_constituent_set[constituent_set] = (rank, proxy)

    physical_proxies: dict[str, dict] = {}
    for index_id in sorted(proxy_candidate_index_ids):
        index_record = data.get("indices", {}).get(index_id, {})
        constituent_set = canonical_constituent_set_id(
            index_record.get("name") or index_id
        )
        candidate = proxy_by_constituent_set.get(constituent_set)
        if candidate is not None:
            physical_proxies[index_id] = candidate[1]
    fund_rows: list[dict] = []
    for identity, fund in sorted(active_funds.items()):
        tickers = fund.get("tickers") or []
        fund_index_id = str(fund.get("index_id") or "")
        index_record = data.get("indices", {}).get(fund_index_id, {})
        index_enrichment = index_record.get("official_enrichment") or {}
        index_composition = _composition_with_holdings(
            index_record.get("composition"), registry_target,
        )
        if str(index_composition.get("source") or "") not in OFFICIAL_INDEX_COMPOSITION_SOURCES:
            index_composition = {}
        proxy_composition = physical_proxies.get(fund_index_id) or {}
        fund_enrichment = fund.get("official_enrichment") or {}
        if index_composition.get("holdings"):
            composition_status = "complete_shared_index"
            composition_coverage = float(
                index_composition.get("coverage")
                or sum(
                    max(float(item.get("weight") or 0.0), 0.0)
                    for item in index_composition.get("holdings") or []
                )
            )
            composition_url = str(index_composition.get("source_url") or "")
            composition_attempt = str(index_composition.get("updated_at") or "")
            composition_error = ""
        elif proxy_composition.get("holdings"):
            composition_status = "proxy_disponible"
            composition_coverage = float(proxy_composition.get("coverage") or 0.0)
            composition_url = str(proxy_composition.get("proxy_source_url") or "")
            composition_attempt = str(proxy_composition.get("updated_at") or "")
            composition_error = ""
        else:
            composition_status = str(fund_enrichment.get("status") or "non_verifie")
            composition_coverage = float(fund_enrichment.get("coverage") or 0.0)
            composition_url = str(fund_enrichment.get("source_url") or "")
            composition_attempt = str(fund_enrichment.get("last_attempt_at") or "")
            composition_error = str(
                index_enrichment.get("error") or fund_enrichment.get("error") or ""
            )
        mapping_status = (
            "FOUND"
            if str(fund.get("index_id") or "").strip()
            else "ERROR"
            if str((fund.get("official_enrichment") or {}).get("status") or "")
            in {"temporary_error", "parse_error", "http_error"}
            else "NOT_FOUND"
        )
        for ticker in tickers or [""]:
            fund_rows.append({
                "Ticker": str(ticker).strip().upper(),
                "ISIN": str(fund.get("isin") or ""),
                "Nom": str(fund.get("name") or ""),
                "Indice_ID": str(fund.get("index_id") or ""),
                "Indice": str(fund.get("index_name") or ""),
                "Statut_Resolution": mapping_status,
                "Erreur_Resolution": str(
                    (fund.get("official_enrichment") or {}).get("error") or ""
                ),
                "Fournisseur_Indice": str(index_record.get("provider") or ""),
                "Identifiant_Fournisseur": str(
                    index_record.get("provider_index_id") or ""
                ),
                "Statut_Indice": str(index_enrichment.get("status") or "non_verifie"),
                "Replication": str(fund.get("replication") or "unknown"),
                "Source": str(fund.get("source") or "unresolved"),
                "Confiance": str(fund.get("confidence") or "low"),
                "Verifie_le": str(fund.get("verified_at") or ""),
                "Source_Indice_URL": str(
                    fund.get("evidence_url") or fund.get("official_product_url") or ""
                ),
                "Identite": identity,
                "Statut_Composition": str(
                    composition_status
                ),
                "Couverture_pct": composition_coverage * 100.0,
                "Source_URL": composition_url,
                "Derniere_tentative": composition_attempt,
                "Erreur_Composition": composition_error,
                "Proxy_Physique": bool(
                    physical_proxies.get(str(fund.get("index_id") or ""))
                ),
                "Proxy_Ticker": str(
                    (physical_proxies.get(str(fund.get("index_id") or "")) or {}).get(
                        "proxy_ticker"
                    ) or ""
                ),
                "Proxy_ISIN": str(
                    (physical_proxies.get(str(fund.get("index_id") or "")) or {}).get(
                        "proxy_isin"
                    ) or ""
                ),
                "Proxy_Source_URL": str(
                    (physical_proxies.get(str(fund.get("index_id") or "")) or {}).get(
                        "proxy_source_url"
                    ) or ""
                ),
                "Frais_gestion_pct": (
                    float(fund["management_fee_rate"]) * 100.0
                    if fund.get("management_fee_rate") is not None
                    else None
                ),
                "Source_frais": str(fund.get("management_fee_source") or ""),
                "Frais_verifies_le": str(
                    fund.get("management_fee_checked_at") or ""
                ),
            })

    # Un ancien enregistrement ``TICKER:...`` peut subsister après résolution
    # de l'ISIN. Un listing ne doit apparaître qu'une fois dans l'audit : garder
    # en priorité l'identité ISIN, puis la composition la mieux résolue.
    fund_frame = pd.DataFrame(fund_rows)
    if not fund_frame.empty:
        status_rank = {
            "complete_shared_index": 4,
            "proxy_disponible": 3,
            "complete": 2,
            "aggregate_complete": 1,
        }
        fund_frame["__isin_rank"] = fund_frame["ISIN"].fillna("").astype(str).str.len().gt(0).astype(int)
        fund_frame["__identity_rank"] = fund_frame["Identite"].fillna("").astype(str).str.startswith("ISIN:").astype(int)
        fund_frame["__status_rank"] = fund_frame["Statut_Composition"].map(status_rank).fillna(0)
        fund_frame = (
            fund_frame.sort_values(
                ["Ticker", "__isin_rank", "__identity_rank", "__status_rank"],
                ascending=[True, False, False, False],
                kind="stable",
            )
            .drop_duplicates("Ticker", keep="first")
            .drop(columns=["__isin_rank", "__identity_rank", "__status_rank"])
        )

    constituent_rows: list[dict] = []
    exported_compositions: dict[tuple[str, str], str] = {}
    for index_id, index in sorted(data.get("indices", {}).items()):
        composition_record = index.get("composition")
        composition = _composition_with_holdings(
            composition_record, registry_target,
        )
        source = str(composition.get("source") or "")
        composition_type = "OFFICIEL"
        if source not in OFFICIAL_INDEX_COMPOSITION_SOURCES:
            composition = physical_proxies.get(index_id) or {}
            source = str(composition.get("source") or "")
            composition_type = "PROXY_PHYSIQUE" if composition else "NON_RESOLU"
        # Conserver aussi une ligne d'audit pour tout indice non résolu. Le
        # classeur doit distinguer explicitement "non trouvé" d'une absence
        # silencieuse, quelle que soit la méthode de réplication de l'ETF.
        constituent_set_id = canonical_constituent_set_id(
            index.get("name") or index_id
        )
        holdings_reference = composition.get("holdings_ref") or {}
        holdings_sha = str(holdings_reference.get("sha256") or "")
        composition_reference_id = ""
        holdings = composition.get("holdings") or []
        if holdings and constituent_set_id:
            # Le SHA du fichier externe identifie exactement le panier. C'est
            # plus sûr qu'un rapprochement de libellés et mutualise aussi les
            # alias dont les noms diffèrent sans fusionner deux variantes ESG.
            composition_key = (
                composition_type,
                f"SHA256:{holdings_sha}" if holdings_sha else constituent_set_id,
            )
            composition_reference_id = exported_compositions.get(
                composition_key, ""
            )
            if composition_reference_id:
                # L'indice reste explicitement présent, mais pointe vers l'unique
                # panier exporté au lieu d'en dupliquer toutes les positions.
                holdings = [{}]
                composition_type = f"{composition_type}_REFERENCE"
            else:
                exported_compositions[composition_key] = index_id
        if not holdings:
            holdings = [{}]
        enrichment = index.get("official_enrichment") or {}
        for holding in holdings:
            constituent_rows.append({
                "Indice_ID": index_id,
                "Indice": str(index.get("name") or ""),
                "Constituent_Set_ID": constituent_set_id,
                "Composition_Reference_ID": composition_reference_id,
                "Type_Composition": composition_type,
                "Statut_Composition": (
                    "complete"
                    if composition_type == "OFFICIEL"
                    else "proxy_disponible"
                    if composition_type == "PROXY_PHYSIQUE"
                    else "complete_reference"
                    if composition_type == "OFFICIEL_REFERENCE"
                    else "proxy_reference"
                    if composition_type == "PROXY_PHYSIQUE_REFERENCE"
                    else str(enrichment.get("status") or "non_verifie")
                ),
                "Ticker": str(holding.get("ticker") or "").strip().upper(),
                "ISIN": str(holding.get("isin") or ""),
                "Nom": str(holding.get("name") or ""),
                "Poids_pct": max(float(holding.get("weight") or 0.0), 0.0) * 100.0,
                "Pays": str(holding.get("country") or ""),
                "Secteur": str(holding.get("sector") or ""),
                "Fournisseur": str(composition.get("provider") or index.get("provider") or ""),
                "Identifiant_Fournisseur": str(
                    composition.get("provider_index_id")
                    or index.get("provider_index_id")
                    or ""
                ),
                "Date_Indice": str(composition.get("as_of") or ""),
                "Source_URL": str(composition.get("source_url") or ""),
                "Source": str(composition.get("source") or ""),
                "Mis_a_jour_le": str(composition.get("updated_at") or ""),
                "Proxy_Ticker": str(composition.get("proxy_ticker") or ""),
                "Proxy_ISIN": str(composition.get("proxy_isin") or ""),
                "Avertissement_Proxy": str(composition.get("proxy_warning") or ""),
                "Erreur": str(enrichment.get("error") or "") if not composition else "",
            })
    return fund_frame, pd.DataFrame(constituent_rows)


def sync_registry_to_broker_workbook(
    *,
    path: str | Path | None = None,
    registry_path: str | Path | None = None,
) -> dict[str, int]:
    """Publie le registre dans ToutBroker sans écrire de pays/défensif ETF."""
    import pandas as pd

    if path is None:
        path = Config.BROKER_ETF_FILE
    if not path:
        return {"etf_indices": 0, "constituants": 0, "anciennes_feuilles_supprimees": 0}
    funds, constituents = registry_workbook_frames(load_registry(registry_path))
    removed = 0
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        for legacy_sheet in ("ETF_Pays", "ETF_Defensif"):
            if legacy_sheet in writer.book.sheetnames:
                writer.book.remove(writer.book[legacy_sheet])
                removed += 1
        funds.to_excel(writer, sheet_name=ETF_INDEX_SHEET, index=False)
        constituents.to_excel(writer, sheet_name=INDEX_CONSTITUENTS_SHEET, index=False)
    from .manual_etf_sources import ensure_manual_sheets
    ensure_manual_sheets(path)
    return {
        "etf_indices": len(funds),
        "constituants": len(constituents),
        "anciennes_feuilles_supprimees": removed,
    }
