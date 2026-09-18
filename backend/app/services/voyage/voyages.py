"""Voyages confirmés : checklist de préparation + budget par étape (§5.4).

Le coût estimé d'une étape n'est pas recalculé ici : il réutilise la
ventilation de `costs.cost_breakdown` (hébergement / nourriture / activité /
transport local), seule source de vérité des coûts d'un lieu. Seul le
transport ENTRE étapes reste hors périmètre — il n'appartient à aucune étape
et dépend de l'itinéraire complet (cf. `_format_itineraire`).

`aggregate_budget` est pur (aucune session) pour rester testable.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Sequence
from typing import Any, Protocol

from sqlmodel import Session, select

from app.models.voyage import LieuVoyage, Voyage, VoyageChecklistItem, VoyageEtape
from app.services.voyage.costs import cost_breakdown

# Base commune à tout voyage international ; l'utilisateur ajoute/retire ensuite.
CHECKLIST_DEFAUT: tuple[str, ...] = (
    "Passeport valide 6 mois après le retour",
    "Visa / autorisation d'entrée",
    "Assurance voyage",
    "Vaccins et trousse de premiers soins",
    "Billets et réservations imprimés",
    "Carte bancaire sans frais à l'étranger prévenue du départ",
    "Adaptateur de prise et batterie externe",
)


class _CoutsEtape(Protocol):
    """Ce dont `aggregate_budget` a besoin — un VoyageEtape suffit."""

    cout_estime: float
    cout_reel: float | None


# ── Budget ────────────────────────────────────────────────────────────────────

def budget_etape(lieu: LieuVoyage, jours: int) -> float:
    """Coût estimé d'une étape : séjour sur place + coûts fixes du lieu."""
    c = cost_breakdown(lieu, jours)
    return round(
        c["hebergement"] + c["nourriture"] + c["activite"] + c["transport_local"], 2
    )


def aggregate_budget(etapes: Sequence[_CoutsEtape]) -> dict[str, Any]:
    """Totaux d'un voyage. Le « projeté » prend le réel dès qu'il est saisi et
    retombe sur l'estimé sinon : c'est le seul total comparable au budget de
    départ tant que le voyage n'est pas terminé."""
    estime = sum(e.cout_estime for e in etapes)
    reel = sum(e.cout_reel for e in etapes if e.cout_reel is not None)
    projete = sum(e.cout_reel if e.cout_reel is not None else e.cout_estime for e in etapes)
    return {
        "cout_estime_total": round(estime, 2),
        "cout_reel_total": round(reel, 2),
        "cout_projete_total": round(projete, 2),
        "ecart": round(projete - estime, 2),
        "etapes_avec_cout_reel": sum(1 for e in etapes if e.cout_reel is not None),
    }


# ── Voyage ────────────────────────────────────────────────────────────────────

def create_voyage(
    session: Session, *, titre: str, date_debut: dt.date, date_fin: dt.date,
    etapes: Iterable[dict[str, Any]], depart_iata: str | None = None,
    arrivee_iata: str | None = None, checklist_defaut: bool = True,
) -> Voyage:
    """Persiste un itinéraire retenu. Chaque étape porte `lieu_id` et `jours` ;
    le coût estimé est recalculé côté serveur depuis `lieu_voyage` (le client
    n'est pas autorité sur les montants)."""
    voyage = Voyage(
        titre=titre, date_debut=date_debut, date_fin=date_fin,
        depart_iata=depart_iata, arrivee_iata=arrivee_iata,
    )
    session.add(voyage)
    session.flush()  # besoin de voyage.id avant d'ajouter les enfants

    for ordre, e in enumerate(etapes):
        lieu = session.get(LieuVoyage, e["lieu_id"])
        if lieu is None:
            raise ValueError(f"Lieu {e['lieu_id']} introuvable")
        jours = int(e.get("jours") or 0)
        session.add(VoyageEtape(
            voyage_id=voyage.id, lieu_id=lieu.id, nom=lieu.nom,
            ville=lieu.ville, pays=lieu.pays, ordre=ordre, jours=jours,
            date_arrivee=e.get("date_arrivee"), date_depart=e.get("date_depart"),
            cout_estime=budget_etape(lieu, jours),
        ))

    if checklist_defaut:
        for ordre, label in enumerate(CHECKLIST_DEFAUT):
            session.add(VoyageChecklistItem(voyage_id=voyage.id, label=label, ordre=ordre))

    session.commit()
    session.refresh(voyage)
    return voyage


def list_voyages(session: Session) -> list[Voyage]:
    return list(session.exec(select(Voyage).order_by(Voyage.date_debut.desc())).all())


def get_voyage(session: Session, voyage_id: int) -> Voyage | None:
    return session.get(Voyage, voyage_id)


def delete_voyage(session: Session, voyage_id: int) -> bool:
    voyage = session.get(Voyage, voyage_id)
    if voyage is None:
        return False
    # Suppression explicite des enfants : pas de relations SQLModel déclarées,
    # donc pas de cascade ORM.
    for etape in voyage_etapes(session, voyage_id):
        session.delete(etape)
    for item in voyage_checklist(session, voyage_id):
        session.delete(item)
    session.delete(voyage)
    session.commit()
    return True


def voyage_etapes(session: Session, voyage_id: int) -> list[VoyageEtape]:
    return list(session.exec(
        select(VoyageEtape).where(VoyageEtape.voyage_id == voyage_id)
        .order_by(VoyageEtape.ordre)
    ).all())


def set_cout_reel(
    session: Session, voyage_id: int, etape_id: int, cout_reel: float | None,
) -> VoyageEtape | None:
    etape = session.get(VoyageEtape, etape_id)
    if etape is None or etape.voyage_id != voyage_id:
        return None
    etape.cout_reel = cout_reel
    session.add(etape)
    session.commit()
    session.refresh(etape)
    return etape


# ── Checklist ─────────────────────────────────────────────────────────────────

def voyage_checklist(session: Session, voyage_id: int) -> list[VoyageChecklistItem]:
    return list(session.exec(
        select(VoyageChecklistItem).where(VoyageChecklistItem.voyage_id == voyage_id)
        .order_by(VoyageChecklistItem.ordre, VoyageChecklistItem.id)
    ).all())


def add_checklist_item(
    session: Session, voyage_id: int, label: str, ordre: int | None = None,
) -> VoyageChecklistItem:
    if ordre is None:
        ordre = len(voyage_checklist(session, voyage_id))
    item = VoyageChecklistItem(voyage_id=voyage_id, label=label, ordre=ordre)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def update_checklist_item(
    session: Session, voyage_id: int, item_id: int, *,
    label: str | None = None, fait: bool | None = None, ordre: int | None = None,
) -> VoyageChecklistItem | None:
    item = session.get(VoyageChecklistItem, item_id)
    if item is None or item.voyage_id != voyage_id:
        return None
    if label is not None:
        item.label = label
    if fait is not None:
        item.fait = fait
    if ordre is not None:
        item.ordre = ordre
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def delete_checklist_item(session: Session, voyage_id: int, item_id: int) -> bool:
    item = session.get(VoyageChecklistItem, item_id)
    if item is None or item.voyage_id != voyage_id:
        return False
    session.delete(item)
    session.commit()
    return True
