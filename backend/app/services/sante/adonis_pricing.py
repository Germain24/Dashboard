"""Re-tarification du catalogue nutrition avec les prix Super C.

Historique : ce module tarifait à l'origine les fruits & légumes avec les prix
Adonis (le reste venant de Costco). Adonis et Costco sont retirés le
2026-07-17 (décision user : une seule source de prix, Super C, pour les
courses ET l'optimiseur nutrition — cf.
`orchestration/a-faire/2026-07-14-superc-unique-design.md`). Le nom du module
et des fonctions ci-dessous (`PRODUCE_MAP`, `adonis_price_per_100g_edible`…)
reste hérité de cette époque pour l'instant ; la logique de matching/conversion
(pure, testée) est réutilisée telle quelle par les overlays Super C plus bas.

Parties pures (matching, conversion, overlay) testées ; le rafraîchissement
(scrape navigateur) est best-effort et ne casse jamais l'optimisation.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# Fractions comestibles (cf. README_aliments.md) : le prix est au poids
# BRUT (avec pelure/noyau) ; on le ramène à la portion comestible. 1.0 = tout
# comestible (baies, frozen, feuilles…).
_EDIBLE_DEFAULT = 1.0

# Fruits & légumes du catalogue (noms FR exacts d'aliments.csv) -> mots-clés de
# recherche dans le nom superc.ca (FRANÇAIS depuis le repoint 2026-07-23,
# cf. orchestration/a-faire/2026-07-23-superc-ca-repoint-design.md) + fraction
# comestible. `not` exclut les faux positifs. Accents : la variante accentuée
# ET la variante ASCII sont listées en synonymes (`œuf`/`oeuf`,
# `épinard`/`epinard`…) — `_matches` ne fait AUCUNE normalisation d'accents,
# juste un `.lower()`. IMPORTANT : `_matches` par défaut `match="all"` (TOUS
# les mots-clés requis) -> un item ne peut jamais porter à la fois l'accent
# ET sa variante ASCII, donc toute entrée à 2+ mots-clés synonymes DOIT poser
# `"match": "any"` explicitement (sinon 0 match garanti, cf. Celeri/Epinards/
# Peche/Clementines/Pois verts surgeles ci-dessous).
# Un fruit/légume brut n'est JAMAIS lui-même une eau aromatisée / un jus / une
# soupe / un dessert / de la nourriture pour animaux — mais son NOM l'est très
# souvent comme saveur/ingrédient d'un produit dérivé, moins cher au 100 g que
# le produit frais recherché (découvert en validant CATALOG_MAP contre le vrai
# superc.json, cf. task-3-report.md : "Ananas" matchait une eau pétillante
# saveur ananas, "Brocoli" une soupe condensée, "Carottes" de la nourriture
# pour chien... et, cf. rapport de raffinage 2026-07-24, "Fraises" matchait un
# frappé à saveur de fraise-banane). Exclusion appliquée à TOUT PRODUCE_MAP par
# défaut (union avec le `not` spécifique de chaque aliment, cf.
# _finalize_produce_map) — aucun faux négatif possible : aucun fruit/légume
# n'est lui-même l'un de ces produits dérivés.
# NOTE "sel " (avec l'espace finale) : PAS juste "sel". `_matches` ne pose
# qu'une frontière de mot AVANT le mot-clé (`\b` + kw, jamais de `\b` après),
# donc "sel" bare matche aussi en PRÉFIXE "Selection"/"Sélection" (marque
# maison superc.ca, ~184 produits du cache !) -> plus AUCUN produit
# "Selection ..." ne pouvait jamais matcher le moindre fruit/légume, ex.
# "Selection Pois verts surgelés" (SEUL produit du cache pour cet aliment) ->
# "Pois verts surgeles" ne matchait jamais rien. L'espace finale ancre "sel"
# comme mot entier (suivi d'un espace, ex. "sel de mer", "sel d'oignon") sans
# capturer "sel" + "ection" collé. Idem esprit pour "nectar" : landmine
# identique avec "Nectarine" (produit réel du cache, pas encore un aliment du
# catalogue -> aucun bug actuel, non corrigé pour rester minimal) — si
# "nectar " applique le même correctif afin de ne pas exclure "Nectarine".
# "sorbet"/"tartinade" : mêmes découvertes que "frappé" en validant le
# catalogue entier contre le vrai superc.json (rapport de raffinage
# 2026-07-24) — "Framboises"/"Mangue" matchaient un SORBET (dessert glacé) au
# lieu du fruit ; "tartinade" (pâte à tartiner de fruits, cousine de
# "confiture" déjà exclue) protège pareil. "syrop" (avec un 'y', orthographe
# fautive/anglicisée utilisée par AU MOINS un produit réel, ex. "Diana Pêches
# tranchées dans un syrop léger") : gardé EN PLUS de "sirop" (orthographe
# correcte, déjà présente) — sans lui, ce produit en conserve traversait le
# filtre et faisait passer "Peche" pour une pêche fraîche. "kéfir"/"kefir" :
# boisson laitière fermentée vendue dans les mêmes parfums de fruits que le
# yogourt (déjà exclu) — "Mangue" matchait "Liberté Kéfir à la mangue 1 %"
# (moins cher que la mangue fraîche/surgelée).
_PRODUCE_DISTRACTOR_NOT: list[str] = [
    "eau", "jus", "boisson", "breuvage", "cocktail", "limonade", "nectar ",
    "soupe", "vinaigrette", "sauce", "mayonnaise", "yogourt", "kéfir", "kefir",
    "crème glacée", "biscuit", "gâteau", "muffin", "barre", "confiture",
    "compote", "tarte", "chips", "croustille", "chien", "chat", "sirop",
    "syrop", "mariné", "marine", "café", "nettoyant", "savon", "shampooing",
    "lotion", "sel ", "thé",
    "mélasse", "porc", "farci", "fromage", "graine", "tofu", "dessert",
    "frappé", "smoothie", "sorbet", "tartinade", "marinade",
    "popsicle", "bâton glacé", "baton glace", "barre glacée", "barre glacee",
]


def _finalize_produce_map(raw: dict[str, dict]) -> dict[str, dict]:
    return {
        name: {**spec, "not": [*spec.get("not", []), *_PRODUCE_DISTRACTOR_NOT]}
        for name, spec in raw.items()
    }


PRODUCE_MAP: dict[str, dict] = _finalize_produce_map({
    # "pomme" est un préfixe littéral de "pomme de terre" (patate) : sans le
    # `not`, "Pomme" matcherait toutes les pommes de terre du magasin.
    "Banane": {"kw": ["banane"], "not": ["plantain"], "edible": 0.64},
    # "avocat" est aussi dans "Huile d'avocat" (catalogue séparé) : exclu.
    "Avocat": {"kw": ["avocat"], "not": ["huile"], "edible": 0.73},
    # "orange" est aussi la couleur d'un poivron ("Poivron orange") : exclu.
    "Orange": {"kw": ["orange"], "not": ["jus", "poivron"], "edible": 0.73},
    "Pomme": {"kw": ["pomme"], "not": ["terre"], "edible": 0.90},
    # "tomate raisin" (grape tomato) est un vrai produit FR courant ; "raisins
    # secs" (dried) est un autre aliment que les raisins frais visés ici.
    "Raisins": {"kw": ["raisin"], "not": ["tomate", "sec"], "edible": 1.0},
    "Bleuets frais": {"kw": ["bleuet"], "edible": 1.0},
    "Fraises": {"kw": ["fraise"], "edible": 1.0},
    "Framboises": {"kw": ["framboise"], "edible": 1.0},
    # "tomate cerise" (cherry tomato) est un vrai produit FR courant.
    "Cerises": {"kw": ["cerise"], "not": ["tomate"], "edible": 1.0},
    "Dattes Medjool": {"kw": ["medjool"], "edible": 0.85},
    "Ananas": {"kw": ["ananas"], "edible": 1.0},
    "Kiwi": {"kw": ["kiwi"], "edible": 1.0},
    "Clementines": {"kw": ["clémentine", "clementine"], "match": "any", "edible": 0.73},
    "Poire": {"kw": ["poire"], "edible": 0.90},
    "Peche": {"kw": ["pêche", "peche"], "match": "any", "edible": 0.90},
    "Mangue": {"kw": ["mangue"], "edible": 1.0},
    "Grenade": {"kw": ["grenade"], "edible": 1.0},
    "Pamplemousse": {"kw": ["pamplemousse"], "edible": 1.0},
    # "prune" (prune fraîche) est un préfixe littéral de "pruneau" (prune
    # séchée) : sans le `not`, "Prunes" matcherait les pruneaux séchés.
    "Prunes": {"kw": ["prune"], "not": ["pruneau"], "edible": 1.0},
    "Pruneaux": {"kw": ["pruneau"], "edible": 1.0},
    "Canneberges sechees": {"kw": ["canneberge"], "edible": 1.0},
    "Brocoli": {"kw": ["brocoli"], "edible": 1.0},
    "Epinards": {
        "kw": ["épinard", "epinard"], "match": "any",
        "not": [
            "surgelé", "surgele", "trempette", "saucisse", "feta",
            "pizza", "lasagne", "quiche",
        ],
        "href_any": ["/fruits-et-legumes/"], "edible": 1.0,
    },
    "Carottes": {"kw": ["carotte"], "edible": 0.89},
    "Poivron rouge": {
        "kw": ["poivron rouge"], "href_any": ["/fruits-et-legumes/"],
        "edible": 0.82,
    },
    "Oignon": {"kw": ["oignon"], "edible": 0.90},
    # Exclut les tomates en conserve/concassées (aliment séparé, prix/nutrition
    # différents) qui contiennent aussi le mot "tomate".
    "Tomate fraiche": {
        "kw": ["tomate"],
        "not": [
            "conserve", "concassée", "concassee", "broyée", "broyee",
            "boîte", "boite", "en dés", "en des", "pâte de tomate",
            "pate de tomate", "séchée", "sechee",
        ],
        "href_any": ["/fruits-et-legumes/"],
        "edible": 1.0,
    },
    "Patate douce": {"kw": ["patate douce"], "edible": 0.86},
    "Pomme de terre": {
        "kw": ["pomme de terre"], "not": ["croustille", "chips", "frite"],
        "href_any": ["/fruits-et-legumes/"], "edible": 0.90,
    },
    "Chou vert": {
        "kw": ["chou vert", "chou blanc"], "match": "any",
        "href_any": ["/fruits-et-legumes/"], "edible": 0.90,
    },
    "Chou kale": {
        "kw": ["chou frisé", "chou frise", "kale"], "match": "any",
        "href_any": ["/fruits-et-legumes/"], "edible": 0.90,
    },
    "Champignons blancs": {
        "kw": ["champignon"],
        "not": ["conserve", "sauce", "soupe", "mariné", "marine"],
        "href_any": ["/fruits-et-legumes/"],
        "edible": 1.0,
    },
    "Chou-fleur": {"kw": ["chou-fleur"], "edible": 1.0},
    "Concombre": {"kw": ["concombre"], "edible": 1.0},
    # "céleri-rave" (céleri-rave, racine) est un légume différent du céleri en
    # branches visé ici.
    "Celeri": {"kw": ["céleri", "celeri"], "match": "any", "not": ["rave"], "edible": 1.0},
    "Asperges": {"kw": ["asperge"], "edible": 1.0},
    "Courgette": {"kw": ["courgette"], "edible": 1.0},
    "Aubergine": {"kw": ["aubergine"], "edible": 1.0},
    "Roquette": {"kw": ["roquette"], "edible": 1.0},
    "Haricots verts": {
        "kw": ["haricots verts"],
        "not": ["conserve", "coupés", "coupes"],
        "href_any": ["/fruits-et-legumes/"], "edible": 1.0,
    },
    "Mais surgele": {
        "kw": ["maïs surgelé", "mais surgele"], "match": "any",
        "href_any": ["/produits-surgeles/"], "edible": 1.0,
    },
    "Ail": {
        "kw": ["ail"],
        "not": ["sauce", "assaisonnement", "poudre", "bouchée", "bouchee",
                "pomme de terre", "chili", "frite"],
        "href_any": ["/fruits-et-legumes/"],
        "href_not": ["/produits-surgeles/"], "edible": 0.90,
    },
    "Citron": {
        "kw": ["citron"], "not": ["jus", "lime", "limette"],
        "href_any": ["/fruits-et-legumes/"], "edible": 0.65,
    },
    "Betterave": {
        "kw": ["betterave"], "not": ["hummus", "jus", "marinée", "marinee"],
        "href_any": ["/fruits-et-legumes/"], "edible": 0.90,
    },
    "Navet": {
        "kw": ["navet"], "href_any": ["/fruits-et-legumes/"], "edible": 0.85,
    },
    "Pois verts surgeles": {"kw": ["pois verts surgelés", "pois verts surgeles"], "match": "any", "edible": 1.0},
    "Olives noires": {"kw": ["olives noires"], "edible": 1.0},
    # Extension CIQUAL/Super C 2026-08-12 — uniquement des produits dont le
    # cache fournit un prix au poids exploitable.
    "Banane plantain": {"kw": ["banane plantain"], "edible": 0.65},
    "Celeri-rave": {
        "kw": ["céleri-rave", "celeri-rave"], "match": "any",
        "href_any": ["/fruits-et-legumes/"], "edible": 0.85,
    },
    "Nectarine": {
        "kw": ["nectarine"], "href_any": ["/fruits-et-legumes/"], "edible": 0.90,
    },
    "Papaye": {
        "kw": ["papaye"], "href_any": ["/fruits-et-legumes/"], "edible": 0.70,
    },
    "Poivron vert": {
        "kw": ["poivron vert"], "href_any": ["/fruits-et-legumes/"], "edible": 0.82,
    },
    "Poivron jaune": {
        "kw": ["poivron jaune"], "href_any": ["/fruits-et-legumes/"], "edible": 0.82,
    },
    "Figue de Barbarie": {
        "kw": ["poire cactus", "poires cactus"], "match": "any",
        "href_any": ["/fruits-et-legumes/"], "edible": 0.55,
    },
    "Courge poivree": {
        "kw": ["courge poivrée", "courge poivree"], "match": "any",
        "href_any": ["/fruits-et-legumes/"], "edible": 0.70,
    },
    "Courge spaghetti": {
        "kw": ["courge spaghetti"], "not": ["biologique"],
        "href_any": ["/fruits-et-legumes/"], "edible": 0.70,
    },
    "Poire asiatique": {
        "kw": ["poire asiatique"], "href_any": ["/fruits-et-legumes/"], "edible": 0.90,
    },
    "Piment jalapeno": {
        "kw": ["piment jalapeño", "piment jalapeno"], "match": "any",
        "href_any": ["/fruits-et-legumes/"], "edible": 0.90,
    },
    "Piment habanero": {
        "kw": ["piment habanero"], "href_any": ["/fruits-et-legumes/"], "edible": 0.90,
    },
    "Aubergine chinoise": {
        "kw": ["aubergine chinoise"], "href_any": ["/fruits-et-legumes/"], "edible": 0.90,
    },
    "Courgette jaune": {
        "kw": ["courgette jaune"], "href_any": ["/fruits-et-legumes/"], "edible": 1.0,
    },
    "Patate douce violette": {
        "kw": ["patate douce violette"], "href_any": ["/fruits-et-legumes/"], "edible": 0.86,
    },
    "Kiwi dore": {
        "kw": ["kiwi doré", "kiwis doré", "kiwi dore", "kiwis dore"],
        "match": "any", "href_any": ["/fruits-et-legumes/"], "edible": 0.80,
    },
})

_LB_KG = 0.453592
_OZ_KG = 0.0283495


def _unit_to_kg(v: float, u: str) -> float | None:
    """Convertit `v` d'unité `u` en kg. Le volume (ml/l) suppose une densité ≈
    1 g/ml (eau/lait/sirop/conserves liquides) — approximation raisonnable pour
    un candidat à revoir, sinon impossible de tarifer les produits en ml/L."""
    return {
        "kg": v, "g": v / 1000, "lb": v * _LB_KG, "oz": v * _OZ_KG,
        "ml": v / 1000, "l": v,
    }.get(u)


def _format_weight_kg(item: dict) -> float | None:
    """Poids (kg) déduit du format ("675 g", "1.75 kg", "4,54 kg", "540 ml",
    "2 l") ou, à défaut, du slug d'URL ("blackberries-6-oz", "gala-apple-3-lbs",
    "...-1-75-kg"). Le volume (ml/l) est ramené au poids via densité ≈ 1
    (cf. `_unit_to_kg`). Séparateur décimal `.` OU `,` (formats superc.ca,
    FR, ex. "4,54 kg" — sans la variante `,`, la virgule coupait le nombre en
    plein milieu et un match parasite plus loin dans la chaîne pouvait donner
    un poids ~10x trop élevé ; validé contre data/imports/Cuisine/superc.json,
    177/1547 items réels avec virgule dans `format`, cf. task-4-report.md)."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g|lb|oz|ml|l)\b", item.get("format") or "", re.I)
    if m:
        return _unit_to_kg(float(m.group(1).replace(",", ".")), m.group(2).lower())
    # Les cartons d'œufs sont vendus à l'unité (6/12/18/24/30), jamais au
    # poids. Un gros œuf fournit environ 50 g de portion comestible.
    name = str(item.get("name") or "").lower()
    count = re.search(r"(\d+)\s*(?:un|unités?|unites?)\b", item.get("format") or "", re.I)
    if count and re.search(r"\b(?:œuf|oeuf)s?\b", name) and not re.search(
        r"liquide|mariné|marine|sandwich|pâtes|pates|nouille|torsade", name
    ):
        return int(count.group(1)) * 0.050
    # La circulaire omet parfois le format alors que la fiche correspondante
    # est explicitement le carton Naturalia de 12 gros œufs. Sans ce repli, la
    # promo est visible mais rejetée comme non chiffrable avant le solveur.
    if (
        not (item.get("format") or "").strip()
        and re.search(r"\b(?:œuf|oeuf)s?\b", name)
        and "naturalia" in name
        and "poules en liberté" in name
        and "format économique" not in name
    ):
        return 12 * 0.050
    # Slug : "-6-oz", "-675-g", "-3-lbs", "-1-75-kg" (le point devient tiret).
    h = re.search(r"-(\d+(?:-\d+)?)-(kg|g|lbs?|oz|ml|l)(?:[-?/]|$)", item.get("href") or "", re.I)
    if h:
        v = float(h.group(1).replace("-", "."))
        return _unit_to_kg(v, h.group(2).lower().rstrip("s"))
    return None


def purchase_unit_weight_kg(item: dict) -> float | None:
    """Poids d'une unité réellement ajoutée au panier.

    Pour un paquet, il s'agit du poids indiqué dans ``format``. Pour un produit
    vendu au poids mais ajouté par unité (fruit, légume, barquette de viande),
    Super C fournit à la fois le prix estimé de l'unité et le prix au kg/lb :
    leur rapport donne le poids moyen d'une unité. Cette seconde forme empêche
    notamment de traiter un seul plantain comme s'il pouvait couvrir 1,2 kg.
    """
    formatted = _format_weight_kg(item)
    if formatted and formatted > 0:
        return formatted
    price = item.get("price")
    unit_price = item.get("unit_price")
    unit = str(item.get("unit") or "").lower()
    if not isinstance(price, (int, float)) or price <= 0:
        return None
    if not isinstance(unit_price, (int, float)) or unit_price <= 0:
        return None
    amount = float(price) / float(unit_price)
    return {"kg": amount, "lb": amount * _LB_KG, "g": amount / 1000.0}.get(unit)


def adonis_price_per_100g_edible(item: dict, edible: float = _EDIBLE_DEFAULT) -> float | None:
    """CAD/100 g de portion comestible depuis un item Adonis, ou None si indéterminable.

    Priorité à `price_per_100g` (fourni directement par le scraper superc.ca,
    Task 1 — plus précis) ; sinon prix unitaire au poids ($/kg ou $/lb) ; sinon
    dérivé du prix paquet + poids du format.
    """
    edible = edible or 1.0
    pp = item.get("price_per_100g")
    if isinstance(pp, (int, float)) and not isinstance(pp, bool) and pp > 0:
        return round(float(pp) / edible, 3)
    per_kg = None
    up, u = item.get("unit_price"), (item.get("unit") or "").lower()
    if up and u:
        if u == "kg":
            per_kg = up
        elif u == "lb":
            per_kg = up / _LB_KG
        elif u == "g":
            per_kg = up * 1000
    if per_kg is None and item.get("price"):
        w = _format_weight_kg(item)
        if w:
            per_kg = item["price"] / w
    if per_kg is None:
        return None
    return round((per_kg / 10.0) / edible, 3)


def _matches(item: dict, spec: dict) -> bool:
    # Nom SEUL depuis le repoint superc.ca (2026-07-23, cf.
    # orchestration/a-faire/2026-07-23-superc-ca-repoint-design.md §B). Avant
    # (Instacart), le slug d'URL était un nom de produit à part entière
    # (/products/<id>-nom-du-produit) et complétait un `name` parfois peu
    # fiable. Sur superc.ca, `href` est un fil d'Ariane de CATÉGORIES
    # (/allees/produits-laitiers-et-oeufs/laits-cremes-et-beurres/.../p/<upc>)
    # : matcher dessus fait fuiter le nom d'un rayon entier sur chaque produit
    # qu'il contient (ex. TOUT produit laitier a "oeufs" et "beurres" dans son
    # href, via le nom du rayon "produits-laitiers-et-oeufs" et de la
    # sous-catégorie "laits-cremes-et-beurres" -> faux match "Oeufs"/"Beurre"
    # -> "Lait 0%", trouvé en validant contre le vrai cache, cf. rapport Task
    # 3). `name` (attribut data-product-name du scraper Task 1) est déjà fiable
    # ("bien plus fiable que parser le texte affiché", cf. task-1-report.md) :
    # plus besoin du slug. `match` = "all" (défaut) : tous les mots-clés requis
    # (ex. bell+pepper) ; "any" : au moins un (mots-clés SYNONYMES).
    n = str(item.get("name") or "").lower()
    href = str(item.get("href") or "").lower()
    if spec.get("href_any") and not any(part.lower() in href for part in spec["href_any"]):
        return False
    if any(part.lower() in href for part in spec.get("href_not", [])):
        return False
    kws = spec["kw"]
    if spec.get("match", "all") == "any":
        if not any(re.search(r"\b" + re.escape(kw), n) for kw in kws):
            return False
    elif any(not re.search(r"\b" + re.escape(kw), n) for kw in kws):
        return False
    return not any(re.search(r"\b" + re.escape(no), n) for no in spec.get("not", []))


def build_price_overlay(adonis_items: list[dict], item_map: dict | None = None) -> dict[str, float]:
    """{aliment FR: prix CAD/100 g comestible} pour les aliments matchés.

    `item_map` (défaut : PRODUCE_MAP, les fruits & légumes) mappe chaque aliment
    FR à `{kw, edible, not?}`. Passer un autre map (ex. CATALOG_MAP) pour couvrir
    tout le catalogue. En cas de plusieurs correspondances, garde la MOINS chère.
    """
    if item_map is None:
        item_map = PRODUCE_MAP
    overlay: dict[str, float] = {}
    for fr, spec in item_map.items():
        best = None
        for it in adonis_items:
            if not (it.get("name") or it.get("href")) or not _matches(it, spec):
                continue
            p = adonis_price_per_100g_edible(it, spec.get("edible", _EDIBLE_DEFAULT))
            if p is not None and (best is None or p < best):
                best = p
        if best is not None:
            overlay[fr] = best
    return overlay


def apply_overlay_to_df(df, overlay: dict[str, float]):
    """Remplace `Prix` des aliments présents dans `overlay` ET dans `df`.

    Retourne (df, liste des aliments effectivement re-tarifés)."""
    changed = []
    for nom, prix in overlay.items():
        if nom in df.index:
            df.loc[nom, "Prix"] = prix
            changed.append(nom)
    return df, changed


# ── Super C (magasin unique) ───────────────────────────────────────────────
# Le cache superc.json (écrit par frontend/.superc_scrape.mjs via
# store_pricing.refresh_all_if_stale au démarrage) vient de superc.ca depuis
# le repoint 2026-07-23 (noms FR, price_per_100g direct, UPC — cf. Task 1) ;
# build_price_overlay / adonis_price_per_100g_edible sont réutilisés tels
# quels (logique pure, seuls les mots-clés — désormais FR — ont changé).

def _superc_cache_path() -> Path:
    return settings.imports_dir / "Cuisine" / "superc.json"


def load_superc_cached_items() -> list[dict]:
    path = _superc_cache_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("items", [])
    except Exception:
        return []


def apply_superc_produce_prices(df):
    """Re-tarife les fruits & légumes du catalogue avec les prix Super C.

    Best-effort : cache absent/illisible ou toute erreur -> `df` inchangé. La
    fraîcheur du cache superc.json est assurée par
    `store_pricing.refresh_all_if_stale` au démarrage (scrape search-based sur
    les termes de la semaine) — pas de scrape à la volée ici. Désactivable via
    SUPERC_PRODUCE_PRICING=0. Retourne (df, liste des aliments re-tarifés).
    """
    if os.getenv("SUPERC_PRODUCE_PRICING", "1") not in ("1", "true", "True"):
        return df, []
    try:
        items = load_superc_cached_items()
        if not items:
            return df, []
        return apply_overlay_to_df(df, build_price_overlay(items))
    except Exception as exc:
        logger.warning("[superc] re-tarification produce ignorée (%s)", exc)
        return df, []


def apply_superc_catalog_prices(df, shopping_day=None):
    """Re-tarife tout le catalogue avec prix courants ET circulaire Super C.

    L'overlay est appliqué en mémoire : les valeurs nutritionnelles et le CSV
    source ne sont jamais modifiés. Pour chaque aliment, le prix unitaire le
    moins cher entre le catalogue courant et la circulaire gagne.

    `shopping_day` : jour où le panier sera PAYÉ (cf.
    `sante.fenetre.shopping_day_for`). S'il tombe du lundi au mercredi, le
    rabais étudiant de 10 % est appliqué à tous les prix, promotions comprises.
    None = pas de rabais supposé (on ne sous-estime jamais la facture).
    """
    if os.getenv("SUPERC_CATALOG_PRICING", "1") not in ("1", "true", "True"):
        return df, []
    try:
        from app.services.cuisine import student_discount
        from app.services.cuisine.store_pricing import load_cached_items
        from app.services.sante.superc_catalog_rebuild import catalog_price_overlay

        items = [*load_cached_items("superc"), *load_cached_items("superc_flyer")]
        if not items:
            return df, []
        # L'affichage d'un plan final ne contient qu'une vingtaine d'aliments :
        # ne pas recalculer les prix de toutes les familles du catalogue.
        overlay = catalog_price_overlay(items, target_names=set(map(str, df.index)))
        remise = student_discount.factor(shopping_day)
        if remise != 1.0:
            overlay = {nom: prix * remise for nom, prix in overlay.items()}
        return apply_overlay_to_df(df, overlay)
    except Exception as exc:
        logger.warning("[superc] re-tarification catalogue ignorée (%s)", exc)
        return df, []
