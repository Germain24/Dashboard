from app.services.budget.rules import apply_rules_pure


def test_no_match():
    rules = [{"pattern": "STARBUCKS", "category_id": 1, "priorite": 0}]
    assert apply_rules_pure("METRO GROCERY", rules) is None


def test_match_case_insensitive():
    rules = [{"pattern": "starbucks", "category_id": 1, "priorite": 0}]
    assert apply_rules_pure("STARBUCKS #42", rules) == 1


def test_priority_order():
    rules = [
        {"pattern": "METRO", "category_id": 2, "priorite": 0},
        {"pattern": "METRO", "category_id": 1, "priorite": 10},
    ]
    assert apply_rules_pure("METRO", rules) == 1
