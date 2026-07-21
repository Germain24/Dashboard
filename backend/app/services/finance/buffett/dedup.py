"""Dédoublonnage des cross-listings (fuzzy matching sur le nom normalisé)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .config import Config

if TYPE_CHECKING:
    import pandas as pd

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


def drop_correlated(
    returns, volumes: dict, threshold: float = 0.97,
    removable: set | None = None, min_periods: int = 60,
    broker_access: dict | None = None,
) -> tuple[list, list]:
    """Retire itérativement les « jumeaux » fortement corrélés (même indice, émetteurs
    différents) que ni le nom ni l'ISIN n'attrapent.

    Algorithme déterministe : tant qu'il existe une paire de corrélation (signée) ≥
    ``threshold``, on prend la **plus** corrélée et on retire un des deux tickers.
    Corrélation NÉGATIVE = pas un doublon → jamais fusionnée.

    ``broker_access`` (optionnel) : ``{ticker: frozenset[broker]}``, les brokers
    actifs où chaque ticker est disponible. La dispo broker est vérifiée **avant**
    le volume (#bug rapporté : la dédup corrélation ne connaissait que le volume,
    et pouvait retirer le SEUL ticker accessible sur un broker au profit d'un
    jumeau plus liquide mais indisponible chez ce broker — ce broker perdait alors
    toute exposition à l'indice). Règle : on ne retire un ticker que si son
    ensemble de brokers est un **sous-ensemble** de celui du partenaire gardé (donc
    aucun broker n'est perdu) ; à dispo égale, le volume tranche comme avant. Si
    aucun des deux n'est sous-ensemble de l'autre (brokers exclusifs disjoints),
    la paire n'est PAS fusionnée : les deux sont gardés. Sans ``broker_access``,
    comportement inchangé (volume seul, comme avant).

    ``removable`` : si fourni, seules les paires dont les DEUX tickers y figurent
    sont considérées (décision utilisateur : dedup corrélation ENTRE ETF seulement,
    une action n'est jamais retirée ni fusionnée avec un ETF). ``min_periods`` :
    chevauchement minimal (jours) pour qu'une corrélation soit exploitable — deux
    séries qui ne se recouvrent presque pas produisent des corrélations parasites.

    ``returns`` doit déjà être exprimé dans une devise commune (cf. caller : conversion
    EUR), sinon le bruit de change masque l'équivalence. Retourne (kept, removed).
    """
    import numpy as np
    cols = list(returns.columns)
    if len(cols) < 2:
        return cols, []
    # Matrice numpy + masquage : l'ancienne version rescannait TOUTES les paires
    # en `.loc` pandas a chaque retrait (O(n^3)) -- sur ~2200 titres avec des
    # centaines de jumeaux d'ETF, le run restait bloque ici PLUSIEURS HEURES,
    # sans le moindre log (#bug rapporte). Ici : argmax vectorise par retrait.
    c = returns.corr(min_periods=min_periods).to_numpy(dtype=float)
    c = np.where(np.isnan(c), -np.inf, c)
    c[np.tril_indices(len(cols))] = -np.inf   # ne garder que i<j (une fois par paire)
    if removable is not None:
        rem_up = {str(t).upper() for t in removable}
        not_removable = np.array([str(t).upper() not in rem_up for t in cols])
        c[not_removable, :] = -np.inf   # paire consideree seulement si les DEUX
        c[:, not_removable] = -np.inf   # tickers sont des ETF
    removed: list = []   # (ticker_retiré, partenaire_gardé, corrélation)
    dropped: set = set()
    while True:
        flat = int(np.argmax(c))
        i, j = divmod(flat, c.shape[1])
        if not np.isfinite(c[i, j]) or c[i, j] < threshold:
            break
        a, b = cols[i], cols[j]
        if broker_access is not None:
            acc_a = broker_access.get(a, frozenset())
            acc_b = broker_access.get(b, frozenset())
            if acc_a == acc_b:
                k = i if float(volumes.get(a, 0) or 0) <= float(volumes.get(b, 0) or 0) else j
            elif acc_b <= acc_a:      # b n'apporte aucun broker que a n'a pas
                k = j
            elif acc_a <= acc_b:      # symétrique
                k = i
            else:
                # Brokers exclusifs disjoints : retirer l'un ferait perdre
                # l'exposition à cet indice sur un broker actif -> ne pas fusionner.
                c[i, j] = -np.inf
                continue
        else:
            k = i if float(volumes.get(a, 0) or 0) <= float(volumes.get(b, 0) or 0) else j
        partner = cols[j] if k == i else cols[i]
        removed.append((cols[k], partner, round(float(c[i, j]), 4)))
        dropped.add(cols[k])
        c[k, :] = -np.inf
        c[:, k] = -np.inf
    kept = [t for t in cols if t not in dropped]
    return kept, removed


from .currency import SUFFIX_CCY as _SUFFIX_CCY  # source unique (currency.py)


def _ticker_currency(t: str) -> str:
    """Devise de cotation d'un ticker, par SUFFIXE (aucun appel réseau), sauf
    pour `.L` : la LSE cote GBP/GBp/USD selon la ligne -> fast_info yfinance
    (accès par CLÉ : `fast_info.get()` est cassé dans yfinance 1.x et renvoie
    toujours le défaut, cf. yf_session.fast_last_price). Avant : un appel
    yfinance PAR ticker (throttlé ~1,8 s chacun, ~1 h pour 2200 titres) dont le
    résultat était de toute façon perdu par le `.get()` cassé. 'GBp'/'GBX'
    (pence) ramené à 'GBP' (sans effet sur les rendements/corrélations, qui
    sont des ratios)."""
    suf = t.rsplit(".", 1)[1].upper() if "." in t else ""
    cur = None
    if suf == "L":
        try:
            import yfinance as yf
            from app.services.finance.yf_session import yf_session
            fi = yf.Ticker(t, session=yf_session()).fast_info
            try:
                cur = fi["currency"]
            except Exception:
                cur = getattr(fi, "currency", None)
        except Exception:
            cur = None
    if not cur:
        cur = _SUFFIX_CCY.get(suf, "USD")
    cur = str(cur).strip().upper()
    return "GBP" if cur in ("GBP", "GBX") else cur


def _broker_access_sets(df, ticker_col: str) -> dict[str, frozenset[str]]:
    """Brokers actifs (budget > 0) où chaque ticker est disponible.

    Lit les colonnes ajoutées à ``df`` par ``merge_broker_columns`` (nommées
    exactement comme les clés de ``Config.BUDGET_BROKERS`` — cf. son docstring).
    Absence de colonne pour un broker actif -> disponible partout par défaut,
    même convention que ``_is_true``/``prepare_optimization`` dans optimizer.py.
    """
    from .optimizer import _is_true
    active = [b for b, budget in Config.BUDGET_BROKERS.items() if budget > 0]
    cols = [b for b in active if b in df.columns]
    out: dict[str, frozenset[str]] = {}
    for _, row in df.iterrows():
        t = str(row[ticker_col]).strip()
        out[t] = frozenset(b for b in active if b not in cols or _is_true(row[b]))
    return out


def returns_in_base_currency(returns, base_ccy: str = "EUR", *, strict: bool = False):
    """Convertit des rendements de cotation vers ``base_ccy``.

    Fonction partagée par la déduplication et la présélection diversifiée des ETF.
    En cas d'indisponibilité FX, renvoie les rendements natifs sans casser le run.
    """
    import pandas as pd

    cols = list(returns.columns)
    if len(cols) < 1:
        return returns
    try:
        currencies = {t: _ticker_currency(t) for t in cols}
        need = sorted({c for c in currencies.values() if c and c != base_ccy})
        fx_ret: dict = {}
        if need:
            from app.services.finance.yf_session import download_with_timeout, yf_session
            for ccy in need:
                raw = download_with_timeout(
                    tickers=f"{ccy}{base_ccy}=X", period="5y", interval="1d",
                    progress=False, session=yf_session(),
                )
                if raw is None or raw.empty:
                    raise RuntimeError(f"FX {ccy}{base_ccy} indisponible")
                close = raw["Close"]
                close = close.iloc[:, 0] if hasattr(close, "columns") else close
                fx_ret[ccy] = close.pct_change().reindex(returns.index).fillna(0.0)
        conv = {}
        for ticker in cols:
            ccy = currencies[ticker]
            conv[ticker] = returns[ticker] if ccy == base_ccy else (
                (1.0 + returns[ticker]) * (1.0 + fx_ret[ccy]) - 1.0
            )
        return pd.DataFrame(conv, index=returns.index)
    except Exception as exc:
        if strict:
            raise RuntimeError(
                f"Conversion historique obligatoire vers {base_ccy} impossible: {exc}"
            ) from exc
        print(f"[dedup] conversion {base_ccy} impossible ({exc}); corrélation en devise native.")
        return returns


def deduplicate_correlated(returns, df, ticker_col: str = "Ticker Yahoo Finance",
                           threshold: float | None = None, base_ccy: str = "EUR",
                           returns_already_converted: bool = False):
    """Retire les jumeaux d'indice (corrélation ≥ ``threshold``) sur rendements
    **convertis en ``base_ccy``** (sinon le change masque l'équivalence cross-devises).

    Ne s'applique QU'ENTRE ETF (colonne Secteur == ETF, comme deduplicate_tickers) :
    une ACTION n'est jamais retirée pour cause de corrélation, ni fusionnée avec un
    ETF (#bug rapporté : sur fenêtre courte, KIE absorbé par l'action ADBE, NOBL par
    NVO...). L'optimiseur reçoit ensuite les rendements NATIFS des survivants (on ne
    convertit que pour la DÉCISION). Robuste : toute erreur (devise/FX introuvable)
    -> repli sur la corrélation en devise native plutôt que de casser le run.
    """
    import pandas as pd
    if threshold is None:
        threshold = float(Config.CORRELATION_DEDUP_THRESHOLD)
    cols = list(returns.columns)
    if len(cols) < 2:
        return returns
    # volume par ticker (règle de conservation) + ensemble des ETF (seuls candidats
    # au retrait par corrélation)
    vol: dict = {}
    etf_set: set = set()
    try:
        sub = df[[ticker_col, "Volume", "Secteur"]].copy() if "Secteur" in df.columns \
            else df[[ticker_col, "Volume"]].copy()
        sub[ticker_col] = sub[ticker_col].astype(str).str.strip()
        for _, row in sub.iterrows():
            t = row[ticker_col]
            v = row["Volume"]
            vol.setdefault(t, float(v) if pd.notna(v) else 0.0)
            if "ETF" in str(row.get("Secteur", "")).upper():
                etf_set.add(t.upper())
    except Exception:
        vol = {}

    rets_eur = returns if returns_already_converted else returns_in_base_currency(
        returns, base_ccy
    )

    broker_access = _broker_access_sets(df, ticker_col) if df is not None else None
    kept, removed = drop_correlated(rets_eur, vol, threshold, removable=etf_set,
                                     broker_access=broker_access)
    if removed:
        print(f"[dedup] {len(removed)} jumeaux d'indice ETF (corr>={threshold}) retires :")
        for t, partner, c in removed:
            print(f"[dedup]   - {t} (corr {c} avec {partner}, garde)")
    return returns[kept]


def _norm_isin(v) -> str:
    """ISIN nettoyé en MAJ, ou '' si absent / sentinelle yfinance ('-')."""
    s = str(v).strip().upper() if v is not None else ""
    return "" if s in ("", "-", "NAN", "NONE") else s


def deduplicate_tickers(returns, df, ticker_col: str = "Ticker Yahoo Finance") -> "pd.DataFrame":
    """Supprime les cross-listings (même entreprise, plusieurs bourses)."""
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
