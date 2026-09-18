"""Validation Yahoo en lots, sans appel `.info` unitaire."""

from __future__ import annotations

from collections.abc import Callable, Iterable


def validate_yahoo_symbols(
    symbols: Iterable[str],
    *,
    batch_size: int = 100,
    downloader: Callable | None = None,
) -> dict[str, bool]:
    """Valide la présence d'un historique court via téléchargements groupés."""
    requested = list(dict.fromkeys(str(s).upper() for s in symbols if str(s).strip()))
    if downloader is None:
        from app.services.finance.yf_session import download_prices_bulk_with_retry
        downloader = download_prices_bulk_with_retry
    result: dict[str, bool] = {}
    for offset in range(0, len(requested), batch_size):
        batch = requested[offset : offset + batch_size]
        frame = downloader(
            batch, period="5d", interval="1d", progress=False, group_by="ticker",
            use_cache=True,
        )
        for symbol in batch:
            valid = False
            if frame is not None and not frame.empty:
                if len(batch) == 1:
                    valid = "Close" in frame and bool(frame["Close"].notna().any())
                elif symbol in frame.columns.get_level_values(0):
                    closes = frame[symbol].get("Close")
                    valid = closes is not None and bool(closes.notna().any())
            result[symbol] = valid
    return result
