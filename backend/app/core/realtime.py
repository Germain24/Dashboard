"""Bus d'événements temps réel en mémoire pour le dashboard.

Le déploiement actuel utilise un seul worker. Le bus est donc volontairement
local au processus, mais reste sûr pour les threads FastAPI, APScheduler et
Finance.
"""

from __future__ import annotations

import itertools
import queue
import threading
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class RealtimeEvent:
    id: int
    topic: str
    timestamp: str
    data: Any = None
    invalidate: list[list[str]] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(eq=False)
class Subscription:
    events: queue.Queue[RealtimeEvent]
    closed: bool = False


class RealtimeBus:
    """Historique borné + fan-out non bloquant vers des files bornées."""

    def __init__(self, *, history_size: int = 2_000, subscriber_size: int = 512) -> None:
        self._history: deque[RealtimeEvent] = deque(maxlen=history_size)
        self._subscribers: set[Subscription] = set()
        self._ids = itertools.count(1)
        self._subscriber_size = subscriber_size
        self._lock = threading.RLock()

    def publish(
        self,
        topic: str,
        *,
        data: Any = None,
        invalidate: list[list[str]] | None = None,
    ) -> RealtimeEvent:
        with self._lock:
            event = RealtimeEvent(
                id=next(self._ids),
                topic=topic,
                timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                data=data,
                invalidate=invalidate,
            )
            self._history.append(event)
            for subscriber in tuple(self._subscribers):
                if subscriber.closed:
                    self._subscribers.discard(subscriber)
                    continue
                try:
                    subscriber.events.put_nowait(event)
                except queue.Full:
                    # Un onglet suspendu ne doit jamais ralentir un producteur.
                    # On jette son retard et lui demande une resynchronisation unique.
                    while True:
                        try:
                            subscriber.events.get_nowait()
                        except queue.Empty:
                            break
                    subscriber.events.put_nowait(
                        RealtimeEvent(
                            id=event.id,
                            topic="resync_required",
                            timestamp=event.timestamp,
                            data={"reason": "slow_consumer"},
                        )
                    )
            return event

    def subscribe(self, last_event_id: int | None = None) -> Subscription:
        subscriber = Subscription(queue.Queue(maxsize=self._subscriber_size))
        with self._lock:
            if last_event_id is not None and self._history:
                oldest = self._history[0].id
                replay = [event for event in self._history if event.id > last_event_id]
                if last_event_id < oldest - 1 or len(replay) > self._subscriber_size:
                    newest = self._history[-1]
                    subscriber.events.put_nowait(
                        RealtimeEvent(
                            id=newest.id,
                            topic="resync_required",
                            timestamp=newest.timestamp,
                            data={"reason": "history_lost"},
                        )
                    )
                else:
                    for event in replay:
                        subscriber.events.put_nowait(event)
            self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: Subscription) -> None:
        with self._lock:
            subscriber.closed = True
            self._subscribers.discard(subscriber)

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)


realtime_bus = RealtimeBus()


def publish(
    topic: str,
    *,
    data: Any = None,
    invalidate: list[list[str]] | None = None,
) -> RealtimeEvent:
    """Point d'entrée court utilisable depuis n'importe quel thread."""
    return realtime_bus.publish(topic, data=data, invalidate=invalidate)
