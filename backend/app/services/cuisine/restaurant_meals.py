"""Plats Crew disponibles avec le crédit repas des shifts.

Les prix viennent du menu de commande Crew Collective & Café (catégorie
"From the Kitchen", consulté le 14 septembre 2026). Les macros ne sont pas
publiées par le restaurant : ce sont des estimations à partir des ingrédients.
"""

from __future__ import annotations

import datetime as dt
from itertools import combinations

MENU_URL = "https://order.koomi.com/crew-collective-cafe-8erOozBrrP/fr/2016031701/dinein/menu/de-la-cuisine-25"
COUPON_CAD = 30.0
NOTE_PREFIX = "crew-menu:"

# kcal, protéines, glucides et lipides par portion. Soupe et gâteau sont
# écartés : ce ne sont pas des repas complets pour l'optimisation du plan.
MENU: tuple[dict, ...] = (
    {"id": 4170, "name": "Chili crisp tuna bun", "price": 20, "description": "Laitue iceberg, coriandre, amande", "calories": 610, "proteines": 38, "glucides": 55, "lipides": 27},
    {"id": 4168, "name": "Green goddess salad & achiote chicken", "price": 28, "description": "Verdure locale, avocat, feta crémeuse, tomate, noix, poulet", "calories": 650, "proteines": 45, "glucides": 35, "lipides": 38},
    {"id": 4166, "name": "Za'atar salmon bowl", "price": 29, "description": "Zhoug épicé, freekeh, œuf, salade de fenouil", "calories": 700, "proteines": 42, "glucides": 58, "lipides": 32},
    {"id": 4007, "name": "Turkey BLT", "price": 20, "description": "Pain blanc, tomate, mayo épicée, laitue, bacon, dinde fumée", "calories": 680, "proteines": 39, "glucides": 57, "lipides": 31},
    {"id": 3761, "name": "Three cheeses grilled cheese", "price": 22, "description": "Pain au levain, confiture bacon-oignon, trempette au poivron", "calories": 790, "proteines": 29, "glucides": 69, "lipides": 44},
    {"id": 3760, "name": "Avocado toast", "price": 19, "description": "Salsa macha au tournesol, œuf", "calories": 560, "proteines": 19, "glucides": 47, "lipides": 34},
    {"id": 675, "name": "Fairmont bagel & smoked salmon", "price": 26, "description": "Saumon fumé, fromage à la crème, concombre, aneth, oignon, câpre", "calories": 610, "proteines": 31, "glucides": 62, "lipides": 25},
    {"id": 459, "name": "Yogurt & Granola", "price": 19, "description": "Yogourt grec, fruits de saison, granola, érable, noix", "calories": 520, "proteines": 24, "glucides": 72, "lipides": 15},
    {"id": 4167, "name": "Pain Doré", "price": 29, "description": "Fraises du Québec, yogourt fouetté, érable, noisette", "calories": 760, "proteines": 20, "glucides": 105, "lipides": 27},
)

# Portions de recette approximatives servant uniquement à estimer les
# micronutriments à partir du catalogue CIQUAL local. Les macros globaux du
# plat restent les estimations dédiées ci-dessus.
ESTIMATED_INGREDIENTS: dict[int, tuple[tuple[str, float], ...]] = {
    4170: (("Thon jaune en conserve", 90), ("Pain complet", 80), ("Epinards", 25), ("Dion Persil", 5), ("Amandes", 8), ("Huile d'olive extra-vierge", 8)),
    4168: (("Poitrine de poulet", 120), ("Epinards", 50), ("Avocat", 50), ("Feta", 30), ("Tomate fraiche", 50), ("Noix de Grenoble", 10), ("Huile d'olive extra-vierge", 8)),
    4166: (("Saumon atlantique", 130), ("Boulgour (sec)", 50), ("Oeufs", 50), ("Celeri", 60), ("Dion Persil", 10), ("Huile d'olive extra-vierge", 8)),
    4007: (("Dinde hachee", 90), ("Bacon", 20), ("Pain complet", 75), ("Tomate fraiche", 35), ("Epinards", 15), ("Huile de canola", 8)),
    3761: (("Pain complet", 90), ("Fromage cheddar", 25), ("Mozzarella", 25), ("Parmesan", 10), ("Bacon", 15), ("Poivron rouge", 25)),
    3760: (("Pain complet", 65), ("Avocat", 70), ("Oeufs", 50), ("Graines de tournesol", 10), ("Tomate fraiche", 25)),
    675: (("Selection Bagels nature", 100), ("Saumon fume", 60), ("Philadelphia Fromage a la creme fouette original", 25), ("Concombre", 50), ("Oignon", 10), ("Dion Persil", 3)),
    459: (("Yogourt grec nature entier", 100), ("Flocons d'avoine", 35), ("Bleuets frais", 50), ("Sirop d'erable", 15), ("Noix de Grenoble", 10)),
    4167: (("Pain complet", 100), ("Oeufs", 50), ("Fraises", 50), ("Yogourt grec nature entier", 40), ("Sirop d'erable", 15), ("Amandes", 8)),
}

MEAL_WINDOWS = (
    ("petit_dejeuner", dt.time(6), dt.time(10)),
    ("dejeuner", dt.time(11), dt.time(15)),
    ("souper", dt.time(17), dt.time(22)),
)


def menu_item(product_id: int) -> dict | None:
    item = next((item for item in MENU if item["id"] == product_id), None)
    if item is None:
        return None
    return {
        **item,
        "ingredients_micro_estimes": [
            {"aliment": name, "quantite_g": grams}
            for name, grams in ESTIMATED_INGREDIENTS.get(product_id, ())
        ],
        "menu_url": MENU_URL,
        "macros_estimees": True,
        "micros_estimes": True,
    }


def entry_menu_id(notes: str | None) -> int | None:
    if not notes or not notes.startswith(NOTE_PREFIX):
        return None
    try:
        return int(notes[len(NOTE_PREFIX):])
    except ValueError:
        return None


def week_start(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError:
        year, week = value.split("-W", 1)
        return dt.date.fromisocalendar(int(year), int(week), 1)


def _overlap_minutes(start: dt.datetime, end: dt.datetime, day: dt.date, start_time: dt.time, end_time: dt.time) -> int:
    window_start = dt.datetime.combine(day, start_time)
    window_end = dt.datetime.combine(day, end_time)
    return max(0, int((min(end, window_end) - max(start, window_start)).total_seconds() // 60))


def assign_shift_meals(shifts: list[tuple[dt.datetime, dt.datetime]]) -> dict[dt.date, dict[str, dict]]:
    """Associe un coupon à un repas par shift, au plus un coupon par repas/jour."""
    assigned: dict[dt.date, dict[str, dict]] = {}
    for start, end in sorted(shifts):
        last_day = (end - dt.timedelta(microseconds=1)).date()
        candidate_days = [start.date() + dt.timedelta(days=i) for i in range((last_day - start.date()).days + 1)]
        choices: list[tuple[int, int, dt.date, str]] = []
        for day in candidate_days:
            day_assignments = assigned.get(day, {})
            for meal, window_start, window_end in MEAL_WINDOWS:
                if meal in day_assignments:
                    continue
                overlap = _overlap_minutes(start, end, day, window_start, window_end)
                window_begin = dt.datetime.combine(day, window_start)
                window_finish = dt.datetime.combine(day, window_end)
                distance = max(0, int((max(window_begin - end, start - window_finish)).total_seconds() // 60))
                choices.append((overlap, -distance, day, meal))
        if not choices:
            continue
        _overlap, _distance, day, meal = max(choices)
        assigned.setdefault(day, {})[meal] = {"shift_start": start, "shift_end": end}
    return assigned


def choose_menu_item(targets: dict[str, float]) -> dict:
    """Choisit le plat <= 30 $ le plus proche des macros cibles du repas."""
    candidates = [item for item in MENU if item["price"] <= COUPON_CAD]
    best = min(
        candidates,
        key=lambda item: sum(
            weight * abs(item[key] - float(targets.get(key, 0))) / max(float(targets.get(key, 0)), 1.0)
            for key, weight in (("calories", 0.8), ("proteines", 1.8), ("glucides", 0.7), ("lipides", 0.6))
        ),
    )
    return dict(best)


def menu_combo_candidates(targets: dict[str, float], limit: int = 3) -> list[dict]:
    """Renvoie des options repas (un ou plusieurs plats), classées par macros,
    crédit utilisé et dépassement à payer. Le planificateur Santé les évalue
    ensuite conjointement avec le panier d'épicerie.
    """
    candidates: list[tuple[float, tuple[dict, ...]]] = []
    eligible = [item for item in MENU if item["price"] > 0]
    for size in range(1, min(3, len(eligible)) + 1):
        for combo in combinations(eligible, size):
            total = sum(float(item["price"]) for item in combo)
            if total > COUPON_CAD + 20:
                continue
            combined = {
                key: sum(float(item[key]) for item in combo)
                for key in ("calories", "proteines", "glucides", "lipides")
            }
            mismatch = sum(
                weight * abs(combined[key] - float(targets.get(key, 0)))
                / max(float(targets.get(key, 0)), 1.0)
                for key, weight in (("calories", 0.8), ("proteines", 1.8),
                                    ("glucides", 0.7), ("lipides", 0.6))
            )
            unused_credit = max(0.0, COUPON_CAD - total) / COUPON_CAD
            overage = max(0.0, total - COUPON_CAD)
            # Un crédit inutilisé compte, mais pas assez pour pousser à
            # commander beaucoup trop de nourriture uniquement pour le vider.
            score = mismatch + 0.55 * unused_credit + 0.025 * overage
            candidates.append((score, combo))

    out = []
    for _score, selected in sorted(candidates, key=lambda candidate: candidate[0])[:max(1, limit)]:
        total = round(sum(float(item["price"]) for item in selected), 2)
        covered = round(min(COUPON_CAD, total), 2)
        dishes = [menu_item(int(item["id"])) for item in selected]
        dishes = [item for item in dishes if item is not None]
        macros = {
            key: sum(float(item[key]) for item in selected)
            for key in ("calories", "proteines", "glucides", "lipides")
        }
        out.append({
            **macros,
            "id": "+".join(str(item["id"]) for item in selected),
            "name": " + ".join(item["name"] for item in selected),
            "description": " ; ".join(item["description"] for item in selected),
            "items": dishes,
            "price": total,
            "credit_couvert": covered,
            "reste_a_payer": round(max(0.0, total - COUPON_CAD), 2),
            "menu_url": MENU_URL,
            "macros_estimees": True,
        })
    return out


def choose_menu_combo(targets: dict[str, float]) -> dict:
    """Compatibilité pour Cuisine : retourne l'option la mieux classée."""
    return menu_combo_candidates(targets, limit=1)[0]
