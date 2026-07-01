"""Enrichit les échelles de Vetements.xlsx avec des marques FR intermédiaires.

Curation informée BonneGueule : les listes actuelles sont déjà riches (japonais/
anglo + luxe) mais sans marque FR mid-tier. On insère ces marques juste après la
marque d'entrée. Master gitignoré : la modif est locale (backup + re-sync).

Usage (depuis backend/) :
    uv run python -m scripts.enrich_bonnegueule
"""
from __future__ import annotations


def _norm(s: str | None) -> str:
    return " ".join(str(s or "").strip().casefold().split())


def insert_after_entry(echelle: list[str], brands: list[str]) -> list[str]:
    """Insère `brands` juste après `echelle[0]`, dédupliquées (casse/espaces).

    N'ajoute que des marques absentes de `echelle` et non dupliquées entre elles ;
    ordre préservé. Ne retire jamais → len(résultat) >= len(echelle).
    """
    def _dedup(items: list[str], already: set[str]) -> list[str]:
        out: list[str] = []
        seen = set(already)
        for b in items:
            k = _norm(b)
            if not k or k in seen:
                continue
            seen.add(k)
            out.append(b)
        return out

    if not echelle:
        return _dedup(brands, set())
    new = _dedup(brands, {_norm(x) for x in echelle})
    return [echelle[0]] + new + echelle[1:]


# Type objectif -> marques FR intermédiaires à insérer (cf. spec).
ENRICHMENT: dict[str, list[str]] = {
    # Hauts
    "T-shirts": ["Loom", "Asphalte", "Le Minor"],
    "Polos": ["Asphalte", "Le Minor"],
    "Chemises": ["Asphalte", "Officine Générale", "De Bonne Facture"],
    "Débardeurs": ["Le Minor", "Saint James"],
    "Pulls": ["Officine Générale", "De Bonne Facture", "Maison Montagut"],
    "Sweats": ["Asphalte", "Maison Labiche"],
    "Gilets": ["Officine Générale", "De Bonne Facture"],
    "Overshirts": ["Asphalte", "De Bonne Facture"],
    # Bas
    "Jeans": ["Asphalte", "1083", "Ateliers de Nîmes"],
    "Pantalons chino": ["Asphalte", "Officine Générale", "De Bonne Facture"],
    "Pantalons habillés": ["Officine Générale", "De Fursac", "Husbands"],
    "Shorts": ["Asphalte"],
    "Pantalons en velours": ["Officine Générale", "De Bonne Facture"],
    # Vestes / manteaux
    "Vestes légères": ["Officine Générale", "De Bonne Facture", "Harmony"],
    "Blazers": ["Officine Générale", "De Fursac", "Husbands"],
    "Manteaux": ["Officine Générale", "Harmony", "Éditions M.R"],
    # Costume
    "Vestes de costume": ["De Fursac", "Husbands", "Samson"],
    "Pantalons de costume": ["De Fursac", "Husbands"],
    "Gilets de costume": ["De Fursac", "Husbands"],
    "Smokings": ["De Fursac", "Husbands"],
    # Sous-vêtements
    "Boxers": ["Le Slip Français"],
    "Slips": ["Le Slip Français"],
    "Maillots de corps": ["Le Slip Français"],
    "Chaussettes": ["Bleuforêt", "Labonal", "Royalties"],
    # Chaussures
    "Bottines": ["Jules & Jenn", "Anthology Paris"],
    "Chaussures de ville": ["Bexley", "Jacques & Déclercq", "Markowski"],
    # Accessoires
    "Ceintures": ["JOSEPH BONNIE", "Bleu de Chauffe"],
    "Cravates": ["Le Colonel Moutarde", "Cinabre"],
    "Nœuds papillon": ["Le Colonel Moutarde", "Cinabre"],
    "Foulards": ["Cinabre"],
    "Lunettes de soleil": ["Jimmy Fairly", "Ateliers Loden"],
    "Sacs à dos": ["Bleu de Chauffe", "Bonastre", "Côme"],
    "Sacs de voyage": ["Bleu de Chauffe", "Bonastre"],
    "Portefeuilles": ["Bleu de Chauffe", "JOSEPH BONNIE"],
    # Technique
    "Maillots techniques": ["Circle Sportswear"],
    "Shorts techniques": ["Circle Sportswear"],
}
