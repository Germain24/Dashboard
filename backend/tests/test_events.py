"""Tests du bus d'événements interne (#202)."""

from __future__ import annotations

import pytest

from app.core.events import Event, EventBus, Events


def test_subscribe_and_publish_delivers_event():
    bus = EventBus()
    recu: list[Event] = []
    bus.subscribe("budget.transaction_created", recu.append)

    delivered = bus.emit("budget.transaction_created", montant=-42.0, marchand="METRO")

    assert delivered == 1
    assert len(recu) == 1
    assert recu[0].name == "budget.transaction_created"
    assert recu[0].payload == {"montant": -42.0, "marchand": "METRO"}


def test_multiple_handlers_all_receive():
    bus = EventBus()
    a: list[Event] = []
    b: list[Event] = []
    bus.subscribe("x", a.append)
    bus.subscribe("x", b.append)

    delivered = bus.emit("x")

    assert delivered == 2
    assert len(a) == 1 and len(b) == 1


def test_handler_only_receives_its_own_event():
    bus = EventBus()
    recu: list[Event] = []
    bus.subscribe("a", recu.append)

    bus.emit("b")

    assert recu == []


def test_wildcard_handler_receives_all_events():
    bus = EventBus()
    seen: list[str] = []
    bus.subscribe(EventBus.WILDCARD, lambda e: seen.append(e.name))

    bus.emit("a")
    bus.emit("b")

    assert seen == ["a", "b"]


def test_unsubscribe_stops_delivery():
    bus = EventBus()
    recu: list[Event] = []
    unsubscribe = bus.subscribe("x", recu.append)

    bus.emit("x")
    unsubscribe()
    bus.emit("x")

    assert len(recu) == 1


def test_failing_handler_is_isolated():
    """Un handler qui lève n'empêche pas les autres de recevoir l'événement."""
    bus = EventBus()
    recu: list[Event] = []

    def boom(_event: Event) -> None:
        raise RuntimeError("handler cassé")

    bus.subscribe("x", boom)
    bus.subscribe("x", recu.append)

    delivered = bus.emit("x")

    # boom échoue, le second handler reçoit quand même → 1 livraison réussie
    assert delivered == 1
    assert len(recu) == 1


def test_clear_removes_all_subscriptions():
    bus = EventBus()
    recu: list[Event] = []
    bus.subscribe("x", recu.append)

    bus.clear()
    bus.emit("x")

    assert recu == []


def test_event_has_utc_timestamp():
    e = Event(name="x")
    assert e.at.tzinfo is not None
    assert e.payload == {}


def test_event_names_constants_are_namespaced():
    # Les constantes documentent les événements métier publiés par les modules.
    assert Events.BUDGET_TRANSACTION_CREATED == "budget.transaction_created"
    assert "." in Events.SANTE_WEIGHT_LOGGED
    assert "." in Events.ENTRAINEMENT_WORKOUT_LOGGED


def test_global_bus_is_shared_singleton():
    from app.core.events import bus as bus1
    from app.core.events import bus as bus2

    assert bus1 is bus2


@pytest.fixture(autouse=True)
def _reset_global_bus():
    """Évite les fuites d'abonnements entre tests sur le bus global."""
    from app.core.events import bus

    yield
    bus.clear()


def test_create_transaction_emits_event(mem_session):
    """Câblage de référence : créer une transaction publie l'événement métier."""
    import datetime as dt

    from app.core.events import Events, bus
    from app.services.budget.transactions import create_transaction

    recu: list[Event] = []
    bus.subscribe(Events.BUDGET_TRANSACTION_CREATED, recu.append)

    create_transaction(mem_session, dt.date(2026, 6, 10), -42.0, "METRO")

    assert len(recu) == 1
    assert recu[0].payload["montant"] == -42.0
    assert recu[0].payload["marchand"] == "METRO"
    assert recu[0].payload["date"] == "2026-06-10"
