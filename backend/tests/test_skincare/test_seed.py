import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.services.skincare.products import seed_skincare, list_products


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_seed_is_idempotent(session):
    seed_skincare(session)
    n1 = len(list_products(session))
    seed_skincare(session)
    n2 = len(list_products(session))
    assert n1 > 0
    assert n1 == n2  # pas de doublons au second appel
