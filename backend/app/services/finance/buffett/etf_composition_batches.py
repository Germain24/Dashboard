"""Présélection et validation économique des ETF par lots anticipés.

Le sélecteur final vise ``ETF_MAX_CANDIDATES_PER_BROKER`` ETF par broker.  La
validation historique ne chargeait que ces ETF, puis recommençait la sélection
après chaque rejet.  En fin de catalogue cela pouvait produire des dizaines de
tours d'un seul fonds.  Ce module sélectionne aussi une réserve, la valide dans
le même lot, puis ne relance une vague que si les ETF déjà vérifiés ne suffisent
toujours pas à remplir la cible.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .config import Config
from .etf_selection import select_etfs_per_broker

ProgressCallback = Callable[[int, str, int, int, str], None]
BatchCallback = Callable[[int, list[str], dict], None]


@dataclass
class EtfCompositionBatchResult:
    returns: Any
    frame: Any
    selection_diagnostics: dict
    compositions: dict[str, dict] = field(default_factory=dict)
    quality_by_ticker: dict[str, dict] = field(default_factory=dict)
    exclusions: set[str] = field(default_factory=set)
    rejected_by_broker: dict[str, set[str]] = field(default_factory=dict)
    attempted: set[str] = field(default_factory=set)
    batches: int = 0
    stopped: bool = False
    initial_broker_candidates: dict[str, int] = field(default_factory=dict)


def select_verified_etfs_per_broker(
    returns_pool,
    frame_pool,
    ticker_col: str,
    *,
    etf_tickers: set[str],
    metadata_by_ticker: dict[str, Any],
    constituent_metadata: dict[str, dict],
    forced_tickers: list[str] | None = None,
    returns_are_base_currency: bool = True,
    should_stop: Callable[[], bool] | None = None,
    on_batch: BatchCallback | None = None,
    on_progress: ProgressCallback | None = None,
    on_error: Callable[[Exception], None] | None = None,
    budget=None,
) -> EtfCompositionBatchResult:
    """Valide la cible ETF avec une réserve de remplaçants à chaque vague."""
    from .equity_lookthrough import etf_composition_quality, fetch_etf_holdings
    from .etf_research_budget import EtfResearchBudget
    if budget is None:
        budget = EtfResearchBudget()

    target = max(1, int(Config.ETF_MAX_CANDIDATES_PER_BROKER))
    buffer_size = max(0, int(Config.ETF_COMPOSITION_BATCH_BUFFER_PER_BROKER))
    batch_cap = target + buffer_size
    normalized_etfs = {str(value).strip().upper() for value in etf_tickers}
    exclusions: set[str] = set()
    attempted: set[str] = set()
    compositions: dict[str, dict] = {}
    quality_by_ticker: dict[str, dict] = {}
    rejected_by_broker: dict[str, set[str]] = {}
    initial_broker_candidates: dict[str, int] = {}
    batches = 0

    final_returns, final_frame, final_diagnostics = select_etfs_per_broker(
        returns_pool,
        frame_pool,
        ticker_col,
        maximum=target,
        returns_are_base_currency=returns_are_base_currency,
        excluded_tickers=exclusions,
        forced_tickers=forced_tickers,
    )

    while True:
        if should_stop is not None and should_stop():
            return EtfCompositionBatchResult(
                final_returns,
                final_frame,
                final_diagnostics,
                compositions,
                quality_by_ticker,
                exclusions,
                rejected_by_broker,
                attempted,
                batches,
                True,
                initial_broker_candidates,
            )

        batches += 1
        batch_returns, _batch_frame, batch_diagnostics = select_etfs_per_broker(
            returns_pool,
            frame_pool,
            ticker_col,
            maximum=batch_cap,
            returns_are_base_currency=returns_are_base_currency,
            excluded_tickers=exclusions,
            forced_tickers=forced_tickers,
        )
        if not initial_broker_candidates:
            initial_broker_candidates = {
                broker: int(values.get("candidates_before", 0))
                for broker, values in (batch_diagnostics.get("brokers") or {}).items()
            }

        selected_batch = sorted(
            str(ticker).strip().upper()
            for ticker in batch_returns.columns
            if str(ticker).strip().upper() in normalized_etfs
        )
        pending = [ticker for ticker in selected_batch if ticker not in attempted]
        if on_batch is not None:
            on_batch(batches, pending, batch_diagnostics)

        if pending:
            attempted.update(pending)

            def progress(
                stage: str,
                done: int,
                total: int,
                item: str,
                current_batch: int = batches,
            ) -> None:
                if on_progress is not None:
                    on_progress(current_batch, stage, done, total, item)

            try:
                compositions.update(
                    fetch_etf_holdings(
                        pending,
                        refresh_indices=True,
                        budget=budget,
                        progress_cb=progress,
                        **({"should_stop": should_stop} if should_stop is not None else {}),
                    )
                )
            except Exception as exc:  # pragma: no cover - garde réseau global
                if on_error is not None:
                    on_error(exc)

        rejected: set[str] = set()
        for ticker in selected_batch:
            if ticker not in attempted:
                continue
            quality = etf_composition_quality(
                compositions.get(ticker, {}),
                metadata_by_ticker.get(ticker, {}),
                minimum_coverage=float(Config.ETF_ECONOMIC_COMPOSITION_MIN_COVERAGE),
                constituent_metadata=constituent_metadata,
            )
            quality_by_ticker[ticker] = quality
            if not quality["eligible"]:
                rejected.add(ticker)

        for broker, values in (batch_diagnostics.get("brokers") or {}).items():
            selected_for_broker = {
                str(value).strip().upper()
                for value in values.get("selected_tickers", [])
            }
            rejected_by_broker.setdefault(broker, set()).update(
                rejected & selected_for_broker
            )
        exclusions.update(rejected)

        final_returns, final_frame, final_diagnostics = select_etfs_per_broker(
            returns_pool,
            frame_pool,
            ticker_col,
            maximum=target,
            returns_are_base_currency=returns_are_base_currency,
            excluded_tickers=exclusions,
            forced_tickers=forced_tickers,
        )
        selected_target = {
            str(ticker).strip().upper()
            for ticker in final_returns.columns
            if str(ticker).strip().upper() in normalized_etfs
        }
        missing_target = selected_target - attempted
        if not missing_target:
            break

        # Aucun nouveau candidat dans le lot élargi : le catalogue admissible a
        # été réellement épuisé. Cette garde garantit une terminaison monotone.
        if not pending or batches >= max(1, int(Config.ETF_COMPOSITION_MAX_ROUNDS)):
            # Exclude ALL unverified candidates; otherwise reselection simply
            # promotes yet another unverified ETF at the budget boundary.
            exclusions.update(normalized_etfs - {
                ticker for ticker, quality in quality_by_ticker.items() if quality.get("eligible")
            })
            final_returns, final_frame, final_diagnostics = select_etfs_per_broker(
                returns_pool,
                frame_pool,
                ticker_col,
                maximum=target,
                returns_are_base_currency=returns_are_base_currency,
                excluded_tickers=exclusions,
                forced_tickers=forced_tickers,
            )
            break

    final_diagnostics["research_budget"] = budget.snapshot()
    return EtfCompositionBatchResult(
        final_returns,
        final_frame,
        final_diagnostics,
        compositions,
        quality_by_ticker,
        exclusions,
        rejected_by_broker,
        attempted,
        batches,
        False,
        initial_broker_candidates,
    )
