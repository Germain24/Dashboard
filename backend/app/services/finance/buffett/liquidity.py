"""Filtre de liquidité pour l'éligibilité à l'optimisation.

On évite d'allouer un titre trop peu liquide (ex. REIT athénien BLEKEDROS.AT à
~5 000 €/jour) : il fausse l'optimiseur (variance faible/artefactuelle → Sharpe
gonflé → sur-pondération) et serait difficile à acheter/revendre. La colonne
``Volume`` est DÉJÀ le volume échangé en €/jour (cf. currency.volume_eur) : on
la compare directement au seuil ``Config.MIN_VOLUME_EUR``.
"""

from __future__ import annotations

from .config import Config


def daily_eur_volume(volume_eur) -> float:
    """Volume échangé par jour en € (0 si donnée manquante/invalide)."""
    try:
        return float(volume_eur or 0)
    except (TypeError, ValueError):
        return 0.0


def is_liquid(volume_eur, min_eur: float | None = None) -> bool:
    """Vrai si le volume €/jour atteint le seuil (défaut ``Config.MIN_VOLUME_EUR``)."""
    threshold = Config.MIN_VOLUME_EUR if min_eur is None else min_eur
    return daily_eur_volume(volume_eur) >= float(threshold)


def passes_portfolio_liquidity(
    volume_eur,
    *,
    is_etf: bool = False,
    is_forced: bool = False,
    min_eur: float | None = None,
) -> bool:
    """Filtre d'univers : seuil actions, exemption ETF et positions forcées.

    Le volume d'une cotation d'ETF ne reflète pas toute sa liquidité économique :
    les teneurs de marché peuvent créer/racheter des parts contre le panier. Le
    volume reste un critère de classement entre ETF, mais pas une exclusion dure.
    """
    return bool(is_forced or is_etf or is_liquid(volume_eur, min_eur=min_eur))
