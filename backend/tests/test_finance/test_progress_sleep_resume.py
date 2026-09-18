from app.services.finance.buffett import progress_state


def test_sleep_gap_is_excluded_and_network_session_rotated(monkeypatch):
    ticks = iter([100.0, 100.0, 400.0, 400.0])
    monkeypatch.setattr(progress_state.time, "monotonic", lambda: next(ticks))
    rotated = []
    monkeypatch.setattr(
        "app.services.finance.yf_session.rotate_session",
        lambda: rotated.append(True),
    )
    progress_state.start(run_id=1, total=10)
    progress_state.update(done=1)
    snap = progress_state.snapshot()
    assert rotated == [True]
    assert snap["throughput_per_min"] > 0
