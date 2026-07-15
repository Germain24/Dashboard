"""Budget de voyage finançable en chaînant les cartes de crédit actives.

Principe : UNE seule carte utilisée à la fois, vidée (limite pleine) sur un
mois, remboursée intégralement avant l'échéance (délai de grâce -> 0 %
d'intérêt), puis on passe à la carte suivante. Jamais deux cartes ouvertes en
parallèle. Exemple (15000 + 5000 + 3000 CAD) -> 23000 CAD financables sur 3
mois (mois 1 = 15000, mois 2 = 5000, mois 3 = 3000).

Fonction pure : ne touche pas la DB.
"""

from __future__ import annotations


def compute_voyage_budget(accounts: list, *, ordre: str = "desc") -> dict:
    """`accounts` : objets avec `.statut`, `.limite_actuelle`, `.institution`,
    `.produit`. `ordre` = "desc" (plus grosse limite en premier, par défaut)
    ou "asc". Renvoie `{mois: [...], budget_total, mois_total}`."""
    actifs = [a for a in accounts if a.statut == "actif" and (a.limite_actuelle or 0) > 0]
    actifs = sorted(actifs, key=lambda a: a.limite_actuelle, reverse=(ordre != "asc"))
    mois = [
        {
            "mois": i + 1,
            "institution": a.institution,
            "produit": a.produit,
            "budget": round(a.limite_actuelle, 2),
        }
        for i, a in enumerate(actifs)
    ]
    return {
        "mois": mois,
        "budget_total": round(sum(m["budget"] for m in mois), 2),
        "mois_total": len(mois),
    }
