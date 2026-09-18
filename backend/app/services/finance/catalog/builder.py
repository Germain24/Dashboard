"""Construction déterministe du catalogue maître depuis des exports officiels."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path

ALLOWED_TYPES = {"EQUITY", "REIT", "ADR", "GDR", "ETF", "ETN", "ETC"}
EXCLUDED_WORDS = {
    "BOND", "NOTE", "OPTION", "WARRANT", "RIGHT", "CERTIFICATE",
    "MUTUAL FUND", "STRUCTURED", "PREFERRED",
}
EURONEXT_MARKET_MIC = {
    "PARIS": "XPAR",
    "AMSTERDAM": "XAMS",
    "BRUSSELS": "XBRU",
    "LISBON": "XLIS",
    "DUBLIN": "XDUB",
    "MILAN": "XMIL",
    "ETF PLUS": "XMIL",
    "OSLO": "XOSL",
    "EUROTLX": "XMIL",
}
ISIN_HOME_MICS = {
    "FR": {"XPAR"},
    "GB": {"XLON"},
    "US": {"XNYS", "XNAS", "XASE"},
    "DE": {"XETR", "XFRA"},
    "IT": {"XMIL"},
    "ES": {"XMAD"},
    "CH": {"XSWX"},
    "NL": {"XAMS"},
    "BE": {"XBRU"},
    "PT": {"XLIS"},
    "IE": {"XDUB"},
    "CA": {"XTSE", "XTSX"},
    "JP": {"XJPX"},
    "HK": {"XHKG"},
    "AU": {"XASX"},
}


class CatalogError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    mic: str
    local_symbol: str
    yahoo_symbol: str
    isin: str = ""
    name: str = ""
    instrument_type: str = "EQUITY"
    currency: str = ""
    primary_market: bool = True
    primary_mic: str = ""
    fundamentals_symbol: str = ""
    source: str = ""
    source_date: str = ""


def load_registry(path: Path | None = None) -> dict:
    path = path or Path(__file__).with_name("markets.json")
    return json.loads(path.read_text(encoding="utf-8"))


def build_yahoo_symbol(local_symbol: str, mic: str, registry: dict | None = None) -> str:
    """Construit une fois le symbole Yahoo depuis le symbole local canonique."""
    markets = (registry or load_registry())["markets"]
    mic = mic.strip().upper()
    if mic not in markets:
        raise CatalogError(f"MIC inconnu: {mic}")
    symbol = str(local_symbol).strip().upper()
    if not symbol:
        raise CatalogError("symbole local vide")
    suffix = markets[mic]["yahoo_suffix"].upper()
    if suffix and symbol.endswith(suffix + suffix):
        raise CatalogError(f"suffixe Yahoo répété: {symbol}")
    if suffix and symbol.endswith(suffix):
        symbol = symbol[: -len(suffix)]
    if mic in {"XSHG", "XSHE"}:
        if not symbol.isdigit():
            raise CatalogError(f"code chinois non numérique: {symbol}")
        symbol = symbol.zfill(6)
    elif mic == "XHKG" and symbol.isdigit():
        symbol = symbol.zfill(4)
    elif mic in {"XNYS", "XNAS", "XASE"}:
        # Yahoo encode les classes US BRK.B/BF.B avec un tiret.
        symbol = re.sub(r"(?<=[A-Z0-9])\.(?=[A-Z]$)", "-", symbol)
    return f"{symbol}{suffix}"


def _normalise_type(raw: str, name: str = "") -> str:
    value = f"{raw} {name}".upper()
    if any(word in value for word in EXCLUDED_WORDS):
        return "EXCLUDED"
    if "REIT" in value or "REAL ESTATE INVESTMENT TRUST" in value:
        return "REIT"
    if "ADR" in value or "AMERICAN DEPOSIT" in value:
        return "ADR"
    if "GDR" in value or "GLOBAL DEPOSIT" in value:
        return "GDR"
    if "ETC" in value:
        return "ETC"
    if "ETN" in value:
        return "ETN"
    if "ETF" in value or "TRACKER" in value or "EXCHANGE TRADED FUND" in value:
        return "ETF"
    return "EQUITY"


def _first(row: dict, *names: str) -> str:
    lower = {str(k).strip().lower(): v for k, v in row.items()}
    for name in names:
        value = lower.get(name.lower())
        if value is not None and str(value).strip() not in {"", "nan", "None"}:
            return str(value).strip()
    return ""


def _canonical_fundamentals_entry(group: list[CatalogEntry]) -> CatalogEntry:
    """Choisit la cotation de référence d'un ISIN, de façon déterministe."""
    declared_primary_mics = {
        entry.primary_mic for entry in group if entry.primary_mic
    }
    isin_country = group[0].isin[:2].upper() if group and group[0].isin else ""
    home_mics = ISIN_HOME_MICS.get(isin_country, set())

    def rank(entry: CatalogEntry) -> tuple[int, int, int, int, str]:
        return (
            int(entry.mic in declared_primary_mics),
            int(entry.primary_market),
            int(entry.mic in home_mics),
            int(entry.mic not in {"XETR", "XFRA"} or isin_country == "DE"),
            entry.yahoo_symbol,
        )

    return max(group, key=rank)


class CatalogBuilder:
    def __init__(self, registry: dict | None = None):
        self.registry = registry or load_registry()
        self.entries: list[CatalogEntry] = []
        self.transformed: list[dict[str, str]] = []
        self.rejected: list[dict[str, str]] = []

    def add_rows(
        self,
        rows: Iterable[dict],
        *,
        mic: str,
        source: str,
        source_date: str | None = None,
        default_type: str = "EQUITY",
    ) -> None:
        for row in rows:
            local = _first(row, "local_symbol", "symbol", "ticker", "code", "epic", "mnemonic")
            name = _first(row, "name", "security name", "company name", "instrument name", "issuer name")
            kind = _normalise_type(_first(row, "type", "instrument type", "category") or default_type, name)
            if not local or kind not in ALLOWED_TYPES:
                self.rejected.append({"symbol": local, "reason": "type_excluded" if local else "missing_symbol"})
                continue
            try:
                yahoo = build_yahoo_symbol(local, mic, self.registry)
            except CatalogError as exc:
                self.rejected.append({"symbol": local, "reason": str(exc)})
                continue
            if yahoo != local.upper():
                self.transformed.append({"mic": mic, "local": local, "yahoo": yahoo})
            primary_mic = _first(
                row,
                "primary mic",
                "primary market mic",
                "primary market mic code",
            ).upper()
            primary_raw = _first(row, "primary market", "primary")
            primary_market = (
                primary_raw.lower() not in {"false", "0", "no"}
                if primary_raw
                else not primary_mic or primary_mic == mic.upper()
            )
            self.entries.append(CatalogEntry(
                mic=mic.upper(),
                local_symbol=local.upper(),
                yahoo_symbol=yahoo,
                isin=_first(row, "isin"),
                name=name,
                instrument_type=kind,
                currency=_first(row, "currency", "trading currency"),
                primary_market=primary_market,
                primary_mic=primary_mic,
                source=source,
                source_date=source_date or date.today().isoformat(),
            ))

    def add_file(self, path: Path, *, mic: str, source: str, default_type: str = "EQUITY") -> None:
        import pandas as pd

        if path.suffix.lower() in {".xlsx", ".xls"}:
            frame = pd.read_excel(
                path,
                engine="calamine" if path.suffix.lower() == ".xls" else None,
            )
        else:
            # Les exports officiels Deutsche Börse commencent par deux lignes
            # de métadonnées ("Market:", "Date:") et sont encodés latin-1.
            # Les lire comme un CSV générique décalerait les colonnes et ferait
            # perdre ISIN + Primary Market MIC Code.
            prefix = path.read_bytes()[:256].decode("latin-1", errors="ignore")
            if mic.upper() in {"XETR", "XFRA"} and prefix.lstrip().startswith("Market:"):
                frame = pd.read_csv(
                    path,
                    sep=";",
                    skiprows=2,
                    encoding="latin-1",
                    dtype=str,
                )
            else:
                # sep=None gère les autres fichiers officiels CSV, TSV et pipe-delimited.
                frame = pd.read_csv(path, sep=None, engine="python", dtype=str)
        rows = frame.fillna("").to_dict("records")
        source_date = date.fromtimestamp(path.stat().st_mtime).isoformat()
        if mic.upper() == "EURONEXT":
            for row in rows:
                market = _first(row, "market").upper()
                resolved_mic = next(
                    (value for token, value in EURONEXT_MARKET_MIC.items() if token in market),
                    "",
                )
                if not resolved_mic or "TRADING AFTER HOURS" in market:
                    self.rejected.append({
                        "symbol": _first(row, "symbol"),
                        "reason": f"unsupported_market:{market or 'missing'}",
                    })
                    continue
                self.add_rows(
                    [row], mic=resolved_mic, source=source,
                    source_date=source_date, default_type=default_type,
                )
        else:
            self.add_rows(
                rows, mic=mic, source=source, source_date=source_date,
                default_type=default_type,
            )

    def build(self) -> list[CatalogEntry]:
        unique: dict[tuple[str, str], CatalogEntry] = {}
        for entry in self.entries:
            key = (entry.mic, entry.local_symbol)
            previous = unique.get(key)
            richer_type = previous is not None and (
                previous.instrument_type == "EQUITY"
                and entry.instrument_type in {"REIT", "ADR", "GDR", "ETF", "ETN", "ETC"}
            )
            if previous is None or (not previous.isin and entry.isin) or richer_type:
                unique[key] = entry
        entries = list(unique.values())
        by_isin: dict[str, list[CatalogEntry]] = {}
        for entry in entries:
            if entry.isin:
                by_isin.setdefault(entry.isin.strip().upper(), []).append(entry)

        resolved: dict[tuple[str, str], CatalogEntry] = {}
        for entry in entries:
            group = by_isin.get(entry.isin.strip().upper(), []) if entry.isin else []
            canonical = _canonical_fundamentals_entry(group) if group else entry
            resolved[(entry.mic, entry.local_symbol)] = replace(
                entry,
                fundamentals_symbol=canonical.yahoo_symbol,
            )
        return sorted(
            resolved.values(),
            key=lambda e: (e.mic, e.local_symbol, e.yahoo_symbol),
        )

    def report(self, old_tickers: Iterable[str] = ()) -> dict:
        built = self.build()
        by_market: dict[str, int] = {}
        by_type: dict[str, int] = {}
        isin_groups: dict[str, list[str]] = {}
        for entry in built:
            by_market[entry.mic] = by_market.get(entry.mic, 0) + 1
            by_type[entry.instrument_type] = by_type.get(entry.instrument_type, 0) + 1
            if entry.isin:
                isin_groups.setdefault(entry.isin, []).append(entry.yahoo_symbol)
        new = {e.yahoo_symbol for e in built}
        old = {str(t).strip().upper() for t in old_tickers if str(t).strip()}
        payload = {
            "catalog_version": self.registry["version"],
            "catalog_checksum": catalog_checksum(built),
            "total": len(built),
            "by_market": dict(sorted(by_market.items())),
            "by_type": dict(sorted(by_type.items())),
            "transformed_count": len(self.transformed),
            "transformed_sample": self.transformed[:100],
            "rejected_count": len(self.rejected),
            "rejected_sample": self.rejected[:100],
            "cross_listed_isin": {k: v for k, v in sorted(isin_groups.items()) if len(v) > 1},
            "added_vs_old": sorted(new - old),
            "removed_vs_old": sorted(old - new),
            "duplicate_yahoo_symbols": sorted(
                symbol for symbol in new if sum(e.yahoo_symbol == symbol for e in built) > 1
            ),
            "unresolved_yahoo_symbols": [],
        }
        return payload


def catalog_checksum(entries: Iterable[CatalogEntry]) -> str:
    canonical = "\n".join(
        json.dumps(asdict(e), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        for e in entries
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def write_catalog_csv(path: Path, entries: Iterable[CatalogEntry]) -> None:
    fields = list(CatalogEntry.__dataclass_fields__)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(asdict(entry) for entry in entries)


def write_legacy_tickers(path: Path, entries: Iterable[CatalogEntry], registry: dict | None = None) -> None:
    markets = (registry or load_registry())["markets"]
    seen: set[str] = set()
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=";", lineterminator="\n")
        for entry in entries:
            if entry.yahoo_symbol in seen:
                continue
            seen.add(entry.yahoo_symbol)
            writer.writerow([
                entry.yahoo_symbol,
                entry.name,
                markets[entry.mic]["name"],
                entry.instrument_type,
            ])
