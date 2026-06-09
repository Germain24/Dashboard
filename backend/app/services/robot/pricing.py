"""Tarification d'usage de l'API Claude (#165) — fonctions pures.

Prix par million de tokens (USD), source skill claude-api (cache 2026-05).
Les lectures de cache coûtent ~0.1x l'input, les écritures ~1.25x.
"""

from __future__ import annotations

# model -> (input $/Mtok, output $/Mtok)
PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}

DEFAULT_PRICING = (5.0, 25.0)
CACHE_READ_FACTOR = 0.1
CACHE_WRITE_FACTOR = 1.25


def model_pricing(model: str) -> tuple[float, float]:
    """Prix (input, output) $/Mtok pour un modèle, défaut Opus si inconnu."""
    return PRICING.get(model, DEFAULT_PRICING)


def compute_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
) -> float:
    """Pur : coût USD d'un appel.

    `input_tokens` = tokens NON cachés (plein tarif). Les tokens lus du cache et
    écrits dans le cache sont facturés séparément à leur facteur.
    """
    in_price, out_price = model_pricing(model)
    cost = (
        input_tokens * in_price
        + output_tokens * out_price
        + cache_read_tokens * in_price * CACHE_READ_FACTOR
        + cache_creation_tokens * in_price * CACHE_WRITE_FACTOR
    ) / 1_000_000
    return round(cost, 6)
