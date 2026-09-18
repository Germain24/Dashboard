"""Cotation et cours figés communs à la comparaison et aux ordres proposés."""

from __future__ import annotations


def prepare_execution_quotes(tickers, brokers, access, frame, prices):
    """Résout les routes broker et charge leurs cours une seule fois par calcul.

    Une route secondaire sans cours reste indisponible : le cours de la
    cotation principale ne permet pas d'en déduire une quantité achetable.
    """
    from .allocation import close_prices_from_download, latest_prices_eur

    rows = {
        str(row.get("Ticker Yahoo Finance") or "").strip().upper(): row
        for _, row in frame.iterrows()
    }
    routes = {}
    secondary = set()
    for i, ticker in enumerate(tickers):
        metadata = rows.get(str(ticker).upper(), {}).get("Execution Routes")
        metadata = metadata if isinstance(metadata, dict) else {}
        for j, broker in enumerate(brokers):
            route = str(metadata.get(broker) or ticker).strip() or ticker
            routes[ticker, broker] = route
            if access[i][j] and route.upper() != ticker.upper():
                secondary.add(route)
    secondary_prices = {}
    if secondary:
        from app.services.finance.yf_session import download_prices_bulk_with_retry

        requested = sorted(secondary)
        raw = download_prices_bulk_with_retry(
            requested, period="5d", interval="1d", progress=False,
            group_by="ticker", use_cache=True,
        )
        if raw is not None and not raw.empty:
            secondary_prices = latest_prices_eur(
                close_prices_from_download(raw, requested), requested,
            )
    quoted = {
        (ticker, broker): (
            prices.get(ticker, 0.0)
            if routes[ticker, broker].upper() == ticker.upper()
            else secondary_prices.get(routes[ticker, broker], 0.0)
        )
        for ticker in tickers for broker in brokers
    }
    return routes, quoted
