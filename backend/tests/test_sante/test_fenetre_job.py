"""Génération asynchrone de la fenêtre (job en mémoire + interrogation)."""
from __future__ import annotations

import time

import pytest

from app.services.sante import fenetre_job


@pytest.fixture(autouse=True)
def _reset():
    fenetre_job._reset_for_tests()
    yield
    fenetre_job._reset_for_tests()


def _attendre_fin(job_id: str, timeout: float = 10.0) -> dict:
    limite = time.time() + timeout
    while time.time() < limite:
        job = fenetre_job.get_generate(job_id)
        assert job is not None
        if job["status"] in ("completed", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError("le job ne s'est jamais terminé")


def test_un_job_rend_immediatement_un_identifiant(monkeypatch):
    monkeypatch.setattr(fenetre_job, "_run", lambda *a, **k: None)
    job, cree = fenetre_job.start_generate()
    assert cree is True
    assert job["job_id"]
    assert job["status"] == "queued"


def test_un_echec_est_rapporte_sans_faire_tomber_le_thread(monkeypatch):
    """Une génération impossible (aucun poids connu, par exemple) doit remonter
    proprement au client, pas mourir en silence dans le thread."""
    import app.services.sante.fenetre_service as fs

    def boom(*_a, **_k):
        raise ValueError("Aucun poids connu et aucun poids fourni.")

    monkeypatch.setattr(fs, "generate_window", boom)
    job, _ = fenetre_job.start_generate()
    fini = _attendre_fin(job["job_id"])
    assert fini["status"] == "failed"
    assert "poids" in fini["error"]


def test_deux_demandes_rapprochees_ne_lancent_qu_une_optimisation(monkeypatch):
    """Deux clics sur « Générer » ne doivent pas lancer deux SLSQP concurrents :
    ils se voleraient le CPU et doubleraient le temps des deux."""
    demarrages = []

    def lent(job_id, *_a, **_k):
        demarrages.append(job_id)
        time.sleep(0.4)
        fenetre_job._update(job_id, status="completed", message="fini")

    monkeypatch.setattr(fenetre_job, "_run", lent)
    premier, cree1 = fenetre_job.start_generate()
    time.sleep(0.05)
    second, cree2 = fenetre_job.start_generate()

    assert cree1 is True
    assert cree2 is False, "le second appel doit rejoindre le job en cours"
    assert premier["job_id"] == second["job_id"]
    _attendre_fin(premier["job_id"])
    assert len(demarrages) == 1


def test_un_job_inconnu_est_introuvable():
    assert fenetre_job.get_generate("inexistant") is None


def test_arret_cooperatif_est_memorise(monkeypatch):
    monkeypatch.setattr(fenetre_job, "_run", lambda *a, **k: None)
    job, _ = fenetre_job.start_generate()
    stopped = fenetre_job.request_stop(job["job_id"])
    assert stopped is not None
    assert stopped["stop_requested"] is True
    assert "Arrêt demandé" in stopped["message"]

    # Régression : le callback de progression de l'essai en cours envoyait
    # encore stop_requested=False et annulait silencieusement le clic.
    fenetre_job._update(
        job["job_id"], status="running", stop_requested=False,
        message="Nouvelle progression",
    )
    after_progress = fenetre_job.get_generate(job["job_id"])
    assert after_progress is not None
    assert after_progress["stop_requested"] is True


def test_job_actif_peut_etre_rejoint_apres_navigation(monkeypatch):
    monkeypatch.setattr(fenetre_job, "_run", lambda *a, **k: None)
    job, _ = fenetre_job.start_generate()
    active = fenetre_job.get_active_generate()
    assert active is not None
    assert active["job_id"] == job["job_id"]


def test_un_nouveau_job_est_possible_une_fois_le_precedent_fini(monkeypatch):
    monkeypatch.setattr(
        fenetre_job, "_run",
        lambda job_id, *a, **k: fenetre_job._update(job_id, status="completed"),
    )
    premier, _ = fenetre_job.start_generate()
    _attendre_fin(premier["job_id"])
    second, cree = fenetre_job.start_generate()
    assert cree is True
    assert second["job_id"] != premier["job_id"]
