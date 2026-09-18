"""Score de style et compatibilité couleurs.

Port à l'identique de `legacy_code/habits/logic.py`. Le score combine :
- 30 % cohérence de style (multi-styles supporté)
- 40 % matching couleurs deux-à-deux
- 30 % respect du ratio 60/30/10 (Neutres / Secondaires / Accents)
"""

from __future__ import annotations

from typing import Any

from app.services.garderobe.constants import (
    ACCENTS,
    MATCHING_COLORS,
    NEUTRES,
    SECONDAIRES,
)


def get_color_category(color: str | None) -> str:
    """Retourne 'Neutre', 'Secondaire' ou 'Accent'."""
    if not color:
        return "Accent"
    c_lower = color.lower()
    if any(n.lower() == c_lower for n in NEUTRES):
        return "Neutre"
    if any(s.lower() == c_lower for s in SECONDAIRES):
        return "Secondaire"
    if any(a.lower() == c_lower for a in ACCENTS):
        return "Accent"
    return "Accent"


def colors_compat(c1: str | None, c2: str | None) -> bool:
    if not c1 or not c2:
        return True
    cat1 = get_color_category(c1)
    cat2 = get_color_category(c2)
    if cat1 == "Neutre" or cat2 == "Neutre":
        return True
    if c2 in MATCHING_COLORS.get(c1, []) or c1 in MATCHING_COLORS.get(c2, []):
        return True
    if cat1 == cat2:
        return True
    return False


def _styles_of(item: dict[str, Any]) -> set[str]:
    s = item.get("style") or []
    if isinstance(s, list):
        return {x for x in s if x}
    if isinstance(s, str) and s:
        return {s}
    return set()


def style_score(items: list[dict[str, Any] | None]) -> float:
    """Score de style 0–100 pour une collection d'items (None autorisés)."""
    if not items:
        return 0.0

    valid_items = [i for i in items if i is not None]
    if not valid_items:
        return 0.0

    # 1. Cohérence de style
    item_styles = [_styles_of(i) for i in valid_items]
    all_possible_styles: set[str] = set()
    for s_set in item_styles:
        all_possible_styles.update(s_set)

    if not all_possible_styles:
        style_consist = 50.0  # neutre si aucun style défini
    else:
        max_score = 0.0
        for style in all_possible_styles:
            matches = sum(1 for s_set in item_styles if style in s_set)
            current = (matches / len(valid_items)) * 100.0
            if current > max_score:
                max_score = current
        style_consist = max_score

    # 2. Matching couleurs deux-à-deux
    colors = [i.get("couleur", "") for i in valid_items if i.get("couleur")]
    match_score = 100.0
    if len(colors) >= 2:
        pairs = 0
        matches = 0.0
        for i in range(len(colors)):
            for j in range(i + 1, len(colors)):
                c1, c2 = colors[i], colors[j]
                pairs += 1
                if c2 in MATCHING_COLORS.get(c1, []) or c1 in MATCHING_COLORS.get(c2, []):
                    matches += 1.0
                elif get_color_category(c1) == "Neutre" or get_color_category(c2) == "Neutre":
                    matches += 0.7
                elif get_color_category(c1) == get_color_category(c2):
                    matches += 0.5
        match_score = (matches / pairs) * 100.0 if pairs > 0 else 100.0

    # 3. Ratio 60/30/10
    counts = {"Neutre": 0, "Secondaire": 0, "Accent": 0}
    for c in colors:
        counts[get_color_category(c)] += 1

    total = len(colors) if colors else 1
    ratios = {k: v / total for k, v in counts.items()}
    dist = (
        abs(ratios["Neutre"] - 0.6)
        + abs(ratios["Secondaire"] - 0.3)
        + abs(ratios["Accent"] - 0.1)
    )
    ratio_score = max(0.0, 100.0 * (1 - dist / 1.5))

    return (style_consist * 0.3) + (match_score * 0.4) + (ratio_score * 0.3)
