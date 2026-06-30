"""Filtre de liquidité pour l'éligibilité à l'optimisation.

On évite d'allouer un titre trop peu liquide (ex. REIT athénien BLEKEDROS.AT à
~5 000 €/jour) : il fausse l'optimiseur (variance faible/artefactuelle → Sharpe
gonflé → sur-pondération) et serait difficile à acheter/revendre. Mesure retenue :
**volume échangé en €/jour** = volume (actions) × prix. Seuil : ``Config.MIN_VOLUME_EUR``.
"""

from __future__ import annotations

from .config import Config


def daily_eur_volume(volume, prix) -> float:
    """Volume échangé par jour en € = nb d'actions × prix (0 si donnée manquante)."""
    try:
        return float(volume or 0) * float(prix or 0)
    except (TypeError, ValueError):
        return 0.0


def is_liquid(volume, prix, min_eur: float | None = None) -> bool:
    """Vrai si le volume €/jour atteint le seuil (défaut ``Config.MIN_VOLUME_EUR``)."""
    threshold = Config.MIN_VOLUME_EUR if min_eur is None else min_eur
    return daily_eur_volume(volume, prix) >= float(threshold)
