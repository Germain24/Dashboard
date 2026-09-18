"""Relève les prix réels des suppléments chez Canadian Protein.

Pourquoi un import séparé de Super C : ces produits ne sont pas vendus en
épicerie. Sans lui, la créatine et la poudre de protéine gardaient un prix
d'ordre de grandeur inventé (6 $ et 5 $ / 100 g), sur lequel l'optimiseur
arbitrait pourtant un budget réel.

Canadian Protein tourne sous Shopify, qui expose un JSON public
(`/collections/<handle>/products.json`). On lit donc des données structurées —
titre, variante, prix, **poids exact de la variante** — plutôt que de parser du
HTML : le prix au 100 g est alors calculé, jamais estimé.

Choix du format retenu : le meilleur prix au 100 g parmi les variantes en stock,
ce qui revient au plus gros format. C'est cohérent avec l'usage (un supplément
se garde des mois) et avec l'objectif d'économie.

Ces aliments doivent rester identifiés comme achetés à part : ils ne figurent
sur aucune liste de courses d'épicerie (cf. `SOURCE_CANADIAN_PROTEIN`).

Usage (depuis backend/) :
  .venv/Scripts/python.exe scripts/import_canadian_protein.py            # aperçu
  .venv/Scripts/python.exe scripts/import_canadian_protein.py --apply    # écrit
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

BASE = "https://canadianprotein.com"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

#: Aliment du catalogue -> (collection Shopify, mots du titre à exiger).
#: Les mots servent à ne pas confondre « Creatine Monohydrate » avec un mélange
#: pré-entraînement qui en contient.
CIBLES: dict[str, tuple[str, tuple[str, ...]]] = {
    "Creatine monohydrate": ("creatine-supplements", ("creatine", "monohydrate")),
    "Proteine en poudre": ("whey-isolate", ("whey", "isolate")),
}


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


#: Format maximal retenu (g). Shopify propose jusqu'à 10 kg, dont le prix au
#: 100 g est imbattable mais qui n'a aucun sens pour un achat personnel : le
#: relevé doit refléter ce qui sera réellement acheté.
FORMAT_MAX_G = 2500.0

_POIDS_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|g)\b", re.IGNORECASE)


def poids_net_g(titre_variante: str) -> float | None:
    """Poids ANNONCÉ de la variante, en grammes.

    On ne se fie pas au champ Shopify `grams` : il porte le poids d'EXPÉDITION,
    emballage compris (1 100 g pour un pot de 1 kg, 10 100 g pour 10 kg). L'y
    prendre sous-estimait le prix au 100 g d'environ 10 %.
    """
    for valeur, unite in _POIDS_RE.findall(titre_variante or ""):
        nombre = float(valeur.replace(",", "."))
        grammes = nombre * 1000 if unite.lower() == "kg" else nombre
        if grammes >= 100:            # ignore les « 2.2 lb », tailles de scoop…
            return grammes
    return None


def variantes(collection: str) -> list[dict]:
    """Toutes les variantes d'une collection, avec leur poids net et leur prix."""
    out: list[dict] = []
    page = 1
    while page <= 5:
        data = _get(f"{BASE}/collections/{collection}/products.json"
                    f"?limit=250&page={page}")
        produits = data.get("products") or []
        if not produits:
            break
        for prod in produits:
            for var in prod.get("variants") or []:
                prix = float(var.get("price") or 0)
                grammes = poids_net_g(str(var.get("title") or ""))
                if not grammes or prix <= 0:
                    continue
                out.append({
                    "produit": prod.get("title", ""),
                    "variante": var.get("title", ""),
                    "grammes": grammes,
                    "prix": prix,
                    "prix_100g": round(prix / grammes * 100, 4),
                    "disponible": bool(var.get("available")),
                })
        page += 1
    return out


def meilleur_prix(collection: str, mots: tuple[str, ...],
                  format_max_g: float = FORMAT_MAX_G) -> dict | None:
    """Meilleur prix au 100 g parmi les variantes en stock d'un format achetable."""
    candidats = [
        v for v in variantes(collection)
        if all(m in v["produit"].lower() for m in mots)
        and v["disponible"] and v["grammes"] <= format_max_g
    ]
    return min(candidats, key=lambda v: v["prix_100g"]) if candidats else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="écrit les prix relevés dans aliments.csv")
    args = ap.parse_args()

    releves: dict[str, dict] = {}
    for aliment, (collection, mots) in CIBLES.items():
        try:
            meilleur = meilleur_prix(collection, mots)
        except Exception as exc:  # noqa: BLE001
            print(f"[{aliment}] relevé impossible : {exc}")
            continue
        if not meilleur:
            print(f"[{aliment}] aucun produit correspondant dans /{collection}")
            continue
        releves[aliment] = meilleur
        print(f"[{aliment}]")
        print(f"    {meilleur['produit']} — {meilleur['variante']}")
        print(f"    {meilleur['grammes']:.0f} g à {meilleur['prix']:.2f} $ "
              f"-> {meilleur['prix_100g']:.3f} $/100 g")

    if not releves:
        sys.exit("aucun prix relevé — rien à écrire")

    from app.services.sante.aliments import load_aliments_dataframe
    df = load_aliments_dataframe()
    print("\n--- comparaison avec le catalogue ---")
    for aliment, releve in releves.items():
        if aliment not in df.index:
            print(f"  {aliment} : absent du catalogue")
            continue
        actuel = float(df.at[aliment, "Prix"])
        neuf = releve["prix_100g"]
        ecart = (neuf - actuel) / actuel * 100 if actuel else 0.0
        print(f"  {aliment:24s} {actuel:6.2f} $ -> {neuf:6.2f} $/100 g "
              f"({ecart:+.0f} %)")

    if not args.apply:
        print("\n[aperçu] rien écrit — relancer avec --apply")
        return

    n, bak = ecrire_prix({a: r["prix_100g"] for a, r in releves.items()})
    print(f"\n{n} prix mis à jour dans aliments.csv (backup : {bak})")


CSV_PATH = _BACKEND.parent / "data" / "imports" / "Sante" / "tableur" / "aliments.csv"


def ecrire_prix(prix_par_aliment: dict[str, float]) -> tuple[int, str]:
    """Réécrit la ligne « Prix » du catalogue pour les aliments donnés.

    Le CSV est TRANSPOSÉ (nutriments en lignes, aliments en colonnes) : on
    remplace donc des cellules d'une seule ligne, sans toucher au reste du
    fichier ni à l'ordre des colonnes.
    """
    import datetime

    from app.services.backup_storage import backup_file

    texte = CSV_PATH.read_text(encoding="utf-8-sig")
    lignes = texte.splitlines()
    entetes = lignes[0].split(";")
    index = {nom.strip(): i for i, nom in enumerate(entetes)}

    inconnus = [a for a in prix_par_aliment if a not in index]
    if inconnus:
        raise SystemExit(f"absents du catalogue : {inconnus}")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = backup_file(
        CSV_PATH,
        category="maintenance/import_canadian_protein",
        filename=CSV_PATH.name + f".bak-canadianprotein-{stamp}",
    )

    modifiees = 0
    for n, ligne in enumerate(lignes):
        cellules = ligne.split(";")
        if cellules[0].strip() != "Prix":
            continue
        for aliment, prix in prix_par_aliment.items():
            cellules[index[aliment]] = f"{prix:.4f}".rstrip("0").rstrip(".")
            modifiees += 1
        lignes[n] = ";".join(cellules)
        break
    CSV_PATH.write_text("\n".join(lignes) + "\n", encoding="utf-8-sig")
    return modifiees, bak.name


if __name__ == "__main__":
    main()
