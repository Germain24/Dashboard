"""Dédoublonnage des cross-listings (fuzzy matching sur le nom normalisé)."""

from __future__ import annotations

import re

from .config import Config

ABBREV: dict[str, str] = {
    " international ": " intl ", " national ": " natl ", " american ": " amer ",
    " european ": " euro ", " technology ": " tech ", " technologies ": " tech ",
    " systems ": " sys ", " semiconductor ": " semi ", " information ": " info ",
    " infrastructure ": " infra ", " engineering ": " eng ",
    " pharmaceutical ": " pharma ", " pharmaceuticals ": " pharma ",
    " healthcare ": " hlth ", " biologics ": " biol ", " medical ": " med ",
    " laboratories ": " lab ", " laboratory ": " lab ", " financial ": " fin ",
    " insurance ": " ins ", " investment ": " invest ", " investments ": " invest ",
    " capital ": " cap ", " manufacturing ": " mfg ", " management ": " mgmt ",
    " corporation ": " corp ", " associates ": " assoc ", " holdings ": " hldg ",
    " properties ": " prop ", " property ": " prop ", " industries ": " ind ",
    " electronics ": " elec ", " electronic ": " elec ", " equipment ": " equip ",
    " environmental ": " envir ", " materials ": " matl ", " chemical ": " chem ",
    " chemicals ": " chem ", " energy ": " engy ", " aerospace ": " aero ",
    " communications ": " comm ", " telecommunication ": " telecom ",
    " telecommunications ": " telecom ", " entertainment ": " entmt ",
    " development ": " dev ", " resources ": " res ", " sciences ": " sci ",
    " transportation ": " transp ", " logistics ": " logis ", " services ": " svc ",
    " service ": " svc ", " markets ": " mkt ", " market ": " mkt ",
}
NOISE = r"\b(incorporated|corporation|limited|holdings?|inc|corp|ltd|plc|nv|ag|se|sa|ab|llc|lp|adr|gdr|drn|spon|unsp|cdi|cedear|ord|del|de|la|the|grp|group|sab|cvr|cv)\b"


def normalize(name: str) -> str:
    s = name.strip().lower()
    s = re.split(r"\s+-\s+", s)[0]
    s = s.replace("-", " ").replace(".", " ").replace("&", " ")
    s = re.sub(r"[\,\(\)\[\]:]+$", "", s).strip()
    s = re.sub(r"\s+", " ", s).strip()
    s = " " + s + " "
    for long_f, short_f in ABBREV.items():
        s = s.replace(long_f, short_f)
    s = re.sub(NOISE, "", s.strip(), flags=re.IGNORECASE)
    s = re.sub(r"\b[a-z]{1,2}\b", "", s)
    s = re.sub(r"\b\d+\b", "", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _lev_ratio(a: str, b: str) -> float:
    if not a and not b: return 1.0
    if not a or not b: return 0.0
    prev = list(range(len(b) + 1))
    for i, c1 in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, c2 in enumerate(b, 1):
            curr[j] = prev[j - 1] if c1 == c2 else 1 + min(prev[j], curr[j - 1], prev[j - 1])
        prev = curr
    return 1.0 - prev[len(b)] / max(len(a), len(b))


def fuzzy_ratio(a: str, b: str) -> float:
    if not a or not b: return 0.0
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb: return 0.0
    if len(ta) == 1 and len(tb) == 1:
        return 1.0 if (a == b and len(a) >= 4) else 0.0
    inter = sorted(ta & tb)
    inter_s = " ".join(inter)
    sa = (inter_s + " " + " ".join(sorted(ta - tb))).strip()
    sb = (inter_s + " " + " ".join(sorted(tb - ta))).strip()
    ts = max(_lev_ratio(inter_s, sa), _lev_ratio(inter_s, sb), _lev_ratio(sa, sb))
    jac = len(ta & tb) / len(ta | tb)
    ns = _lev_ratio(a.replace(" ", ""), b.replace(" ", ""))
    if ns >= 0.90:
        return 0.40 * ts + 0.10 * jac + 0.50 * ns
    return 0.65 * ts + 0.25 * jac + 0.10 * ns


def deduplicate_tickers(returns, df, ticker_col: str = "Ticker Yahoo Finance") -> "pd.DataFrame":
    """Supprime les cross-listings (même entreprise, plusieurs bourses)."""
    import pandas as pd
    cols = list(returns.columns)
    forced_up = [t.upper() for t in Config.FORCED_BUY_TICKERS]
    groups: dict[str, list[tuple[str, float]]] = {}

    for t in cols:
        rows = df[df[ticker_col] == t]
        if rows.empty:
            groups[f"_SOLO_{t}"] = [(t, 0.0)]
            continue
        row = rows.iloc[0]
        raw = str(row.get("Nom", ""))
        vol = float(row.get("Volume", 0))
        is_etf = "ETF" in str(row.get("Secteur", "")).upper()
        is_forced = t.upper() in forced_up

        if is_forced or is_etf:
            groups[f"_ETF_{t}"] = [(t, vol)]
            continue

        norm = normalize(raw)
        found = next(
            (k for k in groups if fuzzy_ratio(norm, k) >= Config.DEDUP_FUZZY_THRESHOLD),
            None,
        )
        if found:
            groups[found].append((t, vol))
        else:
            groups[norm] = [(t, vol)]

    kept = [sorted(g, key=lambda x: x[1], reverse=True)[0][0] for g in groups.values()]
    removed = len(cols) - len(kept)
    if removed:
        print(f"[dedup] {removed} cross-listings supprimés.")
    return returns[kept]
