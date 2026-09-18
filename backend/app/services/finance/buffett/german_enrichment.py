"""Classification hors-ligne + validation Yahoo des instruments allemands
(Xetra `.DE` / Francfurt `.F`) à partir des CSV de référence Deutsche Börse.

Voir orchestration/a-faire/2026-07-22-enrichissement-instruments-allemands-plan.md.

Chaîne : `load_official_maps` (parse les CSV officiels) -> `classify_ticker`
(mnémonique -> type/ISIN/nom, garde ETF/ETN/ETC/CS) -> `probe_symbols`
(endpoint quote v7 groupé, valide + prix/devise) -> `build_rows` (lignes
ToutBroker + tri des invalides) -> `write_tickers_csv` / `upsert_toutbroker`.
"""
from __future__ import annotations

import datetime
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.services.backup_storage import backup_file

# Réutilise la classification ETF par mots-clés du nom (Secteur 2-5).
from scripts.classify_etf_sectors import classify as _classify_etf_name

KEEP_TYPES = {"ETF", "ETN", "ETC", "CS"}
ETF_TYPES = {"ETF", "ETN", "ETC"}

_QUOTE_HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")


# ── Modèles ───────────────────────────────────────────────────────────────
@dataclass
class Official:
    mnemonic: str
    isin: str
    name: str
    instrument_type: str
    market: str  # "Xetra" | "Börse Frankfurt"


@dataclass
class Classified:
    ticker: str
    kind: str          # "Tracker/ETF" | "Action"
    is_etf: bool
    isin: str
    official_name: str
    market: str
    instrument_type: str
    secteur2: str
    secteur3: str
    secteur4: str
    secteur5: str


@dataclass
class Quote:
    symbol: str
    quote_type: str
    price: float | None
    currency: str | None
    long_name: str | None


# ── Task 1 : chargement officiel + classification ─────────────────────────
def _read_official(path: str, market: str) -> dict[str, Official]:
    df = pd.read_csv(path, sep=";", skiprows=2, dtype=str,
                     on_bad_lines="skip", encoding="latin-1")
    out: dict[str, Official] = {}
    for _, r in df.iterrows():
        mn = str(r.get("Mnemonic") or "").strip().upper()
        if not mn or mn == "NAN":
            continue
        out.setdefault(mn, Official(
            mnemonic=mn,
            isin=str(r.get("ISIN") or "").strip(),
            name=str(r.get("Instrument") or "").strip(),
            instrument_type=str(r.get("Instrument Type") or "").strip().upper(),
            market=market,
        ))
    return out


def load_official_maps(xetra_path: str, frankfurt_path: str):
    """(xetra_by_mnemonic, frankfurt_by_mnemonic), clés en MAJUSCULES."""
    return (_read_official(xetra_path, "Xetra"),
            _read_official(frankfurt_path, "Börse Frankfurt"))


def _lookup(ticker: str, xetra: dict, frankfurt: dict) -> Official | None:
    tu = ticker.strip().upper()
    if tu.endswith(".DE"):
        return xetra.get(tu[:-3])
    if tu.endswith(".F"):
        base = tu[:-2]
        return frankfurt.get(base) or xetra.get(base)
    return None


def classify_ticker(ticker: str, xetra: dict, frankfurt: dict) -> Classified | None:
    """None si non apparié ou type hors KEEP_TYPES (BOND/FUN/OTHER/WAR)."""
    off = _lookup(ticker, xetra, frankfurt)
    if off is None or off.instrument_type not in KEEP_TYPES:
        return None
    is_etf = off.instrument_type in ETF_TYPES
    if is_etf:
        s2, s3, s4, s5 = _classify_etf_name(off.name)
        kind = "Tracker/ETF"
    else:
        s2, s3, s4, s5 = "Actions", "", "", ""
        kind = "Action"
    return Classified(
        ticker=ticker.strip(), kind=kind, is_etf=is_etf, isin=off.isin,
        official_name=off.name, market=off.market,
        instrument_type=off.instrument_type,
        secteur2=s2, secteur3=s3, secteur4=s4, secteur5=s5,
    )


# ── Task 2 : sonde Yahoo groupée ──────────────────────────────────────────
def chunked(seq, n: int) -> Iterator[list]:
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def parse_quote_response(payload: dict) -> dict[str, Quote]:
    res = ((payload or {}).get("quoteResponse") or {}).get("result") or []
    out: dict[str, Quote] = {}
    for r in res:
        sym = r.get("symbol")
        if not sym:
            continue
        out[sym] = Quote(
            symbol=sym,
            quote_type=str(r.get("quoteType") or ""),
            price=r.get("regularMarketPrice"),
            currency=r.get("currency"),
            long_name=r.get("longName") or r.get("shortName"),
        )
    return out


def fetch_crumb(session) -> str | None:
    try:
        session.get("https://fc.yahoo.com")
    except Exception:
        pass
    for host in _QUOTE_HOSTS:
        try:
            r = session.get(f"https://{host}/v1/test/getcrumb")
            txt = getattr(r, "text", "") or ""
            if getattr(r, "status_code", 0) == 200 and txt and "html" not in txt.lower():
                return txt.strip()
        except Exception:
            continue
    return None


def probe_symbols(symbols, session=None, chunk_size: int = 50,
                  sleep: float = 0.0, on_batch=None) -> dict[str, Quote]:
    """Valide/typifie une liste de symboles via l'endpoint quote v7 groupé.

    Symbole absent de la réponse = non résolu par Yahoo (invalide/délisté).
    `session=None` -> `yf_session()` (quota global 2 000/min + rotation du projet).
    `on_batch(done, total, found)` : callback de progression optionnel.
    """
    if session is None:
        from app.services.finance.yf_session import yf_session
        session = yf_session()
    crumb = fetch_crumb(session)
    out: dict[str, Quote] = {}
    all_syms = list(symbols)
    done = 0
    for batch in chunked(all_syms, chunk_size):
        params = {"symbols": ",".join(batch)}
        if crumb:
            params["crumb"] = crumb
        payload = None
        for host in _QUOTE_HOSTS:
            try:
                r = session.get(f"https://{host}/v7/finance/quote", params=params)
                if getattr(r, "status_code", 0) == 401:
                    crumb = fetch_crumb(session)      # crumb périmé -> rafraîchir
                    if crumb:
                        params["crumb"] = crumb
                    r = session.get(f"https://{host}/v7/finance/quote", params=params)
                if getattr(r, "status_code", 0) == 200:
                    payload = r.json()
                    break
            except Exception:
                continue
        if payload:
            out.update(parse_quote_response(payload))
        done += len(batch)
        if on_batch:
            on_batch(done, len(all_syms), len(out))
        if sleep:
            time.sleep(sleep)
    return out


# ── Task 3 : construction des lignes ToutBroker ───────────────────────────
def _norm_name(s) -> str:
    return " ".join(str(s or "").strip().upper().split())


def existing_sector_map(df) -> dict[str, tuple[str, str]]:
    """Nom normalisé -> (Secteur GICS, Secteur 1 FR) des lignes existantes non
    vides — sert à recopier le secteur d'un doublon EXACT de nom."""
    out: dict[str, tuple[str, str]] = {}
    if df is None or "Nom" not in df.columns:
        return out
    sec = df["Secteur"] if "Secteur" in df.columns else [None] * len(df)
    sec1 = df["Secteur 1"] if "Secteur 1" in df.columns else [None] * len(df)
    for nom, s, s1 in zip(df["Nom"], sec, sec1):
        key = _norm_name(nom)
        if not key:
            continue
        sv = "" if s is None or str(s) == "nan" else str(s).strip()
        s1v = "" if s1 is None or str(s1) == "nan" else str(s1).strip()
        if sv or s1v:
            out.setdefault(key, (sv, s1v))
    return out


def build_rows(kept, quotes, existing_sector_by_name):
    """(rows prêts pour ToutBroker, tickers invalides absents de `quotes`)."""
    rows: list[dict] = []
    invalid: list[str] = []
    for c in kept:
        if c.ticker not in quotes:
            invalid.append(c.ticker)
            continue
        q = quotes[c.ticker]
        row = {
            "Ticker Yahoo Finance": c.ticker,
            "Nom": q.long_name or c.official_name,
            "ISIN": c.isin,
            "Prix": q.price,
            "Secteur 2": c.secteur2,
            "Secteur 3": c.secteur3,
            "Secteur 4": c.secteur4,
            "Secteur 5": c.secteur5,
        }
        if c.is_etf:
            row["Secteur 1"] = "ETF"
        else:
            gics, gics_fr = existing_sector_by_name.get(
                _norm_name(c.official_name), ("", ""))
            if gics:
                row["Secteur"] = gics
            if gics_fr:
                row["Secteur 1"] = gics_fr
        rows.append(row)
    return rows, invalid


# ── Task 4 : écritures avec backups ───────────────────────────────────────
def _backup(path: str) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    source = Path(path)
    return str(backup_file(
        source,
        category="runtime/finance-buffett",
        filename=f"{source.name}.bak-{ts}",
    ))


def write_tickers_csv(path: str, kind_by_ticker, drop) -> tuple[int, int]:
    """Met à jour Marché/Type (kind_by_ticker[t]=(marché, type)), supprime les
    lignes de `drop`. Backup avant écriture. Retourne (n_maj, n_suppr)."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    _backup(path)
    out: list[str] = []
    n_maj = n_del = 0
    for line in lines:
        if not line.strip():
            continue
        parts = (line.split(";") + ["", "", "", ""])[:4]
        tk = parts[0].strip()
        if tk in drop:
            n_del += 1
            continue
        if tk in kind_by_ticker:
            marche, typ = kind_by_ticker[tk]
            parts[2], parts[3] = marche, typ
            n_maj += 1
        out.append(";".join(parts))
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")
    return n_maj, n_del


def upsert_toutbroker(path: str, rows: list[dict]) -> int:
    """Upsert par `Ticker Yahoo Finance`, préserve les autres feuilles, backup
    avant écriture, invalide le cache ETF. Retourne le nombre de lignes traitées."""
    from .broker_availability import (
        _find_ticker_col, _save_main_sheet, read_broker_excel, reset_etf_cache,
    )
    df = read_broker_excel(path)
    tcol = _find_ticker_col(df.columns, "Ticker Yahoo Finance") or "Ticker Yahoo Finance"
    for col in {k for r in rows for k in r} - {tcol}:
        if col in df.columns:
            df[col] = df[col].astype(object)
    index: dict[str, int] = {}
    for i, k in df[tcol].astype(str).str.strip().items():
        index.setdefault(k, i)
    new_rows: list[dict] = []
    n = 0
    for r in rows:
        tk = str(r.get(tcol, "")).strip()
        if not tk:
            continue
        payload = {k: v for k, v in r.items() if k != tcol}
        if tk in index:
            for col, val in payload.items():
                if col not in df.columns:
                    df[col] = pd.NA
                    df[col] = df[col].astype(object)
                df.at[index[tk], col] = val
        else:
            new_rows.append(r)
        n += 1
    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    _backup(path)
    _save_main_sheet(df, path)
    reset_etf_cache()
    return n
