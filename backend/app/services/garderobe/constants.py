"""Constantes du module Garde-robe : slots, palette de couleurs, matières.

Toutes les valeurs métier issues du `legacy_code/habits/logic.py` (port à
l'identique sauf indication contraire).
"""

from __future__ import annotations

from typing import TypedDict


class SlotConfig(TypedDict, total=False):
    id: str
    emoji: str
    categories: list[str]
    need: str        # "ALWAYS" | "METEO" | "OPTIONAL"
    trigger: str     # pour les slots METEO : "cold_or_rain" | "cool" | "very_cold"


# ─────────────────────────────────────────────────────────────────────────────
# 12 emplacements de tenue
# ─────────────────────────────────────────────────────────────────────────────
SLOTS: list[SlotConfig] = [
    {"id": "Manteau",    "emoji": "🧥", "categories": ["Manteau"],                                "need": "METEO",    "trigger": "cold_or_rain"},
    {"id": "Veste",      "emoji": "🧥", "categories": ["Veste"],                                  "need": "METEO",    "trigger": "cool"},
    {"id": "Haut",       "emoji": "👕", "categories": ["Haut", "T-shirt", "Chemise", "Pull", "Shirt"], "need": "ALWAYS"},
    {"id": "Pantalon",   "emoji": "👖", "categories": ["Pantalon", "Short", "Jean"],              "need": "ALWAYS"},
    {"id": "Chaussures", "emoji": "👟", "categories": ["Chaussures", "Bottes", "Sneakers"],       "need": "ALWAYS"},
    {"id": "Echarpe",    "emoji": "🧣", "categories": ["Accessoire Cou"],                         "need": "METEO",    "trigger": "very_cold"},
    {"id": "Casquette",  "emoji": "🧢", "categories": ["Tête"],                                   "need": "OPTIONAL"},
    {"id": "Lunettes",   "emoji": "🕶️", "categories": ["Yeux"],                                   "need": "OPTIONAL"},
    {"id": "Bijoux 1",   "emoji": "💍", "categories": ["Bijoux"],                                 "need": "OPTIONAL"},
    {"id": "Bijoux 2",   "emoji": "💍", "categories": ["Bijoux"],                                 "need": "OPTIONAL"},
    {"id": "Montre",     "emoji": "⌚", "categories": ["Poignet"],                                "need": "OPTIONAL"},
    {"id": "Pendentif",  "emoji": "📿", "categories": ["Cou"],                                    "need": "OPTIONAL"},
]


# Emojis par catégorie (fallback quand pas d'asset PNG)
EMO_CAT: dict[str, str] = {
    "Manteau": "🧥", "Veste": "🧥",
    "Haut": "👕", "T-shirt": "👕", "Chemise": "👔", "Shirt": "👔", "Pull": "🧶",
    "Pantalon": "👖", "Short": "🩳", "Jean": "👖",
    "Chaussures": "👟", "Bottes": "🥾", "Sneakers": "👟",
    "Accessoire Cou": "🧣",
    "Tête": "🧢",
    "Yeux": "🕶️",
    "Bijoux": "💍",
    "Poignet": "⌚",
    "Cou": "📿",
}


# Coefficients de chaleur par matière (multiplicatifs)
MATIERE_THERMIQUE: dict[str, float] = {
    "Laine": 1.8,
    "Cachemire": 2.0,
    "Duvet": 2.5,
    "Polaire": 1.5,
    "Coton": 1.0,
    "Denim": 1.1,
    "Synthétique": 1.2,
    "Cuir": 1.3,
    "Soie": 1.1,
    "Lin": 0.8,
}


# Catégories qui ne tiennent pas chaud (impact thermique nul)
THERMAL_NEUTRAL_CATS = {"Yeux", "Bijoux", "Poignet", "Cou"}


# ─────────────────────────────────────────────────────────────────────────────
# Palette couleurs (Old Money + accents)
# ─────────────────────────────────────────────────────────────────────────────
COULEURS_TOP = [
    "Bleu Marine",
    "Gris Anthracite",
    "Blanc Pur",
    "Vert Sapin",
    "Bordeaux",
    "Bleu Cobalt",
    "Noir",
]

COULEURS_A_EVITER = [
    "Olive Jauni",
    "Jaune Moutarde",
    "Orange / Rouille",
    "Beige Camel",
    "Marron Chocolat",
    "Saumon / Pêche",
]

MATCHING_COLORS: dict[str, list[str]] = {
    "Marron":           ["Bleu ciel", "Terracotta", "Ocre", "Beige", "Camel"],
    "Khaki":            ["Bordeaux", "Prune", "Moutarde", "Olive", "Vert sauge", "Vert pâle"],
    "Bleu marine":      ["Orange cuivré", "Brique", "Vert sapin", "Violet", "Bleu ciel", "Bleu gris"],
    "Vert émeraude":    ["Rouge cerise", "Bordeaux", "Bleu marine", "Bleu canard", "Gris anthracite", "Noir"],
    "Gris anthracite":  ["Jaune moutarde", "Ocre", "Bleu marine", "Gris perle", "Blanc", "Rose poudré"],
    "Beige sable":      ["Bleu marine", "Bleu indigo", "Marron", "Khaki", "Ocre", "Blanc", "Gris clair"],
    "Noir anthracite":  ["Jaune moutarde", "Orange brûlé", "Bleu marine", "Gris graphite", "Blanc cassé", "Beige sable"],
    "Bordeaux":         ["Vert émeraude", "Khaki", "Bleu marine", "Violet", "Gris anthracite", "Beige sable"],
    "Bleu ciel":        ["Marron", "Bleu marine", "Terracotta", "Gris anthracite", "Beige sable", "Bordeaux", "Blanc"],
    "Beige clair":      ["Noir", "Noir anthracite", "Bleu marine", "Marron", "Gris anthracite", "Bordeaux", "Bleu ciel", "Blanc"],
    "Or":               ["Bleu marine", "Vert émeraude", "Marron", "Khaki", "Bordeaux", "Noir anthracite", "Beige sable", "Beige clair"],
}

NEUTRES = ["Noir", "Blanc", "Bleu marine", "Gris anthracite", "Beige sable", "Noir anthracite", "Bleu ciel"]
SECONDAIRES = ["Marron", "Khaki", "Vert émeraude", "Bordeaux"]
ACCENTS = ["Or"]


# ─────────────────────────────────────────────────────────────────────────────
# Body coton — paramètres
# ─────────────────────────────────────────────────────────────────────────────
BODY_THERMAL_BONUS = 1.5  # bonus de chaleur quand le body est porté
