from app.models.voyage import LieuVoyage
from app.services.voyage.costs import cost_breakdown


def test_historical_daily_cost_is_split_without_double_counting():
    lieu = LieuVoyage(
        nom="Ville", cout_jour_estime=100, jours_min=2, jours_max=4,
    )
    costs = cost_breakdown(lieu, days=3)
    assert costs["hebergement"] == 195
    assert costs["nourriture"] == 105
    assert costs["hebergement"] + costs["nourriture"] == 300
    assert costs["activite"] > 0
    assert costs["transport_local"] > 0


def test_explicit_costs_override_fallbacks():
    lieu = LieuVoyage(
        nom="Musée", cout_jour_estime=100, jours_min=2, jours_max=4,
        cout_hebergement_jour=70, cout_nourriture_jour=45,
        cout_activite=55, cout_transport_local=30,
    )
    costs = cost_breakdown(lieu, days=2)
    assert costs["hebergement"] == 140
    assert costs["nourriture"] == 90
    assert costs["activite"] == 55
    assert costs["transport_local"] == 30
    assert costs["source_journalier"] == "renseigné"
    assert costs["source_activite"] == "renseigné"

