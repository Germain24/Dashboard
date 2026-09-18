from __future__ import annotations

import datetime as dt
import queue
from concurrent.futures import ThreadPoolExecutor

from app.core.realtime import RealtimeBus


def test_event_ids_are_ordered_across_threads():
    bus = RealtimeBus(history_size=500, subscriber_size=500)
    subscriber = bus.subscribe()

    with ThreadPoolExecutor(max_workers=8) as pool:
        events = list(pool.map(lambda n: bus.publish("test", data={"n": n}), range(200)))

    ids = sorted(event.id for event in events)
    assert ids == list(range(1, 201))
    received = [subscriber.events.get_nowait().id for _ in range(200)]
    assert received == sorted(received)


def test_replay_after_last_event_id_and_unsubscribe():
    bus = RealtimeBus()
    for n in range(5):
        bus.publish("test", data=n)

    subscriber = bus.subscribe(last_event_id=3)
    assert [subscriber.events.get_nowait().id for _ in range(2)] == [4, 5]
    bus.unsubscribe(subscriber)
    bus.publish("test", data=6)
    with __import__("pytest").raises(queue.Empty):
        subscriber.events.get_nowait()
    assert bus.subscriber_count == 0


def test_lost_history_and_slow_consumer_require_one_resync():
    history_bus = RealtimeBus(history_size=2)
    for n in range(4):
        history_bus.publish("test", data=n)
    replay = history_bus.subscribe(last_event_id=1).events.get_nowait()
    assert replay.topic == "resync_required"
    assert replay.data == {"reason": "history_lost"}

    slow_bus = RealtimeBus(subscriber_size=2)
    slow = slow_bus.subscribe()
    slow_bus.publish("test", data=1)
    slow_bus.publish("test", data=2)
    slow_bus.publish("test", data=3)
    event = slow.events.get_nowait()
    assert event.topic == "resync_required"
    assert event.data == {"reason": "slow_consumer"}


def test_sse_route_is_exposed_in_openapi():
    from app.main import create_app

    schema = create_app().openapi()
    response = schema["paths"]["/api/v1/events"]["get"]["responses"]["200"]
    assert response["description"] == "Successful Response"


def test_commits_publish_domain_invalidations(mem_session):
    from app.core.realtime import realtime_bus
    from app.models.scheduler import JobRun, Notification

    subscriber = realtime_bus.subscribe()
    try:
        mem_session.add(Notification(titre="Terminé"))
        mem_session.add(JobRun(job_id="daily", started_at=dt.datetime.now(dt.timezone.utc)))
        mem_session.commit()

        events = [subscriber.events.get_nowait(), subscriber.events.get_nowait()]
        assert {event.topic for event in events} == {"jobs.changed", "notifications.changed"}
        assert {tuple(event.invalidate[0]) for event in events} == {
            ("jobs",),
            ("notifications",),
        }
    finally:
        realtime_bus.unsubscribe(subscriber)
