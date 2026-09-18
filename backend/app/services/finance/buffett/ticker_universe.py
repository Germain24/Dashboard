"""Lecture et validation déterministes de l'univers Buffett."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

_REPEATED_SUFFIX = re.compile(r"(\.[A-Z]{1,5})\1$", re.IGNORECASE)


class TickerCatalogError(RuntimeError):
    """Catalogue absent, vide ou impropre à la création d'un run."""

    def __init__(self, message: str, diagnostics: TickerCatalogDiagnostics):
        super().__init__(message)
        self.diagnostics = diagnostics


@dataclass
class TickerCatalogDiagnostics:
    catalog_path: str
    row_count: int = 0
    ticker_count: int = 0
    encoding_errors: int = 0
    invalid_rows: list[int] = field(default_factory=list)
    invalid_ticker_rows: list[int] = field(default_factory=list)
    duplicate_symbols: list[str] = field(default_factory=list)
    repeated_suffixes: list[str] = field(default_factory=list)
    source_checksum: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TickerCatalog:
    rows: tuple[tuple[str, ...], ...]
    tickers: tuple[str, ...]
    diagnostics: TickerCatalogDiagnostics

    def canonical_bytes(self) -> bytes:
        output = io.StringIO(newline="")
        writer = csv.writer(output, delimiter=";", lineterminator="\n")
        writer.writerows(self.rows)
        return output.getvalue().encode("utf-8")


def read_ticker_catalog(
    csv_path: str | Path,
    *,
    require_canonical: bool = False,
) -> TickerCatalog:
    """Lit le CSV sans laisser une erreur d'encodage devenir un univers vide.

    Les champs descriptifs peuvent être décodés avec remplacement pour produire
    un diagnostic exploitable. Un ticker corrompu est toujours rejeté.
    ``require_canonical`` bloque aussi les octets invalides, doublons et suffixes
    terminaux répétés avant la création d'un nouveau run.
    """
    path = Path(csv_path)
    diagnostics = TickerCatalogDiagnostics(catalog_path=str(path.resolve()))
    if not path.exists():
        raise TickerCatalogError(f"catalogue introuvable: {path}", diagnostics)

    payload = path.read_bytes()
    diagnostics.source_checksum = hashlib.sha256(payload).hexdigest()
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = payload.decode("utf-8-sig", errors="replace")
        diagnostics.encoding_errors = text.count("\ufffd")

    rows: list[tuple[str, ...]] = []
    tickers: list[str] = []
    seen: set[str] = set()
    duplicates: set[str] = set()
    repeated: set[str] = set()
    reader = csv.reader(io.StringIO(text), delimiter=";")
    for line_number, raw_row in enumerate(reader, 1):
        if not raw_row or not any(cell.strip() for cell in raw_row):
            continue
        diagnostics.row_count += 1
        row = tuple(cell.strip() for cell in raw_row)
        ticker = row[0].upper() if row else ""
        if (
            not ticker
            or ticker == "TICKER"
            or "\ufffd" in ticker
            or any(char.isspace() for char in ticker)
        ):
            if ticker not in {"TICKER"}:
                diagnostics.invalid_ticker_rows.append(line_number)
            continue
        if len(row) < 4:
            diagnostics.invalid_rows.append(line_number)
            continue
        normalized = (ticker, *row[1:])
        rows.append(normalized)
        if ticker in seen:
            duplicates.add(ticker)
        else:
            seen.add(ticker)
            tickers.append(ticker)
        if _REPEATED_SUFFIX.search(ticker):
            repeated.add(ticker)

    diagnostics.ticker_count = len(tickers)
    diagnostics.duplicate_symbols = sorted(duplicates)
    diagnostics.repeated_suffixes = sorted(repeated)
    catalog = TickerCatalog(tuple(rows), tuple(tickers), diagnostics)

    blockers: list[str] = []
    if not tickers:
        blockers.append("aucun ticker valide")
    if diagnostics.invalid_ticker_rows:
        blockers.append(f"{len(diagnostics.invalid_ticker_rows)} ticker(s) corrompu(s)")
    if require_canonical:
        if diagnostics.encoding_errors:
            blockers.append(f"{diagnostics.encoding_errors} erreur(s) d'encodage")
        if diagnostics.invalid_rows:
            blockers.append(f"{len(diagnostics.invalid_rows)} ligne(s) invalide(s)")
        if duplicates:
            blockers.append(f"{len(duplicates)} symbole(s) dupliqué(s)")
        if repeated:
            blockers.append(f"{len(repeated)} suffixe(s) répété(s)")
    if blockers:
        raise TickerCatalogError(
            "catalogue invalide: " + ", ".join(blockers),
            diagnostics,
        )
    return catalog
