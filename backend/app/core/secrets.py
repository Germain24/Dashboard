"""Gestion des secrets (#192) : masquage + état des intégrations sans fuite.

Politique : les secrets vivent uniquement dans `.env` (gitignoré, jamais commité)
et sont validés par `Settings`. On ne les journalise jamais en clair — d'où
`mask_secret`. Le chiffrement « au repos » n'est volontairement pas implémenté :
sur une machine locale mono-utilisateur, la clé de déchiffrement devrait vivre à
côté du secret, sans gain de sécurité réel face à un accès disque.
"""

from __future__ import annotations


def mask_secret(value: str | None, *, visible: int = 4) -> str:
    """Masque un secret pour l'affichage : ``"sk-abcd…wxyz"`` ou ``"(absent)"``.

    Ne révèle au plus que ``visible`` caractères de début et de fin, et seulement
    si le secret est assez long pour que ça ne le divulgue pas.
    """
    if not value:
        return "(absent)"
    if len(value) <= visible * 2:
        return "•" * len(value)
    return f"{value[:visible]}…{value[-visible:]}"


def integration_status(settings) -> dict[str, bool]:
    """Quelles intégrations sont configurées (présence, jamais la valeur)."""
    return {
        "google_calendar": bool(
            settings.google_client_id
            and settings.google_client_secret
            and settings.google_refresh_token
        ),
        "ical_sync": bool(settings.ical_sync_url_list),
        "anthropic": bool(getattr(settings, "anthropic_api_key", "")),
    }
