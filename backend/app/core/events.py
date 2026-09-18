"""Bus d'événements interne en mémoire (#202).

Permet de réagir à un événement métier (nouvelle transaction, poids saisi,
séance loggée…) et pas seulement au cron. C'est la fondation des
automatisations de la section T : les routines (#201), briefings (#203/#204)
et la détection d'anomalies (#213) s'abonnent à ces événements.

Choix d'implémentation : synchrone, mono-process (cohérent avec le cache #11 et
le rate limit #193). Les handlers sont appelés en ligne lors du `publish` ;
un handler qui échoue est isolé (les autres reçoivent quand même l'événement)
et l'exception est journalisée, jamais propagée à l'émetteur métier.

Pour un usage multi-process, brancher un broker (Redis pub/sub) derrière la
même API `subscribe`/`publish`.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Event:
    """Un événement métier immuable."""

    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


Handler = Callable[[Event], None]


class Events:
    """Noms canoniques des événements métier (namespace `module.action`).

    Centralisés ici pour éviter les chaînes magiques et documenter ce que
    chaque module publie. Ajouter une constante en câblant un nouvel émetteur.
    """

    BUDGET_TRANSACTION_CREATED = "budget.transaction_created"
    SANTE_WEIGHT_LOGGED = "sante.weight_logged"
    ENTRAINEMENT_WORKOUT_LOGGED = "entrainement.workout_logged"
    HABITUDE_CHECKED = "habitudes.checked"
    AGENDA_EVENT_CREATED = "agenda.event_created"


class EventBus:
    """Bus publish/subscribe thread-safe en mémoire."""

    WILDCARD = "*"

    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_name: str, handler: Handler) -> Callable[[], None]:
        """Abonne `handler` à `event_name` (ou ``WILDCARD`` pour tout).

        Renvoie une fonction de désabonnement.
        """
        with self._lock:
            self._subs.setdefault(event_name, []).append(handler)

        def unsubscribe() -> None:
            with self._lock:
                handlers = self._subs.get(event_name)
                if handlers and handler in handlers:
                    handlers.remove(handler)

        return unsubscribe

    def publish(self, event: Event) -> int:
        """Distribue `event` aux abonnés ; renvoie le nombre de livraisons réussies."""
        # Snapshot sous verrou : un handler peut (dés)abonner pendant la diffusion.
        with self._lock:
            handlers = list(self._subs.get(event.name, []))
            handlers += list(self._subs.get(self.WILDCARD, []))

        delivered = 0
        for handler in handlers:
            try:
                handler(event)
                delivered += 1
            except Exception:  # isolation : un handler cassé n'impacte pas les autres
                logger.exception("event handler failed for %s", event.name)
        return delivered

    def emit(self, name: str, **payload: Any) -> int:
        """Raccourci : construit et publie un :class:`Event`."""
        return self.publish(Event(name=name, payload=payload))

    def clear(self) -> None:
        """Supprime tous les abonnements (utile en tests)."""
        with self._lock:
            self._subs.clear()


# Bus global partagé par l'application.
bus = EventBus()
