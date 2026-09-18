"""Construit le « réservoir » : les produits Super C rattachés à CIQUAL.

`aliments.csv` reste le catalogue CURÉ à la main, source de vérité et toujours
prioritaire. Le réservoir est un second catalogue, GÉNÉRÉ, qui élargit le choix
offert à l'optimiseur avec les produits réellement vendus en magasin :

    produit Super C (nom + prix/100 g)  ->  aliment CIQUAL le plus proche
                                        ->  45 teneurs + prix = entrée du réservoir

Deux exigences pour qu'un produit entre :
  - un PRIX au 100 g (sans lui, l'optimiseur ne peut ni le comparer ni le
    budgéter) ;
  - un rattachement CIQUAL d'une confiance suffisante (sans lui, on inventerait
    des teneurs, et l'optimiseur — qui maximise la densité par dollar — irait
    droit sur l'aliment mal renseigné).

Logique PURE : les I/O vivent dans `scripts/build_reservoir.py`.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Optional

from app.services.sante.ciqual_matching import MIN_CONFIDENCE, CiqualIndex
from app.services.sante.ciqual_matching import Match
from app.services.sante.reservoir_overrides import ciqual_override_code

logger = logging.getLogger(__name__)

#: Colonnes ajoutées aux 45 teneurs, pour la traçabilité et la revue humaine.
PROVENANCE_COLUMNS = ("Source", "UPC", "Rayon", "CiqualCode", "CiqualNom", "Confiance")

#: Bornes de quantité par défaut des aliments générés (en grammes).
#: `MaxQty` empêche l'optimiseur d'empiler 400 g/jour d'un même produit
#: transformé ; `MinQty` reste à 0 (pas de quantité d'achat minimale connue).
DEFAULT_MIN_QTY = 0.0
DEFAULT_MAX_QTY = 300.0

# Pour chaque profil CIQUAL, seuls les produits Super C les plus ressemblants
# peuvent concourir sur le prix. La distance est quadratique afin qu'une baisse
# de confiance près du seuil soit pénalisée plus fortement qu'un petit écart
# entre deux excellents rapprochements.
DEFAULT_CIQUAL_CANDIDATES = 10
DEFAULT_MAX_SQUARED_DISTANCE = 0.0625  # (1 - 0,75)²

#: Groupes CIQUAL dont les aliments supportent la congélation, et ceux qui font
#: de bons pots CREAMi (où la texture cassée par le gel est justement voulue).
#: Dérivé des valeurs déjà saisies à la main dans `aliments.csv`.
CONGELABLE_GROUPES: frozenset[str] = frozenset({
    "viandes, œufs, poissons et assimilés",
    "produits céréaliers",
    "entrées et plats composés",
    "matières grasses",
    "aides culinaires et ingrédients divers",
})
CREAMI_GROUPES: frozenset[str] = frozenset({
    "fruits, légumes, légumineuses et oléagineux",
    "produits laitiers et assimilés",
    "eaux et autres boissons",
    "glaces et sorbets",
    "produits sucrés",
})


@dataclass
class ReservoirStats:
    """Ce qui est entré, et surtout ce qui n'est pas entré et pourquoi."""
    total_produits: int = 0
    sans_prix: int = 0
    non_rattaches: int = 0
    doublons: int = 0
    alternatives_ciqual: int = 0
    inadmissibles_optimiseur: int = 0
    retenus: int = 0
    faible_confiance: list[dict] = field(default_factory=list)

    def resume(self) -> str:
        return (
            f"{self.retenus} aliments retenus sur {self.total_produits} produits "
            f"({self.sans_prix} sans prix, {self.non_rattaches} sans rattachement "
            f"CIQUAL fiable, {self.inadmissibles_optimiseur} non adaptés à un "
            f"plan alimentaire, {self.doublons} doublons, "
            f"{self.alternatives_ciqual} alternatives CIQUAL écartées)"
        )


# Un produit peut avoir un rattachement CIQUAL correct sans être interprétable
# comme une quantité réellement mangée. Exemple : CIQUAL décrit le café moulu,
# mais 30 g de café servent à INFUSER une boisson et ne sont pas ingérés. Même
# problème pour la gélatine sèche, les glaçons, ou les produits très transformés
# que l'optimiseur sélectionne uniquement pour exploiter un profil générique.
_NON_OPTIMIZER_PRODUCT_RE = re.compile(
    r"(?:\b(?:gatorade|powerade)\b|boisson(?:s)? pour sportif|boisson(?:s)? energetique|"
    r"sac de glace|glacon|glace concassee|cafe (?:moulu|en grain|instantane)|"
    r"gelatine|barre(?:s)? glacee|creme glacee|popsicle|sorbet|"
    r"croustille|\bchips?\b|croissant|beigne|donut|gateau|cupcake|"
    r"bonbon|confiserie|marmelade|confiture|"
    r"pate (?:de foie|au jambon|au porc)|bologne|pepperoni|salami|hot dog|"
    r"bouillon|bicarbonate|vinaigre|sauce barbecue|marinade|tempura|"
    r"saucisse|pizza|pochette(?:s)?|poulet bbq cuit chaud|cuit chaud|"
    r"bouchee(?:s)? de pomme(?:s)? de terre|"
    r"piment de cayenne.*sachet|coriandre moulue)",
    re.IGNORECASE,
)


def optimizer_product_is_eligible(item: dict) -> bool:
    """Vrai si le produit peut représenter directement des grammes consommés.

    Cette barrière est volontairement indépendante du rattachement lexical :
    une confiance CIQUAL élevée ne rend pas un sac de glace comestible ni du
    café moulu équivalent à la boisson infusée.
    """
    raw = str(item.get("name") or item.get("Aliment") or "")
    normalized = "".join(
        char for char in unicodedata.normalize("NFKD", raw.lower())
        if not unicodedata.combining(char)
    ).replace("œ", "oe")
    return not bool(_NON_OPTIMIZER_PRODUCT_RE.search(normalized))


def price_per_100g(item: dict) -> Optional[float]:
    """Prix CAD/100 g d'un produit du cache Super C, ou None si non chiffrable.

    Le scraper renseigne `price_per_100g` directement quand le site l'affiche,
    et `unit_price` en $/kg sinon. Un produit vendu à l'unité sans poids (une
    douzaine d'œufs, une laitue) n'a ni l'un ni l'autre : il est écarté plutôt
    que deviné.
    """
    direct = item.get("price_per_100g")
    if direct:
        try:
            value = float(direct)
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    if item.get("unit") == "kg" and item.get("unit_price"):
        try:
            value = float(item["unit_price"]) / 10.0
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    return None


def _nom_unique(nom: str, pris: set[str]) -> str:
    """Nom d'aliment unique dans le catalogue (l'index du DataFrame est le nom).

    Deux produits réellement distincts peuvent porter le même libellé ; on
    suffixe plutôt que d'en perdre un silencieusement. Les vrais doublons, eux,
    sont éliminés en amont par `_deduplicate` — c'est là qu'il faut regarder si
    des « (2) » apparaissent dans le catalogue.
    """
    base = nom.strip() or "Produit Super C"
    if base not in pris:
        return base
    for n in range(2, 100):
        candidat = f"{base} ({n})"
        if candidat not in pris:
            return candidat
    return f"{base} ({len(pris)})"


def _cle_doublon(nom: str) -> str:
    """Clé de regroupement des variantes d'un même produit.

    Super C référence le même article sous plusieurs UPC (formats, lots,
    réapprovisionnements) : « Selection Farine tout usage » est apparu deux fois
    dans le premier réservoir, occupant deux places de la présélection pour un
    seul aliment réel. On regroupe sur le libellé normalisé.
    """
    return " ".join(str(nom or "").lower().split())


def _deduplicate(produits: list[dict]) -> list[dict]:
    """Une seule variante par produit : la MOINS chère au 100 g.

    Le moins cher, et non le premier venu : c'est la variante que l'utilisateur
    achèterait, et c'est celle qui donne à l'optimiseur le bon signal de prix.
    """
    meilleur: dict[str, tuple[float, dict]] = {}
    for item in produits:
        prix = price_per_100g(item)
        if prix is None:
            continue
        cle = _cle_doublon(item.get("name"))
        actuel = meilleur.get(cle)
        if actuel is None or prix < actuel[0]:
            meilleur[cle] = (prix, item)
    return [item for _prix, item in meilleur.values()]


def build_reservoir(
    produits: Iterable[dict],
    index: CiqualIndex,
    teneurs_par_code: dict[str, dict[str, float]],
    *,
    rayon_par_upc: Optional[dict[str, str]] = None,
    nom_sitemap_par_upc: Optional[dict[str, str]] = None,
    min_confidence: float = MIN_CONFIDENCE,
    ciqual_candidates: int = DEFAULT_CIQUAL_CANDIDATES,
    max_squared_distance: float | None = None,
    exclure: frozenset[str] = frozenset(),
) -> tuple[list[dict], ReservoirStats]:
    """Produits Super C -> lignes de réservoir + statistiques de construction.

    `produits`            : items du cache Super C (nom, sku/UPC, prix).
    `index`               : index CIQUAL pour le rattachement.
    `teneurs_par_code`    : {code CIQUAL: {colonne: valeur}} depuis le CSV normalisé.
    `rayon_par_upc`       : rayon issu du sitemap, qui affine le rattachement.
    `nom_sitemap_par_upc` : nom issu du sitemap — SANS marque ni format, donc
                            bien meilleur pour le rattachement que le libellé
                            commercial (« Black Diamond Fromage cheddar blanc
                            fort » contre « fromage cheddar blanc fort »). Le
                            libellé commercial reste le nom AFFICHÉ.
    `exclure`             : noms déjà présents dans le catalogue curé — ils
                            gagnent toujours, on ne crée pas de doublon.

    Chaque produit est d'abord rattaché à son UNIQUE meilleur profil CIQUAL.
    Pour chaque profil, on garde ensuite les `ciqual_candidates` produits à la
    plus petite distance `(1 - confiance)²`, sous `max_squared_distance`, puis
    le moins cher aux 100 g parmi eux. Un produit bon marché mais trop éloigné
    ne peut donc jamais gagner uniquement grâce à son prix. Sans distance
    explicite, la limite équivaut exactement à `min_confidence`.
    """
    rayons = rayon_par_upc or {}
    noms_sitemap = nom_sitemap_par_upc or {}
    stats = ReservoirStats()
    lignes: list[dict] = []
    pris: set[str] = set(exclure)
    candidats_par_code: dict[str, list[dict]] = {}

    if ciqual_candidates < 1:
        raise ValueError("ciqual_candidates doit être supérieur ou égal à 1")
    if max_squared_distance is None:
        max_squared_distance = (1.0 - min_confidence) ** 2
    if not 0.0 <= max_squared_distance <= 1.0:
        raise ValueError("max_squared_distance doit être compris entre 0 et 1")

    bruts = [p for p in produits if str(p.get("name") or "").strip()]
    stats.total_produits = len(bruts)
    stats.inadmissibles_optimiseur = sum(
        1 for p in bruts if not optimizer_product_is_eligible(p)
    )
    bruts = [p for p in bruts if optimizer_product_is_eligible(p)]
    stats.sans_prix = sum(1 for p in bruts if price_per_100g(p) is None)
    chiffrables = [p for p in bruts if price_per_100g(p) is not None]
    retenus_apres_dedup = _deduplicate(chiffrables)
    stats.doublons = len(chiffrables) - len(retenus_apres_dedup)

    for item in retenus_apres_dedup:
        nom_commercial = str(item.get("name") or "").strip()
        prix = price_per_100g(item)
        if prix is None:                     # déjà filtré, garde défensive
            continue

        upc = str(item.get("sku") or item.get("id") or "")
        rayon = rayons.get(upc, "")
        # Le nom du sitemap est débarrassé de la marque et du format : il donne
        # un rattachement nettement plus juste. Repli sur le libellé commercial
        # pour les produits absents du sitemap.
        nom_a_rattacher = noms_sitemap.get(upc) or nom_commercial
        override_code = ciqual_override_code(nom_commercial)
        if override_code:
            entry = next((e for e in index.entries if e.code == override_code), None)
            match = (
                Match(entry.code, entry.nom, entry.groupe, 1.0)
                if entry is not None else None
            )
        else:
            match = index.match(nom_a_rattacher, rayon)
        distance_quadratique = (
            (1.0 - float(match.confiance)) ** 2 if match is not None else 1.0
        )
        if (
            match is None
            or match.confiance < min_confidence
            or distance_quadratique > max_squared_distance
        ):
            stats.non_rattaches += 1
            if match is not None:
                stats.faible_confiance.append({
                    "produit": nom_commercial, "ciqual": match.nom,
                    "confiance": match.confiance, "rayon": rayon,
                })
            continue

        teneurs = teneurs_par_code.get(match.code)
        if teneurs is None:
            stats.non_rattaches += 1
            continue

        candidats_par_code.setdefault(match.code, []).append({
            "item": item,
            "nom_commercial": nom_commercial,
            "prix": prix,
            "upc": upc,
            "rayon": rayon,
            "match": match,
            "teneurs": teneurs,
            "distance_quadratique": distance_quadratique,
        })

    gagnants: list[dict] = []
    for candidats in candidats_par_code.values():
        proches = sorted(
            candidats,
            key=lambda c: (c["distance_quadratique"], c["prix"], c["nom_commercial"]),
        )[:ciqual_candidates]
        gagnants.append(min(
            proches,
            key=lambda c: (c["prix"], c["distance_quadratique"], c["nom_commercial"]),
        ))
        stats.alternatives_ciqual += len(candidats) - 1

    for candidat in gagnants:
        nom_commercial = candidat["nom_commercial"]
        prix = candidat["prix"]
        upc = candidat["upc"]
        rayon = candidat["rayon"]
        match = candidat["match"]
        teneurs = candidat["teneurs"]
        nom = _nom_unique(nom_commercial, pris)
        if nom in pris:
            continue
        pris.add(nom)

        ligne: dict = {"Aliment": nom, **teneurs}
        ligne["Prix"] = round(prix, 4)
        ligne["MinQty"] = DEFAULT_MIN_QTY
        ligne["MaxQty"] = DEFAULT_MAX_QTY
        ligne["Congelable"] = 1 if match.groupe in CONGELABLE_GROUPES else 0
        ligne["CreamiOk"] = 1 if match.groupe in CREAMI_GROUPES else 0
        ligne["Source"] = "superc"
        ligne["UPC"] = upc
        ligne["Rayon"] = rayon
        ligne["CiqualCode"] = match.code
        ligne["CiqualNom"] = match.nom
        ligne["Confiance"] = match.confiance
        lignes.append(ligne)
        stats.retenus += 1

    stats.faible_confiance.sort(key=lambda r: r["confiance"], reverse=True)
    return lignes, stats
