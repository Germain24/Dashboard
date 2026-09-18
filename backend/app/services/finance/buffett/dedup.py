"""Dédoublonnage déterministe des cross-listings."""

from __future__ import annotations

import re
from dataclasses import dataclass
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
    """Nom d'ÉMETTEUR normalisé. Tronque au premier « - » : les suffixes de
    cotation (« - SPONS ADR », « - Class B ») ne font pas partie de l'identité."""
    return _normalize_core(re.split(r"\s+-\s+", name.strip().lower())[0])


def normalize_fund(name: str) -> str:
    """Nom de FONDS normalisé, nom COMPLET conservé.

    Un ETF ne s'identifie pas par son émetteur mais par son indice, et c'est
    justement ce qui suit le « - » : « Amundi Index Solutions - Amundi CAC 40 ESG »
    et « Amundi Index Solutions - Amundi Russell 2000 » se réduisaient tous deux à
    `amundi index solutions`, si bien que le repli par nom fusionnait quatre
    indices sans rapport. Même chose pour « iShares VII PLC - ... », qui absorbait
    le Core S&P 500 dans un Pacific ex-Japan.

    La troncature garde tout son sens pour les ACTIONS (cf. ``normalize``), où le
    suffixe désigne une ligne de cotation et non un sous-jacent différent.
    """
    return _normalize_core(name.strip().lower())


def _normalize_core(s: str) -> str:
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
    cols = list(returns.columns)
    if len(cols) < 2:
        return cols, []
    # Matrice numpy + masquage : l'ancienne version rescannait TOUTES les paires
    # en `.loc` pandas a chaque retrait (O(n^3)) -- sur ~2200 titres avec des
    # centaines de jumeaux d'ETF, le run restait bloque ici PLUSIEURS HEURES,
    # sans le moindre log (#bug rapporte). Ici : argmax vectorise par retrait.
    c = returns.corr(min_periods=min_periods).to_numpy(dtype=float)
    return _drop_correlated_matrix(
        cols,
        c,
        volumes,
        threshold=threshold,
        removable=removable,
        broker_access=broker_access,
    )


def _drop_correlated_matrix(
    cols: list[str],
    correlation,
    volumes: dict,
    *,
    threshold: float,
    removable: set | None = None,
    broker_access: dict | None = None,
) -> tuple[list[str], list[tuple[str, str, float]]]:
    """Même déduplication que :func:`drop_correlated`, sur une matrice déjà calculée.

    La matrice est toujours copiée : les tours de remplacement des ETF peuvent
    donc rejouer la décision après une exclusion sans recalculer des années de
    corrélations ni altérer le contexte partagé.
    """
    import numpy as np

    if len(cols) < 2:
        return list(cols), []
    c = np.asarray(correlation, dtype=float).copy()
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


@dataclass(frozen=True)
class CorrelatedEtfDedupContext:
    """Corrélations ETF réutilisables pendant les remplacements de composition."""

    all_tickers: tuple[str, ...]
    etf_tickers: tuple[str, ...]
    correlation: object
    volumes: dict[str, float]
    broker_access: dict[str, frozenset[str]]
    threshold: float


def prepare_correlated_etf_dedup(
    returns,
    df,
    ticker_col: str = "Ticker Yahoo Finance",
    *,
    threshold: float | None = None,
) -> CorrelatedEtfDedupContext:
    """Prépare une seule matrice ETF pour tous les tours de remplacement.

    ``returns`` doit déjà être exprimé dans la devise de base. Les actions ne
    sont volontairement pas incluses dans la matrice : elles ne sont jamais
    supprimées par cette règle et leur présence rendait l'ancien calcul carré
    inutilement coûteux.
    """
    import pandas as pd

    limit = float(Config.CORRELATION_DEDUP_THRESHOLD if threshold is None else threshold)
    all_tickers = tuple(str(ticker) for ticker in returns.columns)
    available = set(all_tickers)
    etfs: list[str] = []
    volumes: dict[str, float] = {}
    if df is not None and ticker_col in df.columns:
        for _, row in df.iterrows():
            ticker = str(row.get(ticker_col) or "").strip()
            if not ticker or ticker not in available:
                continue
            try:
                volume = float(row.get("Volume", 0) or 0)
                volumes[ticker] = volume if pd.notna(volume) else 0.0
            except (TypeError, ValueError):
                volumes[ticker] = 0.0
            if "ETF" in str(row.get("Secteur", "") or "").upper():
                etfs.append(ticker)
    etf_tickers = tuple(dict.fromkeys(etfs))
    if len(etf_tickers) >= 2:
        correlation = returns[list(etf_tickers)].corr(min_periods=60).to_numpy(dtype=float)
    else:
        correlation = []
    return CorrelatedEtfDedupContext(
        all_tickers=all_tickers,
        etf_tickers=etf_tickers,
        correlation=correlation,
        volumes=volumes,
        broker_access=_broker_access_sets(df, ticker_col) if df is not None else {},
        threshold=limit,
    )


def apply_correlated_etf_dedup(
    returns,
    context: CorrelatedEtfDedupContext,
    *,
    excluded_tickers: set[str] | None = None,
    log: bool = False,
) -> tuple[object, list[tuple[str, str, float]]]:
    """Applique un contexte pré-calculé après exclusion de représentants invalides."""
    import numpy as np

    excluded = {
        str(ticker).strip().upper()
        for ticker in (excluded_tickers or set())
        if str(ticker).strip()
    }
    active_etfs = [
        ticker for ticker in context.etf_tickers if ticker.upper() not in excluded
    ]
    index = {ticker: i for i, ticker in enumerate(context.etf_tickers)}
    if len(active_etfs) >= 2:
        positions = [index[ticker] for ticker in active_etfs]
        matrix = np.asarray(context.correlation)[np.ix_(positions, positions)]
        kept_etfs, removed = _drop_correlated_matrix(
            active_etfs,
            matrix,
            context.volumes,
            threshold=context.threshold,
            removable=set(active_etfs),
            broker_access=context.broker_access,
        )
    else:
        kept_etfs, removed = active_etfs, []
    kept_etf_set = set(kept_etfs)
    etf_set = set(context.etf_tickers)
    kept = [
        ticker
        for ticker in context.all_tickers
        if ticker.upper() not in excluded
        and (ticker not in etf_set or ticker in kept_etf_set)
    ]
    if log and removed:
        print(
            f"[dedup] {len(removed)} jumeaux d'indice ETF "
            f"(corr>={context.threshold}) retires :"
        )
        for ticker, partner, correlation in removed:
            print(f"[dedup]   - {ticker} (corr {correlation} avec {partner}, garde)")
    return returns[kept], removed


from .currency import SUFFIX_CCY as _SUFFIX_CCY  # source unique (currency.py)


def ticker_currency_raw(t: str) -> str | None:
    """Devise BRUTE telle que Yahoo la renvoie, ou None si indéterminable.

    Conserve la distinction 'GBp'/'GBX' (pence) vs 'GBP' (livres), que
    ``_ticker_currency`` écrase — sans elle, impossible de savoir s'il faut
    diviser un cours londonien par 100. Seules les lignes `.L` justifient un
    appel réseau : la LSE cote GBP, GBp ou USD selon la ligne, alors que les
    autres places se déduisent du suffixe.

    Accès par CLÉ : `fast_info.get()` est cassé dans yfinance 1.x et renvoie
    toujours le défaut (cf. yf_session.fast_last_price).
    """
    suf = t.rsplit(".", 1)[1].upper() if "." in t else ""
    if suf != "L":
        return None
    try:
        import yfinance as yf

        from app.services.finance.yf_session import yf_session
        fi = yf.Ticker(t, session=yf_session()).fast_info
        try:
            return fi["currency"]
        except Exception:
            return getattr(fi, "currency", None)
    except Exception:
        return None


def currency_from_raw(t: str, raw: str | None) -> str:
    """Devise normalisée à partir d'une devise brute DÉJÀ obtenue.

    Séparée du fetch pour qu'un appelant qui a besoin des deux (la devise pour
    le taux de change ET la distinction pence pour le facteur de prix) n'ait pas
    à interroger Yahoo deux fois pour le même ticker.

    'GBp'/'GBX' (pence) est ramené à 'GBP' : sans effet sur les rendements et
    corrélations, qui sont des ratios.
    """
    suf = t.rsplit(".", 1)[1].upper() if "." in t else ""
    cur = str(raw or _SUFFIX_CCY.get(suf, "USD")).strip().upper()
    return "GBP" if cur in ("GBP", "GBX") else cur


def _ticker_currency(t: str) -> str:
    """Devise de cotation d'un ticker, par SUFFIXE (aucun appel réseau), sauf
    pour `.L` (cf. ``ticker_currency_raw``). Avant : un appel yfinance PAR
    ticker (inutilement coûteux sur un grand univers) dont le résultat était de
    toute façon perdu par le `.get()` cassé."""
    return currency_from_raw(t, ticker_currency_raw(t))


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
                inverse = False
                if raw is None or raw.empty:
                    raw = download_with_timeout(
                        tickers=f"{base_ccy}{ccy}=X", period="5y", interval="1d",
                        progress=False, session=yf_session(),
                    )
                    inverse = raw is not None and not raw.empty
                if raw is not None and not raw.empty:
                    close = raw["Close"]
                    close = close.iloc[:, 0] if hasattr(close, "columns") else close
                    rate = (1.0 / close) if inverse else close
                    source = "Yahoo inverse" if inverse else "Yahoo"
                else:
                    from app.services.finance.fx import get_historical_rates

                    rate = get_historical_rates(ccy, base_ccy)
                    source = "ECB"
                if rate is None or rate.empty:
                    raise RuntimeError(
                        f"FX {ccy}{base_ccy} indisponible via Yahoo direct/inverse et ECB"
                    )
                rate = rate.reindex(rate.index.union(returns.index)).sort_index().ffill()
                rate = rate.reindex(returns.index)
                if rate.notna().sum() < 2:
                    raise RuntimeError(f"FX {ccy}{base_ccy} historique insuffisant")
                fx_ret[ccy] = rate.pct_change(fill_method=None).fillna(0.0)
                if source != "Yahoo":
                    print(f"[dedup] FX {ccy}->{base_ccy} fourni par {source}.")
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
    if threshold is None:
        threshold = float(Config.CORRELATION_DEDUP_THRESHOLD)
    cols = list(returns.columns)
    if len(cols) < 2:
        return returns
    rets_eur = returns if returns_already_converted else returns_in_base_currency(
        returns, base_ccy
    )
    context = prepare_correlated_etf_dedup(
        rets_eur,
        df,
        ticker_col,
        threshold=threshold,
    )
    filtered, _ = apply_correlated_etf_dedup(
        returns,
        context,
        log=True,
    )
    return filtered


def deduplicate_same_index(
    returns,
    df,
    ticker_col: str = "Ticker Yahoo Finance",
    *,
    broker_table=None,
    registry_path=None,
):
    """Garde le meilleur ETF par indice exact et broker, avant la corrélation.

    Une cotation n'est retirée que si tous ses brokers sont déjà couverts par un
    autre fonds du même indice. Pour chaque broker, le TER/OCF officiel le plus
    faible prime; le volume ne départage que les coûts égaux ou inconnus. Deux
    fonds disponibles sur des brokers disjoints restent donc tous les deux
    investissables. Les variantes ESG, hedgées, capped/equal-weight, etc. ont des
    ``index_id`` différents et ne sont jamais fusionnées ici.
    """
    import pandas as pd

    from .etf_index_registry import index_groups, resolve_index_registry

    columns = list(returns.columns)
    if len(columns) < 2:
        return returns
    etf_tickers: set[str] = set()
    volumes: dict[str, float] = {}
    if df is not None and ticker_col in df.columns:
        for _, row in df.iterrows():
            ticker = str(row.get(ticker_col) or "").strip()
            if not ticker:
                continue
            if "ETF" in str(row.get("Secteur", "")).upper():
                etf_tickers.add(ticker.upper())
            try:
                value = float(row.get("Volume", 0) or 0)
                volumes[ticker] = value if pd.notna(value) else 0.0
            except (TypeError, ValueError):
                volumes[ticker] = 0.0
    candidates = [ticker for ticker in columns if str(ticker).upper() in etf_tickers]
    if len(candidates) < 2:
        return returns
    metadata = resolve_index_registry(
        candidates,
        broker_table=broker_table,
        path=registry_path,
    )
    groups = index_groups(metadata)
    duplicate_members = sorted({
        ticker
        for members in groups.values()
        if len(members) > 1
        for ticker in members
    })
    # Le catalogue ne porte pas le TER. On ne contacte donc les émetteurs que
    # pour les indices réellement dupliqués, une fois par ISIN puis via le cache.
    # Les tests à registre temporaire restent entièrement déterministes.
    if duplicate_members and registry_path is None:
        try:
            from .official_etf_enrichment import enrich_official_etfs

            enrich_official_etfs(duplicate_members, broker_table=broker_table)
            metadata = resolve_index_registry(
                candidates,
                broker_table=broker_table,
                path=registry_path,
            )
            groups = index_groups(metadata)
        except Exception as exc:
            print(f"[dedup] frais officiels ETF indisponibles ({exc}); repli volume")
    access = _broker_access_sets(df, ticker_col)
    dropped: set[str] = set()
    removed: list[tuple[str, str, str]] = []

    for index_id, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        def ranking_key(ticker: str) -> tuple[bool, float, float, str]:
            raw_fee = metadata.get(ticker, {}).get("management_fee_rate")
            try:
                fee = float(raw_fee)
                known = fee >= 0 and fee == fee
            except (TypeError, ValueError):
                fee, known = float("inf"), False
            return (
                not known,
                fee if known else float("inf"),
                -float(volumes.get(ticker, 0.0) or 0.0),
                ticker,
            )

        brokers = sorted({broker for ticker in members for broker in access.get(ticker, ())})
        kept_set: set[str] = set()
        winner_by_broker: dict[str, str] = {}
        for broker in brokers:
            available = [ticker for ticker in members if broker in access.get(ticker, ())]
            if not available:
                continue
            winner = min(available, key=ranking_key)
            kept_set.add(winner)
            winner_by_broker[broker] = winner
        if not kept_set:
            kept_set.add(min(members, key=ranking_key))
        for ticker in members:
            if ticker in kept_set:
                continue
            ticker_brokers = access.get(ticker, frozenset())
            replacement = next(
                (
                    winner_by_broker[broker]
                    for broker in sorted(ticker_brokers)
                    if broker in winner_by_broker
                ),
                min(kept_set, key=ranking_key),
            )
            dropped.add(ticker)
            removed.append((ticker, replacement, index_id))

    if removed:
        print(f"[dedup] {len(removed)} ETF du même indice exact retirés :")
        for ticker, replacement, index_id in removed[:30]:
            removed_fee = metadata.get(ticker, {}).get("management_fee_rate")
            kept_fee = metadata.get(replacement, {}).get("management_fee_rate")
            fee_note = (
                f", frais {float(removed_fee) * 100:.3f}% -> "
                f"{float(kept_fee) * 100:.3f}%"
                if removed_fee is not None and kept_fee is not None
                else ", frais indisponibles: départage volume"
            )
            print(
                f"[dedup]   - {ticker} = {replacement} "
                f"({index_id}{fee_note})"
            )
    return returns[[ticker for ticker in columns if ticker not in dropped]]


def _norm_isin(v) -> str:
    """ISIN nettoyé en MAJ, ou '' si absent / sentinelle yfinance ('-')."""
    s = str(v).strip().upper() if v is not None else ""
    return "" if s in ("", "-", "NAN", "NONE") else s


def _norm_score(v) -> float | None:
    """Score ``Chance MOAT`` arrondi au centième, ou None si absent / illisible.

    L'arrondi est indispensable : le score transite par Excel et la base, et deux
    lignes du même émetteur peuvent différer au 12e chiffre significatif.
    """
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else round(f, 2)  # f != f : NaN


class _UnionFind:
    """Union-find sur des tickers, avec compression de chemin.

    Permet de fusionner selon PLUSIEURS relations indépendantes (ISIN, puis
    nom+score) là où un groupement par clé unique obligeait à n'en choisir
    qu'une seule — et perdait donc les rapprochements de l'autre.
    """

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def add(self, x: str) -> None:
        self._parent.setdefault(x, x)

    def find(self, x: str) -> str:
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != root:
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a: str, b: str) -> bool:
        """Fusionne et renvoie True si les deux étaient bien dans des groupes distincts."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self._parent[rb] = ra
        return True


def deduplicate_tickers(returns, df, ticker_col: str = "Ticker Yahoo Finance") -> pd.DataFrame:
    """Supprime les cross-listings (même entreprise, plusieurs bourses).

    Deux relations sont appliquées, dans cet ordre, sur une union-find :

    1. **Même ISIN non vide.** L'identité officielle, quand elle est renseignée.
    2. **Même nom normalisé exact ET même score ``Chance MOAT``** (actions
       uniquement).

    La relation 2 existe parce que l'ISIN manque sur ~36 % de l'univers, et
    précisément sur les cotations PRINCIPALES (``BBVA.MC``, ``MC.PA``, ``SAN.MC``,
    ``GOOGL``, ``ORNBV.HE``…). Grouper par ISIN seul laissait donc passer deux fois
    la même entreprise — ``BBVA.MC`` (ISIN vide) et ``BVA.L`` (ES0113211835) se
    retrouvaient tous deux dans le portefeuille, cumulant 12,9 % et franchissant
    ainsi le plafond par ligne.

    Le **score** est ce qui rend la fusion par nom sûre. Il est calculé une fois
    par ``fundamentals_symbol`` puis propagé à toutes les cotations de l'émetteur :
    les 7 lignes de BBVA valent toutes 94,43. Deux sociétés réellement distinctes
    que ``normalize`` rapprocherait (« Orion Oyj » / « Orion Corporation ») n'ont
    pratiquement jamais le même score au centième. Fusionner sur le nom SEUL serait
    au contraire dangereux, ``NOISE`` retirant sa/inc/plc/de… Un score absent agit
    en joker (il rejoint le groupe de nom sans pouvoir le scinder), ce qui préserve
    le comportement sur les catalogues dépourvus de la colonne.

    Les ETF gardent l'ancienne règle (ISIN, sinon nom normalisé exact) : leur score
    vaut 200 par convention pour tous, le garde-fou y serait inopérant, et deux
    indices distincts ont des noms proches.

    Un rapprochement flou global a été retiré : il rendait ce passage quadratique
    et pouvait immobiliser la préparation pendant des dizaines de minutes.
    """
    cols = list(returns.columns)
    forced_up = [t.upper() for t in Config.FORCED_BUY_TICKERS]

    # Indexer les métadonnées une seule fois. L'ancienne recherche
    # ``df[df[ticker_col] == t]`` rescannait les ~15 000 lignes pour chacun des
    # ~15 000 tickers.
    rows_by_ticker: dict[str, object] = {}
    if df is not None and ticker_col in df.columns:
        for _, candidate in df.iterrows():
            key = str(candidate.get(ticker_col, "")).strip()
            if key:
                rows_by_ticker[key] = candidate

    uf = _UnionFind()
    entries: dict[str, tuple[float, bool]] = {}  # ticker -> (volume, place principale)
    isin_edges: dict[str, str] = {}              # clé ISIN -> premier ticker vu
    # (type, nom) -> {"first": 1er ticker vu, "by_score": {score arrondi: 1er ticker}}
    name_groups: dict[tuple[str, str], dict] = {}
    name_pairs: list[tuple[str, str, str]] = []  # fusions apportées par le nom seul

    for t in cols:
        uf.add(t)
        row = rows_by_ticker.get(str(t).strip())
        if row is None:
            entries[t] = (0.0, False)
            continue  # métadonnées absentes : jamais fusionné
        raw = str(row.get("Nom", ""))
        try:
            vol = float(row.get("Volume", 0))
            if vol != vol:  # NaN
                vol = 0.0
        except (TypeError, ValueError):
            vol = 0.0
        primary_raw = row.get("Primary Market", row.get("primary_market", False))
        is_primary = (
            bool(primary_raw)
            if isinstance(primary_raw, bool)
            else str(primary_raw).strip().lower() in {"1", "true", "yes", "oui", "vrai"}
        )
        entries[t] = (vol, is_primary)

        if t.upper() in forced_up:
            continue  # ticker forcé : jamais fusionné
        is_etf = "ETF" in str(row.get("Secteur", "")).upper()
        isin = _norm_isin(row.get("ISIN"))
        kind = "ETF" if is_etf else "STOCK"

        if isin:
            isin_edges.setdefault(f"{kind}:{isin}", t)
        # Un ETF s'identifie par son INDICE, une action par son émetteur.
        norm = normalize_fund(raw) if is_etf else normalize(raw)
        if not norm:
            continue
        if is_etf and isin:
            continue  # repli ETF : nom exact, et seulement à défaut d'ISIN
        group = name_groups.setdefault((kind, norm), {"first": t, "by_score": {}})
        score = None if is_etf else _norm_score(row.get("Chance MOAT"))
        if score is not None:
            group["by_score"].setdefault(score, t)

    # 1re passe : l'ISIN. On l'applique d'abord pour que la 2e passe puisse
    # rapporter exactement ce qu'elle apporte EN PLUS.
    for t in cols:
        row = rows_by_ticker.get(str(t).strip())
        if row is None or t.upper() in forced_up:
            continue
        isin = _norm_isin(row.get("ISIN"))
        if not isin:
            continue
        kind = "ETF" if "ETF" in str(row.get("Secteur", "")).upper() else "STOCK"
        uf.union(isin_edges[f"{kind}:{isin}"], t)

    # 2e passe : nom + score. On journalise les fusions RÉELLEMENT nouvelles,
    # celles que l'ISIN seul ne faisait pas — c'est le correctif à auditer.
    for t in cols:
        row = rows_by_ticker.get(str(t).strip())
        if row is None or t.upper() in forced_up:
            continue
        raw = str(row.get("Nom", ""))
        is_etf = "ETF" in str(row.get("Secteur", "")).upper()
        norm = normalize_fund(raw) if is_etf else normalize(raw)
        if not norm:
            continue
        isin = _norm_isin(row.get("ISIN"))
        if is_etf and isin:
            continue
        group = name_groups.get(("ETF" if is_etf else "STOCK", norm))
        if group is None:
            continue
        score = None if is_etf else _norm_score(row.get("Chance MOAT"))
        if score is None:
            # Sans score, le nom seul décide — et `normalize` est grossier : il
            # retire les chiffres, si bien que « Company 1 » et « Company 2 » se
            # confondent. Ce repli reste donc cantonné à son périmètre d'origine,
            # les lignes SANS ISIN (anciens catalogues, NVO / NOVO-B.CO). Une
            # ligne déjà identifiée par son ISIN n'a pas besoin de lui.
            if isin:
                continue
            twin = group["first"]
        else:
            # Score présent des DEUX côtés : discriminant suffisant pour fusionner
            # même quand un ISIN est là, car c'est justement le cas BBVA.MC (ISIN
            # vide) / BVA.L (ES0113211835).
            twin = group["by_score"][score]
        if uf.union(twin, t):
            name_pairs.append((t, twin, raw))

    # Composantes dans l'ordre de première apparition, comme l'ancien groupement.
    components: dict[str, list[tuple[str, float, bool]]] = {}
    for t in cols:
        vol, is_primary = entries[t]
        components.setdefault(uf.find(t), []).append((t, vol, is_primary))

    # La place principale officielle prime toujours. Le volume ne tranche
    # qu'entre lignes de même statut (catalogues anciens sans ce champ inclus).
    #
    # Une composante peut toutefois contenir des cotations disponibles chez des
    # brokers différents. Garder un unique gagnant global supprimait notamment
    # la seule ligne PEA Bourse Direct au profit de la cotation Trading212 plus
    # liquide. On garde donc le meilleur représentant nécessaire à CHAQUE broker
    # actif. Si un même ticker couvre plusieurs brokers, il n'est conservé qu'une
    # fois. Cette règle est identique à celle des déduplications d'indice et de
    # corrélation plus bas dans le pipeline.
    broker_access = _broker_access_sets(df, ticker_col) if df is not None else {}

    def ranking_key(entry: tuple[str, float, bool]) -> tuple[bool, float, str]:
        ticker, volume, is_primary = entry
        return (not is_primary, -volume, ticker)

    kept_set: set[str] = set()
    for group in components.values():
        covered_brokers = sorted({
            broker
            for ticker, _, _ in group
            for broker in broker_access.get(ticker, frozenset())
        })
        if covered_brokers:
            for broker in covered_brokers:
                available = [
                    entry for entry in group
                    if broker in broker_access.get(entry[0], frozenset())
                ]
                if available:
                    kept_set.add(min(available, key=ranking_key)[0])
        else:
            kept_set.add(min(group, key=ranking_key)[0])
    kept = [ticker for ticker in cols if ticker in kept_set]
    removed = len(cols) - len(kept)
    if removed:
        print(f"[dedup] {removed} cross-listings supprimés.")
    if name_pairs:
        print(
            f"[dedup] dont {len(name_pairs)} rapprochés par nom+score "
            "(ISIN manquant sur la cotation principale) :"
        )
        for t, twin, raw in name_pairs[:20]:
            print(f"[dedup]   - {t} = {twin} ({raw})")
        if len(name_pairs) > 20:
            print(f"[dedup]   ... et {len(name_pairs) - 20} autres")
    return returns[kept]
