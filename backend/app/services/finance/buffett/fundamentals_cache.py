"""Cache SQLite incrémental des métadonnées et états financiers."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from io import StringIO
from pathlib import Path

from .config import Config


class FundamentalsCache:
    def __init__(self, path: Path | None = None):
        self.path = path or (Path(Config.DATA_DIR) / "finance_cache.db")

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path, timeout=30)
        con.execute("pragma journal_mode=wal")
        con.executescript(
            """create table if not exists yahoo_metadata (
                 yahoo_symbol text not null,
                 as_of text not null,
                 data_json text not null,
                 primary key (yahoo_symbol, as_of)
               );
               create table if not exists fundamentals (
                 identity_key text not null,
                 yahoo_symbol text not null,
                 fiscal_year integer not null,
                 income_json text,
                 balance_json text,
                 cashflow_json text,
                 updated_at text not null,
                 primary key (identity_key, fiscal_year)
               );
               create index if not exists ix_fundamentals_symbol
                 on fundamentals(yahoo_symbol);"""
        )
        return con

    @staticmethod
    def _identity(ticker: str, info: dict) -> str:
        return str(info.get("isin") or info.get("ISIN") or ticker).strip().upper()

    def save(
        self,
        ticker: str,
        data: dict,
        *,
        identity_key: str | None = None,
    ) -> None:
        import pandas as pd

        info = data.get("info") if isinstance(data.get("info"), dict) else {}
        identity = (
            str(identity_key).strip().upper()
            if identity_key
            else self._identity(ticker, info)
        )
        now = datetime.now(timezone.utc).isoformat()
        years: set[int] = set()
        frames: dict[str, dict[int, str]] = {}
        for key in ("income", "balance", "cashflow"):
            frame = data.get(key)
            by_year: dict[int, str] = {}
            if isinstance(frame, pd.DataFrame) and not frame.empty:
                normalized = frame.copy()
                normalized.index = pd.to_datetime(normalized.index)
                for year, subset in normalized.groupby(normalized.index.year):
                    years.add(int(year))
                    by_year[int(year)] = subset.to_json(
                        orient="split", date_format="iso", default_handler=str
                    )
            frames[key] = by_year
        with self._connect() as con:
            if info:
                con.execute(
                    """insert into yahoo_metadata(yahoo_symbol, as_of, data_json)
                       values (?, ?, ?)
                       on conflict(yahoo_symbol, as_of) do update set data_json=excluded.data_json""",
                    (ticker.upper(), date.today().isoformat(), json.dumps(info, default=str)),
                )
            for year in years:
                con.execute(
                    """insert into fundamentals
                       (identity_key, yahoo_symbol, fiscal_year, income_json,
                        balance_json, cashflow_json, updated_at)
                       values (?, ?, ?, ?, ?, ?, ?)
                       on conflict(identity_key, fiscal_year) do update set
                         yahoo_symbol=excluded.yahoo_symbol,
                         income_json=coalesce(excluded.income_json, fundamentals.income_json),
                         balance_json=coalesce(excluded.balance_json, fundamentals.balance_json),
                         cashflow_json=coalesce(excluded.cashflow_json, fundamentals.cashflow_json),
                         updated_at=excluded.updated_at""",
                    (
                        identity, ticker.upper(), year,
                        frames["income"].get(year), frames["balance"].get(year),
                        frames["cashflow"].get(year), now,
                    ),
                )

    def load(
        self,
        ticker: str,
        *,
        identity_key: str | None = None,
        metadata_symbol: str | None = None,
    ) -> dict | None:
        import pandas as pd

        with self._connect() as con:
            con.row_factory = sqlite3.Row
            metadata = con.execute(
                """select data_json from yahoo_metadata where yahoo_symbol=?
                   order by as_of desc limit 1""",
                (ticker.upper(),),
            ).fetchone()
            if metadata is None and metadata_symbol:
                metadata = con.execute(
                    """select data_json from yahoo_metadata where yahoo_symbol=?
                       order by as_of desc limit 1""",
                    (metadata_symbol.upper(),),
                ).fetchone()
            info = json.loads(metadata["data_json"]) if metadata else {}
            identity = (
                str(identity_key).strip().upper()
                if identity_key
                else self._identity(ticker, info)
            )
            rows = con.execute(
                """select * from fundamentals where identity_key=? or yahoo_symbol=?
                   order by fiscal_year""",
                (identity, ticker.upper()),
            ).fetchall()
        if not metadata and not rows:
            return None
        result: dict = {}
        if metadata:
            result["info"] = info
        for key, column in (
            ("income", "income_json"),
            ("balance", "balance_json"),
            ("cashflow", "cashflow_json"),
        ):
            parts = [
                pd.read_json(StringIO(row[column]), orient="split")
                for row in rows if row[column]
            ]
            if parts:
                frame = pd.concat(parts)
                frame.index = pd.to_datetime(frame.index)
                result[key] = frame[~frame.index.duplicated(keep="last")].sort_index()
        return result or None
