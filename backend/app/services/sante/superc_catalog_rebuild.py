"""Phase 3 « Super C unique » — outillage NON destructif de reconstruction des
prix d'`aliments.csv` sur les prix Super C.

Le catalogue est hand-curé (teneurs CIQUAL 2020 + prix Costco relevés à la main,
ajustés à la portion comestible). On ne l'écrase JAMAIS automatiquement :
`scripts/rebuild_superc_catalog.py` lit le cache `superc.json`, calcule les
nouveaux prix pour les aliments matchés, et écrit un CSV **candidat** + un
rapport des aliments **retirés** (aucun match Super C = non vendu → retiré,
décision user 2026-07-14). L'utilisateur revoit puis bascule lui-même.

Ce module ne contient que la logique pure (mapping, plan de reconstruction,
réécriture texte du CSV transposé) ; les I/O vivent dans le script.

Réf : orchestration/a-faire/2026-07-14-superc-unique-design.md (Phase 3).
"""
from __future__ import annotations

from app.services.cuisine.store_categories import (
    NON_PRODUCE_KW,
    SOURCE_CANADIAN_PROTEIN,
    est_alimentaire,
)
from app.services.sante.adonis_pricing import PRODUCE_MAP, build_price_overlay

# Suppléments / marques que Super C ne vend pas : jamais mappés → toujours
# « non matchés » → retirés du catalogue (décision user). Repérés au suffixe.
_SUPPLEMENT_MARKERS = ("(inshape)", "(on)", "(costco)")


def _is_supplement(name: str) -> bool:
    n = name.lower()
    return any(m in n for m in _SUPPLEMENT_MARKERS)


# Œufs & produits laitiers absents des maps « courses » (seed extensible, même
# philosophie que PRODUCE_MAP : à corriger/étendre au vu des résultats réels).
# `edible` = 1.0 (pas de partie jetée) sauf indication ; `not` exclut les faux
# positifs (Beurre ≠ beurre d'arachide/amande). Mots-clés en FRANÇAIS depuis le
# repoint superc.ca (2026-07-23) ; `œuf`/`oeuf` : les deux graphies (ligature
# et digramme) sont listées, `_matches` ne normalise pas les accents.
_DAIRY_EGGS_SPEC: dict[str, dict] = {
    # Bug historique (Instacart EN) : "egg" matchait "eggplant" (aubergine).
    # En FR "œuf"/"oeuf" ne sont substrings d'aucun autre mot du catalogue
    # (notamment PAS de "bœuf" : `\b` exige une frontière de mot juste avant
    # "œuf", or "b" et "œ" sont tous deux `\w` pour `re` -> pas de frontière
    # entre eux, vérifié), mais le `not` "aubergine" est conservé en garde
    # défensive. Les vrais œufs entiers se vendent à la douzaine (jamais au
    # poids) -> AUCUN carton d'œufs entiers n'a de `price_per_100g` ni de
    # poids dérivable ("12 un" n'est pas une unité de poids) : n'importe quel
    # produit CONTENANT "œuf(s)" et chiffrable (donc PAS un carton) gagne par
    # défaut, même si ce n'est pas des œufs entiers. D'où la longue liste de
    # `not` : "liquide" (Blancs d'oeufs liquide, sans jaune), "mariné"/
    # "marine" (œufs marinés au vinaigre, collation à l'unité), "torsade"
    # (pain torsadé AUX œufs, pas des œufs), "pâtes"/"pates" (pâtes alimentaires
    # aux œufs), "nouille" (nouilles aux œufs), "sandwich" (sandwich à la
    # tartinade aux œufs) — tous des produits qui NOMMENT "œufs" comme simple
    # ingrédient, moins chers au 100 g que le seul carton d'œufs cuits durs
    # écalés du cache (qui, lui, reste éligible : ce sont de vrais œufs
    # entiers, juste précuits). Cf. rapport de raffinage 2026-07-24.
    "Oeufs": {
        "kw": ["oeuf", "œuf"],
        "not": [
            "aubergine", "liquide", "mariné", "marine",
            "torsade", "pâtes", "pates", "nouille", "sandwich",
        ],
        "edible": 1.0,
    },
    # "cheddar" reste le mot-clé le plus difficile à isoler (saveur très
    # utilisée sur snacks/craquelins/riz/saucisses) : exclusions best-effort,
    # pas garanties exhaustives (cf. task-3-report.md, limitation connue).
    "Fromage cheddar": {
        "kw": ["cheddar"],
        "not": [
            "saucisse", "riz", "craquelin", "macaroni", "préparation",
            "preparation", "pâtes", "pates", "croustille", "chips",
            "sauce", "soupe", "biscuit", "collation",
        ],
        "edible": 1.0,
    },
    "Mozzarella": {"kw": ["mozzarella"], "edible": 1.0},
    # "parmesan" bare, en plus de "sauce"/"mayonnaise", matchait (moins cher
    # au 100 g que le vrai fromage) une trempette, une fondue surgelée, un
    # poulet parmesan surgelé, des pâtes en sachet et des chips aromatisées
    # -> validé contre le vrai superc.json, cf. rapport de raffinage 2026-07-24.
    "Parmesan": {
        "kw": ["parmesan"],
        "not": [
            "sauce", "mayonnaise", "trempette", "fondue", "poulet",
            "pâtes", "pates", "chips", "croûton", "crouton",
            "saucisson", "torsade", "feuilleté", "feuillete",
        ],
        "edible": 1.0,
    },
    "Yogourt grec nature 0%": {
        "kw": [
            "yogourt grec nature 0 %", "yogourt grec nature 0%",
            "yogourt grec 0 % nature", "yogourt grec 0% nature",
        ],
        "not": ["vanille", "fraise", "mangue", "pêche", "peche", "miel"],
        "edible": 1.0,
    },
    "Yogourt grec nature 2%": {
        "kw": [
            "yogourt grec nature 2 %", "yogourt grec nature 2%",
            "yogourt nature 2 % grec", "yogourt nature 2% grec",
            "yogourt 2 % nature grec", "yogourt 2% nature grec",
        ],
        "not": ["vanille", "fraise", "mangue", "pêche", "peche", "miel"],
        "edible": 1.0,
    },
    "Yogourt grec nature entier": {
        "kw": [
            "yogourt grec nature 4 %", "yogourt grec nature biologique 4 %",
            "yogourt grec biologique nature 4 %", "yogourt grec nature 5 %",
            "yogourt grec nature 8 %",
            "yogourt grec nature 9 %",
            "yogourt grec nature 10 %", "yogourt grec 4 % nature",
            "yogourt grec 5 % nature",
            "yogourt grec 8 % nature", "yogourt grec 9 % nature",
            "yogourt grec 10 % nature",
        ],
        "not": ["vanille", "fraise", "mangue", "pêche", "peche", "miel"],
        "edible": 1.0,
    },
    # Le vrai superc.json écrit TOUJOURS "Lait 2 %" avec une espace avant le
    # "%" (ex. "Beatrice Lait 2 %", "Natrel Lait 2 %") : "lait 2%" (collé,
    # sans espace) ne matchait donc JAMAIS rien -> aucun match, cf. rapport
    # de raffinage 2026-07-24. "lait partiellement écrémé 2%" n'existe pas
    # comme tel dans le cache réel (conservé quand même en synonyme
    # défensif, `match="any"` donc gratuit). Le fait de chercher le
    # sous-texte EXACT "lait 2 %" (et pas juste "lait" + "2 %" séparés)
    # exclut aussi, sans `not` dédié, les variantes "Lait au chocolat 2 %"/
    # "Lait sans lactose 2 %"/"Lait biologique 2 %" (mots intercalés ->
    # substring absente) : comportement voulu, on vise le lait nature.
    "Lait 2%": {
        "kw": [
            "lait 2 %", "lait 2%",
            "lait partiellement écrémé 2%", "lait partiellement ecreme 2%",
        ],
        "not": ["amande", "avoine", "soja", "soya", "coco"],
        "edible": 1.0,
    },
    # Le vrai superc.json ne vend pas de "lait d'amande" : la famille de
    # produits s'appelle "Boisson d'amande" (même convention que "Boisson
    # d'avoine"/"Boisson de soya" ci-dessous) -> "lait d'amande non sucré"
    # ne matchait jamais rien, cf. rapport de raffinage 2026-07-24.
    "Lait d'amande non sucre": {
        "kw": ["boisson d'amande non sucrée", "boisson d'amande non sucree"],
        "edible": 1.0,
    },
    "Beurre": {
        "kw": ["beurre"],
        # "gâteau"/"biscuit"/"café" : "beurre" bare matche aussi des desserts
        # et rehausseurs à café qui le nomment comme ingrédient/saveur (ex.
        # "Mélange à gâteau ... au beurre", "Rehausseur de café ... beurre et
        # pacanes") -> validé contre le vrai superc.json, cf. task-3-report.md.
        # "végétal" : "Becel Beurre végétal (non) salé" (margarine, PAS un
        # produit laitier) était moins cher que le vrai beurre et gagnait
        # -> validé contre le vrai superc.json, cf. rapport de raffinage
        # 2026-07-24.
        "not": [
            "arachide", "cacahuète", "cacahuete", "amande", "cajou",
            "gâteau", "biscuit", "café", "rehausseur", "végétal", "vegetal",
            "saveur", "maïs soufflé", "mais soufflé", "croustille", "popcorn",
            "poulet", "chocolat", "craquelin",
        ],
        "edible": 1.0,
    },
    # "saucisse" : "feta" bare matche aussi des saucisses de poulet farcies
    # au feta -> validé contre le vrai superc.json, cf. task-3-report.md.
    "Feta": {"kw": ["feta"], "not": ["saucisse", "salade"], "edible": 1.0},
    # "porc"/"farci" : "brie" bare matche aussi un filet de porc farci au brie
    # (plat préparé, pas un morceau de fromage) -> validé contre le vrai
    # superc.json, cf. task-3-report.md.
    "Brie": {"kw": ["brie"], "not": ["porc", "farci"], "edible": 1.0},
    "Gouda": {"kw": ["gouda"], "edible": 1.0},
    # "feuilleté" : "gruyère" bare matchait un snack apéro feuilleté au
    # gruyère (moins cher que le vrai fromage, SEUL autre produit "gruyère"
    # du cache) -> validé contre le vrai superc.json, cf. rapport de
    # raffinage 2026-07-24.
    "Gruyere": {"kw": ["gruyere", "gruyère"], "not": ["feuilleté", "feuillete"], "edible": 1.0},
    "Emmental": {"kw": ["emmental"], "edible": 1.0},
    "Fromage de chevre": {"kw": ["fromage de chèvre", "fromage de chevre"], "edible": 1.0},
    "Camembert": {"kw": ["camembert"], "edible": 1.0},
    "Provolone": {"kw": ["provolone"], "edible": 1.0},
    # Comme "Lait 2%" : le vrai superc.json nomme le lait entier/écrémé par
    # son taux de gras ("Lait 3,25 %"/"Lait 0 %"), jamais littéralement "lait
    # entier". "lait écrémé" existe bien dans le cache réel mais SEULEMENT
    # pour le lait EN POUDRE ("Lait écrémé en poudre instantané", un produit
    # différent, plus cher) -> sans "lait 0 %"/"lait 0%", "Lait ecreme" ne
    # matchait jamais le vrai lait écrémé liquide. Cf. rapport de raffinage
    # 2026-07-24.
    "Lait entier": {
        "kw": ["lait entier", "lait 3,25 %", "lait 3,25%", "lait 3.25 %", "lait 3.25%"],
        "not": ["amande", "avoine", "soja", "soya", "coco"],
        "edible": 1.0,
    },
    "Lait ecreme": {
        "kw": ["lait écrémé", "lait ecreme", "lait 0 %", "lait 0%"],
        "not": ["amande", "avoine", "soja", "soya", "coco", "poudre"],
        "edible": 1.0,
    },
    "Boisson d'avoine": {"kw": ["boisson d'avoine"], "edible": 1.0},
    "Kefir": {
        "kw": ["kéfir", "kefir"],
        "not": [
            "fraise", "mangue", "pêche", "peche", "vanille", "framboise",
            "bleuet", "cerise", "ananas", "fruit",
        ],
        "edible": 1.0,
    },
    # Au Québec, l'équivalent du fromage blanc européen est commercialisé
    # principalement comme « fromage cottage ». Ne pas chercher le générique
    # « fromage blanc » : il ramenait notamment un fromage Krinos en saumure,
    # nutritionnellement beaucoup plus proche d'une feta.
    "Fromage blanc": {
        "kw": ["fromage cottage", "cottage", "quark"],
        "match": "any",
        "not": ["crème", "creme", "gâteau", "gateau"],
        "edible": 1.0,
    },
}


# `not` défensifs pour quelques items NON_PRODUCE_KW (garde-manger/viandes) à
# risque de faux match catégorie — découverts en validant CATALOG_MAP contre
# le vrai superc.json (cf. task-3-report.md), ex. "Miel" matchait des
# arachides rôties AU miel, "Sel marin" des ailes de poulet, "Noix de cajou"
# un poulet thaï surgelé. NON_PRODUCE_KW reste `list[str]` (pas de notion de
# `not` là-bas, aussi utilisé par store_categories pour les courses) : cet
# overlay ne s'applique qu'ici, à la construction du catalogue prix précis.
_NON_PRODUCE_NOT: dict[str, list[str]] = {
    "Miel": ["arachide", "moutarde", "sauce", "céréale"],
    "Sirop d'erable": ["fève", "feve", "yogourt", "céréale", "granola"],
    "Huile d'olive extra-vierge": ["mayonnaise"],
    "Huile d'avocat": ["mayonnaise", "margarine"],
    "Sel marin": ["poulet", "aile", "croustille", "chips", "craquelin"],
    "Sel iode": ["poivre", "mélange", "melange", "assaisonnement"],
    "Amandes": [
        "boisson", "beurre", "farine", "café", "colorant", "céréale",
        "barre", "granola", "miel", "olive", "farcie", "farci",
        "crème glacée", "creme glacee", "glace",
    ],
    "Arachides": [
        "beurre", "barre", "céréale", "cereale", "chocolat", "biscuit",
        "assaisonnée", "assaisonnee", "saveur", "bbq", "barbecue",
        "blanchies salées", "blanchies salees", "mélange", "melange",
    ],
    "Noix de cajou": ["poulet", "thaï", "thai", "barre"],
    # "chocolat"/"cajou" ajoutés 2026-07-24 (rapport de raffinage) : "pacane"
    # bare matchait des mini-chocolats Nestlé (caramel + pacanes = confiserie,
    # pas des noix) et un mélange noix de cajou/pacane (pas des pacanes
    # pures) — les deux moins chers que les vraies pacanes en morceaux/
    # moitiés, validé contre le vrai superc.json.
    "Pacanes": [
        "crème glacée", "glace", "gâteau", "café", "rehausseur", "biscuit",
        "granola", "tarte", "chocolat", "cajou",
    ],
    "Pistaches": ["crème glacée", "glace"],
    # « farine » bare matche farine d'amandes/noix de coco, bien plus chères :
    # les retenir ferait passer les tortillas maison pour ruineuses.
    "Farine tout usage": ["amande", "amandes", "noix de coco", "sarrasin", "épeautre",
                          "epeautre", "avoine", "riz", "gâteau", "pâtisserie"],
    "Masa harina": ["amande", "amandes", "croustille", "chips", "semoule"],
    # Les croustilles de tortilla coûtent ~3× la tortilla souple : les inclure
    # inverserait l'arbitrage cuisiner/acheter.
    "Tortilla de mais": ["croustille", "chips", "nacho", "doritos", "tostitos"],
    "Tortilla de ble": ["croustille", "chips", "nacho", "doritos", "tostitos", "wrap garni"],
    "Pignons": ["vin"],
    # Le cache réel ne contient AUCUNE noix de macadamia nature (seulement des
    # barres énergétiques et des biscuits qui en contiennent) -> exclure les
    # deux pour finir SANS match (honnête) plutôt que de chiffrer sur une
    # confiserie, cf. rapport de raffinage 2026-07-24.
    "Noix de macadamia": ["biscuit", "barre"],
    # "chocolat noir" bare matchait une boisson aux amandes aromatisée, des
    # céréales granola et un dessert glacé, tous moins chers que la vraie
    # tablette de chocolat noir 72 % -> validé contre le vrai superc.json,
    # cf. rapport de raffinage 2026-07-24.
    "Chocolat noir 72%": ["boisson", "céréale", "cereale", "granola", "dessert", "barre", "amande"],
    "Bacon": ["vinaigrette", "saucisse", "chien", "mayonnaise", "sauce"],
    "Quinoa (sec)": ["pain", "céréale"],
    # Ces grains apparaissent dans les ingrédients de pains et de céréales,
    # sans être vendus seuls. Ne jamais appliquer le profil du grain brut à un
    # produit transformé seulement parce que son nom le mentionne.
    "Sarrasin entier (sec)": [
        "farine", "pain", "céréale", "cereale", "barre", "craquelin",
        "crêpe", "crepe", "mélange", "melange",
    ],
    "Orge monde (sec)": [
        "farine", "pain", "céréale", "cereale", "barre", "soupe",
        "mélange", "melange",
    ],
    "Amarante (sec)": [
        "farine", "pain", "céréale", "cereale", "barre", "purée", "puree",
        "mélange", "melange",
    ],
    "Pates (sec)": ["sauce", "préparation", "preparation", "fromage"],
    "Couscous (sec)": ["salade", "thon", "préparé", "prepare"],
    "Pain complet": ["sandwich", "hamburger", "hot dog"],
    "Huile de canola": ["mayonnaise", "margarine", "vinaigrette"],
    "Huile de tournesol": ["mayonnaise", "margarine", "thon"],
    "Saumon en conserve": ["fumé", "fume", "frais", "chien", "chat"],
    "Graines de tournesol": [
        "assaisonnée", "assaisonnee", "salée", "salee", "amande", "mélange",
        "melange", "céréale", "cereale", "granola", "fruits", "noix", "barre",
    ],
    "Graines de sesame": ["pain", "craquelin", "barre", "tahini"],
    "Pate de tomate": ["pâtes alphabet", "pates alphabet", "sauce"],
    "Semoule de mais (sec)": ["pozole", "farine", "croustille", "chips"],
    "Pilons de poulet": ["pané", "pane", "portugais"],
    "Poitrine de poulet": [
        "marinée", "marinee", "assaisonnée", "assaisonnee", "panée", "panee",
        "saucisse", "charcuterie", "sandwich",
    ],
    "Ailes de poulet": ["pané", "pane", "sauce", "assaisonné", "assaisonne"],
    "Poulet hache": ["saucisse", "boulette"],
    "Porc hache": ["saucisse", "boulette"],
    "Crevettes crues": ["tempura", "brochette", "cuites", "cocktail"],
    "Thon jaune en conserve": ["salade", "huile", "chili", "tomate"],
    "Thon pale en conserve": [
        "salade", "quinoa", "chili", "thaï", "thai", "épicé", "epice",
        "citron", "aneth", "tomate", "mexicaine", "piment",
    ],
    "Saumon fume": ["fromage", "tartinade", "bol"],
    "Cacao non sucre en poudre": [
        "boisson", "céréale", "cereale", "barre", "chocolat chaud", "garniture",
        "biscuit", "granola", "pépite", "pepite", "tartinade", "vermicelle",
    ],
    "Cannelle moulue": [
        "céréale", "cereale", "gruau", "barre", "biscuit", "rouleau", "thé", "the",
    ],
    "The vert infuse non sucre": [
        "crème glacée", "creme glacee", "concentré", "concentre", "latté", "latte",
        "grenade", "framboise", "fraise", "ginseng", "citron", "miel", "jasmin",
    ],
    # "crevette" (catch-all ajouté dans store_categories.NON_PRODUCE_KW,
    # cf. rapport de raffinage 2026-07-24) matcherait aussi une tartinade de
    # crevettes/homard/saumon fumé (pas des crevettes entières) : exclue.
    "Crevettes cuites": [
        "tartinade", "crue", "crues", "dumpling", "ravioli", "wonton",
        "rouleau", "soupe", "plat préparé", "plat prepare",
    ],
}


def _build_catalog_map() -> dict[str, dict]:
    """Mapping aliment FR → {kw, edible, not?} pour TOUT le catalogue.

    Réutilise les mots-clés « courses » (NON_PRODUCE_KW, source unique) + un seed
    œufs/laitiers, avec `edible=1.0` par défaut. Les fruits & légumes (PRODUCE_MAP)
    apportent leur propre fraction comestible et écrasent les doublons éventuels.
    Les suppléments/marques Costco sont EXCLUS (→ retirés à la reconstruction).
    """
    m: dict[str, dict] = {}
    # NON_PRODUCE_KW + laitiers = listes de SYNONYMES -> match "any" (au moins un
    # mot-clé), sinon un item ne peut jamais porter les 2 synonymes à la fois.
    for name, kw in NON_PRODUCE_KW.items():
        if _is_supplement(name):
            continue
        if name == "Crevettes cuites":
            # Les mots peuvent être séparés (« crevettes blanches du Pacifique
            # cuites surgelées »), mais doivent être présents tous les deux.
            # Le mot générique « crevette » seul ramenait dumplings et produits
            # panés, qui héritaient ensuite à tort du profil CIQUAL des crevettes.
            spec = {"kw": ["crevette", "cuite"], "edible": 1.0, "match": "all"}
        else:
            spec = {"kw": kw, "edible": 1.0, "match": "any"}
        if name in _NON_PRODUCE_NOT:
            spec["not"] = _NON_PRODUCE_NOT[name]
        if name == "Pates (sec)":
            spec["href_any"] = ["/garde-manger/pates-riz-et-feves/pates/"]
        elif name == "Haricots noirs en conserve":
            spec["href_any"] = ["/conserve", "/aliments-en-conserve"]
        m[name] = spec
    for name, spec in _DAIRY_EGGS_SPEC.items():
        m[name] = {**spec, "match": "any"}
    m.update(PRODUCE_MAP)   # produce : un seul mot-clé/aliment, edible/`not` propres
    return m


CATALOG_MAP: dict[str, dict] = _build_catalog_map()


def catalog_price_overlay(
    cache_items: list[dict], target_names: set[str] | None = None
) -> dict[str, float]:
    """{aliment FR: prix CAD/100 g comestible} pour tout le catalogue, depuis les
    items Super C en cache (schéma superc.ca, noms FR — cf. Task 1 du repoint).

    Les rayons non alimentaires sont écartés en amont : l'overlay retient le
    produit le MOINS cher de chaque famille, or une pâtée pour chats « aux
    saveurs de crevette » à 0,47 $/100 g bat toujours de vraies crevettes.
    """
    alimentaires = [it for it in cache_items if est_alimentaire(it)]
    mapping = (
        CATALOG_MAP
        if target_names is None
        else {name: spec for name, spec in CATALOG_MAP.items() if name in target_names}
    )
    return build_price_overlay(alimentaires, mapping)


def plan_rebuild(
    catalog_items: list[str], overlay: dict[str, float], mappable: set[str]
) -> tuple[dict[str, float], list[str], list[str]]:
    """Classe les aliments du catalogue en (matchés, retirés, gardés_sans_prix).

    - `matched` : {aliment: prix Super C} — re-tarifés.
    - `removed` : aliments HORS mapping (`mappable`) = suppléments / marques que
      Super C ne vend pas → RETIRÉS (décision user).
    - `kept_no_price` : aliments mappés mais sans prix Super C matché cette fois
      (produit vendu mais gap de scrape / prix non dérivable) → CONSERVÉS avec
      leur prix actuel, à vérifier/saisir. On NE les retire PAS : supprimer un
      aliment que Super C vend sur un simple trou de scrape serait destructeur.

    Ordre = ordre du catalogue (rapports déterministes).
    """
    matched = {name: overlay[name] for name in catalog_items if name in overlay}
    # Les aliments achetés hors épicerie ne sont pas « non vendus » : ils sont
    # vendus ailleurs, avec un prix relevé à la source
    # (scripts/import_canadian_protein.py). Les retirer parce que Super C ne les
    # référence pas effacerait la créatine et la poudre de protéine du catalogue.
    removed = [name for name in catalog_items
               if name not in mappable and name not in SOURCE_CANADIAN_PROTEIN]
    kept_no_price = [
        name for name in catalog_items
        if name not in overlay and (name in mappable
                                    or name in SOURCE_CANADIAN_PROTEIN)
    ]
    return matched, removed, kept_no_price


def _fmt_price(price: float) -> str:
    """Prix en texte pour le CSV (décimales conservées, jamais de notation sci)."""
    return f"{price:.3f}".rstrip("0").rstrip(".")


def rewrite_catalog_csv(
    lines: list[str], matched: dict[str, float], removed: list[str]
) -> list[str]:
    """Réécrit le CSV transposé (`;`) en NE touchant QUE la ligne `Prix` (aliments
    matchés) et en RETIRANT les colonnes des aliments `removed` (hors mapping).

    Les aliments mappés mais sans prix Super C (kept_no_price) NE sont PAS passés
    ici → conservés tels quels. `lines` : lignes du CSV d'origine (sans `\\n`
    final). Ligne 0 = en-tête (`Nutriments;aliment1;…`). Les teneurs CIQUAL sont
    préservées à l'identique. Retourne les nouvelles lignes.
    """
    if not lines:
        return []
    header = lines[0].split(";")
    foods = header[1:]
    removed_set = set(removed)
    # Indices de colonnes à RETIRER (décalés de 1 : la colonne 0 est le libellé).
    drop = {i + 1 for i, f in enumerate(foods) if f in removed_set}
    keep = [i for i in range(len(header)) if i not in drop]

    out: list[str] = []
    for line in lines:
        cells = line.split(";")
        # Pad défensif si une ligne est plus courte que l'en-tête.
        if len(cells) < len(header):
            cells = cells + [""] * (len(header) - len(cells))
        if cells and cells[0] == "Prix":
            for i, f in enumerate(foods):
                if f in matched:
                    cells[i + 1] = _fmt_price(matched[f])
        out.append(";".join(cells[i] for i in keep))
    return out
