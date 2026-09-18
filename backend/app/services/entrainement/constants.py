"""Constantes du module Entraînement — CONV 7.

Décisions prises :
- Split par défaut : PPL / Repos / UL / Repos (5 jours sport, 2 jours repos).
- Cardio V1 : course à pied uniquement (distance + temps).
- Catalogue : seed maison ~30 exos clés, ajout à la volée via POST /exercises.
- 1RM : formule Epley.
"""

from __future__ import annotations

# Catégories d'exercices (utilisées par seed + filtres UI)
CATEGORIES: tuple[str, ...] = (
    "push", "pull", "legs", "upper", "lower", "core", "cardio",
)

# Niveaux d'intensité — contrat figé avec Santé (CONV 3).
INTENSITY_LEVELS: tuple[str, ...] = ("none", "low", "medium", "high")

# Labels d'un jour de programme (en français — affiché dans l'UI)
DAY_LABELS: tuple[str, ...] = (
    "Push", "Pull", "Legs", "Upper", "Lower", "Repos", "Cardio", "Custom",
)

# Programme par défaut (réponse à la 1re question des décisions CONV 7) :
# Germain s'entraîne 5j/sem : Lun=Push, Mar=Pull, Mer=Legs, Jeu=Repos,
# Ven=Upper, Sam=Lower, Dim=Repos.
DEFAULT_PROGRAMME_NAME = "PPL/UL"
DEFAULT_PROGRAMME_DESCRIPTION = (
    "Push / Pull / Legs / Repos / Upper / Lower / Repos — 5 jours sport. "
    "Volume hebdomadaire : 2× chaque groupe musculaire. Adapté prise de muscle."
)
DEFAULT_WEEKDAY_LABELS: dict[int, str] = {
    0: "Push",    # lundi
    1: "Pull",    # mardi
    2: "Legs",    # mercredi
    3: "Repos",   # jeudi
    4: "Upper",   # vendredi
    5: "Lower",   # samedi
    6: "Repos",   # dimanche
}

# Pour le défaut date-based de l'intensité (fallback uniquement).
SPORT_WEEKDAYS_DEFAULT: tuple[int, ...] = (0, 1, 2, 4, 5)

# Seuils utilisés par compute_intensity_for_session
# (cf. brief CONV 7, section "Lien avec Nutrition") :
#   - low    : récup active / mobilité (< 30 min, faible charge)
#   - medium : séance normale (~ 45-60 min)
#   - high   : séance lourde (> 60 min OU charge > 80% du 1RM moyen)
DUREE_LOW_MAX_MIN = 30
DUREE_HIGH_MIN_MIN = 60
PCT_1RM_HIGH = 0.80
