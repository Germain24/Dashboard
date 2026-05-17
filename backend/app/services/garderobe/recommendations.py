"""Recommandations d'achat pour la garde-robe.

Port à l'identique de `legacy_code/habits/logic.py`. Analyse 4 axes :
1. Catégories essentielles manquantes ou faibles
2. Équilibre des couleurs (60/30/10)
3. Couleurs orphelines (pas de match dans la palette)
4. Style dominant incomplet
"""

from __future__ import annotations

from typing import Any

from app.services.garderobe.constants import MATCHING_COLORS, SLOTS
from app.services.garderobe.style import get_color_category


def get_purchase_recommendations(wardrobe: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not wardrobe:
        return [{
            "nom": "Haut Neutre (Blanc/Noir)",
            "raison": "Ta garde-robe est vide !",
            "potentiel": 100,
            "type": "Basique",
        }]

    recs: list[dict[str, Any]] = []

    # 1) Catégories essentielles
    cat_counts: dict[str, int] = {}
    for item in wardrobe:
        cat = item.get("categorie", "Autre")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    essential_cats: set[str] = set()
    for s in SLOTS:
        essential_cats.update(s["categories"])

    for cat in essential_cats:
        if cat_counts.get(cat, 0) == 0:
            recs.append({
                "nom": f"{cat} Basique",
                "raison": f"Tu n'as aucun article dans la catégorie '{cat}'.",
                "potentiel": 90,
                "type": "Basique",
            })
        elif cat_counts.get(cat, 0) < 2:
            recs.append({
                "nom": f"Deuxième {cat}",
                "raison": f"Tu n'as qu'un seul article dans la catégorie '{cat}'.",
                "potentiel": 60,
                "type": "Rotation",
            })

    # 2) Ratio couleurs
    color_cats = {"Neutre": 0, "Secondaire": 0, "Accent": 0}
    for item in wardrobe:
        color_cats[get_color_category(item.get("couleur"))] += 1
    total = len(wardrobe)
    ratios = {k: v / total for k, v in color_cats.items()}
    if ratios["Neutre"] < 0.5:
        recs.append({
            "nom": "Haut ou Pantalon Neutre",
            "raison": "Ta garde-robe manque de couleurs neutres pour faciliter les associations.",
            "potentiel": 85,
            "type": "Polyvalence",
        })

    # 3) Couleurs orphelines
    all_colors = {item.get("couleur") for item in wardrobe if item.get("couleur")}
    for color in all_colors:
        if color in MATCHING_COLORS:
            matches = MATCHING_COLORS[color]
            has_match = any(m in all_colors for m in matches)
            if not has_match and matches:
                recs.append({
                    "nom": f"Article {matches[0]}",
                    "raison": f"Tu as des articles '{color}' mais rien pour les accorder.",
                    "potentiel": 75,
                    "type": "Harmonie",
                })

    # 4) Style dominant incomplet
    style_counts: dict[str, int] = {}
    for item in wardrobe:
        s = item.get("style", "")
        styles = s if isinstance(s, list) else [s] if s else []
        for style_name in styles:
            style_counts[style_name] = style_counts.get(style_name, 0) + 1

    if style_counts:
        dominant_style = max(style_counts, key=style_counts.get)
        for slot in SLOTS:
            cats = slot["categories"]
            has_style_in_cat = any(
                dominant_style in (i.get("style") if isinstance(i.get("style"), list) else [i.get("style")])
                for i in wardrobe
                if i.get("categorie") in cats
            )
            if not has_style_in_cat:
                recs.append({
                    "nom": f"{cats[0]} {dominant_style}",
                    "raison": f"Pour compléter ton look '{dominant_style}', il te manque des articles dans la catégorie {cats[0]}.",
                    "potentiel": 70,
                    "type": "Style",
                })

    recs.sort(key=lambda x: x["potentiel"], reverse=True)

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for r in recs:
        if r["nom"] not in seen:
            unique.append(r)
            seen.add(r["nom"])
    return unique[:5]
