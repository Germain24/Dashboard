"""One thread-safe network allowance shared by all ETF preparation waves."""
from __future__ import annotations

import threading
import time

from .config import Config


class ResearchBudgetExceeded(RuntimeError):
    """Deferred work, not evidence that a composition is unavailable."""


class EtfResearchBudget:
    def __init__(self, *, seconds=None, requests=None, funds=None, indices=None):
        self.seconds = Config.ETF_RESEARCH_SECONDS if seconds is None else seconds
        self.max_requests = Config.ETF_RESEARCH_REQUESTS if requests is None else requests
        self.limits = {
            "fund": Config.ETF_RESEARCH_FUNDS if funds is None else funds,
            "index": Config.ETF_RESEARCH_INDICES if indices is None else indices,
        }
        self.seen = {"fund": set(), "index": set()}
        self.requests = 0
        self.started = None
        self.lock = threading.Lock()

    def remaining(self):
        return max(0.0, self.seconds - (time.monotonic() - self.started)) if self.started is not None else self.seconds

    def exhausted(self):
        return self.remaining() <= 0 or self.requests >= self.max_requests

    def claim(self, kind, identity):
        with self.lock:
            if self.exhausted() or identity in self.seen[kind] or len(self.seen[kind]) >= self.limits[kind]:
                return False
            if self.started is None:
                self.started = time.monotonic()
            self.seen[kind].add(identity)
            return True

    def before_request(self):
        with self.lock:
            if self.exhausted():
                raise ResearchBudgetExceeded("Budget global ETF atteint; recherche différée")
            if self.started is None:
                self.started = time.monotonic()
            self.requests += 1
            return max(0.01, min(10.0, self.remaining()))

    def snapshot(self):
        return {"requests": self.requests, "funds": len(self.seen["fund"]),
                "indices": len(self.seen["index"]), "exhausted": self.exhausted(),
                "limits": {"seconds": self.seconds, "requests": self.max_requests, **self.limits},
                "remaining_seconds": round(self.remaining(), 1)}


class BudgetClient:
    def __init__(self, client, budget):
        self.client, self.budget = client, budget

    def get(self, url, **kwargs):
        kwargs["timeout"] = self.budget.before_request()
        return self.client.get(url, **kwargs)

    def post(self, url, **kwargs):
        kwargs["timeout"] = self.budget.before_request()
        return self.client.post(url, **kwargs)

    def __getattr__(self, name):
        return getattr(self.client, name)
