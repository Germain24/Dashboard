"""Aliments complets courants absents du tableur historique.

Les profils viennent de CIQUAL normalisé. Aucun prix n'est inventé : ces lignes
ne deviennent candidates que si ``fenetre_service._verified_catalog`` trouve un
produit Super C chiffrable correspondant.
"""
from __future__ import annotations

import csv

from app.core.config import settings


SUPER_C_EXPANSION_CODES: dict[str, str] = {
    # 30 aliments présents et chiffrables dans le cache Super C 2026-08-12.
    "Banane plantain": "53100",
    "Celeri-rave": "20055",
    "Nectarine": "13030",
    "Papaye": "13035",
    "Poivron vert": "20085",
    "Poivron jaune": "20168",
    "Figue de Barbarie": "13063",
    "Courge poivree": "20139",
    "Courge spaghetti": "20145",
    "Poire asiatique": "13037",
    "Piment jalapeno": "20151",
    "Piment habanero": "20151",
    "Aubergine chinoise": "20053",
    "Courgette jaune": "20020",
    "Patate douce violette": "4101",
    "Kiwi dore": "13021",
    "Semoule de mais (sec)": "9614",
    "Pate de tomate": "20068",
    "Graines de sesame": "15010",
    "Huile de tournesol": "17440",
    "Palourdes en conserve": "10027",
    "Cotelettes de porc": "28100",
    "Saumon coho sauvage": "26161",
    "Pilons de poulet": "36022",
    "Ailes de poulet": "36023",
    "Poulet hache": "36003",
    "Porc hache": "28472",
    "Bifteck de cote": "6103",
    "Crevettes crues": "10038",
    "Thon jaune en conserve": "26181",
}


COMMON_FOOD_CODES: dict[str, str] = {
    # Bases demandées pour l'optimisation sportive. CIQUAL ne contient pas de
    # haricot noir : le haricot rouge appertisé égoutté est l'approximation
    # botanique et culinaire la plus proche, explicitement assumée ici.
    "Haricots noirs en conserve": "20524",
    "Sarrasin entier (sec)": "9380",
    "Orge monde (sec)": "9320",
    "Amarante (sec)": "9345",
    "Pates aux oeufs (sec)": "9821",
    "Pates de ble entier (sec)": "9870",
    "Yogourt grec nature entier": "19860",
    "Cacao non sucre en poudre": "18100",
    "Cannelle moulue": "11025",
    "The vert infuse non sucre": "18155",
    "Pomme de terre": "4008",
    "Chou vert": "20069",
    "Chou kale": "20218",
    "Pois casses secs": "20515",
    "Orge perlee (sec)": "9321",
    "Couscous (sec)": "9681",
    "Boulgour (sec)": "9690",
    "Pain complet": "7110",
    "Saumon en conserve": "26119",
    "Huile de canola": "17130",  # colza = canola
    "Mais surgele": "20233",
    "Ail": "11000",
    "Citron": "13009",
    "Betterave": "20091",
    "Navet": "20064",
    "Tempeh": "20917",
    "Sel iode": "11058",
    **SUPER_C_EXPANSION_CODES,
}

# Plafonds quotidiens réalistes pour les ajouts ci-dessus. Sans eux, les épices
# très concentrées pourraient être consommées par centaines de grammes afin de
# remplir artificiellement les micros.
COMMON_FOOD_MAX_QTY: dict[str, float] = {
    "Cannelle moulue": 5.0,
    "Cacao non sucre en poudre": 30.0,
    "The vert infuse non sucre": 750.0,
    "Yogourt grec nature entier": 400.0,
    "Sarrasin entier (sec)": 250.0,
    "Orge monde (sec)": 250.0,
    "Amarante (sec)": 250.0,
    "Pates aux oeufs (sec)": 200.0,
    "Pates de ble entier (sec)": 200.0,
}


def load_common_foods() -> dict[str, dict[str, float]]:
    """Charge les profils CIQUAL ci-dessus, ou un dictionnaire vide si absent."""
    path = settings.imports_dir / "Sante" / "ciqual" / "ciqual_normalise.csv"
    if not path.exists():
        return {}
    # Plusieurs aliments commerciaux peuvent volontairement partager le même
    # profil CIQUAL (p. ex. jalapeño et habanero). Ne pas perdre le premier en
    # construisant un simple dictionnaire code -> nom.
    wanted: dict[str, list[str]] = {}
    for name, code in COMMON_FOOD_CODES.items():
        wanted.setdefault(code, []).append(name)
    out: dict[str, dict[str, float]] = {}
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter=";"):
                names = wanted.get(row.get("CiqualCode", ""))
                if not names:
                    continue
                props: dict[str, float] = {}
                for key, raw in row.items():
                    if key in {"CiqualCode", "CiqualNom", "CiqualGroupe", "CiqualSousGroupe"}:
                        continue
                    if raw not in (None, ""):
                        props[key] = float(raw)
                props.update({
                    "Prix": 0.0, "MinQty": 0.0,
                    "Congelable": 0.0, "CreamiOk": 0.0,
                })
                for name in names:
                    profile = props.copy()
                    profile["MaxQty"] = COMMON_FOOD_MAX_QTY.get(name, 400.0)
                    out[name] = profile
    except (OSError, ValueError):
        return {}
    return out
