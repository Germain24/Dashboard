"""Présélection diversifiée des ETF, avec un plafond distinct par broker.

Les actions ne sont jamais retirées ici. Les ETF sont d'abord protégés par grande
famille d'exposition, puis complétés gloutonnement selon leur corrélation positive
maximale avec la sélection. La qualité/liquidité départage les candidats proches.
"""

from __future__ import annotations

import math
import re

import numpy as np
from scipy import stats

from .config import Config


def _positive_number(*values) -> float:
    """Premier nombre positif exploitable, sans laisser passer NaN/inf."""
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and number > 0:
            return number
    return 0.0


def select_index_representatives_before_history(
    df,
    metadata_by_ticker: dict[str, dict],
    *,
    etf_tickers: set[str],
    ticker_col: str = "Ticker Yahoo Finance",
    excluded_tickers: set[str] | None = None,
) -> tuple[set[str], object, dict]:
    """Choisit un ETF par indice exact et par broker, sans cours historiques.

    Cette sélection est volontairement indépendante des corrélations : elle peut
    donc précéder le téléchargement des cinq années de cours. L'ordre demandé est
    réplication physique, puis synthétique/swap, puis inconnue; à méthode égale,
    l'encours prime, puis le volume échangé et enfin les frais.

    Le DataFrame retourné conserve toutes les actions. Pour les ETF, chaque masque
    broker n'est vrai que si le fonds est le représentant de cet indice chez ce
    broker. En rappelant la fonction avec ``excluded_tickers``, l'appelant obtient
    automatiquement le candidat suivant du même indice après un échec de
    composition.
    """
    from .etf_index_registry import canonical_constituent_set_id
    from .optimizer import _is_true

    if df is None or getattr(df, "empty", True) or ticker_col not in df.columns:
        return set(), df, {"enabled": False, "reason": "empty_data"}

    normalized_etfs = {str(value).strip().upper() for value in etf_tickers}
    excluded = {
        str(value).strip().upper()
        for value in (excluded_tickers or set())
        if str(value).strip()
    }
    rows: dict[str, object] = {}
    groups: dict[str, list[str]] = {}
    unresolved: list[str] = []
    for _, row in df.iterrows():
        ticker = str(row.get(ticker_col) or "").strip().upper()
        if not ticker or ticker not in normalized_etfs or ticker in excluded:
            continue
        rows.setdefault(ticker, row)
        meta = metadata_by_ticker.get(ticker, {}) or {}
        index_name = meta.get("index_name") or meta.get("index")
        group_id = canonical_constituent_set_id(index_name, strip_hedging=False)
        if not group_id:
            group_id = str(meta.get("index_id") or "").strip()
        if not group_id:
            # Sans identité d'indice fiable, impossible de garantir la règle
            # « un ETF par indice » ni de choisir un remplaçant économique exact.
            # L'inventaire amont a déjà tenté de résoudre ces fonds : on les
            # ignore ici au lieu de télécharger leurs historiques inutilement.
            unresolved.append(ticker)
            continue
        groups.setdefault(group_id, []).append(ticker)

    active_brokers = [
        broker for broker, budget in Config.BUDGET_BROKERS.items() if budget > 0
    ]
    out = df.copy()
    selected_union: set[str] = set()
    broker_diagnostics: dict[str, dict] = {}

    def ranking_key(ticker: str) -> tuple[int, float, float, float, str]:
        row = rows[ticker]
        meta = metadata_by_ticker.get(ticker, {}) or {}
        replication = str(meta.get("replication") or "unknown").strip().casefold()
        replication_rank = 0 if replication == "physical" else 1 if replication in {
            "synthetic", "swap"
        } else 2
        aum = _positive_number(
            meta.get("aum"), meta.get("fund_size"), meta.get("total_assets"),
            meta.get("totalAssets"), row.get("Encours"), row.get("AUM"),
            row.get("Fund Size"), row.get("Total Assets"),
        )
        volume = _positive_number(row.get("Volume"))
        fee = _positive_number(meta.get("management_fee_rate")) or float("inf")
        return replication_rank, -aum, -volume, fee, ticker

    for broker in active_brokers:
        selected_for_broker: list[str] = []
        candidate_count = 0
        for _group_id, members in sorted(groups.items()):
            available = [
                ticker for ticker in members
                if broker in out.columns and _is_true(rows[ticker].get(broker))
            ]
            candidate_count += len(available)
            if not available:
                continue
            winner = min(available, key=ranking_key)
            selected_for_broker.append(winner)
            selected_union.add(winner)
        broker_diagnostics[broker] = {
            "candidates_before": candidate_count,
            "selected": len(selected_for_broker),
            "indices": len(selected_for_broker),
            "removed": max(candidate_count - len(selected_for_broker), 0),
            "selected_tickers": selected_for_broker,
        }

    # Aucun broker actif est une configuration invalide en production, mais ce
    # repli rend la fonction sûre et testable sans transformer tous les ETF en
    # actions par accident.
    if not active_brokers:
        for members in groups.values():
            selected_union.add(min(members, key=ranking_key))

    etf_mask = out[ticker_col].astype(str).str.strip().str.upper().isin(normalized_etfs)
    out = out[~etf_mask | out[ticker_col].astype(str).str.strip().str.upper().isin(selected_union)].copy()
    for broker in active_brokers:
        if broker not in out.columns:
            out[broker] = False
            continue
        out[broker] = out[broker].astype(object)
        winners = set(broker_diagnostics[broker]["selected_tickers"])
        selected_etf_mask = out[ticker_col].astype(str).str.strip().str.upper().isin(selected_union)
        out.loc[selected_etf_mask, broker] = out.loc[selected_etf_mask, ticker_col].astype(str).str.strip().str.upper().isin(winners)

    return selected_union, out, {
        "enabled": True,
        "method": "one_etf_per_exact_index_and_broker_before_history",
        "n_etf_before": len(rows),
        "n_etf_after": len(selected_union),
        "n_removed_from_union": max(len(rows) - len(selected_union), 0),
        "excluded": sorted(excluded),
        "unresolved_indices": sorted(unresolved),
        "brokers": broker_diagnostics,
    }

_BUCKET_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("actions_monde", ("world", "monde", "global", "all country", "acwi", "msci world")),
    ("actions_usa", ("s&p 500", "sp 500", "usa", "u.s.", "united states", "nasdaq")),
    ("actions_europe", ("europe", "euro stoxx", "stoxx 600", "zone euro")),
    ("actions_emergentes", ("emerging", "emergent", "em markets", "msci em")),
    ("petites_capitalisations", ("small cap", "small-cap", "petites capitalisations")),
    ("obligations_etat", ("government bond", "gov bond", "treasury", "souverain", "etat")),
    ("obligations_entreprises", ("corporate bond", "credit bond", "obligations entreprises")),
    ("obligations_inflation", ("inflation", "tips", "index-linked", "index linked")),
    ("or_metaux", ("gold", "or physique", "physical gold", "precious metal", "metaux precieux")),
    ("matieres_premieres", ("commodity", "commodities", "matiere premiere")),
    ("immobilier", ("real estate", "reit", "immobilier")),
)


def _clean_text(value) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def classify_etf_bucket(row) -> str:
    """Classe grossière destinée à protéger les expositions cœur."""
    fields = [
        row.get("Nom", ""),
        row.get("Secteur 2", ""),
        row.get("Secteur 3", ""),
        row.get("Secteur 4", ""),
        row.get("Secteur 5", ""),
    ]
    text = _clean_text(" ".join(str(value or "") for value in fields))
    for bucket, patterns in _BUCKET_PATTERNS:
        if any(pattern in text for pattern in patterns):
            return bucket
    return "specialise"


def _quality_scores(df, tickers: list[str], ticker_col: str) -> dict[str, float]:
    volumes: dict[str, float] = {}
    for _, row in df.iterrows():
        ticker = str(row.get(ticker_col, "") or "").strip()
        if ticker not in tickers:
            continue
        try:
            value = max(float(row.get("Volume", 0) or 0), 0.0)
        except (TypeError, ValueError):
            value = 0.0
        volumes[ticker] = max(volumes.get(ticker, 0.0), value)
    logged = {ticker: math.log1p(volumes.get(ticker, 0.0)) for ticker in tickers}
    values = np.array(list(logged.values()), dtype=float)
    lo = float(np.min(values)) if values.size else 0.0
    hi = float(np.max(values)) if values.size else 0.0
    scale = max(hi - lo, 1e-12)
    return {ticker: (logged[ticker] - lo) / scale for ticker in tickers}


def _spearman_correlation(returns, tickers: list[str]) -> np.ndarray:
    # `to_numeric(errors="coerce")` protège contre un `False` résiduel dans une
    # colonne de rendements : NumPy 2 lève sinon "Invalid value 'False' for
    # dtype 'float64'" et fait échouer toute la présélection ETF (2 runs en
    # erreur le 2026-07-20). Un non-numérique devient NaN, déjà neutralisé plus
    # bas par `nan_to_num`.
    import pandas as pd

    frame = returns[tickers].apply(pd.to_numeric, errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    )
    if len(tickers) < 2:
        return np.eye(len(tickers))
    values = np.asarray(frame, dtype=float)
    if len(frame) < 2:
        corr = np.full((len(tickers), len(tickers)), np.nan)
    elif np.isfinite(values).all() and (np.ptp(values, axis=0) > 0).all():
        ranks = np.apply_along_axis(stats.rankdata, 0, values)
        corr = np.atleast_2d(np.corrcoef(ranks, rowvar=False))
    else:
        # Un trou ne doit pas effacer toute la série de rangs. Pandas calcule
        # chaque paire sur les dates communes, sans inventer de rendements.
        corr = frame.corr(method="spearman", min_periods=min(60, max(2, len(frame)))).to_numpy()
    from .starr import shrink_correlation

    unknown = ~np.isfinite(corr)
    # shrink_correlation remplace les NaN par la moyenne connue (parfois zéro).
    # Le repli prudent doit donc être appliqué AVANT cette régularisation.
    corr = np.where(unknown, 0.75, corr)
    np.fill_diagonal(corr, 1.0)
    corr = shrink_correlation(corr, float(Config.STARR_CORRELATION_SHRINKAGE))
    # Une corrélation inconnue ne doit pas être interprétée comme diversification.
    corr[unknown] = 0.75
    np.fill_diagonal(corr, 1.0)
    return corr


def _select_for_broker(
    candidates: list[str],
    corr: np.ndarray,
    ticker_index: dict[str, int],
    quality: dict[str, float],
    buckets: dict[str, str],
    forced: set[str],
    maximum: int,
) -> list[str]:
    if len(candidates) <= maximum:
        return list(candidates)

    selected: list[str] = sorted(t for t in candidates if t.upper() in forced)

    # Un représentant liquide de chaque grande famille avant les produits spécialisés.
    for bucket in (name for name, _ in _BUCKET_PATTERNS):
        members = [t for t in candidates if buckets.get(t) == bucket and t not in selected]
        if members and len(selected) < maximum:
            selected.append(max(members, key=lambda t: (quality.get(t, 0.0), t)))

    if not selected and candidates:
        selected.append(max(candidates, key=lambda t: (quality.get(t, 0.0), t)))

    while len(selected) < maximum:
        remaining = [ticker for ticker in candidates if ticker not in selected]
        if not remaining:
            break
        selected_idx = tuple(ticker_index[ticker] for ticker in selected)
        selected_buckets = frozenset(buckets.get(ticker) for ticker in selected)

        def marginal_score(
            ticker: str,
            selected_indices: tuple[int, ...] = selected_idx,
            existing_buckets: frozenset[str | None] = selected_buckets,
        ) -> tuple[float, float, str]:
            i = ticker_index[ticker]
            positive_redundancy = max(
                0.0,
                max(float(corr[i, j]) for j in selected_indices),
            )
            new_bucket = buckets.get(ticker) not in existing_buckets
            # La redondance reste dominante ; qualité et nouvelle exposition ne
            # servent qu'à éviter de remplir avec des ETF exotiques/illiquides.
            score = positive_redundancy - 0.15 * quality.get(ticker, 0.0)
            if new_bucket:
                score -= 0.05
            return score, -quality.get(ticker, 0.0), ticker

        selected.append(min(remaining, key=marginal_score))
    return selected


def select_etfs_per_broker(
    returns,
    df,
    ticker_col: str = "Ticker Yahoo Finance",
    maximum: int | None = None,
    forced_tickers: list[str] | None = None,
    returns_are_base_currency: bool = False,
    excluded_tickers: set[str] | None = None,
) -> tuple[object, object, dict]:
    """Limite les ETF admissibles à ``maximum`` par broker actif.

    Retourne ``(returns_filtrés, df_filtré_avec_masques_broker, diagnostics)``.
    Un ETF partagé n'est allouable chez un broker que s'il appartient à la sélection
    de ce broker. L'union des sélections reste disponible pour l'optimisation.

    ``excluded_tickers`` retire des ETF du vivier avant sélection : le runner s'en
    sert pour remplacer, un tour après l'autre, ceux dont la composition reste
    dont la composition économique officielle reste introuvable. La sélection
    étant gloutonne, le remplaçant est celui qui minimise la redondance avec les
    ETF déjà retenus — pas simplement le suivant d'un classement figé.
    """
    from .dedup import returns_in_base_currency
    from .optimizer import _is_true

    cap = int(
        Config.ETF_MAX_CANDIDATES_PER_BROKER if maximum is None else maximum
    )
    if cap <= 0 or df is None or getattr(df, "empty", True):
        return returns, df, {"enabled": False, "reason": "invalid_cap_or_empty_data"}

    available_tickers = list(returns.columns)
    excluded = {str(t).strip().upper() for t in (excluded_tickers or set()) if str(t).strip()}
    rows = {}
    etf_tickers: list[str] = []
    for _, row in df.iterrows():
        ticker = str(row.get(ticker_col, "") or "").strip()
        if not ticker or ticker not in available_tickers:
            continue
        rows.setdefault(ticker, row)
        if "ETF" in str(row.get("Secteur", "") or "").upper():
            etf_tickers.append(ticker)
    etf_tickers = list(dict.fromkeys(etf_tickers))
    # Écartés du vivier : ils ne peuvent ni être sélectionnés, ni survivre via la
    # branche « non-ETF » de ``keep`` plus bas.
    etf_tickers = [ticker for ticker in etf_tickers if ticker.upper() not in excluded]
    if not etf_tickers:
        if excluded:
            keep_all = [t for t in available_tickers if t.upper() not in excluded]
            out_all = df[
                ~df[ticker_col].astype(str).str.strip().str.upper().isin(excluded)
            ].copy()
            return returns[keep_all], out_all, {
                "enabled": True, "n_etf_before": 0, "n_etf_after": 0,
                "excluded": sorted(excluded), "brokers": {},
            }
        return returns, df, {"enabled": True, "n_etf_before": 0, "n_etf_after": 0, "brokers": {}}

    days = min(len(returns), max(60, int(Config.ETF_SELECTION_CORRELATION_DAYS)))
    source = returns[etf_tickers].iloc[-days:]
    converted = source if returns_are_base_currency else returns_in_base_currency(source)
    corr = _spearman_correlation(converted, etf_tickers)
    ticker_index = {ticker: i for i, ticker in enumerate(etf_tickers)}
    quality = _quality_scores(df, etf_tickers, ticker_col)
    buckets = {ticker: classify_etf_bucket(rows[ticker]) for ticker in etf_tickers}
    forced = {str(t).strip().upper() for t in (forced_tickers or Config.FORCED_BUY_TICKERS)}
    # Une position déjà détenue ne doit jamais disparaître au seul motif que le
    # nouveau cap de candidats est atteint : le turnover est arbitré plus tard.
    if "Poids" in df.columns:
        for ticker in etf_tickers:
            try:
                if float(rows[ticker].get("Poids", 0) or 0) > 0:
                    forced.add(ticker.upper())
            except (TypeError, ValueError):
                pass
    active_brokers = [broker for broker, budget in Config.BUDGET_BROKERS.items() if budget > 0]
    out = df.copy()
    broker_diagnostics: dict[str, dict] = {}
    selected_union: set[str] = set()

    for broker in active_brokers:
        if broker in out.columns:
            candidates = [ticker for ticker in etf_tickers if _is_true(rows[ticker].get(broker))]
            # Protection pour les appelants qui fournissent directement des
            # disponibilités Excel 1/0/NaN : pandas 3 refuse d'écrire False
            # dans une Series float64. object accepte à la fois les valeurs
            # historiques et les booléens produits par la présélection.
            out[broker] = out[broker].astype(object)
        else:
            candidates = []
            out[broker] = False
        selected = _select_for_broker(
            candidates, corr, ticker_index, quality, buckets, forced, cap
        )
        selected_set = set(selected)
        selected_union.update(selected_set)
        etf_mask = out[ticker_col].astype(str).str.strip().isin(etf_tickers)
        rejected_mask = etf_mask & ~out[ticker_col].astype(str).str.strip().isin(selected_set)
        out.loc[rejected_mask, broker] = False
        bucket_counts: dict[str, int] = {}
        for ticker in selected:
            bucket = buckets.get(ticker, "specialise")
            bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
        broker_diagnostics[broker] = {
            "candidates_before": len(candidates),
            "selected": len(selected),
            "target": cap,
            "shortfall": max(0, cap - len(selected)),
            "shortfall_reason": (
                "eligible_catalog_exhausted" if len(selected) < cap else ""
            ),
            "removed": max(0, len(candidates) - len(selected)),
            "bucket_counts": bucket_counts,
            "selected_tickers": selected,
        }

    keep = [
        ticker for ticker in available_tickers
        if ticker.upper() not in excluded
        and (ticker not in etf_tickers or ticker in selected_union)
    ]
    out = out[out[ticker_col].astype(str).str.strip().isin(keep)].copy()
    diagnostics = {
        "enabled": True,
        "max_per_broker": cap,
        "correlation_days": days,
        "n_etf_before": len(etf_tickers),
        "n_etf_after": len(selected_union),
        "n_removed_from_union": len(etf_tickers) - len(selected_union),
        "excluded": sorted(excluded),
        "brokers": broker_diagnostics,
    }
    return returns[keep], out, diagnostics
