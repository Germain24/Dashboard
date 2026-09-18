"""Conversion des positions réelles en poids globaux par courtier."""

from __future__ import annotations

import math

from sqlmodel import select

from app.models.finance import Position

from .broker_budgets import canonical_broker_name


def current_broker_weights(
    session,
    *,
    prices_eur: dict[str, float],
    total_capital_eur: float,
    active_brokers: list[str],
) -> dict[str, dict[str, float]]:
    """Retourne ``broker -> ticker -> fraction du capital total``.

    Les cours proviennent du téléchargement déjà effectué pour l'optimisation :
    cette lecture n'ajoute donc aucun appel Yahoo. Les positions sans cours
    exploitable sont ignorées et pourront être signalées par le diagnostic.
    """
    total = max(float(total_capital_eur or 0.0), 1e-9)
    active = {canonical_broker_name(b): b for b in active_brokers}
    output: dict[str, dict[str, float]] = {b: {} for b in active_brokers}
    for position in session.exec(select(Position)).all():
        broker = active.get(canonical_broker_name(position.broker))
        ticker = str(position.ticker or "").strip().upper()
        price = float(prices_eur.get(ticker, 0.0) or 0.0)
        quantity = float(position.quantite or 0.0)
        if (
            broker is None
            or not ticker
            or not math.isfinite(price)
            or not math.isfinite(quantity)
            or price <= 0
            or abs(quantity) <= 1e-12
        ):
            continue
        output[broker][ticker] = output[broker].get(ticker, 0.0) + (
            quantity * price / total
        )
    return output
