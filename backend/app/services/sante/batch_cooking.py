"""Optimisation conjointe de la journée : 2 tacos + 1 pot CREAMi + complément frais.

Le design (`orchestration/a-faire/2026-08-06-batch-cooking-tacos-design.md`) pose
le principe central : **les trois blocs sont optimisés ENSEMBLE, en une passe**.
Optimiser le taco seul puis ajouter du frais pour combler les micronutriments
produit mécaniquement un surplus de macros — un taco couvrant déjà 85 % des
protéines ne laisse plus de place calorique aux fruits et laitages qui portent la
vitamine C, le calcium et le potassium. Ici la contrainte de couverture porte sur
la somme ``2·taco + 1·creami + frais``, donc le dépassement est impossible par
construction.

Mise en œuvre : plutôt que d'écrire un second optimiseur, on construit un
DataFrame « élargi » où chaque aliment autorisé dans un bloc devient une ligne
distincte (``taco::Maquereau``, ``creami::Banane``, ``frais::Kiwi``), dont les
apports et le prix sont multipliés par le nombre de portions du bloc. La physique
de `optimize_nutrition` (bornes, MinQty semi-continu, contraintes dures) est
réutilisée telle quelle, et la solution se redécompose par préfixe.

Deux blocs sont soumis à une **base imposée**, sans quoi l'optimiseur produit des
mélanges du type « 113 g de graines de courge » :

- taco : une tortilla, au moins une source protéique, au moins deux légumes, un liant ;
- pot CREAMi : une base liquide, un fruit, de la protéine en poudre, de la créatine.

Cas particulier de la créatine : c'est un composé pur, sans macro ni micro du
catalogue. Sa contribution à l'objectif est donc *nulle* et son prix positif —
l'optimiseur la mettrait toujours à zéro. Elle est traitée comme un **imposé à
quantité fixe** (dose journalière), retiré du problème et soustrait des cibles,
et non comme une variable de décision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

from app.services.sante.ratio_optimizer import optimize_ratio

#: Balayage du poids-prix réduit par rapport à la fenêtre quotidienne. Le
#: problème élargi compte ~240 variables (trois blocs × catalogue) là où la
#: fenêtre en a 116, et SLSQP y coûte ~8 s par pondération : les six valeurs par
#: défaut mèneraient à plus de dix minutes une fois multipliées par les essais de
#: tortilla et les passes de structure. Trois valeurs couvrent le même intervalle
#: (permissif → avare) pour un tiers du temps. La génération étant MENSUELLE,
#: elle doit de toute façon tourner en tâche de fond, jamais dans une requête.
PRICE_WEIGHTS_BATCH: tuple[float, ...] = (0.001, 0.08, 0.6)

#: Passes de réparation de la base imposée. Chaque passe impose TOUTES les
#: familles manquantes d'un coup, donc deux suffisent en pratique ; la
#: troisième est une sécurité si une famille imposée en évince une autre.
MAX_PASSES_STRUCTURE = 3

#: Candidats retenus par bloc, les meilleurs en couverture par dollar.
#:
#: Ce n'est pas une optimisation de confort : `optimize_nutrition` démarre en
#: posant 5 g sur CHAQUE aliment (100 g sur les féculents de base). Avec trois
#: blocs, ce point de départ passe de 9,49 $ à 25,65 $ et viole la contrainte de
#: budget avant la première itération — SLSQP rend alors « Inequality
#: constraints incompatible » quel que soit le budget accordé. Borner chaque
#: bloc ramène le départ sous le budget et divise le temps de calcul.
#:
#: Les ingrédients de la base imposée sont conservés hors quota : ils sont
#: choisis avant, et leur éviction rendrait la structure infaisable.
MAX_CANDIDATS_PAR_BLOC = 45

#: Portions par jour de chaque bloc. Le taco compte double : la recette est
#: identique pour les deux tacos du jour, donc une variable pour deux portions.
TACOS_PAR_JOUR = 2
CREAMI_PAR_JOUR = 1

#: Dose journalière de créatine (g). Fixe : cf. docstring du module.
CREATINE_G_PAR_JOUR = 5.0

_SEP = "::"

# ── Base imposée : catégories d'ingrédients ────────────────────────────────
# Le catalogue ne porte pas de taxonomie ; ces familles sont donc explicites,
# comme l'est déjà `CREAMI_OK` dans le script d'enrichissement. Elles servent
# uniquement à vérifier/forcer la structure, pas à restreindre l'optimisation.

TORTILLAS: tuple[str, ...] = ("Tortilla de mais", "Tortilla de ble")

PROTEINES_TACO: frozenset[str] = frozenset({
    "Poitrine de poulet", "Cuisses de poulet desossees", "Boeuf hache extra-maigre 5%",
    "Dinde hachee", "Filet de porc", "Bifteck de boeuf (faux-filet)", "Oeufs",
    "Thon pale en conserve", "Sardines en conserve", "Maquereau", "Tilapia",
    "Truite arc-en-ciel", "Saumon atlantique", "Crevettes cuites", "Tofu ferme",
    "Lentilles seches", "Pois chiches en conserve", "Haricots noirs en conserve",
})

LEGUMES_TACO: frozenset[str] = frozenset({
    "Epinards", "Carottes", "Poivron rouge", "Oignon", "Tomate fraiche",
    "Tomates concassees en conserve", "Patate douce", "Champignons blancs",
    "Pois verts surgeles", "Chou-fleur", "Brocoli", "Courgette", "Aubergine",
    "Haricots verts", "Asperges", "Celeri",
})

LIANTS_TACO: frozenset[str] = frozenset({
    "Fromage cheddar", "Mozzarella", "Parmesan", "Gouda", "Gruyere", "Emmental",
    "Provolone", "Houmous", "Tomates concassees en conserve", "Tahini (sesame)",
})

BASES_CREAMI: frozenset[str] = frozenset({
    "Kefir", "Yogourt grec nature 0%", "Fromage blanc", "Lait 2%", "Lait entier",
    "Lait ecreme", "Lait d'amande non sucre", "Boisson de soja", "Boisson d'avoine",
})

FRUITS_CREAMI: frozenset[str] = frozenset({
    "Banane", "Fraises", "Bleuets frais", "Framboises", "Mangue", "Ananas",
    "Peche", "Cerises", "Poire", "Pomme", "Orange", "Clementines", "Kiwi",
    "Prunes", "Grenade", "Raisins", "Dattes Medjool", "Pruneaux",
})

PROTEINE_POUDRE = "Proteine en poudre"
CREATINE = "Creatine monohydrate"


@dataclass
class BlocPlan:
    """Résultat d'un bloc : quantités par portion et apports quotidiens."""

    nom: str
    portions_par_jour: int
    #: {aliment: grammes par portion}
    ingredients: dict[str, float] = field(default_factory=dict)
    cout_par_jour: float = 0.0

    def grammes_par_jour(self) -> dict[str, float]:
        return {k: v * self.portions_par_jour for k, v in self.ingredients.items()}


@dataclass
class JourneeOptimisee:
    taco: BlocPlan
    creami: BlocPlan
    frais: BlocPlan
    metrics: dict[str, Any] = field(default_factory=dict)
    warning: str = ""


#: Réservés au pot CREAMi. Sans cette exclusivité, l'optimiseur verse la poudre
#: de protéine dans la garniture du taco — nutritionnellement équivalent pour
#: lui, mais ce n'est pas une recette que l'on cuisine.
EXCLUSIFS_CREAMI: frozenset[str] = frozenset({PROTEINE_POUDRE, CREATINE})

#: Ingrédients de préparation, jamais consommés tels quels. Ils figurent au
#: catalogue pour chiffrer les tortillas maison ; laissés libres, l'optimiseur en
#: met 113 g dans la garniture parce que ce sont les calories les moins chères.
MATIERES_PREMIERES_EXCLUES: frozenset[str] = frozenset({
    "Farine tout usage", "Masa harina", "Sel marin",
})

#: Aliments écartés du taco pour raison culinaire, pas nutritionnelle : des pâtes
#: dans une tortilla ne se mangent pas. Le riz reste admis (burrito bowl).
HORS_TACO: frozenset[str] = frozenset({"Pates (sec)", "Flocons d'avoine"})

#: Grammages minimaux d'une portion réelle, par famille imposée. Sans eux,
#: l'optimiseur satisfait la structure au grammage plancher du catalogue (5 g) :
#: un pot « 61 g de poudre + 5 g de fraises + 5 g de lait » coche toutes les
#: cases et n'est pas un dessert. Ces minimums décrivent une portion mangeable,
#: ils ne visent aucune cible nutritionnelle.
MIN_PORTION_G: dict[str, float] = {
    "base_creami": 150.0,
    "fruit_creami": 100.0,
    "proteine_poudre": 25.0,
    "legume_taco": 30.0,
    "proteine_taco": 40.0,
    "liant_taco": 15.0,
}

#: Plafond de poudre de protéine par pot : au-delà d'une dose, c'est cher et la
#: texture devient farineuse. L'optimiseur y allait sinon à 61 g (deux doses).
MAX_PROTEINE_POUDRE_G = 40.0


def _bloc_autorise(df: pd.DataFrame, bloc: str) -> list[str]:
    """Aliments admissibles dans un bloc, selon les propriétés du catalogue."""
    if bloc == "taco":
        col = "Congelable"
    elif bloc == "creami":
        col = "CreamiOk"
    else:
        col = None
    if col is None:
        noms = list(df.index)
    elif col not in df.columns:
        # Propriété absente : on n'invente pas d'admissibilité, le bloc est vide
        # et l'appelant verra un avertissement plutôt qu'une recette fantaisiste.
        return []
    else:
        noms = [n for n in df.index if float(df.at[n, col] or 0) >= 1.0]
    if bloc != "creami":
        noms = [n for n in noms if n not in EXCLUSIFS_CREAMI]
    if bloc == "taco":
        noms = [n for n in noms if n not in HORS_TACO]
    return [n for n in noms if n not in MATIERES_PREMIERES_EXCLUES]


def _densite_par_dollar(df: pd.DataFrame, nom: str, targets: dict[str, float]) -> float:
    """Couverture apportée par dollar, pour départager les candidats d'une famille.

    Somme, sur les nutriments visés, de la part de cible couverte par 100 g
    (plafonnée à 1 pour ne pas récompenser un excès), divisée par le prix.
    """
    prix = float(df.at[nom, "Prix"] or 0)
    if prix <= 0:
        return 0.0
    total = 0.0
    for cle, valeur in targets.items():
        col = _CIBLE_VERS_COLONNE.get(cle, cle)
        if col not in df.columns:
            continue
        try:
            cible = float(valeur)
            apport = float(df.at[nom, col])
        except (TypeError, ValueError):
            continue
        if cible > 0:
            total += min(apport / cible, 1.0)
    return total / prix


def construire_df_multibloc(
    df: pd.DataFrame,
    imposes: Optional[dict[str, dict[str, float]]] = None,
    targets: Optional[dict[str, float]] = None,
    max_par_bloc: Optional[int] = None,
) -> pd.DataFrame:
    """DataFrame élargi : une ligne par (bloc, aliment), apports × portions.

    `imposes` retire des aliments du problème (ils sont fixés en amont) pour
    qu'ils ne redeviennent pas des variables de décision. `max_par_bloc` borne
    le nombre de candidats par bloc (cf. `MAX_CANDIDATS_PAR_BLOC`) ; il exige
    `targets` pour classer les aliments par couverture/dollar.
    """
    imposes = imposes or {}
    lignes = []
    index = []
    for bloc, portions in (("taco", TACOS_PAR_JOUR),
                           ("creami", CREAMI_PAR_JOUR),
                           ("frais", 1)):
        fixes = imposes.get(bloc, {})
        candidats = [n for n in _bloc_autorise(df, bloc) if n not in fixes]
        # La structure impose EXACTEMENT une tortilla : celle qui est fixée. Les
        # autres doivent disparaître du bloc, sinon l'optimiseur en ajoute une
        # seconde (nutritionnellement neutre pour lui, mais deux tortillas ne
        # font pas un taco).
        if bloc == "taco" and any(t in fixes for t in TORTILLAS):
            candidats = [n for n in candidats if n not in TORTILLAS]
        if max_par_bloc and targets and len(candidats) > max_par_bloc:
            candidats = sorted(
                candidats,
                key=lambda n: -_densite_par_dollar(df, n, targets),
            )[:max_par_bloc]
        for nom in candidats:
            ligne = df.loc[nom].copy()
            # Les apports et le prix sont exprimés PAR JOUR : la variable reste
            # donc « grammes par portion », ce qui est la forme d'une recette.
            for col in ligne.index:
                if col in ("MinQty", "MaxQty"):
                    continue
                try:
                    ligne[col] = float(ligne[col]) * portions
                except (TypeError, ValueError):
                    pass
            if bloc == "creami" and nom == PROTEINE_POUDRE:
                ligne["MaxQty"] = MAX_PROTEINE_POUDRE_G
            lignes.append(ligne)
            index.append(f"{bloc}{_SEP}{nom}")
    if not lignes:
        return df.iloc[0:0].copy()
    out = pd.DataFrame(lignes)
    out.index = index
    return out


def _apport_impose(df: pd.DataFrame, imposes: dict[str, dict[str, float]]) -> dict[str, float]:
    """Apports totaux (par jour) des ingrédients fixés hors optimisation."""
    total: dict[str, float] = {}
    portions = {"taco": TACOS_PAR_JOUR, "creami": CREAMI_PAR_JOUR, "frais": 1}
    for bloc, fixes in imposes.items():
        for nom, grammes in fixes.items():
            if nom not in df.index:
                continue
            facteur = grammes / 100.0 * portions.get(bloc, 1)
            for col in df.columns:
                try:
                    total[col] = total.get(col, 0.0) + float(df.at[nom, col]) * facteur
                except (TypeError, ValueError):
                    continue
    return total


#: Cibles diminuées des apports imposés. Clé de `targets` -> colonne du catalogue.
_CIBLE_VERS_COLONNE = {
    "Calories": "Energie", "Protéines": "Proteines",
    "Lipides": "Lipides", "Glucides": "Glucides",
}


def _cibles_residuelles(targets: dict[str, float],
                        apport: dict[str, float]) -> dict[str, float]:
    """Retranche les apports imposés des cibles, sans jamais passer sous zéro."""
    out = dict(targets)
    for cle, col in _CIBLE_VERS_COLONNE.items():
        if cle in out and col in apport:
            out[cle] = max(0.0, float(out[cle]) - apport[col])
    for cle, valeur in out.items():
        if cle in _CIBLE_VERS_COLONNE or cle in ("Poids_Corps", "Prix_Max"):
            continue
        if isinstance(valeur, (int, float)) and cle in apport:
            out[cle] = max(0.0, float(valeur) - apport[cle])
    return out


def _decomposer(plan: list[dict], imposes: dict[str, dict[str, float]]) -> dict[str, BlocPlan]:
    portions = {"taco": TACOS_PAR_JOUR, "creami": CREAMI_PAR_JOUR, "frais": 1}
    blocs = {nom: BlocPlan(nom=nom, portions_par_jour=portions[nom])
             for nom in ("taco", "creami", "frais")}
    for nom, fixes in imposes.items():
        for aliment, grammes in fixes.items():
            blocs[nom].ingredients[aliment] = grammes
    for item in plan:
        cle = str(item.get("Aliment", ""))
        if _SEP not in cle:
            continue
        bloc, aliment = cle.split(_SEP, 1)
        if bloc not in blocs:
            continue
        grammes = float(str(item.get("Quantité", 0)).replace("g", "").strip() or 0)
        if grammes <= 0:
            continue
        blocs[bloc].ingredients[aliment] = grammes
        blocs[bloc].cout_par_jour += float(item.get("Prix", 0) or 0)
    return blocs


#: Base imposée, sous forme exploitable : (bloc, famille, nombre requis, libellé).
EXIGENCES: tuple[tuple[str, frozenset[str], int, str, str], ...] = (
    ("taco", frozenset(PROTEINES_TACO), 1, "une source protéique", "proteine_taco"),
    ("taco", frozenset(LEGUMES_TACO), 2, "au moins deux légumes", "legume_taco"),
    ("taco", frozenset(LIANTS_TACO), 1, "un liant", "liant_taco"),
    ("creami", frozenset(BASES_CREAMI), 1, "une base liquide", "base_creami"),
    ("creami", frozenset(FRUITS_CREAMI), 1, "un fruit", "fruit_creami"),
    ("creami", frozenset({PROTEINE_POUDRE}), 1, "de la protéine en poudre",
     "proteine_poudre"),
)


def structure_respectee(blocs: dict[str, BlocPlan]) -> list[str]:
    """Manquements à la base imposée, en clair. Liste vide = structure conforme."""
    manques: list[str] = []
    if len(set(blocs["taco"].ingredients) & set(TORTILLAS)) != 1:
        manques.append("le taco doit contenir exactement une tortilla")
    # Une famille n'est satisfaite qu'à partir d'une portion mangeable : 5 g de
    # fraises « cochent » le fruit sans faire un dessert.
    for bloc, famille, requis, libelle, cle_min in EXIGENCES:
        seuil = MIN_PORTION_G.get(cle_min, 0.0)
        presents = [n for n, g in blocs[bloc].ingredients.items()
                    if n in famille and g >= seuil]
        if len(presents) < requis:
            quoi = "le taco" if bloc == "taco" else "le pot CREAMi"
            manques.append(f"{quoi} doit contenir {libelle}")
    if CREATINE not in blocs["creami"].ingredients:
        manques.append("le pot CREAMi doit contenir de la créatine")
    return manques


def optimiser_journee(
    df: pd.DataFrame,
    targets: dict[str, float],
    budget_max_daily: Optional[float] = None,
    seed: Optional[int] = None,
    tortilla: Optional[str] = None,
    price_weights: tuple[float, ...] = PRICE_WEIGHTS_BATCH,
) -> JourneeOptimisee:
    """Optimise en une passe les 2 tacos, le pot CREAMi et le complément frais.

    `tortilla` fixe la tortilla du taco ; None essaie les deux et garde la
    meilleure (le choix est structurel, donc combinatoire : SLSQP ne peut pas
    l'arbitrer, on énumère).
    """
    if tortilla is None:
        candidates = [t for t in TORTILLAS if t in df.index]
        if not candidates:
            return JourneeOptimisee(
                taco=BlocPlan("taco", TACOS_PAR_JOUR),
                creami=BlocPlan("creami", CREAMI_PAR_JOUR),
                frais=BlocPlan("frais", 1),
                warning="aucune tortilla au catalogue — recette impossible",
            )
        meilleur: JourneeOptimisee | None = None
        for cand in candidates:
            essai = optimiser_journee(df, targets, budget_max_daily, seed,
                                      tortilla=cand, price_weights=price_weights)
            if essai.metrics.get("ratio", 0) > (meilleur.metrics.get("ratio", 0)
                                                if meilleur else -1):
                meilleur = essai
        return meilleur  # type: ignore[return-value]

    # Ingrédients retirés du problème et fixés : la tortilla (une par taco, à sa
    # quantité d'achat minimale) et la créatine (dose journalière).
    imposes: dict[str, dict[str, float]] = {"taco": {}, "creami": {}, "frais": {}}
    if tortilla in df.index:
        mini = float(df.at[tortilla, "MinQty"] or 0) or 30.0
        imposes["taco"][tortilla] = mini
    if CREATINE in df.index:
        imposes["creami"][CREATINE] = CREATINE_G_PAR_JOUR

    # La base imposée est combinatoire : SLSQP ne sait pas « au moins deux
    # légumes ». Elle est donc décidée AVANT l'optimisation, en choisissant le
    # meilleur représentant de chaque famille, puis les grammages de tout le
    # reste sont optimisés conjointement en UNE passe. Les blocs restent donc
    # arbitrés ensemble : c'est la composition qui est fixée, pas la répartition
    # des apports — le principe « aucun surplus de macros » tient.
    #
    # Une version antérieure imposait les familles manquantes de façon
    # itérative, en relançant après chaque ajout. Elle empilait les quantités
    # figées (708 puis 847 kcal) jusqu'à rendre les contraintes dures
    # incompatibles : plus on imposait, moins l'optimiseur avait de marge.
    _completer_structure(df, targets, imposes)
    resultat = _resoudre(df, targets, budget_max_daily, seed, imposes, tortilla,
                         price_weights)
    if not resultat.metrics:
        # Structure infaisable dans le budget : on retente sans les imposés du
        # taco (les plus lourds), plutôt que de ne rien rendre du tout.
        allege = {"taco": {k: v for k, v in imposes["taco"].items()
                           if k in TORTILLAS},
                  "creami": imposes["creami"], "frais": {}}
        resultat = _resoudre(df, targets, budget_max_daily, seed, allege, tortilla,
                             price_weights)
    return resultat


def _completer_structure(
    df: pd.DataFrame,
    targets: dict[str, float],
    imposes: dict[str, dict[str, float]],
) -> None:
    """Choisit d'emblée un représentant par famille de la base imposée.

    Critère : la meilleure couverture par dollar dans la famille — le même
    esprit que l'objectif global, appliqué à un choix que SLSQP ne peut pas
    faire lui-même (il optimise des quantités, pas une combinatoire).
    """
    for bloc, famille, requis, _libelle, cle_min in EXIGENCES:
        deja = {k for k in imposes[bloc] if k in famille}
        manquants = requis - len(deja)
        if manquants <= 0:
            continue
        dispo = [n for n in famille
                 if n in df.index and n in _bloc_autorise(df, bloc)
                 and n not in imposes[bloc]]
        if not dispo:
            continue
        portion = MIN_PORTION_G.get(cle_min, 20.0)
        for nom in sorted(dispo,
                          key=lambda n: -_densite_par_dollar(df, n, targets))[:manquants]:
            imposes[bloc][nom] = max(portion, float(df.at[nom, "MinQty"] or 0))


def _resoudre(
    df: pd.DataFrame,
    targets: dict[str, float],
    budget_max_daily: Optional[float],
    seed: Optional[int],
    imposes: dict[str, dict[str, float]],
    tortilla: str,
    price_weights: tuple[float, ...] = PRICE_WEIGHTS_BATCH,
) -> "JourneeOptimisee":
    """Une passe d'optimisation conjointe, à structure imposée donnée."""
    apport = _apport_impose(df, imposes)
    residuelles = _cibles_residuelles(targets, apport)

    elargi = construire_df_multibloc(df, imposes, targets, MAX_CANDIDATS_PAR_BLOC)
    if elargi.empty:
        return JourneeOptimisee(
            taco=BlocPlan("taco", TACOS_PAR_JOUR),
            creami=BlocPlan("creami", CREAMI_PAR_JOUR),
            frais=BlocPlan("frais", 1),
            warning="catalogue sans aliment congelable ou compatible CREAMi",
        )

    cout_impose = float(apport.get("Prix", 0.0))
    budget = None if budget_max_daily is None else max(0.0, budget_max_daily - cout_impose)
    plan, warning, metrics = optimize_ratio(
        elargi, residuelles, budget_max_daily=budget, seed=seed,
        price_weights=price_weights,
    )
    if plan is None:
        return JourneeOptimisee(
            taco=BlocPlan("taco", TACOS_PAR_JOUR),
            creami=BlocPlan("creami", CREAMI_PAR_JOUR),
            frais=BlocPlan("frais", 1),
            warning=warning or "optimisation impossible",
        )

    blocs = _decomposer(plan, imposes)
    blocs["taco"].cout_par_jour += cout_impose
    metrics = dict(metrics)
    metrics["cout_total"] = float(metrics.get("cout_total", 0.0)) + cout_impose
    metrics["ratio"] = (metrics.get("couverture_moyenne", 0.0)
                        / metrics["cout_total"]) if metrics["cout_total"] else 0.0
    metrics["tortilla"] = tortilla
    metrics["structure_manquante"] = structure_respectee(blocs)
    return JourneeOptimisee(
        taco=blocs["taco"], creami=blocs["creami"], frais=blocs["frais"],
        metrics=metrics, warning=warning,
    )
