"""Classification des ingrédients de la liste de courses en catégories
d'achat, avec mots-clés de recherche FRANÇAIS (superc.ca, repoint
2026-07-23 — auparavant EN pour la vitrine Instacart), pour la comparaison
de prix Super C / Adonis. Voir
orchestration/finis/2026-07-06-lufa-superc-comparaison-prix-design.md et
orchestration/a-faire/2026-07-23-superc-ca-repoint-design.md (§B).

Première version : seed manuel à corriger/étendre au fil de l'usage réel,
même philosophie que PRODUCE_MAP dans adonis_pricing.py (édite directement
le dict, aucun réimport nécessaire).

Mots-clés = listes de SYNONYMES (au moins un doit matcher, cf.
`superc_catalog_rebuild._build_catalog_map` -> `match: "any"`), PAS des
mots indépendants tous requis. Ce dict reste `list[str]` (pas de `not`
possible ici, contrairement à PRODUCE_MAP/_DAIRY_EGGS_SPEC) : les collisions
FR connues (ex. "amande" bare matcherait "beurre d'amande") sont évitées en
choisissant des expressions assez spécifiques (le pluriel du fruit à coque
entier ne matche pas le singulier de "beurre d'amande"/"beurre d'arachide" ;
cf. adonis_pricing.PRODUCE_MAP pour les items qui, eux, ont besoin de `not`.
"""
from __future__ import annotations

from app.services.sante.adonis_pricing import PRODUCE_MAP

_PANTRY_KW: dict[str, list[str]] = {
    # PAS de "avoine" seul (trop générique : matche aussi "Boisson à l'avoine"
    # -> validé contre le vrai superc.json, cf. task-3-report.md).
    "Flocons d'avoine": ["flocons d'avoine", "gruau"],
    "Riz basmati (sec)": ["riz basmati", "basmati"],
    "Riz brun (sec)": ["riz brun"],
    "Quinoa (sec)": ["quinoa"],
    "Pois casses secs": ["pois cassés", "pois casses"],
    "Orge perlee (sec)": ["orge perlée", "orge perlee"],
    "Orge monde (sec)": ["orge mondé", "orge monde", "orge entière", "orge entiere"],
    "Sarrasin entier (sec)": [
        "sarrasin entier", "gruau de sarrasin", "sarrasin décortiqué",
        "sarrasin decortique",
    ],
    "Amarante (sec)": ["amarante"],
    "Couscous (sec)": ["couscous"],
    "Boulgour (sec)": ["boulgour", "bulgur"],
    "Pain complet": ["pain complet", "pain de blé entier", "pain de ble entier"],
    # Termes spécifiques (pas de "pâtes" seul) : évite "pâtes de fruits"
    # (confiseries) que le mot générique matcherait aussi.
    "Pates (sec)": ["pâtes alimentaires", "pates alimentaires", "spaghetti", "macaroni", "penne", "fusilli"],
    "Pates aux oeufs (sec)": [
        "pâtes aux œufs", "pates aux oeufs", "nouilles aux œufs", "nouilles aux oeufs",
    ],
    "Pates de ble entier (sec)": [
        "pâtes de blé entier", "pates de ble entier", "pâtes de blé complet",
        "pates de ble complet",
    ],
    # Idem : "lentilles" seul risquerait de matcher des lentilles de contact
    # (pharmacie) sur un site Metro/Super C ; couleurs = spécifique épicerie.
    "Lentilles seches": ["lentilles sèches", "lentilles seches", "lentilles vertes", "lentilles rouges", "lentilles brunes"],
    "Pois chiches en conserve": ["pois chiche"],
    # Pluriel : le vrai superc.json écrit toujours "Haricots noirs" (jamais
    # "Haricot noir" au singulier) -> "haricot noir" (singulier) ne matchait
    # jamais "haricots noirs" (le "s" de "haricots" casse le \b + substring
    # littéral avant d'atteindre " noir"), cf. rapport de raffinage 2026-07-24.
    "Haricots noirs en conserve": ["haricots noirs"],
    "Tomates concassees en conserve": [
        "tomates concassées", "tomates concassees", "tomates en dés", "tomates en des",
        "tomates broyées", "tomates broyees",
    ],
    "Sel marin": ["sel marin"],
    "Sel iode": ["sel iodé", "sel iode"],
    # Bases des préparations maison (tortillas) — cf. `preparations.py`. Les prix
    # doivent venir de Super C comme tout le reste : sans ces entrées, l'arbitrage
    # cuisiner/acheter se calculerait sur des estimations.
    "Farine tout usage": ["farine tout usage", "farine tout-usage", "farine blanche"],
    "Masa harina": ["masa harina", "maseca", "farine de maïs", "farine de mais"],
    "Semoule de mais (sec)": ["semoule de maïs jaune", "semoule de mais jaune", "polenta"],
    "Pate de tomate": ["pâte de tomates", "pate de tomates"],
    "Graines de sesame": ["graines de sésame", "graines de sesame"],
    # Tortillas SOUPLES : le mot « tortilla » seul ramène surtout des croustilles
    # (Doritos, Tostitos) — d'où les exclusions dans `_NON_PRODUCE_NOT`.
    "Tortilla de mais": ["tortillas de maïs", "tortillas de mais", "tortilla de maïs"],
    "Tortilla de ble": [
        "tortillas de blé", "tortillas de ble", "tortilla de blé", "tortillas souples",
    ],
    "Huile d'olive extra-vierge": ["huile d'olive"],
    "Huile d'avocat": ["huile d'avocat"],
    "Huile de coco": ["huile de coco", "huile de noix de coco"],
    "Huile de canola": ["huile de canola"],
    "Huile de tournesol": ["huile de tournesol"],
    "Miel": ["miel"],
    "Sirop d'erable": ["sirop d'érable", "sirop d'erable"],
    "Chocolat noir 72%": ["chocolat noir"],
    "Farine d'amande": ["farine d'amande"],
    "Tahini (sesame)": ["tahini"],
    "Graines de tournesol": ["graines de tournesol"],
    "Graines de lin": ["graines de lin"],
    "Graines de chia": ["graines de chia"],
    "Graines de courge": ["graines de courge"],
    # Pluriel volontaire (comme le nom catalogue) : "beurre d'amande"/"beurre
    # d'arachide" sont au singulier après "d'", donc jamais matchés par erreur
    # par le pluriel "amandes"/"arachides" (pas de `not` possible sur ce dict).
    "Amandes": ["amandes"],
    "Noix de cajou": ["noix de cajou"],
    "Noix de Grenoble": ["noix de grenoble"],
    "Pacanes": ["pacanes", "noix de pécan", "noix de pecan"],
    "Pistaches": ["pistaches"],
    "Arachides": ["arachides"],
    "Noix de macadamia": ["noix de macadamia", "macadamia"],
    "Pignons": ["pignons"],
    "Beurre d'arachide": [
        "beurre d'arachide naturel", "beurre d'arachide entièrement naturel",
        "beurre d'arachide entierement naturel", "juste des arachides",
    ],
    "Beurre d'amande": ["beurre d'amande"],
    "Cacao non sucre en poudre": [
        "cacao non sucré", "cacao non sucre", "poudre de cacao", "cacao pur",
        "cacao première qualité", "cacao premiere qualite",
    ],
    "Cannelle moulue": ["cannelle moulue", "cannelle en poudre"],
    "The vert infuse non sucre": ["thé vert", "the vert"],
}

_VIANDE_VOLUME_KW: dict[str, list[str]] = {
    "Poitrine de poulet": ["poitrine de poulet"],
    "Cuisses de poulet desossees": ["cuisses de poulet désossées", "cuisses de poulet desossees", "cuisse de poulet"],
    "Boeuf hache extra-maigre 5%": ["bœuf haché extra-maigre", "boeuf hache extra-maigre"],
    "Dinde hachee": ["dinde hachée", "dinde hachee"],
    "Thon pale en conserve": ["thon pâle", "thon pale"],
    "Sardines en conserve": ["sardine"],
    "Saumon en conserve": ["saumon en conserve", "saumon sockeye sauvage"],
    "Maquereau": ["maquereau"],
    "Bacon": ["bacon"],
    # "crevettes cuites" (substring collée) ne matche AUCUN produit réel : le
    # vrai superc.json insère toujours un descriptif entre les deux mots
    # ("Crevettes NORDIQUES cuites surgelées", "Crevettes BLANCHES DU
    # PACIFIQUE cuites surgelées"...) -> jamais "crevettes cuites" adjacents.
    # "crevette" (générique) ajouté comme catch-all : tout le rayon crevettes
    # du cache est déjà cuit surgelé (pas de crevette crue observée) -> pas de
    # faux positif nutrition ; le seul faux positif catégorie (tartinade de
    # crevettes) est exclu via `_NON_PRODUCE_NOT`. Cf. rapport de raffinage
    # 2026-07-24.
    "Crevettes cuites": [
        "crevette",
        "crevettes cuites", "crevettes cuites et décortiquées", "crevettes cuites et decortiquees",
    ],
    "Palourdes en conserve": ["petites palourdes entières", "petites palourdes entieres"],
    "Pilons de poulet": ["pilons de poulet"],
    "Ailes de poulet": ["ailes de poulet"],
    "Poulet hache": ["poulet haché", "poulet hache"],
    "Porc hache": ["porc haché", "porc hache"],
    "Crevettes crues": ["crevettes sauvages d'argentine crues", "crevettes crues"],
    "Thon jaune en conserve": ["thon pâle à nageoires jaunes", "thon pale a nageoires jaunes"],
}

_VIANDE_NOBLE_KW: dict[str, list[str]] = {
    # PAS de "surlonge" seul (matche aussi la surlonge de PORC, viande
    # différente -> validé contre le vrai superc.json, cf. task-3-report.md).
    # "faux-filet" est un terme spécifiquement bovin.
    "Bifteck de boeuf (faux-filet)": ["faux-filet"],
    "Filet de porc": ["filet de porc"],
    # "saumon frais" (pas "filet de saumon" seul) : evite de matcher "filet
    # de saumon FUME" (aliment separe "Saumon fume", pas de `not` sur ce dict).
    "Saumon atlantique": ["saumon atlantique", "saumon frais"],
    "Saumon fume": ["saumon fumé", "saumon fume"],
    "Tilapia": ["tilapia"],
    "Truite arc-en-ciel": ["truite arc-en-ciel", "truite"],
    "Cotelettes de porc": ["côtelettes de porc", "cotelettes de porc"],
    "Saumon coho sauvage": ["saumon coho"],
    "Bifteck de cote": ["bifteck de côte de bœuf", "bifteck de cote de boeuf"],
}

_TOFU_PROTEINES_KW: dict[str, list[str]] = {
    "Tofu ferme": ["tofu ferme", "tofu extra-ferme"],
    "Tempeh": ["tempeh"],
    "Houmous": ["houmous", "hummus"],
    "Boisson de soja": ["boisson de soja", "boisson soya", "boisson de soya", "lait de soja", "lait de soya"],
    # Suppléments/marques (Inshape/ON/Costco) : Super C ne les vend pas ->
    # jamais mappés dans CATALOG_MAP (cf. _is_supplement) -> jamais matchés
    # contre superc.ca -> mots-clés EN d'origine non traduits (hors scope).
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

# Laitiers, fromages, œufs et boissons végétales. Sans cette table, 21 aliments
# du catalogue n'avaient AUCUN mot-clé : `search_keywords` renvoyait une liste
# vide, ils n'étaient donc jamais cherchés sur superc.ca et leur prix restait
# figé à la valeur d'origine, quel que soit le nombre de scrapes lancés.
#: Aliments achetés hors épicerie, chez Canadian Protein (commande en ligne
#: séparée). Ils ne doivent jamais apparaître dans un panier Super C, et l'UI
#: les signale distinctement puisqu'ils demandent un achat à part.
#: Leur prix est relevé par `scripts/import_canadian_protein.py`.
SOURCE_CANADIAN_PROTEIN: frozenset[str] = frozenset({
    "Creatine monohydrate", "Proteine en poudre",
})


def source_achat(ingredient: str) -> str:
    """Où l'aliment s'achète : "canadian_protein" ou "epicerie" (défaut)."""
    return ("canadian_protein" if ingredient in SOURCE_CANADIAN_PROTEIN
            else "epicerie")


#: Rayons de superc.ca dont AUCUN produit ne doit tarifer un aliment. Le
#: matching se fait par mot-clé sur le nom, donc « crevette » attrapait « Whiskas
#: nourriture sèche pour chats aux saveurs de crevette » à 0,47 $/100 g, et
#: « cajou » une boisson végétale à 0,29 $/100 g. Ces faux positifs sont les
#: MOINS chers de leur famille, donc systématiquement retenus : sans ce filtre,
#: le catalogue tarifie des crevettes au prix des croquettes.
RAYONS_NON_ALIMENTAIRES: tuple[str, ...] = (
    "animalerie", "animaux", "pharmacie", "sante-et-beaute", "beaute",
    "entretien-menager", "nettoyage", "maison", "quincaillerie", "bebe",
    "hygiene", "papeterie", "jouets", "vetements",
)


def est_alimentaire(item: dict) -> bool:
    """Faux si le produit vient d'un rayon non alimentaire (chemin de catégorie).

    On s'appuie sur `href`, qui porte le fil d'Ariane des rayons — le NOM seul ne
    permet pas de distinguer une pâtée pour chat aux crevettes de vraies crevettes.
    """
    href = str(item.get("href") or "").lower()
    return not any(f"/{rayon}" in href or f"{rayon}/" in href
                   for rayon in RAYONS_NON_ALIMENTAIRES)


_LAITIERS_KW: dict[str, list[str]] = {
    "Oeufs": ["oeufs", "œufs"],
    "Beurre": ["beurre non salé", "beurre salé"],
    "Lait 2%": ["lait 2 %", "lait 2%"],
    "Lait entier": ["lait 3,25 %", "lait entier"],
    "Lait ecreme": ["lait écrémé", "lait 0 %"],
    "Kefir": ["kéfir"],
    # Appellation québécoise du fromage blanc européen. « Fromage frais » est
    # trop ambigu et peut désigner du fromage à la crème.
    "Fromage blanc": ["fromage cottage", "cottage", "quark"],
    "Yogourt grec nature 0%": ["yogourt grec nature", "yogourt grec 0 %"],
    "Yogourt grec nature 2%": ["yogourt grec nature 2 %", "yogourt nature 2 % grec"],
    "Yogourt grec nature entier": [
        "yogourt grec nature 5 %", "yogourt grec nature 8 %",
        "yogourt grec nature 9 %",
        "yogourt grec nature 10 %",
    ],
    "Fromage cheddar": ["fromage cheddar"],
    "Mozzarella": ["fromage mozzarella"],
    "Parmesan": ["fromage parmesan"],
    "Feta": ["fromage feta"],
    "Brie": ["fromage brie"],
    "Gouda": ["fromage gouda"],
    "Gruyere": ["fromage gruyère"],
    "Emmental": ["fromage emmental"],
    "Camembert": ["fromage camembert"],
    "Provolone": ["fromage provolone"],
    "Fromage de chevre": ["fromage de chèvre"],
    "Lait d'amande non sucre": ["boisson d'amande", "lait d'amande"],
    "Boisson d'avoine": ["boisson d'avoine", "lait d'avoine"],
}

# Catégorie -> {nom FR: mots-clés FR}. "fruits_legumes" réutilise PRODUCE_MAP
# (adonis_pricing.py) comme source de vérité, pas de duplication.
_CATEGORY_KW: dict[str, dict[str, list[str]]] = {
    "pantry": _PANTRY_KW,
    "viande_volume": _VIANDE_VOLUME_KW,
    "viande_noble": _VIANDE_NOBLE_KW,
    "tofu_proteines": _TOFU_PROTEINES_KW,
    "laitiers": _LAITIERS_KW,
    "fruits_legumes": {fr: spec["kw"] for fr, spec in PRODUCE_MAP.items()},
}

# Mots-clés FR des aliments NON fruits/légumes (viandes, épicerie, tofu/protéines
# ; suppléments/marques Inshape-ON-Costco exclus : EN d'origine, jamais matchés,
# cf. commentaire ci-dessus), exposés pour la reconstruction du catalogue
# Super C (superc_catalog_rebuild.py) — source unique, pas de re-duplication.
NON_PRODUCE_KW: dict[str, list[str]] = {
    **_PANTRY_KW, **_VIANDE_VOLUME_KW, **_VIANDE_NOBLE_KW, **_TOFU_PROTEINES_KW,
    **_LAITIERS_KW,
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
    """Mots-clés FR à chercher dans les vitrines scrapées (superc.ca) pour
    `ingredient`, ou liste vide si non classifié."""
    for kw_map in _CATEGORY_KW.values():
        if ingredient in kw_map:
            return kw_map[ingredient]
    return []
