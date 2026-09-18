"""GET /buffett/progress ne doit jamais reclasser un run "en_cours" en
"termine" seulement parce que le scoring des tickers est a 100% -- seul
finalize_run() (appele apres la PIPELINE COMPLETE, scoring + optimisation DE
+ persistance de l'allocation) a le droit de marquer "termine". Avant ce
correctif, un run dont le DE etait tue en vol (crash, redemarrage --reload)
etait reclasse "termine" au prochain poll, sans portefeuille et sans erreur
visible (#bug rapporte : "l'analyse DE s'est arretee seule")."""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.core.db import get_session
from app.main import create_app
from app.models.finance import BuffettRun


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as c:
        c.engine = engine  # type: ignore[attr-defined]
        yield c


def test_dead_run_with_scoring_done_is_marked_interrompu_not_termine(client):
    with Session(client.engine) as s:
        run = BuffettRun(run_date=dt.date.today(), statut="en_cours",
                          n_tickers_total=100, n_tickers_analyzed=100)
        s.add(run)
        s.commit()
        s.refresh(run)
        run_id = run.id

    r = client.get("/finance/buffett/progress")
    assert r.status_code == 200
    assert r.json()["statut"] == "interrompu"

    with Session(client.engine) as s:
        refreshed = s.get(BuffettRun, run_id)
        assert refreshed.statut == "interrompu"
        assert refreshed.erreur == "Process interrompu (relancez pour reprendre)"


def test_already_interrompu_run_is_left_untouched(client):
    with Session(client.engine) as s:
        run = BuffettRun(run_date=dt.date.today(), statut="interrompu",
                          n_tickers_total=100, n_tickers_analyzed=100,
                          erreur="Process interrompu (relancez pour reprendre)")
        s.add(run)
        s.commit()
        s.refresh(run)
        run_id = run.id

    r = client.get("/finance/buffett/progress")
    assert r.status_code == 200
    assert r.json()["statut"] == "interrompu"

    with Session(client.engine) as s:
        refreshed = s.get(BuffettRun, run_id)
        assert refreshed.statut == "interrompu"  # jamais reclasse "termine"


def test_partially_scored_run_still_marked_interrompu(client):
    """Non-regression du comportement existant : un run interrompu AVANT la
    fin du scoring (n_analyzed < n_total) reste 'interrompu'."""
    with Session(client.engine) as s:
        run = BuffettRun(run_date=dt.date.today(), statut="en_cours",
                          n_tickers_total=100, n_tickers_analyzed=42)
        s.add(run)
        s.commit()

    r = client.get("/finance/buffett/progress")
    assert r.json()["statut"] == "interrompu"


def test_active_progress_state_does_not_duplicate_rest_fields(client, monkeypatch):
    """Le snapshot SSE contient les mêmes champs structurants que la réponse REST."""
    from app.services.finance import scheduler_stub
    from app.services.finance.buffett import progress_state

    with Session(client.engine) as session:
        run = BuffettRun(
            run_date=dt.date.today(),
            statut="en_cours",
            n_tickers_total=100,
            n_tickers_analyzed=42,
            progress_pct=42.0,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id

    monkeypatch.setattr(scheduler_stub, "is_analysis_running", lambda: True)
    progress_state.start(run_id=run_id, total=100)
    progress_state.update(done=43, total=100)
    try:
        response = client.get("/finance/buffett/progress")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        # La DB demeure autoritaire pour le REST; le 43 en mémoire est réservé
        # à l'événement direct jusqu'au prochain commit.
        assert data["n_done"] == 42
        assert data["progress_pct"] == 42.0
    finally:
        progress_state.finish()
