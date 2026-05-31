from app.services.cuisine.macros import compute_macros_for_portion


def test_empty_ingredients():
    result = compute_macros_for_portion([], portions=4)
    assert result == {"calories": 0.0, "proteines": 0.0, "glucides": 0.0, "lipides": 0.0}


def test_per_portion():
    ingredients = [{"quantite_g": 200, "calories_100g": 165, "proteines_100g": 31,
                    "glucides_100g": 0, "lipides_100g": 3.6}]
    result = compute_macros_for_portion(ingredients, portions=4)
    assert abs(result["calories"] - 82.5) < 0.1
    assert abs(result["proteines"] - 15.5) < 0.1


def test_single_portion():
    ingredients = [{"quantite_g": 100, "calories_100g": 200, "proteines_100g": 20,
                    "glucides_100g": 10, "lipides_100g": 5}]
    result = compute_macros_for_portion(ingredients, portions=1)
    assert result["calories"] == 200.0
