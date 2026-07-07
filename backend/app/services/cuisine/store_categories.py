"""Classification des ingrédients de la liste de courses en catégories
d'achat, avec mots-clés de recherche EN (vitrine Instacart en anglais), pour
la comparaison de prix Super C / Adonis. Voir
orchestration/finis/2026-07-06-lufa-superc-comparaison-prix-design.md.

Première version : seed manuel à corriger/étendre au fil de l'usage réel,
même philosophie que PRODUCE_MAP dans adonis_pricing.py (édite directement
le dict, aucun réimport nécessaire).
"""
from __future__ import annotations

from app.services.sante.adonis_pricing import PRODUCE_MAP

_PANTRY_KW: dict[str, list[str]] = {
    "Flocons d'avoine": ["oats", "oatmeal"],
    "Riz basmati (sec)": ["basmati rice"],
    "Riz brun (sec)": ["brown rice"],
    "Quinoa (sec)": ["quinoa"],
    "Pates (sec)": ["pasta"],
    "Lentilles seches": ["lentils"],
    "Pois chiches en conserve": ["chickpeas"],
    "Haricots noirs en conserve": ["black beans"],
    "Tomates concassees en conserve": ["diced tomatoes", "crushed tomatoes"],
    "Sel marin": ["sea salt"],
    "Huile d'olive extra-vierge": ["olive oil"],
    "Huile d'avocat": ["avocado oil"],
    "Huile de coco": ["coconut oil"],
    "Miel": ["honey"],
    "Sirop d'erable": ["maple syrup"],
    "Chocolat noir 72%": ["dark chocolate"],
    "Farine d'amande": ["almond flour"],
    "Tahini (sesame)": ["tahini"],
    "Graines de tournesol": ["sunflower seeds"],
    "Graines de lin": ["flax seed"],
    "Graines de chia": ["chia seed"],
    "Graines de courge": ["pumpkin seeds"],
    "Amandes": ["almonds"],
    "Noix de cajou": ["cashews"],
    "Noix de Grenoble": ["walnuts"],
    "Pacanes": ["pecans"],
    "Pistaches": ["pistachios"],
    "Arachides": ["peanuts"],
    "Noix de macadamia": ["macadamia"],
    "Pignons": ["pine nuts"],
    "Beurre d'arachide": ["peanut butter"],
    "Beurre d'amande": ["almond butter"],
}

_VIANDE_VOLUME_KW: dict[str, list[str]] = {
    "Poitrine de poulet": ["chicken breast"],
    "Cuisses de poulet desossees": ["chicken thighs", "boneless chicken thigh"],
    "Boeuf hache extra-maigre 5%": ["ground beef", "extra lean ground beef"],
    "Dinde hachee": ["ground turkey"],
    "Thon pale en conserve": ["canned tuna", "light tuna"],
    "Sardines en conserve": ["sardines"],
    "Maquereau": ["mackerel"],
    "Bacon": ["bacon"],
    "Crevettes cuites": ["cooked shrimp"],
}

_VIANDE_NOBLE_KW: dict[str, list[str]] = {
    "Bifteck de boeuf (faux-filet)": ["striploin steak", "sirloin steak"],
    "Filet de porc": ["pork tenderloin"],
    "Saumon atlantique": ["atlantic salmon", "salmon fillet"],
    "Saumon fume": ["smoked salmon"],
    "Tilapia": ["tilapia"],
    "Truite arc-en-ciel": ["rainbow trout"],
}

_TOFU_PROTEINES_KW: dict[str, list[str]] = {
    "Tofu ferme": ["firm tofu"],
    "Houmous": ["hummus"],
    "Boisson de soja": ["soy beverage", "soy milk"],
    "Whey protein (Inshape)": ["whey protein"],
    "Clear whey isolat (Inshape)": ["clear whey"],
    "Mass gainer chocolat (Inshape)": ["mass gainer"],
    "Barre proteinee + vitamines (Inshape)": ["protein bar"],
    "Pancakes proteines chocolat (Inshape)": ["protein pancake"],
    "Pate a tartiner proteinee cacao-noisettes (Inshape)": ["protein spread"],
    "Beurre de cacahuetes (Inshape)": ["peanut butter"],
    "Whey Leanfit vanille (Costco)": ["whey protein vanilla"],
    "Whey Gold Standard banane (ON)": ["gold standard whey banana"],
    "Mass gainer Serious Mass banane (ON)": ["serious mass banana"],
    "Clear whey + collagene pomme-framboise (ON)": ["clear whey collagen"],
    "Barre proteinee chocolate berry crunch (ON)": ["protein bar berry"],
    "Barre proteinee chocolate sea salt crunch (ON)": ["protein bar sea salt"],
    "Protein hot chocolate (ON)": ["protein hot chocolate"],
}

# Catégorie -> {nom FR: mots-clés EN}. "fruits_legumes" réutilise PRODUCE_MAP
# (adonis_pricing.py) comme source de vérité, pas de duplication.
_CATEGORY_KW: dict[str, dict[str, list[str]]] = {
    "pantry": _PANTRY_KW,
    "viande_volume": _VIANDE_VOLUME_KW,
    "viande_noble": _VIANDE_NOBLE_KW,
    "tofu_proteines": _TOFU_PROTEINES_KW,
    "fruits_legumes": {fr: spec["kw"] for fr, spec in PRODUCE_MAP.items()},
}


def categorie_achat(ingredient: str) -> str | None:
    """Catégorie d'achat de `ingredient` (nom FR exact, ex. "Tofu ferme"), ou
    None si non classifié (comportement rayon simple inchangé, pas de badge
    magasin)."""
    for categorie, kw_map in _CATEGORY_KW.items():
        if ingredient in kw_map:
            return categorie
    return None


def search_keywords(ingredient: str) -> list[str]:
    """Mots-clés EN à chercher dans les vitrines scrapées pour `ingredient`,
    ou liste vide si non classifié."""
    for kw_map in _CATEGORY_KW.values():
        if ingredient in kw_map:
            return kw_map[ingredient]
    return []
