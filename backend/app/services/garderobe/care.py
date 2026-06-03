"""Étiquettes d'entretien (lavage) dérivées de la matière (#81).

On ne stocke pas l'étiquette : on la dérive de `matiere`. Permet d'afficher la
consigne de lavage/séchage sans saisie supplémentaire. Matière inconnue →
consigne générique prudente.
"""

from __future__ import annotations

from typing import Any, Optional

# matière (lower) -> consigne
_CARE: dict[str, dict[str, Any]] = {
    "laine":       {"lavage": "Lavage main", "temperature": 30, "sechage": "À plat", "icones": "🧼🚫🌀", "delicat": True},
    "cachemire":   {"lavage": "Lavage main", "temperature": 30, "sechage": "À plat", "icones": "🧼🚫🌀", "delicat": True},
    "soie":        {"lavage": "Lavage main", "temperature": 30, "sechage": "À plat, pas de sèche-linge", "icones": "🧼🚫♨️", "delicat": True},
    "duvet":       {"lavage": "Machine cycle doux", "temperature": 30, "sechage": "Sèche-linge doux + balles", "icones": "🌀", "delicat": True},
    "polaire":     {"lavage": "Machine", "temperature": 30, "sechage": "Pas de sèche-linge chaud", "icones": "🌀", "delicat": False},
    "synthétique": {"lavage": "Machine", "temperature": 30, "sechage": "Sèche-linge doux", "icones": "🌀", "delicat": False},
    "coton":       {"lavage": "Machine", "temperature": 40, "sechage": "Sèche-linge ok", "icones": "🌀", "delicat": False},
    "lin":         {"lavage": "Machine", "temperature": 40, "sechage": "Séchage à l'air conseillé", "icones": "🌀", "delicat": False},
    "denim":       {"lavage": "Machine sur l'envers", "temperature": 30, "sechage": "À l'air pour garder la couleur", "icones": "🌀", "delicat": False},
    "cuir":        {"lavage": "Nettoyage spécialisé", "temperature": 0, "sechage": "Jamais de machine", "icones": "🚫💧", "delicat": True},
}

_GENERIC = {"lavage": "Machine", "temperature": 30, "sechage": "Sèche-linge doux", "icones": "🌀", "delicat": False}


def care_label(matiere: Optional[str]) -> dict[str, Any]:
    """Consigne d'entretien pour une matière. Matière inconnue → générique."""
    key = (matiere or "").strip().lower()
    base = _CARE.get(key, _GENERIC)
    temp = base["temperature"]
    resume = (
        f"{base['lavage']} {temp}°C · {base['sechage']}"
        if temp
        else f"{base['lavage']} · {base['sechage']}"
    )
    return {**base, "matiere": matiere, "resume": resume}
