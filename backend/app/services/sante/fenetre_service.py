# backend/app/services/sante/fenetre_service.py
"""Orchestration de la génération d'une fenêtre batch-cook (spec §1-§5).

Assemble : cibles/jour (base, sans J-1), somme fenêtre, dette (conso réelle de la
fenêtre précédente), prix Super C live, optimisation ratio, répartition/jour,
persistance WindowPlan + PlanNutrition/jour.
"""
from __future__ import annotations

import datetime as dt
import logging
import math
import os
import secrets
import threading
import unicodedata
from itertools import product
from typing import Any, Callable, Optional

from sqlmodel import Session, select

from app.models.sante import PlanNutrition, WindowPlan
from app.services.sante import debt, fenetre
from app.services.sante.adonis_pricing import (
    adonis_price_per_100g_edible,
    apply_superc_catalog_prices,
    purchase_unit_weight_kg,
)
from app.services.sante.aliments import load_aliments_dataframe, load_aliments_from_csv
from app.services.sante.cart_matcher import cart_plan as build_cart_plan
from app.services.sante.cart_matcher import resolve_products
from app.services.sante.pantry_fenetre import (
    apply_pantry_deduction,
    load_pantry_stock,
    pantry_stock_grams,
)
from app.services.sante.ratio_optimizer import optimize_ratio
from app.services.sante.shortlist import build_shortlist
from app.services.sante.targets import calculate_daily_targets
from app.services.sante.totals import calculate_plan_totals

logger = logging.getLogger(__name__)


def _estimate_restaurant_micros(meal: dict, df, target_keys: set[str]) -> dict[str, float]:
    """Estime les micros d'un plat en sommant ses ingrédients CIQUAL proxy.

    Les macros du menu sont évaluées par recette dédiée; cette fonction ne
    remplace que les micros et les nutriments à plafond.
    """
    from app.services.sante.constants import NUTRIENT_KEY_TO_CSV

    columns = {
        key: NUTRIENT_KEY_TO_CSV[key]
        for key in target_keys
        if key in NUTRIENT_KEY_TO_CSV
        and key not in {"Calories", "Protéines", "Lipides", "Glucides"}
        and NUTRIENT_KEY_TO_CSV[key] in df.columns
    }
    normalized_index = {
        "".join(c for c in unicodedata.normalize("NFKD", str(name).lower())
                if not unicodedata.combining(c)): name
        for name in df.index
    }
    totals = {key: 0.0 for key in columns}
    for dish in meal.get("items", [meal]):
        for ingredient in dish.get("ingredients_micro_estimes", []):
            name = "".join(
                c for c in unicodedata.normalize("NFKD", str(ingredient["aliment"]).lower())
                if not unicodedata.combining(c)
            )
            row_name = normalized_index.get(name)
            if row_name is None:
                continue
            row = df.loc[row_name]
            factor = float(ingredient.get("quantite_g", 0.0)) / 100.0
            for key, column in columns.items():
                try:
                    value = float(row[column])
                except (TypeError, ValueError):
                    continue
                if math.isfinite(value) and value > 0:
                    totals[key] += value * factor
    meal["micros"] = {key: round(value, 2) for key, value in totals.items()}
    meal["micros_estimes"] = True
    return totals

_refresh_thread: "threading.Thread | None" = None
_refresh_lock = threading.Lock()

# Ingrédients de recette, pas aliments à manger tels quels. Ils restent dans le
# catalogue Cuisine (tortillas, sauces, pâtisserie), mais ne peuvent plus servir
# à remplir artificiellement une fenêtre nutritionnelle.
_OPTIMIZER_EXCLUDED_MARKERS = (
    "farine", "fecule", "masa harina", "amidon de mais", "corn starch",
)

# Noyau sportif demandé par l'utilisateur. Ces aliments restent soumis à la
# disponibilité et au prix vérifié Super C, mais ne peuvent plus être évincés
# ensuite par la shortlist de 400 candidats.
OPTIMIZER_PRIORITY_FOOD_ORDER: tuple[str, ...] = (
    # Les premiers termes sont vérifiés avant les produits rares : ce sont les
    # bases bon marché qui doivent survivre à une interruption Cloudflare.
    "Oeufs", "Fromage blanc", "Yogourt grec nature 0%",
    "Yogourt grec nature 2%", "Yogourt grec nature entier", "Kefir",
    "Lait 2%", "Lait ecreme", "Lait entier",
    "Lentilles seches", "Haricots noirs en conserve", "Pois chiches en conserve",
    "Flocons d'avoine", "Pates (sec)", "Pates aux oeufs (sec)",
    "Pates de ble entier (sec)", "Riz brun (sec)", "Riz basmati (sec)",
    "Pomme de terre", "Patate douce", "Poitrine de poulet", "Tofu ferme",
    "Maquereau", "Truite arc-en-ciel", "Saumon atlantique",
)

OPTIMIZER_PRIORITY_FOODS: frozenset[str] = frozenset({
    "Maquereau", "Truite arc-en-ciel", "Saumon atlantique", "Kefir",
    "Lentilles seches", "Haricots noirs en conserve", "Pois chiches en conserve",
    "Oeufs", "Fromage blanc", "Yogourt grec nature 0%",
    "Yogourt grec nature 2%", "Yogourt grec nature entier",
    "Lait 2%", "Lait ecreme", "Lait entier",
    "Poitrine de poulet", "Dinde hachee", "Tofu ferme",
    "Flocons d'avoine", "Patate douce", "Quinoa (sec)", "Pates (sec)",
    "Pates aux oeufs (sec)", "Pates de ble entier (sec)", "Riz brun (sec)",
    "Riz basmati (sec)", "Tortilla de mais", "Sarrasin entier (sec)",
    "Pomme de terre", "Orge monde (sec)", "Amarante (sec)",
    "Graines de chia", "Graines de tournesol", "Graines de lin", "Amandes",
    "Noix de Grenoble", "Avocat", "Huile d'olive extra-vierge",
    "Beurre d'arachide", "Epinards", "Poivron rouge", "Brocoli",
    "Tomate fraiche", "Champignons blancs", "Haricots verts", "Asperges",
    "Carottes", "Courgette", "Oignon", "Ail", "Chou kale", "Banane",
    "Peche", "Bleuets frais", "Pomme", "Orange", "Pamplemousse", "Kiwi",
    "Fraises", "Cacao non sucre en poudre", "Cannelle moulue",
    "The vert infuse non sucre",
} | set(OPTIMIZER_PRIORITY_FOOD_ORDER))


def _optimizer_food_allowed(name: str) -> bool:
    normalized = "".join(
        char for char in unicodedata.normalize("NFKD", str(name).lower())
        if not unicodedata.combining(char)
    )
    return not any(marker in normalized for marker in _OPTIMIZER_EXCLUDED_MARKERS)


def _reservoir_enabled() -> bool:
    """Le réservoir Super C élargit-il le catalogue ? (SANTE_RESERVOIR=0 pour non)"""
    return os.getenv("SANTE_RESERVOIR", "1") in ("1", "true", "True")


def _noms_proteges(pantry_g: dict) -> set[str]:
    """Aliments que la présélection ne doit jamais écarter.

    Le catalogue curé (vérifié à la main), ce que l'utilisateur a déjà en stock
    (l'écarter reviendrait à lui faire racheter ce qu'il possède) et ses favoris.
    Best-effort sur les favoris : ils ne valent pas de faire échouer un plan.
    """
    proteges: set[str] = (
        set(load_aliments_from_csv()) | set(pantry_g or {}) | set(OPTIMIZER_PRIORITY_FOODS)
    )
    try:
        from app.services.sante import favorites
        proteges |= {str(n) for n in favorites.list_favorites()}
    except Exception as exc:
        logger.debug("[fenetre] favoris ignorés dans la présélection (%s)", exc)
    return proteges


def refresh_prices_best_effort() -> bool:
    """Rafraîchit les caches Super C (courant + circulaire) en ARRIÈRE-PLAN si
    périmés — ne BLOQUE jamais la génération (un scrape superc.ca peut prendre
    >30 s : flux magasin + Cloudflare). La fenêtre courante utilise le cache
    actuel ; le refresh bénéficie aux générations suivantes. Désactivé en test
    via STORE_PRICING_REFRESH=0 (dans le thread).

    Un seul scrape à la fois : deux générations rapprochées empilaient autrefois
    plusieurs scrapes concurrents, qui volaient le CPU à SLSQP.
    """
    global _refresh_thread

    def _run() -> None:
        try:
            from app.services.cuisine import store_pricing
            store_pricing.refresh_all_if_stale()
        except Exception:
            pass

    with _refresh_lock:
        if _refresh_thread is not None and _refresh_thread.is_alive():
            return False
        _refresh_thread = threading.Thread(target=_run, daemon=True, name="superc-refresh")
        _refresh_thread.start()
    return True


# Alias conservé pour les tests et les anciens appels internes.
_refresh_prices_best_effort = refresh_prices_best_effort


def _ensure_prices_before_optimization() -> None:
    """Bloque la génération tant que les deux caches Super C ne sont pas frais."""
    from app.services.cuisine import store_pricing

    store_pricing.ensure_fresh_prices()


_PERISHABLE_AISLES = (
    "/fruits-et-legumes/",
    "/produits-laitiers-et-oeufs/",
    "/viandes-et-volailles/",
    "/poissons-et-fruits-de-mer/",
    "/charcuterie/",
    "/pains-et-patisseries/",
    "/mets-prepares/",
)
_LONG_KEEPING_MARKERS = ("surgel", "/garde-manger/", "/conserve")


def _charge_full_purchase_unit(product: dict) -> bool:
    """Vrai uniquement pour les aliments qui périment rapidement.

    Les produits de garde sont optimisés au gramme consommé; leur contenant
    complet demeure néanmoins visible dans le montant payé à la caisse.
    """
    location = str(product.get("href") or "").lower()
    if any(marker in location for marker in _LONG_KEEPING_MARKERS):
        return False
    return any(aisle in location for aisle in _PERISHABLE_AISLES)


def _verified_catalog(df, shopping_day: dt.date) -> tuple[object, dict[str, dict], list[dict]]:
    """Ne conserve que les aliments reliés à un produit Super C chiffrable."""
    from app.services.cuisine import store_pricing, student_discount
    from app.services.sante.superc_catalog_rebuild import CATALOG_MAP

    cache = store_pricing.load_superc_pricing_items()
    choices = resolve_products(list(df.index), cache)
    if not choices:
        # Les tests et installations volontairement hors ligne gardent le
        # catalogue local. En production, une absence totale est une erreur de
        # prix et non une invitation à optimiser sur des montants inventés.
        if os.getenv("STORE_PRICING_REFRESH", "1") not in ("1", "true", "True"):
            return df, {}, cache
        raise ValueError("Aucun produit Super C avec un prix vérifié n'est disponible.")

    ordered = [name for name in df.index if name in choices]
    df = df.loc[ordered].copy()
    discount = student_discount.factor(shopping_day)
    df["PackagePrice"] = 0.0
    df["PackageWeightG"] = 0.0
    for name, product in choices.items():
        edible = CATALOG_MAP.get(name, {}).get("edible", 1.0)
        price = adonis_price_per_100g_edible(product, edible)
        if price is not None:
            df.loc[name, "Prix"] = price * discount
        # Seuls les produits rapidement périssables sont imputés par unité
        # entière. Huile, grains, pâtes, conserves, etc. sont amortis au gramme.
        package_weight_kg = purchase_unit_weight_kg(product)
        if (
            _charge_full_purchase_unit(product)
            and package_weight_kg
            and isinstance(product.get("price"), (int, float))
        ):
            df.loc[name, "PackagePrice"] = float(product["price"]) * discount
            df.loc[name, "PackageWeightG"] = package_weight_kg * 1000.0
    return df, choices, cache


def _deduplicate_nutrition_twins(df, choices: dict[str, dict]):
    """Évite variantes équivalentes et multiplication des boissons fruitées.

    Deux marques/formats ayant exactement le même profil n'apportent aucune
    diversité nutritionnelle; seule la moins chère au poids est conservée.
    Jus et nectars forment en plus une seule famille d'achat : leurs différences
    doivent venir de fruits entiers, pas de cinq bouteilles distinctes.
    """
    from app.services.sante.aliments import (
        load_reservoir_ciqual_refs,
        load_reservoir_product_refs,
    )

    refs = load_reservoir_ciqual_refs()
    product_refs = load_reservoir_product_refs()
    groups: dict[str, list[str]] = {}
    for name in df.index:
        if code := refs.get(str(name)):
            groups.setdefault(code, []).append(str(name))

    dropped: set[str] = set()

    # Le catalogue contient à la fois les aliments curés (ex. « Graines de
    # lin ») et le produit Super C du réservoir (ex. « Cedar Phoenicia Graines
    # de lin »). Quand les deux pointent vers le même UPC, les garder crée deux
    # variables nutritionnelles puis deux lignes d'achat du même paquet. On
    # garde prioritairement le profil curé, sinon la variante la moins chère.
    same_products: dict[str, list[str]] = {}
    for name, product in choices.items():
        product_id = str(product.get("id") or product.get("sku") or "").strip()
        if product_id and name in df.index:
            same_products.setdefault(product_id, []).append(str(name))
    for names in same_products.values():
        if len(names) < 2:
            continue
        keep = min(
            names,
            key=lambda name: (
                name in product_refs,  # le profil curé gagne sur le réservoir
                float(df.loc[name, "Prix"]),
            ),
        )
        dropped.update(name for name in names if name != keep)

    for names in groups.values():
        names = [name for name in names if name not in dropped]
        if len(names) < 2:
            continue
        # `_verified_catalog` a déjà remplacé `Prix` par le coût vérifié aux
        # 100 g comestibles (rabais étudiant identique pour tous les produits).
        keep = min(names, key=lambda name: float(df.loc[name, "Prix"]))
        dropped.update(name for name in names if name != keep)

    fruit_drinks = [
        str(name) for name in df.index
        if any(word in str(name).lower() for word in ("jus", "nectar", "smoothie"))
        and str(name) not in dropped
    ]
    if len(fruit_drinks) > 1:
        keep = min(fruit_drinks, key=lambda name: float(df.loc[name, "Prix"]))
        dropped.update(name for name in fruit_drinks if name != keep)
    if not dropped:
        return df, choices
    kept_names = [name for name in df.index if str(name) not in dropped]
    return df.loc[kept_names].copy(), {
        name: product for name, product in choices.items() if name not in dropped
    }


# Plafonds ciblés pour les ingrédients concentrés. Les aliments ordinaires
# conservent les limites très larges demandées par l'utilisateur; ces exceptions
# empêchent seulement qu'un condiment soit traité comme le volume principal du
# repas (ex. plus de 200 g de pâte de tomate par jour).
_PRACTICAL_MAX_DAILY_G: dict[str, float] = {
    "pate de tomate": 60.0,
    "tomate sechee": 30.0,
    "tomates sechees": 30.0,
    "sirop d'erable": 25.0,
    "porc hache": 200.0,
    "riz blanc": 250.0,
}


def _practical_daily_cap(name: str) -> float | None:
    normalized = "".join(
        char for char in unicodedata.normalize("NFKD", str(name).lower())
        if not unicodedata.combining(char)
    )
    for marker, cap_g in _PRACTICAL_MAX_DAILY_G.items():
        if marker in normalized:
            return cap_g
    return None


def _apply_practical_quantity_caps(df):
    result = df.copy()
    for name in result.index:
        cap_g = _practical_daily_cap(str(name))
        if cap_g is None:
            continue
        current = float(result.loc[name, "MaxQty"] or 0.0)
        result.loc[name, "MaxQty"] = min(current, cap_g) if current > 0 else cap_g
    return result


def _load_pantry_items() -> list[dict]:
    """Items du garde-manger (best-effort, jamais bloquant). Monkeypatchable en test."""
    try:
        from app.services.cuisine import pantry
        return pantry.list_items()
    except Exception:
        return []


def _prev_window_actuals(session: Session, anchor: dt.date) -> tuple[dict, dict]:
    """(Σ targets, Σ consumed) de la fenêtre précédant `anchor`."""
    prev_anchor = fenetre.anchor_for(anchor - dt.timedelta(days=1))
    try:
        prev_days = fenetre.window_days(prev_anchor)
    except ValueError:
        return {}, {}
    t_sum: dict[str, float] = {}
    c_sum: dict[str, float] = {}
    rows = session.exec(select(PlanNutrition).where(PlanNutrition.date.in_(prev_days))).all()
    for r in rows:
        for k, v in (r.targets or {}).items():
            t_sum[k] = t_sum.get(k, 0.0) + float(v or 0.0)
        for k, v in (r.consumed or {}).items():
            c_sum[k] = c_sum.get(k, 0.0) + float(v or 0.0)
    return t_sum, c_sum


def generate_window(
    session: Session, day: Optional[dt.date] = None,
    poids: Optional[float] = None, force: bool = False,
    refresh_prices: bool = True,
    progress_cb: Optional[Callable[[dict[str, Any]], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
    continuous_search: bool = False,
) -> WindowPlan:
    from app.api.sante.plan import _last_known_weight, _resolve_intensity
    from app.services.sante import ensure_active_goal

    today = day or dt.date.today()
    anchor = fenetre.anchor_for(today)
    days = fenetre.window_days(anchor)
    goal = ensure_active_goal(session)
    if poids is None:
        poids = _last_known_weight(session, before=anchor)
    if poids is None:
        raise ValueError("Aucun poids connu et aucun poids fourni.")

    # 1) Cibles de base par jour (intensité résolue), sans compensation J-1.
    daily_targets: list[dict] = []
    intensities: list[str] = []
    for d in days:
        intensity, _ctx = _resolve_intensity(session, d, goal.sport_days)
        base, _comp = calculate_daily_targets(
            weight=poids, date=d, history=None, intensity=intensity,
            surplus_kcal_sport=goal.surplus_kcal_sport, rest_factor=goal.rest_factor,
            sport_days=goal.sport_days,
        )
        daily_targets.append(base)
        intensities.append(intensity)

    win_targets = fenetre.window_targets(daily_targets)

    # Chaque option Crew reste ouverte jusqu'à ce que le panier soit calculé :
    # les choix de repas et d'épicerie seront comparés avec le même objectif.
    restaurant_slots: list[tuple[dt.date, str, list[dict]]] = []
    try:
        from sqlalchemy import or_
        from app.models.agenda import Evenement
        from app.services.cuisine.restaurant_meals import assign_shift_meals, menu_combo_candidates

        shifts = session.exec(select(Evenement).where(
            Evenement.debut < dt.datetime.combine(days[-1] + dt.timedelta(days=1), dt.time.min),
            Evenement.fin > dt.datetime.combine(days[0], dt.time.min),
            or_(Evenement.categorie.in_(["travail", "work"]), Evenement.source == "work"),
        )).all()
        fixed_shifts = [(e.debut.replace(tzinfo=None), e.fin.replace(tzinfo=None))
                        for e in shifts if e.fin is not None]
        assigned = assign_shift_meals(fixed_shifts)
        target_by_day = dict(zip(days, daily_targets))
        for meal_day, meals in assigned.items():
            if meal_day not in target_by_day:
                continue
            daily = target_by_day[meal_day]
            target_macros = {"calories": float(daily.get("Calories", 0)) / 3,
                             "proteines": float(daily.get("Protéines", 0)) / 3,
                             "glucides": float(daily.get("Glucides", 0)) / 3,
                             "lipides": float(daily.get("Lipides", 0)) / 3}
            for meal in meals:
                restaurant_slots.append((
                    meal_day, meal, menu_combo_candidates(target_macros, limit=2),
                ))
    except Exception:
        logger.exception("[fenetre] impossible de préparer les options de repas de travail")
        restaurant_slots = []

    restaurant_by_date: dict[dt.date, dict] = {}

    # 2) Dette : report + escalade depuis la conso réelle de la fenêtre précédente.
    prev = session.exec(select(WindowPlan).where(WindowPlan.anchor_date < anchor)
                        .order_by(WindowPlan.anchor_date.desc())).first()
    prev_series = prev.debt_series if prev else None
    t_sum, c_sum = _prev_window_actuals(session, anchor)
    target_add, weight_mult, new_series = debt.carryover(t_sum, c_sum, prev_series)
    for k, extra in target_add.items():
        win_targets[k] = win_targets.get(k, 0.0) + extra

    # 3) Les prix sont vérifiés AVANT le calcul. La génération asynchrone permet
    # d'assumer ce coût sans timeout côté navigateur.
    if refresh_prices:
        _ensure_prices_before_optimization()
    # Le panier sera payé le jour de COURSES de la fenêtre (lundi, ou mercredi
    # pour la fenêtre jeu-dim) : c'est ce jour-là qui décide du rabais étudiant,
    # pas la date de génération.
    shopping_day = fenetre.shopping_day_for(anchor)
    # `include_reservoir` : au catalogue curé s'ajoutent les produits Super C
    # rattachés à CIQUAL (`reservoir_superc.csv`). Le curé reste prioritaire en
    # cas d'homonymie. Désactivable par SANTE_RESERVOIR=0.
    df = load_aliments_dataframe(session, include_reservoir=_reservoir_enabled())
    df, _priced = apply_superc_catalog_prices(df, shopping_day)
    df = df.loc[[name for name in df.index if _optimizer_food_allowed(str(name))]]
    df, product_choices, price_cache = _verified_catalog(df, shopping_day)
    df, product_choices = _deduplicate_nutrition_twins(df, product_choices)
    df = _apply_practical_quantity_caps(df)

    for _day, _meal, options in restaurant_slots:
        for option in options:
            option["micros"] = {}
            for dish in option.get("items", []):
                dish["micros"] = _estimate_restaurant_micros(dish, df, set(win_targets))
            for key in set(win_targets):
                option["micros"][key] = round(sum(
                    float(dish.get("micros", {}).get(key, 0.0))
                    for dish in option.get("items", [])
                ), 2)
            option["micros_estimes"] = True

    # Recherche conjointe bornée : on évalue plusieurs paniers Crew avec le
    # panier d'épicerie correspondant, puis garde la meilleure solution globale.
    # La borne évite une explosion combinatoire si plusieurs shifts tombent dans
    # une même fenêtre de quatre jours.
    if restaurant_slots:
        patterns = list(product(*(range(len(slot[2])) for slot in restaurant_slots)))
        patterns.sort(key=lambda choice: (sum(choice), choice))
        patterns = patterns[:8]
    else:
        patterns = [()]

    restaurant_configs: list[dict[dt.date, dict]] = []
    restaurant_targets: list[dict[str, float]] = []
    for pattern in patterns:
        by_day: dict[dt.date, dict] = {}
        for (meal_day, meal_name, options), choice_index in zip(restaurant_slots, pattern):
            by_day.setdefault(meal_day, {})[meal_name] = options[choice_index]
        targets = dict(win_targets)
        for meals in by_day.values():
            for meal_option in meals.values():
                contributions = {
                    **meal_option.get("micros", {}),
                    "Calories": meal_option.get("calories", 0.0),
                    "Protéines": meal_option.get("proteines", 0.0),
                    "Glucides": meal_option.get("glucides", 0.0),
                    "Lipides": meal_option.get("lipides", 0.0),
                }
                for key, amount in contributions.items():
                    if key in targets:
                        targets[key] = max(0.0, float(targets[key]) - float(amount or 0.0))
        restaurant_configs.append(by_day)
        restaurant_targets.append(targets)
    restaurant_by_date = restaurant_configs[0] if restaurant_configs else {}
    optimizer_targets = restaurant_targets[0] if restaurant_targets else win_targets

    # Le coût réduit ne s'applique qu'au stock réellement disponible; le reste
    # repasse au tarif normal. Les lots périmés sont ignorés dans les deux calculs.
    pantry_stock = load_pantry_stock(_load_pantry_items(), today=today)
    pantry_g = pantry_stock_grams(pantry_stock)

    # Présélection : SLSQP ne tient pas des milliers d'aliments (cf. shortlist).
    # Rien de curé, de stocké ni de favori n'est évinçable.
    df_complet = df
    df = build_shortlist(
        df, optimizer_targets,
        keep_names=frozenset(_noms_proteges(pantry_g)),
    )
    if len(df) < len(df_complet):
        logger.info(
            "[fenetre] présélection : %d aliments retenus sur %d",
            len(df), len(df_complet),
        )

    # 4) Optimisation ratio couverture/coût sur la fenêtre.
    # Budget « désactivé » : plafond énorme mais FINI (float("inf") casse la
    # différentiation numérique de SLSQP : inf - inf = nan). Le ratio couverture/
    # coût s'AUTO-LIMITE (dépenser trop fait chuter le score), donc un budget dur
    # est redondant (choix user 2026-07-23). Les minimums stricts calories/
    # protéines sont imposés par optimize_ratio (score = 0 si ratés).
    seed = secrets.randbelow(2**31) if force else None
    best_joint = None
    for config, targets in zip(restaurant_configs or [{}], restaurant_targets or [win_targets]):
        candidate_items, candidate_warning, candidate_score = optimize_ratio(
            df, targets, budget_max_daily=1e9,
            seed=seed, micro_weight_mult=weight_mult or None,
            pantry_stock=pantry_stock or None,
            quantity_days=len(days),
            progress_cb=progress_cb, should_stop=should_stop,
            # La recherche continue s'applique au meilleur panier conjoint,
            # après avoir comparé les alternatives de repas et d'épicerie.
            continuous_until_stopped=False,
        )
        if candidate_items is None:
            continue
        restaurant_overage = sum(
            float(item.get("reste_a_payer", 0.0))
            for meals in config.values() for item in meals.values()
        )
        combined_cost = float(candidate_score.get("cout_total", 0.0)) + restaurant_overage
        combined_ratio = (
            float(candidate_score.get("equilibre_moyen", candidate_score.get("couverture_moyenne", 0.0)))
            / combined_cost if combined_cost > 0 else 0.0
        )
        if best_joint is None or combined_ratio > best_joint[0]:
            best_joint = (combined_ratio, candidate_items, candidate_warning,
                          candidate_score, config, targets)

    if best_joint is None:
        raise ValueError("Aucune combinaison de repas et de courses n'a pu être optimisée.")
    _joint_ratio, plan_items, warning, score, restaurant_by_date, optimizer_targets = best_joint
    if continuous_search:
        plan_items, warning, score = optimize_ratio(
            df, optimizer_targets, budget_max_daily=1e9,
            seed=seed, micro_weight_mult=weight_mult or None,
            pantry_stock=pantry_stock or None,
            quantity_days=len(days),
            progress_cb=progress_cb, should_stop=should_stop,
            continuous_until_stopped=True,
        )
        if plan_items is None:
            raise ValueError(warning or "Optimisation continue de la combinaison retenue impossible.")

    food_set = {it["Aliment"]: float(it["Quantite_g"]) for it in plan_items}

    # 5) Liste de courses (prix + promo best-effort), puis déduction garde-manger :
    #    la liste et le coût À PAYER déduisent le stock ; le ratio utilise le coût
    #    économique 0/50/100 % des portions réellement consommées.
    shopping_full = _build_shopping_list(food_set, df, shopping_day)
    restaurant_a_payer = round(sum(
        float(item.get("reste_a_payer", 0.0))
        for meals in restaurant_by_date.values() for item in meals.values()
    ), 2)
    if pantry_g:
        shopping, _ = apply_pantry_deduction(shopping_full, pantry_g)
    else:
        shopping = shopping_full
    if product_choices:
        cout_optimise = float(score.get("cout_total", 0.0))
        full_cart = build_cart_plan(
            shopping_full, price_cache, product_choices=product_choices,
            shopping_day=shopping_day,
        )
        cart = build_cart_plan(
            shopping, price_cache, product_choices=product_choices,
            shopping_day=shopping_day,
        )
        shopping_full = _attach_cart_prices(shopping_full, full_cart)
        shopping = _attach_cart_prices(shopping, cart)
        # Les prix de ``shopping`` sont désormais les portions réellement
        # consommées. Les montants caisse viennent exclusivement du panier et
        # de ses formats entiers, afin de ne pas afficher deux fois le même
        # panier dans la liste du haut.
        cout_total = round(sum(
            float(it.get("prix_estime") or 0.0) * int(it.get("qty") or 1)
            for it in full_cart
        ), 2)
        cout_a_payer = round(sum(
            float(it.get("prix_estime") or 0.0) * int(it.get("qty") or 1)
            for it in cart
        ), 2)
        ratio = float(score.get("equilibre_moyen", score.get("couverture_moyenne", 0.0))) / max(
            cout_optimise + restaurant_a_payer, 0.01)
        score = {
            **score, "cout_optimise": round(cout_optimise, 2),
            "cout_total": cout_total, "cout_a_payer": cout_a_payer, "ratio": ratio,
            "restaurant_a_payer": restaurant_a_payer,
        }
    else:
        cout_a_payer = round(sum(float(it.get("prix") or 0.0) for it in shopping), 2)
        cout_total = round(float(score.get("cout_total", 0.0)), 2)
        ratio = float(score.get("equilibre_moyen", score.get("couverture_moyenne", 0.0))) / max(
            cout_total + restaurant_a_payer, 0.01)
        score = {
            **score, "cout_optimise": cout_total, "cout_total": cout_total,
            "cout_a_payer": cout_a_payer, "ratio": ratio,
            "restaurant_a_payer": restaurant_a_payer,
        }

    # La liste supérieure présente les portions consommées, classées de la
    # plus coûteuse à la moins coûteuse. Les éventuels prix inconnus vont en
    # dernier sans perturber l'ordre déterministe des autres lignes.
    shopping = sorted(
        shopping,
        key=lambda item: (
            item.get("prix") is not None,
            float(item.get("prix") or 0.0),
        ),
        reverse=True,
    )

    # 6) Répartition par jour (prorata des calories-cibles) + persistance/jour.
    cal_targets = [max(0.0, float(t.get("Calories", 0.0)) -
                       sum(item["calories"] for item in restaurant_by_date.get(d, {}).values()))
                   for d, t in zip(days, daily_targets)]
    daily_caps = {
        name: cap for name in food_set
        if (cap := _practical_daily_cap(name)) is not None
    }
    per_day = fenetre.split_by_day(food_set, cal_targets, daily_caps)
    for d, day_grams, day_tgt, intensity in zip(days, per_day, daily_targets, intensities):
        items = [{"Aliment": nom, "Quantite_g": g} for nom, g in day_grams.items()]
        totals = calculate_plan_totals(items, df)
        for restaurant_item in restaurant_by_date.get(d, {}).values():
            for key, target_key in (("calories", "Calories"), ("proteines", "Protéines"),
                                    ("glucides", "Glucides"), ("lipides", "Lipides")):
                totals[target_key] = float(totals.get(target_key, 0.0)) + restaurant_item[key]
            for key, amount in restaurant_item.get("micros", {}).items():
                totals[key] = float(totals.get(key, 0.0)) + float(amount or 0.0)
        row = session.exec(select(PlanNutrition).where(PlanNutrition.date == d)).first()
        if row is None:
            row = PlanNutrition(date=d)
        row.poids_used = poids
        row.intensite = intensity
        row.base_targets = day_tgt
        row.targets = day_tgt
        row.quantites = day_grams
        row.totals = totals
        # `consumed` volontairement préservé (report conso réelle).
        session.add(row)

    # 7) Persistance WindowPlan.
    wp = session.exec(select(WindowPlan).where(WindowPlan.anchor_date == anchor)).first()
    if wp is None:
        wp = WindowPlan(anchor_date=anchor)
    wp.length = len(days)
    wp.poids_used = poids
    wp.food_set = food_set
    wp.shopping_list = shopping
    score["restaurant_meals"] = {
        d.isoformat(): list(meals.values()) for d, meals in restaurant_by_date.items()
    }
    wp.score = score
    wp.debt_series = new_series
    wp.warning = warning or None
    session.add(wp)
    session.commit()
    session.refresh(wp)

    return wp


def _attach_cart_prices(shopping: list[dict], cart: list[dict]) -> list[dict]:
    """Ajoute le produit vérifié sans écraser le coût de la portion consommée.

    ``shopping[i]["prix"]`` provient de Prix/100 g × grammes consommés. Le
    prix du format entier reste dans ``prix_unitaire`` et dans le panier Super
    C séparé; afficher ce dernier ici dupliquait le panier et faisait croire
    que 3 g d'huile coûtaient la bouteille complète.
    """
    by_name = {str(item.get("aliment")): item for item in cart}
    out: list[dict] = []
    for item in shopping:
        match = by_name.get(str(item.get("aliment")))
        if not match or match.get("a_verifier") or match.get("prix_estime") is None:
            continue
        enriched = dict(item)
        enriched.update({
            "product_id": match.get("product_id"),
            "product_name": match.get("product_name"),
            "href": match.get("href"),
            "format": match.get("format"),
            "qty": int(match.get("qty") or 1),
            "prix_unitaire": float(match["prix_estime"]),
            "promo": bool(match.get("promo")),
            "prix_verifie": True,
        })
        out.append(enriched)
    return out


def _build_shopping_list(
    food_set: dict[str, float], df, shopping_day: Optional[dt.date] = None
) -> list[dict]:
    """[{aliment, quantite_g, prix, promo}] — prix = Prix/100 g × grammes, promo
    best-effort via store_pricing (jamais bloquant).

    `df` porte déjà les prix remisés (l'overlay Super C a été appliqué avec le
    même `shopping_day`) : le rabais n'est donc PAS réappliqué ici sur `prix`.
    `shopping_day` n'est transmis que pour que `recommend_store` reste cohérent.
    """
    try:
        from app.services.cuisine import store_pricing
    except Exception:
        store_pricing = None
    out = []
    for nom, grams in food_set.items():
        prix = None
        if nom in df.index:
            try:
                prix = round(float(df.loc[nom, "Prix"]) * grams / 100.0, 2)
            except Exception:
                prix = None
        promo = False
        if store_pricing is not None:
            try:
                rec = store_pricing.recommend_store(nom, shopping_day)
                promo = bool(rec and rec.get("promo"))
            except Exception:
                promo = False
        out.append({"aliment": nom, "quantite_g": round(grams, 1), "prix": prix, "promo": promo})
    return out


def get_current_window(session: Session, day: Optional[dt.date] = None) -> WindowPlan | None:
    anchor = fenetre.anchor_for(day or dt.date.today())
    return session.exec(select(WindowPlan).where(WindowPlan.anchor_date == anchor)).first()
