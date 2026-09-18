"""Quarantaine persistante: aucun incident Yahoo ne modifie le catalogue."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import Config

TRANSIENT_KINDS = {"authentication", "network", "timeout", "suspended", "unknown"}


def classify_error(error: BaseException | str | None) -> str:
    text = str(error or "").lower()
    if any(token in text for token in ("401", "crumb", "nonetype", "none type")):
        return "authentication"
    if any(token in text for token in ("dns", "name resolution", "getaddrinfo", "connection")):
        return "network"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "404" in text or "not found" in text or "possibly delisted" in text:
        return "invalid_mapping"
    if any(token in text for token in ("empty financial", "no financial", "données vides", "donnees vides")):
        return "empty_financials"
    return "unknown"


def record_quarantine(
    ticker: str,
    *,
    error_kind: str,
    error: str,
    mic: str = "",
    source: str = "Yahoo Finance",
    database: Path | None = None,
) -> int:
    database = database or (Path(Config.DATA_DIR) / "finance_cache.db")
    database.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(database) as con:
        con.execute(
            """create table if not exists ticker_quarantine (
                yahoo_symbol text primary key,
                mic text not null default '',
                source text not null,
                error_kind text not null,
                last_error text not null,
                first_seen text not null,
                last_seen text not null,
                confirmations integer not null default 1,
                resolved_at text
            )"""
        )
        con.execute(
            """insert into ticker_quarantine
               (yahoo_symbol, mic, source, error_kind, last_error, first_seen, last_seen, confirmations)
               values (?, ?, ?, ?, ?, ?, ?, 1)
               on conflict(yahoo_symbol) do update set
                 mic=excluded.mic, source=excluded.source, error_kind=excluded.error_kind,
                 last_error=excluded.last_error, last_seen=excluded.last_seen,
                 confirmations=ticker_quarantine.confirmations + 1, resolved_at=null""",
            (ticker.upper(), mic, source, error_kind, error, now, now),
        )
        row = con.execute(
            "select confirmations from ticker_quarantine where yahoo_symbol=?", (ticker.upper(),)
        ).fetchone()
    return int(row[0])
