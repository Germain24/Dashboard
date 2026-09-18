"""Construit le réservoir d'aliments Super C rattachés à CIQUAL.

    python scripts/build_reservoir.py [--min-confiance 0.35] [--dry-run]

Entrées :
  - data/imports/Cuisine/superc.json          prix courants (scraper)
  - data/imports/Cuisine/superc_flyer.json    circulaire
  - data/imports/Cuisine/superc_sitemap.json  rayon par UPC (facultatif)
  - data/imports/Sante/ciqual/ciqual_normalise.csv   teneurs (scripts/import_ciqual.py)

Sorties :
  - data/imports/Sante/tableur/reservoir_superc.csv     le réservoir
  - data/imports/Sante/tableur/reservoir_rapport.txt    rattachements à revoir

Le réservoir n'écrase JAMAIS `aliments.csv` : c'est un second catalogue, que
`load_aliments_dataframe(include_reservoir=True)` concatène derrière le
catalogue curé, lequel garde la priorité en cas d'homonymie. Même contrat que
`rebuild_superc_catalog.py` : on produit, l'utilisateur revoit.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.services.cuisine.store_categories import est_alimentaire  # noqa: E402
from app.services.sante.aliments import load_aliments_from_csv  # noqa: E402
from app.services.sante.ciqual_matching import MIN_CONFIDENCE, CiqualIndex  # noqa: E402
from app.services.sante.reservoir import (  # noqa: E402
    DEFAULT_CIQUAL_CANDIDATES,
    DEFAULT_MAX_SQUARED_DISTANCE,
    PROVENANCE_COLUMNS,
    build_reservoir,
)

RAPPORT_LIGNES = 60


def _cuisine(name: str) -> Path:
    return settings.imports_dir / "Cuisine" / name


def _tableur(name: str) -> Path:
    return settings.imports_dir / "Sante" / "tableur" / name


def _load_json_items(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("items", [])
    except Exception as exc:
        print(f"  cache illisible {path.name} ({exc})", file=sys.stderr)
        return []


def _load_ciqual() -> tuple[list[dict], dict[str, dict[str, float]]]:
    path = settings.imports_dir / "Sante" / "ciqual" / "ciqual_normalise.csv"
    if not path.exists():
        raise SystemExit(
            f"CIQUAL normalisé introuvable : {path}\n"
            "Lancer d'abord : python scripts/import_ciqual.py"
        )
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    teneurs: dict[str, dict[str, float]] = {}
    for row in rows:
        code = row["CiqualCode"]
        teneurs[code] = {
            key: float(value)
            for key, value in row.items()
            if key not in {"CiqualCode", "CiqualNom", "CiqualGroupe", "CiqualSousGroupe"}
            and value not in ("", None)
        }
    return rows, teneurs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-confiance", type=float, default=0.75,
                        help="seuil du réservoir d'optimisation (défaut: 0.75)")
    parser.add_argument(
        "--candidats-par-ciqual", type=int, default=DEFAULT_CIQUAL_CANDIDATES,
        help="nombre de produits les plus proches comparés sur le prix (défaut: 10)",
    )
    parser.add_argument(
        "--distance-max-quadratique", type=float,
        default=DEFAULT_MAX_SQUARED_DISTANCE,
        help="distance (1-confiance)² maximale (défaut: 0.0625)",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="n'écrit rien, affiche seulement le bilan")
    args = parser.parse_args()

    ciqual_rows, teneurs = _load_ciqual()
    index = CiqualIndex(ciqual_rows)
    print(f"CIQUAL : {len(index)} aliments indexés")

    produits = [*_load_json_items(_cuisine("superc.json")),
                *_load_json_items(_cuisine("superc_flyer.json"))]
    # Un même UPC peut figurer dans le cache courant ET la circulaire : on garde
    # le MOINS cher, comme partout ailleurs dans le pipeline prix.
    par_upc: dict[str, dict] = {}
    for item in produits:
        cle = str(item.get("sku") or item.get("id") or item.get("name") or "")
        ancien = par_upc.get(cle)
        if ancien is None or (item.get("price") or 1e9) < (ancien.get("price") or 1e9):
            par_upc[cle] = item
    produits = [p for p in par_upc.values() if est_alimentaire(p)]
    print(f"Super C : {len(produits)} produits alimentaires chiffrables ou non")

    sitemap = _load_json_items(_cuisine("superc_sitemap.json"))
    rayons = {str(e.get("upc")): str(e.get("rayon") or "") for e in sitemap}
    # Le crawl par allée connaît directement le rayon. Il est plus frais et
    # plus complet que l'ancien sitemap, donc il gagne à UPC égal.
    rayons.update({
        str(e.get("sku") or e.get("id")): str(e.get("rayon") or "")
        for e in produits if e.get("sku") or e.get("id")
    })
    noms_sitemap = {str(e.get("upc")): str(e.get("nom") or "") for e in sitemap}
    print(f"Sitemap : {len(rayons)} produits (rayon + nom sans marque) connus par UPC")

    cures = set(load_aliments_from_csv())
    print(f"Catalogue curé : {len(cures)} aliments (toujours prioritaires)\n")

    lignes, stats = build_reservoir(
        produits, index, teneurs,
        rayon_par_upc=rayons, nom_sitemap_par_upc=noms_sitemap,
        min_confidence=args.min_confiance,
        ciqual_candidates=args.candidats_par_ciqual,
        max_squared_distance=args.distance_max_quadratique,
        exclure=frozenset(cures),
    )
    print(stats.resume())

    if not lignes:
        print("Aucun aliment retenu — rien à écrire.", file=sys.stderr)
        return 1

    teneur_cols = [c for c in lignes[0] if c not in ("Aliment", *PROVENANCE_COLUMNS)]
    header = ["Aliment", *teneur_cols, *PROVENANCE_COLUMNS]

    tranches = {">= 0,8": 0, "0,6 - 0,8": 0, "0,5 - 0,6": 0, "< 0,5": 0}
    for ligne in lignes:
        c = ligne["Confiance"]
        cle = ">= 0,8" if c >= 0.8 else "0,6 - 0,8" if c >= 0.6 else "0,5 - 0,6" if c >= 0.5 else "< 0,5"
        tranches[cle] += 1
    print("\nConfiance des rattachements retenus :")
    for cle, n in tranches.items():
        print(f"  {cle:<10} {n:5d}  ({100.0 * n / len(lignes):4.1f} %)")

    if args.dry_run:
        print("\n--dry-run : aucun fichier écrit.")
        return 0

    out = _tableur("reservoir_superc.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        for ligne in sorted(lignes, key=lambda r: r["Aliment"]):
            writer.writerow(ligne)
    print(f"\nRéservoir écrit : {out}")

    rapport = _tableur("reservoir_rapport.txt")
    faibles = sorted(lignes, key=lambda r: r["Confiance"])[:RAPPORT_LIGNES]
    with rapport.open("w", encoding="utf-8") as handle:
        handle.write("RATTACHEMENTS LES MOINS SÛRS — à revoir en priorité\n")
        handle.write("=" * 78 + "\n")
        handle.write(
            "Un mauvais rattachement donne à un produit les teneurs d'un autre "
            "aliment.\nL'optimiseur maximisant la densité nutritionnelle par "
            "dollar, il ira\nchercher en PRIORITÉ un aliment dont les teneurs "
            "sont surestimées.\nCorriger ou retirer la ligne dans "
            "reservoir_superc.csv, ou saisir l'aliment\nà la main dans "
            "aliments.csv (qui reste prioritaire).\n\n"
        )
        for ligne in faibles:
            handle.write(f"[{ligne['Confiance']:.2f}] {ligne['Aliment']}\n")
            handle.write(f"        -> CIQUAL {ligne['CiqualCode']} · {ligne['CiqualNom']}\n")
            handle.write(f"        rayon {ligne['Rayon'] or '?'} · {ligne['Prix']:.3f} $/100 g\n")
        handle.write(f"\n\nPRODUITS ÉCARTÉS FAUTE DE RATTACHEMENT SÛR ({len(stats.faible_confiance)})\n")
        handle.write("=" * 78 + "\n")
        handle.write(
            "Ceux-ci avaient un candidat, mais sous le seuil de confiance.\n"
            "Les plus proches du seuil sont les meilleurs candidats à un ajout\n"
            "manuel dans aliments.csv.\n\n"
        )
        for entree in stats.faible_confiance[:RAPPORT_LIGNES]:
            handle.write(f"[{entree['confiance']:.2f}] {entree['produit']}\n")
            handle.write(f"        -> {entree['ciqual']}\n")
    print(f"Rapport de revue : {rapport}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
