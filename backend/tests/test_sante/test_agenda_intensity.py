import datetime as dt

from app.services.sante.agenda_intensity import classify_agenda_events

DAY = dt.date(2026, 7, 17)


def _event(start: int, end: int, category: str):
    return {
        "debut": dt.datetime.combine(DAY, dt.time(start)),
        "fin": dt.datetime.combine(DAY, dt.time(end)),
        "categorie": category,
    }


def test_long_workday_is_low_not_sport_equivalent():
    result = classify_agenda_events([_event(9, 17, "travail")], DAY)
    assert result["intensity"] == "low"
    assert result["categories_minutes"] == {"travail": 480}


def test_busy_work_and_study_day_is_medium():
    result = classify_agenda_events(
        [_event(8, 17, "travail"), _event(18, 21, "études")], DAY,
    )
    assert result["intensity"] == "medium"
    assert result["scheduled_minutes"] == 720


def test_one_hour_sport_makes_agenda_load_medium():
    result = classify_agenda_events([_event(18, 19, "sport")], DAY)
    assert result["intensity"] == "medium"


def test_event_is_clipped_to_requested_day():
    result = classify_agenda_events([{
        "debut": dt.datetime(2026, 7, 16, 23),
        "fin": dt.datetime(2026, 7, 17, 2),
        "categorie": "travail",
    }], DAY)
    assert result["scheduled_minutes"] == 120
