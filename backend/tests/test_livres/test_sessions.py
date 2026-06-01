from app.services.livres.sessions import LECTURE_HABIT_MIN


def test_lecture_habit_threshold():
    assert LECTURE_HABIT_MIN == 30


def test_triggers_at_threshold():
    assert 30 >= LECTURE_HABIT_MIN
    assert 45 >= LECTURE_HABIT_MIN
    assert 29 < LECTURE_HABIT_MIN
