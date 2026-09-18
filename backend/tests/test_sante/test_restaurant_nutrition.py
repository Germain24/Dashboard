import pandas as pd

from app.services.sante.fenetre_service import _estimate_restaurant_micros


def test_estimates_work_meal_micros_from_ingredient_proxy_rows():
    df = pd.DataFrame(
        {"Omega 3": [2.5], "Selenium": [40.0], "VitD": [10.0], "Proteines": [20.0]},
        index=["Saumon atlantique"],
    )
    meal = {
        "items": [{
            "ingredients_micro_estimes": [
                {"aliment": "Saumon atlantique", "quantite_g": 120},
            ],
        }],
    }

    micros = _estimate_restaurant_micros(
        meal, df, {"Omega3", "Sélénium", "VitD", "Protéines"})

    assert micros == {"Omega3": 3.0, "Sélénium": 48.0, "VitD": 12.0}
    assert meal["micros_estimes"] is True

