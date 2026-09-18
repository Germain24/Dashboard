"""Recherche globale cross-modules (#546).

Étendue aux modules réellement alimentés (audit §2.D) : la recherche ne portait
que sur transactions/recettes/livres, or `recipe` est vide. Musique (1 418
pistes), Voyage (1 295 lieux), Agenda (203 événements) et Garde-robe (40 pièces)
sont désormais couverts.

Note : les `href` pointent vers la racine du module. Le lien profond vers
l'élément trouvé demande d'abord l'onglet-dans-l'URL (audit §2.B).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.core.db import get_session
from app.models.agenda import Evenement, Tache
from app.models.budget import BudgetTransaction
from app.models.cuisine import Recipe
from app.models.documents import Document
from app.models.etudes import Cours, Evaluation
from app.models.garderobe import Vetement
from app.models.livres import Book
from app.models.musique import MusicTrack
from app.models.objectifs import LongTermGoal
from app.models.voyage import LieuVoyage

router = APIRouter(tags=["search"])


def _fmt_montant(montant: float, devise: str) -> str:
    """Montant signé avec sa devise réelle.

    Les 887 transactions importées sont en CAD : le « € » codé en dur affichait
    « −11.30 € » pour un achat *SUPER C MONTREAL QC*. Les symboles usuels sont
    rendus ; toute autre devise garde son code ISO en suffixe.
    """
    symbols = {"EUR": "€", "CAD": "$", "USD": "$", "GBP": "£", "CHF": "CHF"}
    symbol = symbols.get((devise or "").upper())
    if symbol and symbol != devise:
        return f"{montant:+.2f} {symbol}"
    return f"{montant:+.2f} {devise or ''}".rstrip()


def _relevance(item: dict, query: str) -> int:
    label = (item.get("label") or "").strip().casefold()
    hint = (item.get("hint") or "").strip().casefold()
    if label == query:
        return 0
    if label.startswith(query):
        return 1
    if query in label:
        return 2
    if query in hint:
        return 3
    return 4


@router.get("/search")
def global_search(q: str, limit: int = 5, session: Session = Depends(get_session)):  # noqa: B008
    """Recherche rapide dans les données personnelles les plus consultées."""
    if not q or len(q.strip()) < 2:
        return {"results": []}

    limit = max(1, min(limit, 10))
    term = f"%{q.strip().lower()}%"
    results = []

    # Transactions budget
    txns = session.exec(
        select(BudgetTransaction)
        .where(
            (BudgetTransaction.marchand.ilike(term))
            | (BudgetTransaction.description.ilike(term))
        )
        .limit(limit)
    ).all()
    for t in txns:
        results.append({
            "type": "transaction",
            "label": t.marchand or t.description or "Transaction",
            "hint": _fmt_montant(t.montant, t.devise),
            "href": "/budget?tab=transactions",
        })

    # Musique
    tracks = session.exec(
        select(MusicTrack)
        .where(
            MusicTrack.title.ilike(term)
            | MusicTrack.artist.ilike(term)
            | MusicTrack.album.ilike(term)
        )
        .limit(limit)
    ).all()
    for track in tracks:
        results.append({
            "type": "musique",
            "label": track.title or track.path,
            "hint": track.artist or track.album or "Piste",
            "href": "/musique",
        })

    # Lieux de voyage
    lieux = session.exec(
        select(LieuVoyage)
        .where(
            LieuVoyage.nom.ilike(term)
            | LieuVoyage.ville.ilike(term)
            | LieuVoyage.pays.ilike(term)
        )
        .limit(limit)
    ).all()
    for lieu in lieux:
        location = ", ".join(filter(None, (lieu.ville, lieu.pays)))
        results.append({
            "type": "lieu",
            "label": lieu.nom,
            "hint": location or "Lieu",
            "href": "/voyage",
        })

    # Événements d'agenda
    events = session.exec(
        select(Evenement)
        .where(Evenement.titre.ilike(term) | Evenement.lieu.ilike(term))
        .order_by(Evenement.debut.desc())
        .limit(limit)
    ).all()
    for event in events:
        results.append({
            "type": "evenement",
            "label": event.titre,
            "hint": ("Travail · " if event.categorie == "travail" else "") + (event.debut.strftime("%d/%m/%Y") if event.debut else "Événement"),
            "href": "/agenda?tab=semaine",
        })

    # Tâches personnelles et échéances accessibles depuis la boîte Agenda.
    tasks = session.exec(
        select(Tache).where(Tache.titre.ilike(term)).order_by(Tache.deadline.asc()).limit(limit)
    ).all()
    for task in tasks:
        deadline = task.deadline.strftime("%d/%m/%Y") if task.deadline else "Sans échéance"
        results.append({
            "type": "tache",
            "label": task.titre,
            "hint": f"Tâche · {deadline}",
            "href": "/agenda?tab=jour",
        })

    # Cours et évaluations.
    courses = session.exec(
        select(Cours)
        .where(Cours.actif == True)  # noqa: E712
        .where(Cours.nom.ilike(term) | Cours.code.ilike(term))
        .limit(limit)
    ).all()
    for course in courses:
        results.append({
            "type": "cours",
            "label": course.nom,
            "hint": f"{course.code} · {course.semestre}",
            "href": "/etudes?tab=cours",
        })

    evaluations = session.exec(
        select(Evaluation).where(Evaluation.titre.ilike(term)).limit(limit)
    ).all()
    evaluation_course_ids = {evaluation.cours_id for evaluation in evaluations}
    course_names = {
        course.id: course.nom
        for course in session.exec(select(Cours).where(Cours.id.in_(evaluation_course_ids))).all()
    }
    for evaluation in evaluations:
        deadline = evaluation.date_limite.strftime("%d/%m/%Y") if evaluation.date_limite else "Sans date"
        results.append({
            "type": "evaluation",
            "label": evaluation.titre,
            "hint": f"{course_names.get(evaluation.cours_id, 'Cours')} · {deadline}",
            "href": "/etudes?tab=deadlines",
        })

    # Documents administratifs et objectifs de vie.
    documents = session.exec(
        select(Document)
        .where(Document.titre.ilike(term) | Document.organisme.ilike(term) | Document.notes.ilike(term))
        .limit(limit)
    ).all()
    for document in documents:
        results.append({
            "type": "document",
            "label": document.titre,
            "hint": document.organisme or document.type,
            "href": "/documents",
        })

    goals = session.exec(
        select(LongTermGoal)
        .where(LongTermGoal.titre.ilike(term) | LongTermGoal.categorie.ilike(term))
        .limit(limit)
    ).all()
    for goal in goals:
        results.append({
            "type": "objectif",
            "label": goal.titre,
            "hint": f"{goal.categorie} · {goal.statut}",
            "href": "/objectifs",
        })

    # Garde-robe
    vetements = session.exec(
        select(Vetement)
        .where(Vetement.nom.ilike(term) | Vetement.marque.ilike(term))
        .limit(limit)
    ).all()
    for vetement in vetements:
        results.append({
            "type": "vetement",
            "label": vetement.nom,
            "hint": vetement.marque or vetement.categorie or "Pièce",
            "href": "/garderobe",
        })

    # Recettes (module encore vide, gardé pour quand il se remplira)
    recipes = session.exec(
        select(Recipe).where(Recipe.titre.ilike(term)).limit(limit)
    ).all()
    for r in recipes:
        results.append({
            "type": "recette",
            "label": r.titre,
            "hint": "Recette",
            "href": "/cuisine",
        })

    # Livres
    books = session.exec(
        select(Book).where(
            Book.titre.ilike(term) | Book.auteur.ilike(term)
        ).limit(limit)
    ).all()
    for b in books:
        results.append({
            "type": "livre",
            "label": b.titre,
            "hint": b.auteur or "Livre",
            "href": "/livres",
        })

    query = q.strip().casefold()
    results.sort(key=lambda item: _relevance(item, query))
    return {"results": results[:limit * 2]}
