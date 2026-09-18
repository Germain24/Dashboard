import datetime as dt

from app.services.agenda import auto_plan


def test_gather_inputs_includes_work_after_the_cycle_for_overnight_sleep(monkeypatch):
    run_date = dt.date(2026, 9, 14)  # lundi : cycle mardi-mercredi
    next_day = dt.date(2026, 9, 17)  # jeudi, après le dernier jour du cycle
    shift = {
        "titre": "Shift matin",
        "debut": dt.datetime(2026, 9, 17, 7, 30),
        "fin": dt.datetime(2026, 9, 17, 16, 30),
        "source": "ical",
        "categorie": "travail",
    }
    captured = {}

    def fake_calendar(_session, start, end):
        captured["start"] = start
        captured["end"] = end
        return [shift]

    monkeypatch.setattr(auto_plan, "get_full_calendar", fake_calendar)
    monkeypatch.setattr(
        "app.services.travail.shifts.list_shifts_for_window",
        lambda *_args: [],
    )

    fixed, _revisions = auto_plan.gather_inputs(None, run_date)

    assert captured["end"] == dt.datetime(2026, 9, 17, 23, 59, 59, 999999)
    assert fixed[next_day] == [(shift["debut"], shift["fin"])]
