"""Discrétisation de l'allocation optimale en ordres réels par broker.

Règle métier (CONV 4 — révision) :
- **Trading212** autorise les *pies* (fractions d'action) → montant € exact.
- **Tous les autres brokers** (BoursDirect, BoursDirect2, IBKR, …) n'autorisent
  que l'achat d'**actions entières** → on convertit le poids cible en un nombre
  entier d'actions à partir du budget du broker et du prix de l'action.
  Conséquence : une action peut représenter moins (ou plus) de 1 % du budget,
  ce que l'ancienne discrétisation par paliers de 1 % ne savait pas faire.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from .config import Config

if TYPE_CHECKING:
    import pandas as pd


def _int_pct_largest_remainder(
    rel: dict[str, float], total_points: int = 100
) -> dict[str, int]:
    """Convertit des poids relatifs en points entiers sommant à ``total_points``.

    Méthode du plus fort reste (Hare-Niemeyer) : plancher puis +1% aux plus grands
    restes. Sert aux pies Trading212 (incréments de 1 point de pourcentage).
    """
    items = [(t, max(float(v), 0.0)) for t, v in rel.items() if v and v > 0]
    tot = sum(v for _, v in items)
    if tot <= 0:
        return {}
    points = max(int(total_points), 0)
    raw = {t: v / tot * points for t, v in items}
    floors = {t: int(math.floor(x)) for t, x in raw.items()}
    rem = points - sum(floors.values())
    order = sorted(raw, key=lambda t: raw[t] - floors[t], reverse=True)
    for t in order[:max(rem, 0)]:
        floors[t] += 1
    return floors


def _clean(name) -> str:
    return "".join(filter(str.isalnum, str(name).upper()))


def _sparse_execution_targets(
    raw_targets: dict[str, float],
    *,
    spend_cap: float,
    total_cap: float,
    broker_budget: float,
    fractional: bool = False,
) -> dict[str, float]:
    """Nettoie le support continu avant de creer des ordres executables.

    Le solveur peut recevoir d'anciens poids ou une allocation progressive
    legerement dense. Pour une action entière, la granularité minimale est une
    action achetable ; pour un pie, c'est un point de 1 % du pie local. Les
    montants conservés sont ensuite renormalisés sur ce support seulement.
    """
    positive = {
        ticker: max(float(value or 0.0), 0.0)
        for ticker, value in raw_targets.items()
        if np.isfinite(float(value or 0.0)) and float(value or 0.0) > 0.0
    }
    raw_total = float(sum(positive.values()))
    target_total = min(raw_total, max(float(spend_cap), 0.0))
    if target_total <= 1e-12 or raw_total <= 1e-12:
        return {}

    scaled = {
        ticker: value * target_total / raw_total
        for ticker, value in positive.items()
    }
    if fractional:
        # Un point de pie est la vraie unité d'exécution de Trading 212. Le
        # minimum est donc local au pie (1 %), jamais relatif au portefeuille
        # global — sinon un petit budget T212 pouvait recevoir 40 % sur une
        # seule ligne.
        threshold_eur = (
            max(float(Config.STARR_MIN_T212_PIE_PCT), 0.0)
            * max(float(broker_budget), 0.0)
        )
        max_lines = max(
            1,
            int(math.floor(1.0 / max(float(Config.STARR_MIN_T212_PIE_PCT), 0.01))),
        )
    else:
        # Une action entière est la granularité minimale : le filtre global de
        # 1 % ne doit pas supprimer une ligne qui peut acheter une action.
        threshold_eur = 0.0
        max_lines = max(1, len(scaled))
    ranked = sorted(scaled, key=lambda ticker: (-scaled[ticker], ticker))
    kept = [
        ticker
        for ticker in ranked
        if threshold_eur <= 0.0 or scaled[ticker] >= threshold_eur - 1e-9
    ][:max_lines]
    if not kept:
        # Pour une ancienne matrice entièrement pulvérisée, le repli reste
        # strictement borné et choisit les poids les plus informatifs.
        useful = 1
        if threshold_eur > 0.0:
            useful = max(1, int(target_total // threshold_eur))
        kept = ranked[: min(max_lines, useful)]

    kept_total = float(sum(scaled[ticker] for ticker in kept))
    if kept_total <= 1e-12:
        return {}
    return {
        ticker: scaled[ticker] * target_total / kept_total
        for ticker in kept
    }


def alloc_to_weight_matrix(
    alloc: list[dict],
    tickers: list[str],
    active_brokers: list[str] | None,
    total_cap: float,
) -> np.ndarray:
    """Poids (fraction du capital total) reconstruits depuis une allocation discrète.

    ``active_brokers=None`` agrège par ticker et renvoie un vecteur ``[n_tickers]`` ;
    sinon une matrice ``[n_tickers × n_brokers]``, comme celle que consomme
    l'optimiseur.

    Trois pièges que cette fonction encapsule une fois pour toutes :

    - la clé d'identité est ``AnalysisTicker``, PAS ``Ticker`` — ce dernier est le
      ticker d'EXÉCUTION, éventuellement routé vers une cotation secondaire ;
    - le montant fait foi (``eur``), pas ``"Poids total (%)"`` arrondi à 4 décimales ;
    - un même titre peut apparaître sur plusieurs brokers : on somme.

    ``discretize_allocation`` omet les lignes nulles, d'où une matrice initialisée
    à zéro. À appeler APRÈS ``enforce_discrete_sector_cap``, qui mute les dicts.
    """
    capital = max(float(total_cap), 0.0)
    index = {str(t).strip().upper(): i for i, t in enumerate(tickers)}
    if active_brokers is None:
        out = np.zeros(len(tickers), dtype=float)
    else:
        out = np.zeros((len(tickers), len(active_brokers)), dtype=float)
        broker_index = {str(b).strip(): j for j, b in enumerate(active_brokers)}
    if capital <= 0.0:
        return out
    for item in alloc or []:
        ticker = str(item.get("AnalysisTicker") or item.get("Ticker") or "").strip().upper()
        row = index.get(ticker)
        if row is None:
            continue
        value = max(float(item.get("eur", 0.0) or 0.0), 0.0) / capital
        if active_brokers is None:
            out[row] += value
            continue
        column = broker_index.get(str(item.get("Broker", "")).strip())
        if column is not None:
            out[row, column] += value
    return out


def broker_line_cap(
    broker_budget: float,
    total_cap: float,
    *,
    min_global_weight: float | None = None,
) -> int:
    """CAPACITÉ ÉCONOMIQUE : combien de lignes ce broker peut tenir au plancher.

    ``floor(budget / (MIN_ALLOCATION_THRESHOLD × capital))``. Cette capacité
    reste un garde-fou économique pour le budget continu ; elle ne constitue
    pas un malus de score.

    À NE PAS CONFONDRE avec ``STARR_MAX_LINES_PER_BROKER`` (20), conservé pour
    les diagnostics historiques. Ce sont deux nombres distincts et cette
    fonction ne doit PAS être bornée par le seuil :

    - les confondre rendait l'ancien malus inatteignable (``_deploy_batch``
      tronquait au seuil lui-même avant de compter) ;
    - supprimer la capacité économique au profit d'un plafond plat a fait
      bien pire : un petit broker pouvait alors étaler son budget sur des dizaines
      de lignes, toutes sous le plancher de 1 %, donc TOUTES annulées par le
      filtre des micro-lignes — et son budget entier ressortait NON INVESTI
      (#bug rapporté : Trading212 à zéro).

    La capacité économique est donc la SEULE troncature structurelle appliquée
    dans l'optimiseur ; le score n'ajoute plus de pénalité au-delà d'un nombre
    de lignes. Pour un gros broker la capacité vaut ~96 lignes et ne bride donc
    pas un portefeuille d'environ 20 positions à 5 %.

    Ne descend jamais sous une ligne pour un broker actif.
    """
    minimum = max(
        float(
            Config.MIN_ALLOCATION_THRESHOLD
            if min_global_weight is None
            else min_global_weight
        ),
        0.0,
    )
    budget = max(float(broker_budget), 0.0)
    capital = max(float(total_cap), 0.0)
    if capital <= 0.0:
        return max(1, int(Config.STARR_MAX_LINES_PER_BROKER))
    if minimum <= 0.0:
        # Compatibilité de l'helper historique : ses appelants de diagnostic
        # attendent encore une capacité calculée sur 1 %. Le chemin réel de
        # l'optimiseur ne l'appelle pas lorsque le seuil global vaut zéro ; il
        # autorise alors toutes les lignes et laisse la discrétisation appliquer
        # la vraie contrainte Bourse Direct (au moins une action).
        minimum = 0.01
    return max(1, int(math.floor(budget / (minimum * capital) + 1e-9)))


def is_fractional_broker(broker_name: str) -> bool:
    """True si le broker autorise les fractions d'action (pies).

    Seul Trading212 (toutes orthographes : Trading212, Tradding 212, T212…).
    """
    c = _clean(broker_name)
    return "TRADING212" in c or "TRADDING212" in c or c == "T212"


def close_prices_from_download(raw, tickers: list[str]):
    """Extrait les prix de clôture d'un ``yf.download(tickers, group_by="ticker")``.

    yfinance renvoie des colonnes MultiIndex ``(Ticker, Price)`` même pour un
    **seul** ticker (contrairement à l'ancienne hypothèse de colonnes aplaties
    ``raw["Close"]``, qui lève ``KeyError: 'Close'``) : on indexe toujours par
    ``raw[t]["Close"]``. Les tickers absents du téléchargement (échec réseau,
    delisting) sont simplement ignorés.
    """
    import pandas as pd
    level0 = set(raw.columns.get_level_values(0))
    cols = {t: raw[t]["Close"] for t in tickers if t in level0}
    return pd.DataFrame(cols)


def average_turnover_eur_from_download(
    raw, tickers: list[str], *, lookback_days: int = 60
) -> dict[str, float]:
    """Calcule le montant moyen échangé depuis le download groupé existant.

    Cette fonction ne provoque aucun appel réseau. Elle exploite les colonnes
    ``Close`` et ``Volume`` déjà téléchargées pour les corrélations et évite
    donc un appel ``Ticker.info`` pour chaque ETF pendant le scoring.
    """
    from .currency import volume_eur

    result: dict[str, float] = {}
    if raw is None or getattr(raw, "empty", True):
        return result
    try:
        level0 = set(raw.columns.get_level_values(0))
    except (AttributeError, IndexError, TypeError):
        return result
    for ticker in tickers:
        if ticker not in level0:
            continue
        try:
            frame = raw[ticker]
            close = frame["Close"]
            volume = frame["Volume"]
            traded = (close * volume).dropna()
            if lookback_days > 0:
                traded = traded.iloc[-lookback_days:]
            native_turnover = float(traded.mean()) if len(traded) else 0.0
            # volume_eur attend volume × prix. Le turnover natif est déjà ce
            # produit ; un prix unité applique uniquement devise/facteur pence.
            result[ticker] = volume_eur(native_turnover, 1.0, ticker, None)
        except (KeyError, TypeError, ValueError):
            continue
    return result


def drop_short_history(close_df, min_days: int) -> tuple[pd.DataFrame, list[str]]:
    """Écarte les colonnes avec moins de ``min_days`` cours non-NaN.

    Sans ce filtre, un seul fonds récent tronque la fenêtre COMMUNE de rendements
    de tout l'univers (le ``dropna()`` qui suit aligne tout le monde sur le plus
    jeune) : corrélations et STARR calculés sur quelques semaines au lieu de 5 ans
    (#bug rapporté). Retourne (df_filtré, tickers_écartés).
    """
    if close_df is None or getattr(close_df, "empty", True) or min_days <= 0:
        return close_df, []
    n_obs = close_df.notna().sum()
    dropped = [t for t in close_df.columns if int(n_obs[t]) < min_days]
    return close_df.drop(columns=dropped), dropped


def latest_prices(close_df, tickers: list[str]) -> dict[str, float]:
    """Dernier prix de clôture connu par ticker depuis un DataFrame de prix."""
    prices: dict[str, float] = {}
    if close_df is None:
        return prices
    for t in tickers:
        try:
            if t in close_df.columns:
                serie = close_df[t].dropna()
                if len(serie):
                    prices[t] = float(serie.iloc[-1])
        except Exception:
            pass
    return prices


def latest_prices_eur(close_df, tickers: list[str]) -> dict[str, float]:
    """Derniers cours convertis en EUR pour la discrétisation des budgets brokers.

    Les poids et budgets sont en EUR : comparer directement un cours USD/GBP à un
    budget EUR produirait un nombre d'actions incorrect. Les cotations LSE en pence
    sont ramenées en livres avant application du taux GBP/EUR.
    """
    from app.services.finance import fx

    from .dedup import currency_from_raw, ticker_currency_raw

    native = latest_prices(close_df, tickers)
    converted: dict[str, float] = {}
    unknown_lse: list[str] = []
    for ticker, price in native.items():
        # UNE seule interrogation de la devise brute : elle sert à la fois au
        # taux de change et au facteur pence. Auparavant ce bloc refaisait,
        # après _ticker_currency, exactement le même appel réseau.
        raw_currency = ticker_currency_raw(ticker)
        currency = currency_from_raw(ticker, raw_currency)
        factor = 1.0
        if ticker.upper().endswith(".L"):
            if raw_currency in ("GBp", "GBX"):
                factor = 0.01
            elif not raw_currency:
                # La plupart des historiques `.L` Yahoo sont en pence, mais
                # appliquer 0,01 sans le savoir serait tout aussi faux. On garde
                # donc 1,0 — en le SIGNALANT : traiter des pence comme des livres
                # multiplie le cours par 100, donc divise par 100 le nombre
                # d'actions achetées, et l'erreur passait jusqu'ici inaperçue.
                unknown_lse.append(ticker)
        rate = float(fx.get_rate(currency, "EUR", stale_ok=True) or 0.0)
        if currency == "EUR":
            rate = 1.0
        if rate > 0 and price > 0:
            converted[ticker] = float(price) * factor * rate
    if unknown_lse:
        print(
            f"    * ATTENTION : devise Yahoo indeterminable pour {len(unknown_lse)} "
            f"ligne(s) londonienne(s) ({', '.join(unknown_lse[:8])}"
            f"{'...' if len(unknown_lse) > 8 else ''}) -> cours suppose en LIVRES. "
            "Si la ligne cote en pence, le nombre d'actions sera 100x trop faible."
        )
    return converted


def discretize_allocation(
    tickers: list[str],
    weights,                 # np.ndarray [n_tickers x n_brokers] : fraction du capital TOTAL
    active_brokers: list[str],
    prices: dict[str, float],
    total_cap: float | None = None,
    sector_by_ticker: dict[str, str] | None = None,
    sector_exposures_by_ticker: dict[str, dict[str, float]] | None = None,
    is_etf_tickers: set[str] | None = None,
    execution_routes: dict[tuple[str, str], str] | None = None,
    execution_prices: dict[tuple[str, str], float] | None = None,
    fee_reserve_eur_by_broker: dict[str, float] | None = None,
) -> list[dict]:
    """Convertit des poids continus en allocation exécutable par broker.

    Retourne une liste de dicts :
      {Ticker, Broker, shares (int|None), eur, prix, type ('pie'|'shares'),
       Poids total (%)}

    - Pies (Trading212) : shares=None, montant € exact (renormalisé au budget).
    - Actions entières  : shares = floor(€_cible / prix), puis le budget restant
      est rempli action par action sur les titres les plus sous-pondérés.
    - ``fee_reserve_eur_by_broker`` retire les frais du prochain rebalancement du
      budget achetable : titres + reserve ne depassent jamais le capital broker.
    """
    weights = np.asarray(weights, dtype=float)
    if weights.ndim == 1:
        weights = weights.reshape(len(tickers), len(active_brokers))
    num_t = len(tickers)
    if total_cap is None:
        total_cap = float(sum(Config.BUDGET_BROKERS.values())) or 1.0

    alloc: list[dict] = []
    routes = execution_routes or {}
    routed_prices = execution_prices or {}
    fee_reserves = fee_reserve_eur_by_broker or {}
    broker_spend_caps: dict[str, float] = {}
    broker_pie_bases: dict[str, float] = {}

    def _route(ticker: str, broker: str) -> str:
        return routes.get((ticker, broker), ticker)

    def _price(ticker: str, broker: str) -> float:
        value = float(
            routed_prices.get((ticker, broker), prices.get(ticker, 0)) or 0
        )
        # 0 × NaN/inf contaminerait même le coût d'une ligne de zéro action,
        # puis le reliquat et toute la boucle de remplissage du broker.
        return value if np.isfinite(value) and value > 0.0 else 0.0

    for j, broker in enumerate(active_brokers):
        gross_budget_j = float(Config.BUDGET_BROKERS.get(broker, 0.0))
        if gross_budget_j <= 0:
            continue
        fee_reserve = min(
            max(float(fee_reserves.get(broker, 0.0) or 0.0), 0.0),
            gross_budget_j,
        )
        spend_cap = gross_budget_j - fee_reserve
        # € cible par ticker chez ce broker (depuis le poids continu)
        raw_targets = {
            tickers[i]: max(float(weights[i, j]), 0.0) * total_cap
            for i in range(num_t)
        }
        eur_target = _sparse_execution_targets(
            raw_targets,
            spend_cap=spend_cap,
            total_cap=total_cap,
            broker_budget=gross_budget_j,
            fractional=is_fractional_broker(broker),
        )
        total_target = sum(eur_target.values())
        if total_target <= 0:
            continue
        broker_spend_caps[broker] = total_target
        broker_pie_bases[broker] = gross_budget_j

        if is_fractional_broker(broker):
            # Respecter la part réellement déployée : un plafond sectoriel
            # infaisable laisse volontairement du cash et ne doit pas être
            # renormalisé à 100 % du broker.
            utilization_points = min(
                100,
                max(0, int(math.floor(total_target / gross_budget_j * 100.0 + 1e-9))),
            )
            active_targets = {
                ticker: value for ticker, value in eur_target.items() if value > 0
            }
            threshold_eur = (
                max(float(Config.STARR_MIN_T212_PIE_PCT), 0.0)
                * gross_budget_j
            )
            minimum_points = (
                int(math.ceil(threshold_eur / gross_budget_j * 100.0 - 1e-9))
                if threshold_eur > 0 and gross_budget_j > 0
                else 0
            )
            # Le plafond adaptatif rend normalement ce minimum faisable. Cette
            # borne couvre aussi un budget fortement amputé par des frais.
            if active_targets:
                minimum_points = min(
                    minimum_points,
                    utilization_points // len(active_targets),
                )
            base_points = minimum_points * len(active_targets)
            remaining_points = max(utilization_points - base_points, 0)
            desired = {
                ticker: value / total_target * utilization_points
                for ticker, value in active_targets.items()
            }
            extra_weights = {
                ticker: max(value - minimum_points, 0.0)
                for ticker, value in desired.items()
            }
            if sum(extra_weights.values()) <= 1e-12:
                extra_weights = active_targets
            extras = _int_pct_largest_remainder(extra_weights, remaining_points)
            pies = {
                ticker: minimum_points + extras.get(ticker, 0)
                for ticker in active_targets
            }
            for t, pct in pies.items():
                if pct <= 0:
                    continue
                e = pct / 100.0 * gross_budget_j
                execution_ticker = _route(t, broker)
                alloc.append({
                    "Ticker": execution_ticker, "AnalysisTicker": t,
                    "Broker": broker, "shares": None,
                    "eur": round(e, 2), "prix": round(_price(t, broker), 4),
                    "type": "pie", "pie_pct": int(pct),
                    "Poids total (%)": round(e / total_cap * 100, 4),
                })
            continue

        # Actions entières
        shares: dict[str, int] = {}
        for i in range(num_t):
            t = tickers[i]
            p = _price(t, broker)
            target = float(eur_target.get(t, 0.0))
            shares[t] = int(np.floor(target / p)) if (p > 0 and target > 0) else 0
        spent = sum(shares[t] * _price(t, broker) for t in shares)
        remaining = total_target - spent

        # Remplir le budget restant action par action. On vise le titre le moins
        # financé EN RELATIF (shares·prix / cible €) parmi ceux dont une action
        # entière rentre encore dans le reliquat. PAS de plafond à la cible du
        # titre : le budget qu'on ne peut PAS placer sur sa ligne d'origine (prix
        # runtime manquant, ou action trop chère pour son reliquat) déborde sur
        # les autres lignes achetables au lieu de rester en cash. Le reste final
        # est ainsi borné par le prix de l'action la moins chère.
        for _ in range(1_000_000):
            best, best_ratio = None, None
            for i in range(num_t):
                t = tickers[i]
                p = _price(t, broker)
                target = float(eur_target.get(t, 0.0))
                if p <= 0 or target <= 0 or p > remaining + 1e-9:
                    continue
                ratio = (shares[t] * p) / target   # taux de financement courant
                if best_ratio is None or ratio < best_ratio:
                    best_ratio, best = ratio, t
            if best is None:
                break
            shares[best] += 1
            remaining -= _price(best, broker)

        for i in range(num_t):
            t = tickers[i]
            n = shares[t]
            if n <= 0:
                continue
            p = _price(t, broker)
            e = n * p
            execution_ticker = _route(t, broker)
            alloc.append({
                "Ticker": execution_ticker, "AnalysisTicker": t,
                "Broker": broker, "shares": int(n),
                "eur": round(e, 2), "prix": round(p, 4),
                "type": "shares", "pie_pct": None,
                "Poids total (%)": round(e / total_cap * 100, 4),
            })
    if (
        sector_by_ticker is None
        and sector_exposures_by_ticker is None
        and is_etf_tickers is None
    ):
        return alloc
    return enforce_discrete_sector_cap(
        alloc,
        total_cap=total_cap,
        sector_by_ticker=sector_by_ticker,
        sector_exposures_by_ticker=sector_exposures_by_ticker,
        is_etf_tickers=is_etf_tickers,
        broker_spend_caps=broker_spend_caps,
        broker_pie_bases=broker_pie_bases,
    )


def enforce_discrete_sector_cap(
    alloc: list[dict],
    *,
    total_cap: float,
    sector_by_ticker: dict[str, str] | None = None,
    sector_exposures_by_ticker: dict[str, dict[str, float]] | None = None,
    is_etf_tickers: set[str] | None = None,
    max_sector_pct: float | None = None,
    broker_spend_caps: dict[str, float] | None = None,
    broker_pie_bases: dict[str, float] | None = None,
) -> list[dict]:
    """Garantit les plafonds par action et par secteur après discrétisation.

    Le budget libéré est réinvesti sur les lignes dont les plafonds autorisent
    encore une action ou un point de pie, y compris pour les ETF transparisés.
    """
    if not alloc or total_cap <= 0:
        return alloc
    from .broker_availability import load_etf_tickers
    from .sector_constraints import constrained_sector_labels

    etfs = {
        str(ticker).strip().upper()
        for ticker in (is_etf_tickers if is_etf_tickers is not None else load_etf_tickers())
    }
    def _analysis_ticker(item: dict) -> str:
        return str(item.get("AnalysisTicker") or item["Ticker"]).upper()

    unique_tickers = list(dict.fromkeys(_analysis_ticker(item) for item in alloc))
    labels = constrained_sector_labels(
        unique_tickers,
        is_etf=[ticker in etfs for ticker in unique_tickers],
        fallback_sectors=sector_by_ticker,
    )
    label_by_ticker = dict(zip(unique_tickers, labels, strict=True))
    from .sector_constraints import SectorCaps, as_sector_caps

    caps = (
        SectorCaps.from_config()
        if max_sector_pct is None
        else as_sector_caps(max_sector_pct)
    )
    cap = caps.default
    # Plafond en euros PAR compartiment : un plafond unique laisserait la
    # discrétisation en actions entières repasser l'or au-dessus de sa limite.
    def _cap_eur(sector) -> float:
        return caps.for_label(sector) * float(total_cap)
    # Montant visé AVANT écrêtage : sert de référence au remplissage final pour
    # rendre le budget aux lignes proportionnellement à leur cible d'origine.
    targets = {id(item): max(float(item.get("eur", 0.0) or 0.0), 0.0) for item in alloc}

    def _reduce_to_cap(positions: list[dict], target_eur: float) -> None:
        exposure = sum(float(item.get("eur", 0.0) or 0.0) for item in positions)
        while exposure > target_eur + 0.005:
            excess = exposure - target_eur
            share_positions = [
                item for item in positions
                if item.get("type") == "shares"
                and int(item.get("shares") or 0) > 0
                and float(item.get("prix") or 0) > 0
            ]
            if share_positions:
                affordable = [
                    item for item in share_positions
                    if float(item["prix"]) <= excess + 1e-9
                ]
                chosen = max(
                    affordable,
                    key=lambda item: float(item["prix"]),
                    default=min(share_positions, key=lambda item: float(item["prix"])),
                )
                price = float(chosen["prix"])
                chosen["shares"] = int(chosen["shares"]) - 1
                chosen["eur"] = round(float(chosen["shares"]) * price, 2)
                exposure -= price
                continue

            pie_positions = [
                item for item in positions
                if item.get("type") == "pie" and int(item.get("pie_pct") or 0) > 0
            ]
            if not pie_positions:
                break
            chosen = max(pie_positions, key=lambda item: float(item.get("eur", 0.0)))
            broker_budget = float(Config.BUDGET_BROKERS.get(chosen["Broker"], 0.0))
            point_eur = broker_budget / 100.0
            if point_eur <= 0:
                break
            chosen["pie_pct"] = int(chosen["pie_pct"]) - 1
            chosen["eur"] = round(float(chosen["pie_pct"]) * point_eur, 2)
            exposure -= point_eur

    # Le remplissage en actions entières peut déborder la cible d'une ligne pour
    # utiliser le reliquat du broker. Réappliquer ici le plafond individuel évite
    # qu'une action dépasse finalement MAX_POSITION_PCT.
    position_cap_eur = float(Config.MAX_POSITION_PCT) * float(total_cap)
    for ticker in unique_tickers:
        if ticker in etfs:
            continue
        _reduce_to_cap(
            [
                item
                for item in alloc
                if _analysis_ticker(item) == ticker
            ],
            position_cap_eur,
        )

    fractions: dict[str, dict[str, float]] | None = None
    if sector_exposures_by_ticker:
        fractions = {}
        for ticker in unique_tickers:
            raw = sector_exposures_by_ticker.get(ticker, {})
            total = sum(max(float(value), 0.0) for value in raw.values())
            fractions[ticker] = (
                {sector: max(float(value), 0.0) / total for sector, value in raw.items()}
                if total > 0
                else {label_by_ticker[ticker]: 1.0}
                if label_by_ticker.get(ticker)
                else {}
            )
        for sector in sorted({key for values in fractions.values() for key in values}):
            def _sector_total(current_sector: str = sector) -> float:
                return sum(
                    float(item.get("eur", 0.0) or 0.0)
                    * fractions.get(_analysis_ticker(item), {}).get(current_sector, 0.0)
                    for item in alloc
                )

            sector_cap_eur = _cap_eur(sector)
            for _ in range(1_000_000):
                if _sector_total() <= sector_cap_eur + 0.005:
                    break
                candidates = [
                    item for item in alloc
                    if fractions.get(_analysis_ticker(item), {}).get(sector, 0.0) > 0
                    and float(item.get("eur", 0.0) or 0.0) > 0
                ]
                if not candidates:
                    break
                def _unit_contribution(
                    item: dict, current_sector: str = sector
                ) -> float:
                    unit = (
                        float(Config.BUDGET_BROKERS.get(item["Broker"], 0.0)) / 100.0
                        if item.get("type") == "pie"
                        else float(item.get("prix") or 0.0)
                    )
                    return unit * fractions[_analysis_ticker(item)][current_sector]
                excess = _sector_total() - sector_cap_eur
                # Ne pas céder une grosse part d'ETF pour corriger quelques
                # euros lorsqu'une unité plus petite suffit.
                within_excess = [
                    item for item in candidates
                    if _unit_contribution(item) <= excess + 1e-9
                ]
                chosen = (
                    max(within_excess, key=_unit_contribution)
                    if within_excess
                    else min(candidates, key=_unit_contribution)
                )
                if chosen.get("type") == "pie":
                    chosen["pie_pct"] = max(0, int(chosen.get("pie_pct") or 0) - 1)
                    point = float(Config.BUDGET_BROKERS.get(chosen["Broker"], 0.0)) / 100.0
                    chosen["eur"] = round(float(chosen["pie_pct"]) * point, 2)
                else:
                    chosen["shares"] = max(0, int(chosen.get("shares") or 0) - 1)
                    chosen["eur"] = round(
                        float(chosen["shares"]) * float(chosen.get("prix") or 0.0), 2
                    )
    else:
        for sector in sorted({label for label in labels if label}):
            positions = [
                item
                for item in alloc
                if label_by_ticker.get(_analysis_ticker(item)) == sector
            ]
            _reduce_to_cap(positions, _cap_eur(sector))

    _refill_broker_budgets(
        alloc,
        total_cap=total_cap,
        etfs=etfs,
        label_by_ticker=label_by_ticker,
        position_cap_eur=position_cap_eur,
        sector_cap_eur=_cap_eur,
        targets=targets,
        broker_spend_caps=broker_spend_caps,
        broker_pie_bases=broker_pie_bases,
        sector_fractions=fractions,
    )

    cleaned: list[dict] = []
    for item in alloc:
        if float(item.get("eur", 0.0) or 0.0) <= 0:
            continue
        item["Poids total (%)"] = round(float(item["eur"]) / total_cap * 100.0, 4)
        cleaned.append(item)
    return cleaned


def _refill_broker_budgets(
    alloc: list[dict],
    *,
    total_cap: float,
    etfs: set[str],
    label_by_ticker: dict[str, str | None],
    position_cap_eur: float,
    sector_cap_eur,
    targets: dict[int, float],
    broker_spend_caps: dict[str, float] | None = None,
    broker_pie_bases: dict[str, float] | None = None,
    sector_fractions: dict[str, dict[str, float]] | None = None,
) -> None:
    """Redépense le budget broker resté libre après écrêtage des plafonds.

    L'application des plafonds (par action puis par secteur) retire des actions
    et des points de pie sans rien remettre à la place : le résultat affichait du
    cash alors que d'autres lignes avaient encore de la marge. Ici on rend ce
    budget, unité par unité (1 action, ou 1 point de pie), à la ligne la plus
    sous-financée par rapport à sa cible d'avant écrêtage, tant qu'aucun plafond
    (action, secteur, budget du broker) n'est franchi.
    """
    if not alloc:
        return

    def _analysis_ticker(item: dict) -> str:
        return str(item.get("AnalysisTicker") or item["Ticker"]).upper()

    def _eur(item: dict) -> float:
        return max(float(item.get("eur", 0.0) or 0.0), 0.0)

    def _fractions(ticker: str) -> dict[str, float]:
        if sector_fractions is not None:
            return sector_fractions.get(ticker, {})
        label = label_by_ticker.get(ticker)
        return {label: 1.0} if label else {}

    # Ces totaux sont communs à tous les brokers. Les maintenir à chaque achat
    # évite de rescanner toutes les positions pour chaque candidat et secteur.
    ticker_exposures: dict[str, float] = {}
    sector_exposures: dict[str, float] = {}
    for item in alloc:
        ticker = _analysis_ticker(item)
        value = _eur(item)
        ticker_exposures[ticker] = ticker_exposures.get(ticker, 0.0) + value
        for label, fraction in _fractions(ticker).items():
            sector_exposures[label] = sector_exposures.get(label, 0.0) + value * fraction

    brokers = list(dict.fromkeys(item["Broker"] for item in alloc))
    # Les budgets brokers sont exprimés en euros réels ; ``total_cap`` peut être
    # une autre échelle (appels ciblés, tests). On ramène chaque budget à sa PART
    # du capital fourni pour ne jamais dépenser plus que ce capital.
    budgets_total = float(sum(Config.BUDGET_BROKERS.values())) or 0.0
    scale = (
        float(total_cap) / budgets_total
        if budgets_total > 0 and abs(budgets_total - float(total_cap)) > 1e-6
        else 1.0
    )
    for broker in brokers:
        default_budget = float(Config.BUDGET_BROKERS.get(broker, 0.0)) * scale
        budget = float(
            (broker_spend_caps or {}).get(broker, default_budget)
        )
        if budget <= 0:
            continue
        positions = [item for item in alloc if item["Broker"] == broker]
        pie_base = float((broker_pie_bases or {}).get(broker, default_budget))
        point_eur = pie_base / 100.0
        remaining = budget - sum(_eur(item) for item in positions)
        for _ in range(1_000_000):
            if remaining <= 1e-9:
                break
            best, best_ratio = None, None
            for item in positions:
                if item.get("type") == "pie":
                    cost = point_eur
                    if cost <= 0 or int(item.get("pie_pct") or 0) >= 100:
                        continue
                else:
                    cost = float(item.get("prix") or 0.0)
                    if cost <= 0:
                        continue
                if cost > remaining + 1e-9:
                    continue
                ticker = _analysis_ticker(item)
                exposure = ticker_exposures.get(ticker, 0.0)
                if ticker not in etfs and exposure + cost > position_cap_eur + 1e-9:
                    continue
                sector_fits = True
                for label, fraction in _fractions(ticker).items():
                    sector_exposure = sector_exposures.get(label, 0.0)
                    limit = (
                        sector_cap_eur(label)
                        if callable(sector_cap_eur)
                        else float(sector_cap_eur)
                    )
                    if sector_exposure + cost * fraction > limit + 1e-9:
                        sector_fits = False
                        break
                if not sector_fits:
                    continue
                target = targets.get(id(item), 0.0)
                if target <= 0:
                    continue
                ratio = _eur(item) / target
                if best_ratio is None or ratio < best_ratio:
                    best_ratio, best = ratio, item
            if best is None:
                break
            previous_eur = _eur(best)
            if best.get("type") == "pie":
                best["pie_pct"] = int(best.get("pie_pct") or 0) + 1
                best["eur"] = round(float(best["pie_pct"]) * point_eur, 2)
            else:
                best["shares"] = int(best.get("shares") or 0) + 1
                best["eur"] = round(float(best["shares"]) * float(best["prix"]), 2)
            spent_increment = _eur(best) - previous_eur
            remaining -= spent_increment
            ticker = _analysis_ticker(best)
            ticker_exposures[ticker] = ticker_exposures.get(ticker, 0.0) + spent_increment
            for label, fraction in _fractions(ticker).items():
                sector_exposures[label] = (
                    sector_exposures.get(label, 0.0) + spent_increment * fraction
                )


def allocation_sector_diagnostics(
    alloc: list[dict],
    *,
    total_cap: float,
    sector_by_ticker: dict[str, str],
    is_etf_tickers: set[str] | None = None,
    sector_exposures_by_ticker: dict[str, dict[str, float]] | None = None,
) -> dict:
    from .broker_availability import load_etf_tickers
    from .lookthrough import fill_unknown_countries, load_lookthrough
    from .sector_constraints import (
        constrained_sector_labels,
        sector_country_diversification_score,
        sector_country_exposures,
    )

    etfs = {
        str(ticker).strip().upper()
        for ticker in (is_etf_tickers if is_etf_tickers is not None else load_etf_tickers())
    }
    tickers = list(dict.fromkeys(
        str(item.get("AnalysisTicker") or item["Ticker"]).upper()
        for item in alloc
    ))
    labels = constrained_sector_labels(
        tickers,
        is_etf=[ticker in etfs for ticker in tickers],
        fallback_sectors=sector_by_ticker,
    )
    by_ticker = dict(zip(tickers, labels, strict=True))
    exposures: dict[str, float] = {}
    invested = 0.0
    for item in alloc:
        value = max(float(item.get("eur", 0.0) or 0.0), 0.0)
        invested += value
        ticker = str(item.get("AnalysisTicker") or item["Ticker"]).upper()
        raw = (sector_exposures_by_ticker or {}).get(ticker, {})
        total = sum(max(float(fraction), 0.0) for fraction in raw.values())
        if total > 0:
            for sector, fraction in raw.items():
                exposures[sector] = exposures.get(sector, 0.0) + (
                    value / total_cap * max(float(fraction), 0.0) / total
                )
        else:
            label = by_ticker.get(ticker)
            if label:
                exposures[label] = exposures.get(label, 0.0) + value / total_cap
    from .sector_constraints import SectorCaps

    diag_caps = SectorCaps.from_config()
    cap = diag_caps.default
    ticker_weights = alloc_to_weight_matrix(alloc, tickers, None, total_cap)
    try:
        _, countries_by_ticker = load_lookthrough()
    except Exception:
        countries_by_ticker = {}
    countries_by_ticker = fill_unknown_countries(countries_by_ticker, tickers)
    countries = sorted({
        country
        for ticker in tickers
        for country in (countries_by_ticker.get(ticker) or {})
    })
    country_matrix = np.zeros((len(tickers), len(countries)), dtype=float)
    country_index = {country: index for index, country in enumerate(countries)}
    for ticker_index, ticker in enumerate(tickers):
        for country, fraction in (countries_by_ticker.get(ticker) or {}).items():
            country_matrix[ticker_index, country_index[country]] = float(fraction)
    from .sector_lookthrough import sector_matrix
    sectors_matrix, sector_names = sector_matrix(
        tickers, sector_exposures_by_ticker or {}, labels
    )
    return {
        "exposures": dict(sorted(exposures.items())),
        "cash_weight": max(0.0, 1.0 - invested / total_cap),
        "compliant": all(
            value <= diag_caps.for_label(label) + 1e-9
            for label, value in exposures.items()
        ),
        "max_sector_pct_overrides": diag_caps.as_dict(),
        "country_diversification": {
            "method": "log_effective_countries_plus_significant_countries",
            "exposures": sector_country_exposures(
                ticker_weights,
                labels,
                country_matrix,
                countries,
                sector_matrix=sectors_matrix,
                sector_names=sector_names,
            ),
            "score": sector_country_diversification_score(
                ticker_weights,
                labels,
                country_matrix,
                sector_matrix=sectors_matrix,
                country_names=countries,
                significant_exposure=float(Config.STARR_SECTOR_COUNTRY_SIGNIFICANT_PCT),
                significant_weight=float(Config.STARR_SECTOR_COUNTRY_SIGNIFICANT_BONUS_WEIGHT),
            ),
        },
    }
