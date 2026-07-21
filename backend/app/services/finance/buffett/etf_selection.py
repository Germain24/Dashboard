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
    values = np.asarray(returns[tickers], dtype=float)
    ranks = np.apply_along_axis(stats.rankdata, 0, values)
    corr = np.atleast_2d(np.corrcoef(ranks, rowvar=False))
    from .starr import shrink_correlation

    corr = shrink_correlation(corr, float(Config.STARR_CORRELATION_SHRINKAGE))
    # Une corrélation inconnue ne doit pas être interprétée comme diversification.
    corr = np.nan_to_num(corr, nan=0.75, posinf=0.75, neginf=-0.75)
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
) -> tuple[object, object, dict]:
    """Limite les ETF admissibles à ``maximum`` par broker actif.

    Retourne ``(returns_filtrés, df_filtré_avec_masques_broker, diagnostics)``.
    Un ETF partagé n'est allouable chez un broker que s'il appartient à la sélection
    de ce broker. L'union des sélections reste disponible pour l'optimisation.
    """
    from .dedup import returns_in_base_currency
    from .optimizer import _is_true

    cap = int(
        Config.ETF_MAX_CANDIDATES_PER_BROKER if maximum is None else maximum
    )
    if cap <= 0 or df is None or getattr(df, "empty", True):
        return returns, df, {"enabled": False, "reason": "invalid_cap_or_empty_data"}

    available_tickers = list(returns.columns)
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
    if not etf_tickers:
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
            candidates = list(etf_tickers)
            out[broker] = True
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
            "removed": max(0, len(candidates) - len(selected)),
            "bucket_counts": bucket_counts,
            "selected_tickers": selected,
        }

    keep = [
        ticker for ticker in available_tickers
        if ticker not in etf_tickers or ticker in selected_union
    ]
    out = out[out[ticker_col].astype(str).str.strip().isin(keep)].copy()
    diagnostics = {
        "enabled": True,
        "max_per_broker": cap,
        "correlation_days": days,
        "n_etf_before": len(etf_tickers),
        "n_etf_after": len(selected_union),
        "n_removed_from_union": len(etf_tickers) - len(selected_union),
        "brokers": broker_diagnostics,
    }
    return returns[keep], out, diagnostics
