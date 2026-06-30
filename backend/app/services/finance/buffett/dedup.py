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


def drop_correlated(returns, volumes: dict, threshold: float = 0.97) -> tuple[list, list]:
    """Retire itérativement les « jumeaux » fortement corrélés (même indice, émetteurs
    différents) que ni le nom ni l'ISIN n'attrapent.

    Algorithme déterministe : tant qu'il existe une paire de corrélation (signée) ≥
    ``threshold``, on prend la **plus** corrélée et on retire le ticker au **volume le
    plus bas** (à volume égal, le premier dans l'ordre des colonnes). Corrélation
    NÉGATIVE = pas un doublon → jamais fusionnée.

    ``returns`` doit déjà être exprimé dans une devise commune (cf. caller : conversion
    EUR), sinon le bruit de change masque l'équivalence. Retourne (kept, removed).
    """
    import pandas as pd  # noqa: F401
    cols = list(returns.columns)
    if len(cols) < 2:
        return cols, []
    corr = returns.corr()
    kept = list(cols)
    removed: list = []   # (ticker_retiré, partenaire_gardé, corrélation)
    while len(kept) >= 2:
        best = None  # (corr, a, b)
        for i in range(len(kept)):
            for j in range(i + 1, len(kept)):
                a, b = kept[i], kept[j]
                c = corr.loc[a, b]
                if c is None or not (c == c):  # NaN
                    continue
                if c >= threshold and (best is None or c > best[0]):
                    best = (c, a, b)
        if best is None:
            break
        c, a, b = best
        drop = a if float(volumes.get(a, 0) or 0) <= float(volumes.get(b, 0) or 0) else b
        partner = b if drop == a else a
        kept.remove(drop)
        removed.append((drop, partner, round(float(c), 4)))
    return kept, removed


_SUFFIX_CCY = {
    "L": "GBP", "PA": "EUR", "DE": "EUR", "AS": "EUR", "MI": "EUR", "MC": "EUR",
    "BR": "EUR", "LS": "EUR", "VI": "EUR", "HE": "EUR", "IR": "EUR",
    "HK": "HKD", "KS": "KRW", "KQ": "KRW", "T": "JPY", "TO": "CAD", "V": "CAD",
    "SW": "CHF", "ST": "SEK", "OL": "NOK", "CO": "DKK", "SI": "SGD", "AX": "AUD",
}


def _ticker_currency(t: str) -> str:
    """Devise de cotation d'un ticker. fast_info yfinance d'abord (fiable, ex. .L
    peut être USD/GBP/GBp), repli sur le suffixe. 'GBp'/'GBX' (pence) ramené à 'GBP'
    (sans effet sur les rendements/corrélations, qui sont des ratios)."""
    cur = None
    try:
        import yfinance as yf
        from app.services.finance.yf_session import yf_session
        fi = yf.Ticker(t, session=yf_session()).fast_info
        cur = (fi.get("currency") if hasattr(fi, "get") else getattr(fi, "currency", None))
    except Exception:
        cur = None
    if not cur:
        suf = t.rsplit(".", 1)[1].upper() if "." in t else ""
        cur = _SUFFIX_CCY.get(suf, "USD")
    cur = str(cur).strip().upper()
    return "GBP" if cur in ("GBP", "GBX") else cur


def deduplicate_correlated(returns, df, ticker_col: str = "Ticker Yahoo Finance",
                           threshold: float | None = None, base_ccy: str = "EUR"):
    """Retire les jumeaux d'indice (corrélation ≥ ``threshold``) sur rendements
    **convertis en ``base_ccy``** (sinon le change masque l'équivalence cross-devises).

    L'optimiseur reçoit ensuite les rendements NATIFS des survivants (on ne convertit
    que pour la DÉCISION). Robuste : toute erreur (devise/FX introuvable) -> repli sur
    la corrélation en devise native plutôt que de casser le run.
    """
    import pandas as pd
    if threshold is None:
        threshold = float(Config.CORRELATION_DEDUP_THRESHOLD)
    cols = list(returns.columns)
    if len(cols) < 2:
        return returns
    # volume par ticker (règle de conservation)
    vol: dict = {}
    try:
        sub = df[[ticker_col, "Volume"]].copy()
        sub[ticker_col] = sub[ticker_col].astype(str).str.strip()
        for t, v in zip(sub[ticker_col], sub["Volume"]):
            vol.setdefault(t, float(v) if pd.notna(v) else 0.0)
    except Exception:
        vol = {}

    rets_eur = returns
    try:
        currencies = {t: _ticker_currency(t) for t in cols}
        need = sorted({c for c in currencies.values() if c and c != base_ccy})
        if need:
            import yfinance as yf
            from app.services.finance.yf_session import yf_session
            fx_ret: dict = {}
            for ccy in need:
                raw = yf.download(f"{ccy}{base_ccy}=X", period="5y", interval="1d",
                                  progress=False, session=yf_session())
                if raw is None or raw.empty:
                    raise RuntimeError(f"FX {ccy}{base_ccy} indisponible")
                close = raw["Close"]
                close = close.iloc[:, 0] if hasattr(close, "columns") else close
                fx_ret[ccy] = close.pct_change().reindex(returns.index).fillna(0.0)
            conv = {}
            for t in cols:
                ccy = currencies[t]
                if ccy == base_ccy:
                    conv[t] = returns[t]
                else:
                    conv[t] = (1.0 + returns[t]) * (1.0 + fx_ret[ccy]) - 1.0
            rets_eur = pd.DataFrame(conv)
    except Exception as e:
        print(f"[dedup] conversion {base_ccy} impossible ({e}); corrélation en devise native.")
        rets_eur = returns

    kept, removed = drop_correlated(rets_eur, vol, threshold)
    if removed:
        print(f"[dedup] {len(removed)} jumeaux d'indice (corr>={threshold}) retires :")
        for t, partner, c in removed:
            print(f"[dedup]   - {t} (corr {c} avec {partner}, garde)")
    return returns[kept]


def _norm_isin(v) -> str:
    """ISIN nettoyé en MAJ, ou '' si absent / sentinelle yfinance ('-')."""
    s = str(v).strip().upper() if v is not None else ""
    return "" if s in ("", "-", "NAN", "NONE") else s


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

        if is_forced:
            groups[f"_ETF_{t}"] = [(t, vol)]   # ticker forcé : jamais fusionné
            continue
        if is_etf:
            # Les ETF ne sont PAS dédupliqués par similarité FLOUE de nom (deux
            # indices distincts ont des noms proches). Mais deux lignes de cotation
            # du MÊME fonds sont de vrais doublons : on les regroupe par ISIN
            # (identité exacte, colonne ToutBroker curée) ou, à défaut, par nom
            # normalisé EXACT. Les classes Acc/Dist (ISIN différents) restent séparées.
            isin = _norm_isin(row.get("ISIN"))
            if isin:
                key = f"_ETFISIN_{isin}"
            else:
                nrm = normalize(raw)
                key = f"_ETFNAME_{nrm}" if nrm else f"_ETF_{t}"
            groups.setdefault(key, []).append((t, vol))
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
