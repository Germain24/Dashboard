"""Recherche globale : devise réelle et extension aux modules alimentés.

Audit §2.D : le montant était formaté « € » en dur alors que les 887
transactions sont en CAD (« −11.30 € » pour un achat montréalais), et la
recherche ignorait Musique/Voyage/Agenda/Garde-robe pourtant remplis.
"""

from __future__ import annotations

import datetime as dt

from app.api.search import global_search
from app.models.agenda import Evenement, Tache
from app.models.budget import BudgetTransaction
from app.models.documents import Document
from app.models.etudes import Cours, Evaluation
from app.models.garderobe import Vetement
from app.models.musique import MusicTrack
from app.models.voyage import LieuVoyage


def _labels_by_type(results: list[dict]) -> dict[str, dict]:
    return {r["type"]: r for r in results}


def test_transaction_hint_uses_real_currency_not_hardcoded_euro(mem_session):
    mem_session.add(BudgetTransaction(
        date=dt.date(2026, 1, 5), montant=-11.30,
        marchand="SUPER C MONTREAL QC", devise="CAD",
    ))
    mem_session.commit()

    results = global_search("super c", session=mem_session)["results"]

    hint = _labels_by_type(results)["transaction"]["hint"]
    assert "€" not in hint
    assert hint == "-11.30 $"


def test_search_covers_music_voyage_agenda_and_garderobe(mem_session):
    mem_session.add(MusicTrack(path="a.flac", title="Nocturne", artist="Chopin"))
    mem_session.add(LieuVoyage(nom="Nocturne Bar", ville="Kyoto", pays="Japon"))
    mem_session.add(Evenement(titre="Nocturne concert", debut=dt.datetime(2026, 3, 1, 20)))
    mem_session.add(Vetement(id=1, nom="Veste Nocturne", categorie="Veste", marque="Uniqlo"))
    mem_session.commit()

    results = global_search("nocturne", limit=10, session=mem_session)["results"]
    by_type = _labels_by_type(results)

    assert by_type["musique"]["hint"] == "Chopin"
    assert by_type["lieu"]["hint"] == "Kyoto, Japon"
    assert by_type["vetement"]["label"] == "Veste Nocturne"
    assert by_type["evenement"]["type"] == "evenement"


def test_search_ranks_exact_matches_before_earlier_module_substring_matches(mem_session):
    mem_session.add_all([
        BudgetTransaction(
            date=dt.date(2026, 1, 5), montant=-10, marchand="Autre Examen", devise="CAD"
        ),
        MusicTrack(path="examen.flac", title="Examen", artist="Artiste"),
    ])
    mem_session.commit()

    results = global_search("examen", limit=1, session=mem_session)["results"]

    assert len(results) == 2
    assert results[0]["type"] == "musique"
    assert results[0]["label"] == "Examen"


def test_short_query_returns_nothing(mem_session):
    assert global_search("a", session=mem_session)["results"] == []


def test_search_finds_tasks_study_deadlines_and_documents(mem_session):
    course = Cours(code="ECO101", nom="Économie appliquée", semestre="A2026")
    mem_session.add(course)
    mem_session.commit()
    mem_session.refresh(course)
    mem_session.add_all([
        Tache(titre="Réviser l'examen d'économie", categorie="etudes"),
        Evaluation(cours_id=course.id, titre="Examen final", type_eval="exam"),
        Document(titre="Contrat de travail", organisme="7shifts"),
    ])
    mem_session.commit()

    results = global_search("examen", limit=10, session=mem_session)["results"]
    by_type = _labels_by_type(results)
    assert by_type["tache"]["href"] == "/agenda?tab=jour"
    assert by_type["evaluation"]["href"] == "/etudes?tab=deadlines"

    documents = global_search("travail", limit=10, session=mem_session)["results"]
    assert any(item["type"] == "document" for item in documents)
