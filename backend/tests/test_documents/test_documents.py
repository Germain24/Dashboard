"""Tests module Documents (#548)."""

import datetime as dt

import pytest
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.services.documents import (
    classify_expiry,
    create_document,
    delete_document,
    get_documents,
    update_document,
    upcoming_expirations,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


# ── classify_expiry ──────────────────────────────────────────────────────────

def test_classify_expired():
    past = dt.date(2020, 1, 1)
    assert classify_expiry(past) == "expired"

def test_classify_warning():
    soon = dt.date.today() + dt.timedelta(days=20)
    assert classify_expiry(soon) == "warning"

def test_classify_ok():
    future = dt.date.today() + dt.timedelta(days=100)
    assert classify_expiry(future) == "ok"

def test_classify_no_date():
    assert classify_expiry(None) == "no_date"


# ── CRUD ─────────────────────────────────────────────────────────────────────

def test_create_and_list(session):
    create_document(session, titre="CNI", type="cni")
    create_document(session, titre="Passeport", type="passeport")
    docs = get_documents(session)
    assert len(docs) == 2

def test_filter_by_type(session):
    create_document(session, titre="Contrat loyer", type="contrat")
    create_document(session, titre="CNI", type="cni")
    contrats = get_documents(session, type="contrat")
    assert len(contrats) == 1

def test_update(session):
    doc = create_document(session, titre="CNI", type="cni")
    updated = update_document(session, doc.id, {"notes": "Expire dans 2 ans"})
    assert updated.notes == "Expire dans 2 ans"

def test_delete(session):
    doc = create_document(session, titre="CNI", type="cni")
    assert delete_document(session, doc.id) is True
    assert get_documents(session) == []

def test_delete_not_found(session):
    assert delete_document(session, 9999) is False


# ── upcoming_expirations ──────────────────────────────────────────────────────

def test_upcoming_expirations(session):
    today = dt.date.today()
    create_document(session, titre="CNI", type="cni", date_expiration=today + dt.timedelta(days=10))
    create_document(session, titre="Passeport", type="passeport", date_expiration=today + dt.timedelta(days=200))
    create_document(session, titre="Contrat", type="contrat")  # pas de date

    exp = upcoming_expirations(session, days=30)
    assert len(exp) == 1
    assert exp[0].titre == "CNI"

def test_upcoming_includes_expired(session):
    past = dt.date.today() - dt.timedelta(days=5)
    create_document(session, titre="CNI périmée", type="cni", date_expiration=past)
    exp = upcoming_expirations(session, days=30)
    assert len(exp) == 1
