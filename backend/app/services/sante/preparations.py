"""Préparations maison : faut-il cuisiner ou acheter ?

Chaque préparation (lait végétal, tortilla…) est décrite par ses **ingrédients du
catalogue**, son rendement et son temps de travail. Le profil nutritionnel et le
coût en sont *calculés*, jamais saisis : les prix suivent donc automatiquement les
promotions Super C, et une préparation cesse d'être intéressante d'elle-même
quand son équivalent commercial est en solde.

Le verdict applique la règle utilisateur : le temps vaut `TAUX_HORAIRE_CAD`. Une
préparation n'est retenue que si l'économie réalisée, ramenée au temps passé,
dépasse ce taux — sinon acheter est le bon choix.

Point de vigilance : comparer un prix au litre entre maison et commerce n'a de
sens qu'à **profil nutritionnel comparable**. Le lait d'avoine du commerce est
hydrolysé enzymatiquement et additionné d'huile ; il est bien plus dense que ce
qu'un filtrage maison extrait. C'est pourquoi l'économie est calculée à apport
équivalent (cf. `economie_par_100g_equivalent`), et non au litre.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

# Règle utilisateur (2026-08-06) : le temps est valorisé au salaire horaire.
TAUX_HORAIRE_CAD = 20.0

# Aliments dont le prix n'a PAS pu être relevé sur Super C et repose donc sur une
# estimation marché. Ils sont mappés dans `store_categories.NON_PRODUCE_KW` : le
# prix deviendra réel dès qu'un scrape aboutira, et il suffira alors de les
# retirer d'ici. Toute évaluation qui en dépend est signalée comme provisoire —
# un verdict « cuisiner/acheter » assis sur un prix inventé serait trompeur.
#
# Contexte 2026-08-06 : `.superc_scrape.mjs` échoue sur la sélection du magasin
# et ramène 0 résultat pour n'importe quel terme ; le cache des prix courants est
# figé au 2026-07-24. Seule la circulaire se rafraîchit encore.
PRIX_NON_VERIFIES: frozenset[str] = frozenset({
    "Farine tout usage", "Masa harina", "Tortilla de mais", "Tortilla de ble",
    # La créatine et la poudre de protéine n'y figurent plus : leur prix est
    # désormais relevé chez Canadian Protein (scripts/import_canadian_protein.py),
    # à partir du JSON Shopify et du poids net annoncé — donc réel, pas estimé.
})

# Nutriments comparés pour juger de l'équivalence avec le produit commercial.
_NUTRIMENTS_CLES = ("Energie", "Proteines", "Lipides", "Glucides")


@dataclass(frozen=True)
class Preparation:
    """Une recette maison candidate au remplacement d'un produit acheté."""

    nom: str
    #: {aliment du catalogue: grammes}, pour un lot de `lot_defaut` unités.
    ingredients: dict[str, float]
    #: Masse produite (g) par lot.
    rendement_g: float
    #: Produit commercial équivalent, présent au catalogue.
    equivalent_commercial: str
    #: Minutes indépendantes de la taille du lot (matériel, vaisselle).
    temps_fixe_min: float
    #: Minutes par unité de lot supplémentaire.
    temps_variable_min: float
    #: Nombre d'unités (litres, fournées) préparées en une session.
    lot_defaut: float = 1.0
    #: Fraction des nutriments des ingrédients qui finit dans le produit.
    #: 1.0 quand rien n'est jeté (pâtes) ; < 1 quand un résidu est filtré
    #: (okara des laits végétaux). Voir la note de chaque préparation.
    extraction: float = 1.0
    notes: str = ""
    #: Ingrédients sans valeur nutritionnelle ni coût suivi (eau, sel).
    ingredients_libres: tuple[str, ...] = field(default_factory=tuple)


PREPARATIONS: tuple[Preparation, ...] = (
    Preparation(
        nom="Lait d'avoine maison",
        ingredients={"Flocons d'avoine": 90.0},
        rendement_g=1000.0,
        equivalent_commercial="Boisson d'avoine",
        temps_fixe_min=6.0,
        temps_variable_min=3.0,
        lot_defaut=2.0,
        # L'okara retient une part importante des solides. 0,55 est une
        # estimation médiane : les mesures publiées vont de 0,45 à 0,70 selon la
        # finesse du filtre et la pression exercée. À affiner si tu pèses ton okara.
        extraction=0.55,
        notes="Eau froide et mixage court : l'amidon libéré rend le lait gluant.",
        ingredients_libres=("Eau", "Sel"),
    ),
    Preparation(
        nom="Lait d'amande maison",
        ingredients={"Amandes": 90.0},
        rendement_g=1000.0,
        equivalent_commercial="Lait d'amande non sucre",
        temps_fixe_min=6.0,
        temps_variable_min=5.0,   # + trempage 8 h, sans surveillance
        lot_defaut=2.0,
        extraction=0.50,
        notes="Trempage 8 h. Presser le résidu, contrairement à l'avoine.",
        ingredients_libres=("Eau", "Sel"),
    ),
    Preparation(
        nom="Tortilla de mais maison",
        ingredients={"Masa harina": 550.0},
        rendement_g=1000.0,   # la masa absorbe son poids d'eau
        equivalent_commercial="Tortilla de mais",
        temps_fixe_min=10.0,
        temps_variable_min=45.0,   # ~22 tortillas de 45 g par lot de 1 kg
        lot_defaut=1.0,
        extraction=1.0,       # rien n'est jeté, seule l'eau s'ajoute
        notes="Presse à tortillas indispensable pour tenir la cadence.",
        ingredients_libres=("Eau", "Sel"),
    ),
    Preparation(
        nom="Tortilla de ble maison",
        ingredients={"Farine tout usage": 620.0, "Huile d'olive extra-vierge": 60.0},
        rendement_g=1000.0,
        equivalent_commercial="Tortilla de ble",
        temps_fixe_min=10.0,
        temps_variable_min=75.0,   # repos 30 min + étalage au rouleau
        lot_defaut=1.0,
        extraction=1.0,
        notes="Repos de 30 min puis étalage : le plus long des quatre.",
        ingredients_libres=("Eau", "Sel"),
    ),
)


@dataclass(frozen=True)
class Evaluation:
    """Résultat chiffré pour une préparation, aux prix du jour."""

    nom: str
    rentable: bool
    taux_horaire: float
    cout_par_100g: float
    cout_commercial_par_100g: float
    economie_par_lot: float
    temps_min: float
    #: Densité énergétique rapportée à celle du produit commercial (1.0 = égale).
    ratio_densite: float
    profil: dict[str, float]
    ingredients_manquants: tuple[str, ...] = ()
    motif: str = ""
    #: Aliments du calcul dont le prix est une estimation, pas un relevé Super C.
    prix_estimes: tuple[str, ...] = ()

    @property
    def verdict_fiable(self) -> bool:
        """False si le verdict repose sur au moins un prix non relevé."""
        return not self.prix_estimes


def _profil_pour_100g(prep: Preparation, df: pd.DataFrame) -> tuple[dict[str, float], list[str]]:
    """Profil nutritionnel calculé depuis les ingrédients, pour 100 g de produit."""
    manquants = [nom for nom in prep.ingredients if nom not in df.index]
    if manquants:
        return {}, manquants
    colonnes = [c for c in df.columns if c not in ("MinQty", "MaxQty", "Congelable", "CreamiOk")]
    profil: dict[str, float] = {}
    for col in colonnes:
        total = sum(
            float(df.loc[nom, col]) * grammes / 100.0
            for nom, grammes in prep.ingredients.items()
        )
        if col != "Prix":
            total *= prep.extraction     # le prix, lui, est payé en entier
        profil[col] = total / prep.rendement_g * 100.0
    return profil, []


def evaluer(
    prep: Preparation, df: pd.DataFrame, taux_horaire: float = TAUX_HORAIRE_CAD,
    lot: Optional[float] = None,
) -> Evaluation:
    """Chiffre une préparation aux prix courants du catalogue."""
    lot = prep.lot_defaut if lot is None else lot
    profil, manquants = _profil_pour_100g(prep, df)
    if manquants:
        return Evaluation(
            nom=prep.nom, rentable=False, taux_horaire=0.0, cout_par_100g=0.0,
            cout_commercial_par_100g=0.0, economie_par_lot=0.0, temps_min=0.0,
            ratio_densite=0.0, profil={}, ingredients_manquants=tuple(manquants),
            motif=f"ingrédients absents du catalogue : {', '.join(manquants)}",
        )
    if prep.equivalent_commercial not in df.index:
        return Evaluation(
            nom=prep.nom, rentable=False, taux_horaire=0.0, cout_par_100g=0.0,
            cout_commercial_par_100g=0.0, economie_par_lot=0.0, temps_min=0.0,
            ratio_densite=0.0, profil=profil,
            motif=f"équivalent commercial absent : {prep.equivalent_commercial}",
        )

    cout_100g = profil["Prix"]
    commercial = df.loc[prep.equivalent_commercial]
    cout_commercial_100g = float(commercial["Prix"])

    # Comparaison à APPORT ÉQUIVALENT, pas à volume égal : un lait maison deux
    # fois moins dense n'économise pas deux fois plus. On ramène le coût maison
    # à la densité énergétique du produit commercial.
    energie_maison = float(profil.get("Energie", 0.0))
    energie_commerciale = float(commercial.get("Energie", 0.0))
    ratio = energie_maison / energie_commerciale if energie_commerciale > 0 else 1.0
    if ratio <= 0:
        ratio = 1.0
    cout_maison_equivalent = cout_100g / ratio

    economie_100g = cout_commercial_100g - cout_maison_equivalent
    # Le lot produit `rendement_g` de maison, soit `rendement_g × ratio` en
    # équivalent commercial.
    equivalent_produit_g = prep.rendement_g * lot * ratio
    economie_lot = economie_100g * equivalent_produit_g / 100.0

    temps_min = prep.temps_fixe_min + prep.temps_variable_min * lot
    taux = economie_lot / (temps_min / 60.0) if temps_min > 0 else 0.0
    rentable = taux >= taux_horaire

    estimes = tuple(sorted(
        (set(prep.ingredients) | {prep.equivalent_commercial}) & PRIX_NON_VERIFIES
    ))
    motif = (
        f"{taux:.2f} $/h ≥ {taux_horaire:.0f} $/h" if rentable
        else f"{taux:.2f} $/h < {taux_horaire:.0f} $/h — acheter"
    )
    if estimes:
        motif += f" (prix estimé : {', '.join(estimes)})"
    return Evaluation(
        nom=prep.nom, rentable=rentable, taux_horaire=taux,
        cout_par_100g=cout_100g, cout_commercial_par_100g=cout_commercial_100g,
        economie_par_lot=economie_lot, temps_min=temps_min, ratio_densite=ratio,
        profil=profil, motif=motif, prix_estimes=estimes,
    )


def evaluer_toutes(
    df: pd.DataFrame, taux_horaire: float = TAUX_HORAIRE_CAD
) -> list[Evaluation]:
    """Chiffre toutes les préparations, les plus rentables d'abord."""
    return sorted(
        (evaluer(p, df, taux_horaire) for p in PREPARATIONS),
        key=lambda e: -e.taux_horaire,
    )


def lot_minimal_rentable(
    prep: Preparation, df: pd.DataFrame, taux_horaire: float = TAUX_HORAIRE_CAD,
    lot_max: float = 12.0,
) -> Optional[float]:
    """Plus petit lot (au quart d'unité près) atteignant le taux horaire visé.

    Le temps de préparation étant largement fixe, une recette non rentable en
    petit lot peut le devenir en grand — c'est l'information utile pour décider,
    plus que le simple verdict à la taille par défaut.
    """
    lot = 0.25
    while lot <= lot_max:
        if evaluer(prep, df, taux_horaire, lot=lot).rentable:
            return lot
        lot += 0.25
    return None


def appliquer_preparations_rentables(
    df: pd.DataFrame, taux_horaire: float = TAUX_HORAIRE_CAD
) -> tuple[pd.DataFrame, list[Evaluation]]:
    """Ajoute au catalogue les préparations qui passent le seuil horaire.

    Les autres sont volontairement absentes : l'optimiseur ne doit pas proposer
    de cuisiner à perte. Le catalogue d'origine n'est jamais modifié en place.
    """
    evaluations = evaluer_toutes(df, taux_horaire)
    retenues = [e for e in evaluations if e.rentable]
    if not retenues:
        return df, evaluations

    df = df.copy()
    for ev in retenues:
        ligne = {col: ev.profil.get(col, 0.0) for col in df.columns}
        source = next(p for p in PREPARATIONS if p.nom == ev.nom)
        commercial = df.loc[source.equivalent_commercial]
        # Propriétés d'usage héritées du produit équivalent : un lait maison se
        # sépare au gel comme un lait acheté.
        for col in ("Congelable", "CreamiOk", "MinQty", "MaxQty"):
            if col in df.columns:
                ligne[col] = float(commercial.get(col, 0.0))
        df.loc[ev.nom] = ligne
    return df, evaluations
