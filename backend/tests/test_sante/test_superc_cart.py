from app.services.sante import superc_cart


class _NoopThread:
    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        return None


def test_start_is_singleton_and_sanitizes_items(monkeypatch):
    superc_cart._reset_for_tests()
    captured = {}

    class CaptureThread:
        def __init__(self, *, target, args, **kwargs):
            captured["args"] = args

        def start(self):
            return None

    monkeypatch.setattr(superc_cart.threading, "Thread", CaptureThread)
    first, created = superc_cart.start_cart_fill(
        [{"aliment": "Riz", "href": "https://evil.test", "qty": 0}],
        "2026-08-03",
    )
    second, created_again = superc_cart.start_cart_fill([], "2026-08-03")

    assert created is True
    assert created_again is False
    assert second["job_id"] == first["job_id"]
    assert captured["args"][1][0]["href"] is None
    assert captured["args"][1][0]["qty"] == 1


def test_events_build_product_report(monkeypatch):
    superc_cart._reset_for_tests()
    monkeypatch.setattr(superc_cart.threading, "Thread", _NoopThread)
    job, _ = superc_cart.start_cart_fill([], "2026-08-03")
    job_id = job["job_id"]

    superc_cart._consume_event(job_id, {
        "type": "status", "status": "running", "current": 0, "total": 1,
        "message": "Ajout…",
    })
    superc_cart._consume_event(job_id, {
        "type": "item",
        "result": {"aliment": "Riz", "status": "added", "added_qty": 2},
    })
    superc_cart._consume_event(job_id, {"type": "done", "message": "Panier prêt."})

    state = superc_cart.get_cart_fill(job_id)
    assert state is not None
    assert state["status"] == "completed"
    assert state["current"] == 1
    assert state["results"][0]["added_qty"] == 2
