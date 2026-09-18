"""Ajoute au module Cuisine les recettes de laits végétaux maison.

Idempotent : une recette portant déjà le même titre est mise à jour, pas dupliquée.

Ces recettes sont la contrepartie concrète des aliments `Lait d'avoine maison` et
`Lait d'amande maison` du catalogue nutrition : ce sont elles qui justifient leur
prix de revient (90 g de matière première par litre au lieu du produit fini).

Usage :
    python -m scripts.seed_recettes_laits_vegetaux [--dry-run]
"""
from __future__ import annotations

import sys

from sqlmodel import Session, select

from app.core.db import engine
from app.models.cuisine import Recipe, RecipeIngredient

# Rendement : 1 L. Les quantités sont celles utilisées pour établir le prix de
# revient dans `enrich_catalogue_batch_cooking.py` — les garder synchronisées.
RECETTES: list[dict] = [
    {
        "titre": "Lait d'avoine maison",
        "portions": 4,          # 1 L ≈ 4 verres
        "temps_prep": 10,
        "temps_cuisson": 0,
        "ingredients": [
            ("Flocons d'avoine", 90, "g"),
            ("Eau froide", 1000, "ml"),
            ("Sel", 1, "pincée"),
        ],
        "instructions": (
            "1. Mixer 90 g de flocons d'avoine avec 1 L d'eau FROIDE pendant "
            "30 secondes, pas plus.\n"
            "2. Filtrer à travers un sac à lait végétal ou un torchon fin. Ne pas "
            "presser le résidu : c'est ce qui rend le lait gluant.\n"
            "3. Ajouter une pincée de sel. Se conserve 4 à 5 jours au frais ; "
            "secouer avant usage, la séparation est normale.\n\n"
            "Deux règles expliquent presque tous les échecs : l'eau doit être "
            "froide et le mixage court. L'eau tiède et le mixage prolongé "
            "libèrent l'amidon de l'avoine, qui donne une texture visqueuse.\n\n"
            "Ne pas congeler tel quel (le lait se sépare) — en revanche il est "
            "excellent en base de préparation Ninja CREAMi.\n\n"
            "ÉCONOMIE : plus faible qu'il n'y paraît. 90 g de flocons ne "
            "contiennent que 330 kcal, quand un litre de boisson d'avoine du "
            "commerce en affiche ~426 : l'industrie hydrolyse l'amidon et ajoute "
            "de l'huile, ce qu'un filtrage maison ne reproduit pas. À apport "
            "équivalent, l'arbitrage tombe à ~10 $/h de travail — sous le seuil "
            "de 20 $/h. Le module `preparations.py` recalcule ce verdict à chaque "
            "génération, en suivant les promotions.\n\n"
            "Le résidu (okara) se garde pour des flocons cuits ou une galette."
        ),
    },
    {
        "titre": "Lait d'amande maison",
        "portions": 4,
        "temps_prep": 15,       # hors trempage
        "temps_cuisson": 0,
        "ingredients": [
            ("Amandes", 90, "g"),
            ("Eau froide", 1000, "ml"),
            ("Sel", 1, "pincée"),
        ],
        "instructions": (
            "1. Faire tremper 90 g d'amandes 8 h (ou une nuit) dans l'eau froide, "
            "puis les rincer.\n"
            "2. Mixer avec 1 L d'eau froide pendant 1 à 2 minutes.\n"
            "3. Filtrer au sac à lait végétal en pressant bien — ici, contrairement "
            "à l'avoine, presser le résidu est souhaitable.\n"
            "4. Ajouter une pincée de sel. Se conserve 3 à 4 jours au frais.\n\n"
            "Ne pas congeler tel quel ; parfait en base Ninja CREAMi.\n\n"
            "ÉCONOMIE : nulle, voire négative. Le lait d'amande du commerce ne "
            "contient que ~2 % d'amandes et coûte peu ; 90 g d'amandes par litre "
            "reviennent, à apport équivalent, au même prix — pour ~16 min de "
            "travail. Acheter est le bon choix, sauf si tu veux un lait bien plus "
            "riche que le commercial.\n\n"
            "L'okara d'amande sèche au four et remplace une partie de la farine "
            "d'amande."
        ),
    },
]


def main(dry_run: bool = False) -> int:
    with Session(engine) as session:
        for spec in RECETTES:
            existante = session.exec(
                select(Recipe).where(Recipe.titre == spec["titre"])
            ).first()
            action = "mise à jour" if existante else "créée"
            recipe = existante or Recipe(titre=str(spec["titre"]))
            recipe.portions = int(spec["portions"])
            recipe.temps_prep = int(spec["temps_prep"])
            recipe.temps_cuisson = int(spec["temps_cuisson"])
            recipe.instructions = str(spec["instructions"])

            if dry_run:
                print(f"{spec['titre']} : {action} (dry-run)")
                continue

            session.add(recipe)
            session.commit()
            session.refresh(recipe)

            # Ingrédients réécrits intégralement : évite les doublons en cas de
            # relance après modification des quantités.
            for ancien in session.exec(
                select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)
            ).all():
                session.delete(ancien)
            for nom, qte, unite in spec["ingredients"]:  # type: ignore[misc]
                session.add(RecipeIngredient(
                    recipe_id=int(recipe.id), nom_libre=nom,
                    quantite=float(qte), unite=unite,
                ))
            session.commit()
            print(f"{spec['titre']} : {action} (#{recipe.id}, "
                  f"{len(spec['ingredients'])} ingrédients)")  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    raise SystemExit(main(dry_run="--dry-run" in sys.argv))
