"""Enrichit `aliments.csv` pour le batch cooking : aliments et propriétés d'usage.

Idempotent : relancer le script ne duplique ni colonne ni ligne.

Deux propriétés répondent à deux questions **opposées** sur la congélation :

- `Congelable` — l'aliment garde-t-il une qualité acceptable après congélation
  puis décongélation ou réchauffage ? Sert aux plats cuisinés (tacos).
- `CreamiOk` — l'aliment donne-t-il un bon résultat en Ninja CREAMi, où il est
  congelé en bloc puis barraté ? Ici la destruction de la texture par les
  cristaux de glace n'est pas un défaut : elle est **recherchée**. Beaucoup
  d'aliments à `Congelable=0` (fruits crus, laitages) sont donc à `CreamiOk=1`.

Aliments ajoutés : les deux tortillas, et les laits végétaux maison — dérivés du
profil de leur équivalent commercial du catalogue, avec le prix de revient réel
des ingrédients (voir `DERIVES`).

Usage :
    python -m scripts.enrich_catalogue_batch_cooking [--dry-run]
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services.backup_storage import backup_file  # noqa: E402

CSV_PATH = REPO / "data" / "imports" / "Sante" / "tableur" / "aliments.csv"

# Passent à 0 — tout le reste du catalogue est congelable.
#
# Trois familles seulement, et pour une raison de texture à chaque fois :
#   - crus gorgés d'eau : les cristaux de glace éclatent les cellules, l'aliment
#     rend son eau et devient mou à la décongélation ;
#   - laitages frais et fromages à pâte molle : l'émulsion se sépare (grainage) ;
#   - fruits destinés à être mangés crus : même problème que les crus aqueux.
#
# Ne sont PAS dans cette liste, volontairement : les petits fruits, la mangue et
# l'ananas (vendus couramment surgelés, parfaits en cuisson), les fruits séchés,
# le beurre, les fromages à pâte dure, les viandes, poissons, légumineuses et
# céréales — tous se congèlent sans dommage.
NON_CONGELABLE: set[str] = {
    # Crus gorgés d'eau
    "Concombre", "Celeri", "Tomate fraiche", "Roquette", "Avocat", "Olives noires",
    # Laitages frais
    "Yogourt grec nature 0%", "Lait 2%", "Lait entier", "Lait ecreme", "Kefir",
    "Fromage blanc", "Lait d'amande non sucre", "Boisson de soja", "Boisson d'avoine",
    "Lait d'avoine maison", "Lait d'amande maison",
    # Fromages à pâte molle
    "Brie", "Camembert", "Fromage de chevre", "Feta",
    # Fruits mangés crus
    "Banane", "Orange", "Pomme", "Raisins", "Fraises", "Kiwi", "Clementines",
    "Poire", "Peche", "Cerises", "Pamplemousse", "Prunes",
}

# Valeurs pour 100 g. Sources et réserves documentées dans README_aliments.md :
# ces deux entrées ne viennent PAS de CIQUAL (aucune entrée fidèle) mais des
# étiquettes des tortillas commerciales vendues au Québec ; le prix n'a pas pu
# être matché automatiquement sur Super C (le scrape ne remonte que des
# croustilles) — il est estimé et marqué « à vérifier ».
TORTILLAS: dict[str, dict[str, float]] = {
    "Tortilla de mais": {
        "Prix": 0.80, "Proteines": 5.7, "Amidon": 42.0, "Fibres": 6.3,
        "Glucose": 0.2, "Fructose": 0.2, "Galactose": 0.0, "Saccharose": 0.5,
        "Lactose": 0.0, "AG satures": 0.4, "AG monoinsatures": 0.77,
        "Omega 6": 1.25, "Omega 3": 0.05, "Lipides": 2.85, "Glucides": 44.6,
        "Energie": 218, "Sodium": 45, "Magnesium": 72, "VitA": 0,
        "VitB1": 0.094, "VitB2": 0.065, "VitB3": 1.25, "VitB5": 0.3,
        "VitB6": 0.2, "VitB9": 5, "VitB12": 0, "VitC": 0, "VitD": 0,
        "VitE": 0.3, "VitK": 0.3, "Calcium": 81, "Chlorure": 0, "Cuivre": 0.15,
        "Fer": 1.23, "Iode": 0, "Manganese": 0.4, "Phosphore": 195,
        "Potassium": 186, "Selenium": 4.5, "Zinc": 1.0, "Cholesterol": 0,
        "Polyols": 0,
        # Une tortilla de maïs pèse ~30 g : c'est l'unité indivisible.
        "MinQty": 30, "MaxQty": 120,
    },
    "Tortilla de ble": {
        "Prix": 0.78, "Proteines": 8.2, "Amidon": 46.0, "Fibres": 3.1,
        "Glucose": 0.3, "Fructose": 0.2, "Galactose": 0.0, "Saccharose": 2.2,
        "Lactose": 0.0, "AG satures": 1.9, "AG monoinsatures": 3.3,
        "Omega 6": 2.0, "Omega 3": 0.1, "Lipides": 7.5, "Glucides": 51.4,
        "Energie": 306, "Sodium": 640, "Magnesium": 21, "VitA": 0,
        "VitB1": 0.40, "VitB2": 0.25, "VitB3": 3.4, "VitB5": 0.4,
        "VitB6": 0.04, "VitB9": 96, "VitB12": 0, "VitC": 0, "VitD": 0,
        "VitE": 0.5, "VitK": 0.5, "Calcium": 128, "Chlorure": 0, "Cuivre": 0.1,
        "Fer": 3.2, "Iode": 0, "Manganese": 0.5, "Phosphore": 250,
        "Potassium": 130, "Selenium": 20, "Zinc": 0.6, "Cholesterol": 0,
        "Polyols": 0,
        # Une tortilla de blé (format taco) pèse ~45 g.
        "MinQty": 45, "MaxQty": 180,
    },
}

CONGELABLE_ROW = "Congelable"
CREAMI_ROW = "CreamiOk"

# Bons en Ninja CREAMi. Le critère n'est PAS celui de `Congelable` : la machine
# rabote un bloc congelé, donc l'éclatement des cellules par le gel est sans
# importance — c'est même lui qui donne le crémeux. Le vrai critère est la
# présence d'eau et de sucres/gras qui cristallisent finement.
#
# Retenus : fruits, laitages, boissons végétales, avoine, noix et beurres de
# noix, chocolat, sucrants. Exclus : viandes, poissons, légumes salés, huiles
# pures, fromages affinés — rien à en tirer en dessert glacé.
CREAMI_OK: set[str] = {
    # Fruits
    "Banane", "Avocat", "Orange", "Pomme", "Raisins", "Bleuets frais", "Fraises",
    "Dattes Medjool", "Canneberges sechees", "Pruneaux", "Ananas", "Kiwi",
    "Framboises", "Clementines", "Poire", "Peche", "Cerises", "Mangue",
    "Grenade", "Pamplemousse", "Prunes",
    # Laitages
    "Yogourt grec nature 0%", "Lait 2%", "Lait entier", "Lait ecreme", "Kefir",
    "Fromage blanc",
    # Boissons végétales (commerciales et maison)
    "Lait d'amande non sucre", "Boisson de soja", "Boisson d'avoine",
    "Lait d'avoine maison", "Lait d'amande maison",
    # Base céréalière, noix et beurres de noix
    "Flocons d'avoine", "Beurre d'arachide", "Beurre d'amande", "Farine d'amande",
    "Tahini (sesame)", "Amandes", "Noix de cajou", "Noix de Grenoble", "Pacanes",
    "Pistaches", "Arachides", "Noix de macadamia", "Graines de chia",
    # Sucrants et chocolat
    "Chocolat noir 72%", "Miel", "Sirop d'erable",
    # Suppléments incorporés au pot (poudres stables, aucune texture à préserver)
    "Creatine monohydrate", "Proteine en poudre",
}

# Les préparations maison (laits végétaux, tortillas) ne sont PLUS des colonnes
# du CSV : leur profil et leur coût sont calculés depuis leurs ingrédients par
# `app/services/sante/preparations.py`, ce qui les fait suivre les promotions et
# évite l'erreur consistant à leur prêter le profil du produit commercial.
# Ce script ne fournit donc que les MATIÈRES PREMIÈRES qui leur manquaient.
DERIVES: dict[str, dict[str, object]] = {}

# Farine tout usage et masa harina : absentes du catalogue, indispensables pour
# chiffrer les tortillas maison. Valeurs pour 100 g.
#
# La farine vendue au Canada est enrichie par obligation réglementaire (fer,
# thiamine, riboflavine, niacine, acide folique) — d'où des micros élevés pour
# un produit raffiné. La masa harina est nixtamalisée : le traitement à la chaux
# explique ses 141 mg de calcium.
#
# Prix : estimations marché (~2,79 $/2,5 kg pour la farine, ~4 $/1,6 kg pour la
# masa), NON matchés Super C — même réserve que les tortillas.
MATIERES_PREMIERES: dict[str, dict[str, float]] = {
    "Farine tout usage": {
        "Prix": 0.11, "Proteines": 10.3, "Amidon": 70.0, "Fibres": 2.7,
        "Glucose": 0.1, "Fructose": 0.1, "Galactose": 0.0, "Saccharose": 0.3,
        "Lactose": 0.0, "AG satures": 0.15, "AG monoinsatures": 0.09,
        "Omega 6": 0.41, "Omega 3": 0.02, "Lipides": 1.0, "Glucides": 76.3,
        "Energie": 364, "Sodium": 2, "Magnesium": 22, "VitA": 0,
        "VitB1": 0.44, "VitB2": 0.27, "VitB3": 3.5, "VitB5": 0.44,
        "VitB6": 0.04, "VitB9": 150, "VitB12": 0, "VitC": 0, "VitD": 0,
        "VitE": 0.06, "VitK": 0.3, "Calcium": 15, "Chlorure": 0, "Cuivre": 0.14,
        "Fer": 4.4, "Iode": 0, "Manganese": 0.68, "Phosphore": 108,
        "Potassium": 107, "Selenium": 33.9, "Zinc": 0.7, "Cholesterol": 0,
        "Polyols": 0, "MinQty": 100, "MaxQty": 0,
    },
    # ── Suppléments du pot CREAMi (décision utilisateur 2026-08-06) ──────────
    # La créatine est un composé pur : elle n'apporte ni macro ni micronutriment
    # du catalogue. L'optimiseur la mettrait donc TOUJOURS à zéro (coût sans
    # contrepartie nutritionnelle) — c'est la structure imposée du pot qui doit
    # la fixer à sa dose, pas la recherche du meilleur ratio. Elle figure ici
    # pour que son coût entre dans le budget et que la recette soit complète.
    #
    # Énergie : 0 kcal par convention. La créatine n'est pas un substrat
    # énergétique (elle est stockée en phosphocréatine puis excrétée en
    # créatinine) ; lui prêter les ~4 kcal/g d'un acide aminé fausserait la
    # cible calorique de la journée.
    "Creatine monohydrate": {
        "Prix": 6.0, "Proteines": 0.0, "Amidon": 0.0, "Fibres": 0.0,
        "Glucose": 0.0, "Fructose": 0.0, "Galactose": 0.0, "Saccharose": 0.0,
        "Lactose": 0.0, "AG satures": 0.0, "AG monoinsatures": 0.0,
        "Omega 6": 0.0, "Omega 3": 0.0, "Lipides": 0.0, "Glucides": 0.0,
        "Energie": 0, "Sodium": 0, "Magnesium": 0, "VitA": 0,
        "VitB1": 0, "VitB2": 0, "VitB3": 0, "VitB5": 0,
        "VitB6": 0, "VitB9": 0, "VitB12": 0, "VitC": 0, "VitD": 0,
        "VitE": 0, "VitK": 0, "Calcium": 0, "Chlorure": 0, "Cuivre": 0,
        "Fer": 0, "Iode": 0, "Manganese": 0, "Phosphore": 0,
        "Potassium": 0, "Selenium": 0, "Zinc": 0, "Cholesterol": 0,
        "Polyols": 0, "MinQty": 5, "MaxQty": 5,
    },
    # Isolat de lactosérum non aromatisé. Valeurs d'étiquette commerciale (pas
    # CIQUAL : aucune entrée fidèle aux isolats vendus ici), arrondies au profil
    # courant des marques distribuées au Québec.
    "Proteine en poudre": {
        "Prix": 5.0, "Proteines": 86.0, "Amidon": 0.0, "Fibres": 0.0,
        "Glucose": 0.0, "Fructose": 0.0, "Galactose": 0.0, "Saccharose": 0.0,
        "Lactose": 1.5, "AG satures": 0.6, "AG monoinsatures": 0.25,
        "Omega 6": 0.05, "Omega 3": 0.01, "Lipides": 1.0, "Glucides": 3.0,
        "Energie": 373, "Sodium": 250, "Magnesium": 50, "VitA": 0,
        "VitB1": 0.05, "VitB2": 1.2, "VitB3": 0.4, "VitB5": 1.5,
        "VitB6": 0.1, "VitB9": 10, "VitB12": 1.5, "VitC": 0, "VitD": 0,
        "VitE": 0.05, "VitK": 0, "Calcium": 550, "Chlorure": 180, "Cuivre": 0.02,
        "Fer": 0.5, "Iode": 25, "Manganese": 0.02, "Phosphore": 300,
        "Potassium": 400, "Selenium": 15, "Zinc": 1.5, "Cholesterol": 10,
        "Polyols": 0, "MinQty": 25, "MaxQty": 0,
    },
    "Masa harina": {
        "Prix": 0.25, "Proteines": 9.3, "Amidon": 66.0, "Fibres": 6.9,
        "Glucose": 0.3, "Fructose": 0.3, "Galactose": 0.0, "Saccharose": 0.6,
        "Lactose": 0.0, "AG satures": 0.55, "AG monoinsatures": 1.0,
        "Omega 6": 1.8, "Omega 3": 0.06, "Lipides": 3.9, "Glucides": 76.3,
        "Energie": 365, "Sodium": 5, "Magnesium": 110, "VitA": 0,
        "VitB1": 1.43, "VitB2": 0.79, "VitB3": 10.1, "VitB5": 0.7,
        "VitB6": 0.35, "VitB9": 220, "VitB12": 0, "VitC": 0, "VitD": 0,
        "VitE": 0.4, "VitK": 0.3, "Calcium": 141, "Chlorure": 0, "Cuivre": 0.2,
        "Fer": 7.6, "Iode": 0, "Manganese": 0.5, "Phosphore": 250,
        "Potassium": 314, "Selenium": 15.4, "Zinc": 2.0, "Cholesterol": 0,
        "Polyols": 0, "MinQty": 100, "MaxQty": 0,
    },
}

# Colonnes de préparations maison écrites par une version antérieure du script :
# retirées du CSV puisqu'elles sont désormais calculées.
OBSOLETES: tuple[str, ...] = ("Lait d'avoine maison", "Lait d'amande maison")


def _fmt(value: float) -> str:
    """Écrit les entiers sans décimale inutile, comme le reste du fichier."""
    if value == int(value):
        return str(int(value))
    return str(value)


def main(dry_run: bool = False) -> int:
    if not CSV_PATH.exists():
        print(f"Introuvable : {CSV_PATH}", file=sys.stderr)
        return 1

    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.reader(f, delimiter=";")]
    if not rows:
        print("CSV vide", file=sys.stderr)
        return 1

    header = rows[0]
    aliments = [a.strip() for a in header[1:]]

    # Garde-fou : une faute de frappe dans NON_CONGELABLE passerait sinon
    # silencieusement, laissant un aliment à 1 alors qu'il devrait être à 0.
    connus = set(aliments) | set(TORTILLAS) | set(MATIERES_PREMIERES)
    inconnus = sorted((NON_CONGELABLE | CREAMI_OK) - connus - set(OBSOLETES))
    if inconnus:
        print(f"Noms absents du catalogue : {inconnus}", file=sys.stderr)
        return 1

    # Retrait des colonnes obsolètes (préparations désormais calculées).
    retires = [n for n in OBSOLETES if n in aliments]
    if retires:
        indices = sorted((aliments.index(n) + 1 for n in retires), reverse=True)
        for i in indices:
            del header[i]
            for row in rows[1:]:
                if row and i < len(row):
                    del row[i]
        aliments = [a.strip() for a in header[1:]]

    nouveaux = [n for n in (*TORTILLAS, *MATIERES_PREMIERES) if n not in aliments]
    for nom in nouveaux:
        header.append(nom)

    props_existantes = {(r[0] or "").strip() for r in rows[1:] if r}

    for row in rows[1:]:
        if not row:
            continue
        prop = (row[0] or "").strip()
        # Aligne d'abord la longueur sur l'en-tête (lignes plus courtes tolérées).
        while len(row) < len(header) - len(nouveaux):
            row.append("0")
        for nom in nouveaux:
            source = TORTILLAS if nom in TORTILLAS else MATIERES_PREMIERES
            row.append(_fmt(source[nom].get(prop, 0)))

    def _upsert(nom_ligne: str, valeur) -> None:
        """Écrit (ou réécrit) une ligne de propriété pour tous les aliments."""
        if nom_ligne not in props_existantes:
            rows.append([nom_ligne, *(valeur(n.strip()) for n in header[1:])])
            return
        for row in rows[1:]:
            if row and (row[0] or "").strip() == nom_ligne:
                for i, nom in enumerate(header[1:], start=1):
                    v = valeur(nom.strip())
                    if i < len(row):
                        row[i] = v
                    else:
                        row.append(v)

    _upsert(CONGELABLE_ROW, lambda n: "0" if n in NON_CONGELABLE else "1")
    _upsert(CREAMI_ROW, lambda n: "1" if n in CREAMI_OK else "0")

    noms = [a.strip() for a in header[1:]]
    n_non = sum(1 for a in noms if a in NON_CONGELABLE)
    n_creami = sum(1 for a in noms if a in CREAMI_OK)
    # Le recoupement est l'information intéressante : ces aliments sont inutiles
    # en plat cuisiné congelé, mais parfaits en CREAMi.
    n_creami_seul = sum(1 for a in noms if a in CREAMI_OK and a in NON_CONGELABLE)
    print(f"Aliments : {len(noms)} (dont {len(nouveaux)} ajoutés : {nouveaux or '—'}"
          f"{f', {len(retires)} retirés : {retires}' if retires else ''})")
    print(f"Congelable : {len(noms) - n_non} à 1, {n_non} à 0")
    print(f"CreamiOk   : {n_creami} à 1 — dont {n_creami_seul} inutilisables en plat cuisiné")

    if dry_run:
        print("(dry-run : rien écrit)")
        return 0

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = backup_file(
        CSV_PATH,
        category="maintenance/enrich-catalogue-batch-cooking",
        filename=f"{CSV_PATH.name}.bak-pre-tortillas-{timestamp}",
    )
    print(f"Sauvegarde NAS : {backup}")

    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, delimiter=";", lineterminator="\n").writerows(rows)
    print(f"Écrit : {CSV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(dry_run="--dry-run" in sys.argv))
