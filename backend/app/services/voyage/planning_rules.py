"""Règles métier de disponibilité, progression et présélection Voyage."""
from __future__ import annotations

import datetime as dt
import re
from collections import defaultdict

from app.models.voyage import LieuVoyage
from app.services.voyage.airports import haversine_km

_MONTH_NAMES = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12, "décembre": 12,
}


def parse_available_months(value: str | None) -> set[int] | None:
    """Accepte `1,2,3`, `05-09` et les noms de mois français.

    `None` signifie que la saison n'est pas renseignée, pas que le lieu est
    disponible toute l'année.
    """
    if not value or value.strip().casefold() in {"tous", "toute l'année", "all"}:
        return None
    normalized = value.casefold().strip()
    for name, month in _MONTH_NAMES.items():
        normalized = normalized.replace(name, str(month))
    months: set[int] = set()
    for token in re.split(r"[,;/ ]+", normalized):
        if not token:
            continue
        match = re.fullmatch(r"(\d{1,2})\s*-\s*(\d{1,2})", token)
        if match:
            start, end = map(int, match.groups())
            if 1 <= start <= 12 and 1 <= end <= 12:
                current = start
                while True:
                    months.add(current)
                    if current == end:
                        break
                    current = current % 12 + 1
        elif token.isdigit() and 1 <= int(token) <= 12:
            months.add(int(token))
    return months or None


def is_in_season(lieu: LieuVoyage, date_debut: dt.date, date_fin: dt.date) -> bool:
    months = parse_available_months(lieu.mois_disponibles)
    if months is None:
        return True
    midpoint = date_debut + (date_fin - date_debut) / 2
    return midpoint.month in months


def unlocked_levels(lieux: list[LieuVoyage]) -> dict[str, int]:
    """Niveau suivant ouvert par filière.

    Un palier est considéré réalisé dès qu'au moins une activité de ce palier
    est visitée. Les niveaux doivent être continus : avoir fait un niveau 3 ne
    contourne pas un niveau 2 encore manquant.
    """
    completed: dict[str, set[int]] = defaultdict(set)
    for lieu in lieux:
        if lieu.visite and lieu.progression and lieu.ordre:
            completed[lieu.progression].add(lieu.ordre)
    result: dict[str, int] = {}
    groups = {lieu.progression for lieu in lieux if lieu.progression}
    for group in groups:
        level = 1
        while level in completed[group]:
            level += 1
        result[group] = level
    return result


def lock_reason(lieu: LieuVoyage, levels: dict[str, int]) -> str | None:
    if not lieu.ordre or not lieu.progression:
        return None
    unlocked = levels.get(lieu.progression, 1)
    if lieu.ordre <= unlocked:
        return None
    return f"Palier {lieu.ordre} verrouillé : termine d'abord le palier {unlocked} ({lieu.progression})"


def select_diverse_candidates(
    candidates: list[tuple[float, LieuVoyage, float]], budget_total: float, limit: int,
) -> list[LieuVoyage]:
    """Présélection sensible au budget, avec plafonds par hub et pays.

    Le coût minimal est comparé à une enveloppe cible par destination. Un gros
    budget remonte donc des voyages plus lointains au lieu de conserver les 25
    lignes les moins chères de la feuille.
    """
    if not candidates:
        return []
    target = max(250.0, budget_total / 5.0)
    ranked = sorted(
        candidates,
        key=lambda item: (
            -(max(1, min(5, item[1].priorite or 3)) * 100),
            # Le détour géographique domine l'utilisation artificielle du
            # budget : avec YUL->CDG, l'Antarctique ne doit jamais remonter
            # simplement parce que le budget est élevé.
            item[2],
            abs(item[0] - target) / target,
            item[0],
            item[1].nom,
        ),
    )
    by_hub: dict[str, int] = defaultdict(int)
    by_country: dict[str, int] = defaultdict(int)
    selected: list[LieuVoyage] = []
    for _cost, lieu, _detour in ranked:
        hub = (lieu.aeroport_iata or lieu.ville or lieu.nom).upper()
        country = lieu.pays or "Pays inconnu"
        if by_hub[hub] >= 2 or by_country[country] >= 5:
            continue
        selected.append(lieu)
        by_hub[hub] += 1
        by_country[country] += 1
        if len(selected) == limit:
            break
    return selected


def route_detour_ratio(
    origin: tuple[float, float], destination: tuple[float, float],
    candidate: tuple[float, float],
) -> float:
    """Longueur via le candidat / longueur directe.

    1.0 est sur le corridor idéal. Pour un aller-retour au même aéroport, le
    ratio n'a pas de sens et vaut 1 afin de laisser le budget/distance décider.
    """
    direct = haversine_km(origin, destination)
    if direct < 100:
        return 1.0
    via = haversine_km(origin, candidate) + haversine_km(candidate, destination)
    return via / direct
