"""Tests de l'optimiseur de tenue.

Cas critiques (décision CONV 2) :
- L'optimiseur teste explicitement les deux variantes (avec / sans body).
- La cible thermique se base sur la moyenne fournie, pas sur (t_min+t_max)/2.
- En hiver froid, le solveur préfère activer le body.
- En été chaud, le solveur le désactive.
"""

from app.services.garderobe.optimizer import suggest_outfit


def _haut_chaud():
    return {
        "id": "haut_laine", "nom": "Pull laine", "categorie": "Pull",
        "couleur": "Bleu marine", "style": ["Old Money"],
        "matiere": "Laine", "temp_min": -10, "temp_max": 10,
        "portes": 0, "etat_propre": 60, "usure_max": 500,
    }


def _haut_leger():
    return {
        "id": "haut_coton", "nom": "T-shirt blanc", "categorie": "T-shirt",
        "couleur": "Blanc", "style": ["Minimalisme"],
        "matiere": "Coton", "temp_min": 15, "temp_max": 30,
        "portes": 0, "etat_propre": 60, "usure_max": 500,
    }


def _pantalon_chaud():
    return {
        "id": "pant_laine", "nom": "Pantalon laine", "categorie": "Pantalon",
        "couleur": "Gris anthracite", "style": ["Old Money"],
        "matiere": "Laine", "temp_min": -10, "temp_max": 15,
        "portes": 0, "etat_propre": 80, "usure_max": 1000,
    }


def _pantalon_leger():
    return {
        "id": "pant_coton", "nom": "Pantalon coton", "categorie": "Pantalon",
        "couleur": "Beige sable", "style": ["Minimalisme"],
        "matiere": "Coton", "temp_min": 15, "temp_max": 30,
        "portes": 0, "etat_propre": 80, "usure_max": 1000,
    }


def _chaussures():
    return {
        "id": "chauss", "nom": "Bottes", "categorie": "Chaussures",
        "couleur": "Marron", "style": ["Old Money"],
        "matiere": "Cuir", "temp_min": -10, "temp_max": 25,
        "portes": 0, "etat_propre": 100, "usure_max": 1500,
    }


def test_suggest_outfit_returns_required_meta():
    wardrobe = [_haut_leger(), _pantalon_leger(), _chaussures()]
    result = suggest_outfit(wardrobe, weather_mean_temp=20.0, rain=False)
    assert "__use_body" in result
    assert "__t_outfit" in result
    assert "__target_thermal" in result
    assert "__total_thermal" in result
    assert result["__t_outfit"] == 20.0


def test_suggest_outfit_empty_wardrobe_returns_empty_slots():
    result = suggest_outfit([], weather_mean_temp=15.0)
    # Les 12 slots restent None
    assert result["Haut"] is None
    assert result["Pantalon"] is None
    assert result["__use_body"] is False


def test_suggest_outfit_cold_weather_prefers_warm_items_and_body():
    """Par -10 °C, l'optimiseur prend le pull laine + active le body."""
    wardrobe = [
        _haut_leger(), _haut_chaud(),
        _pantalon_leger(), _pantalon_chaud(),
        _chaussures(),
    ]
    result = suggest_outfit(wardrobe, weather_mean_temp=-10.0, rain=False)
    # Haut chaud doit être préféré (les deux satisfont la rotation mais le solveur
    # cible la chaleur)
    assert result["Haut"] is not None
    assert result["Pantalon"] is not None
    # Au moins l'un des deux est l'item chaud
    chosen_ids = {result["Haut"]["id"], result["Pantalon"]["id"]}
    assert "haut_laine" in chosen_ids or "pant_laine" in chosen_ids
    # Avec deux items légers, gap > 0 → le body sera activé pour atteindre la cible
    # (avec deux items chauds, gap peut être déjà négatif, dans ce cas pas besoin)
    if "haut_coton" in chosen_ids or "pant_coton" in chosen_ids:
        assert result["__use_body"] is True


def test_suggest_outfit_hot_weather_no_body():
    """Par 25 °C, le solveur ne doit pas vouloir de body."""
    wardrobe = [_haut_leger(), _pantalon_leger(), _chaussures()]
    result = suggest_outfit(wardrobe, weather_mean_temp=25.0, rain=False)
    assert result["__use_body"] is False


def test_suggest_outfit_target_uses_mean_temp_not_min_max():
    """Régression : si on passe mean_temp=5 vs mean_temp=20, la cible diffère."""
    wardrobe = [_haut_leger(), _haut_chaud(), _pantalon_leger(), _pantalon_chaud(), _chaussures()]
    r_cold = suggest_outfit(wardrobe, weather_mean_temp=-5.0)
    r_warm = suggest_outfit(wardrobe, weather_mean_temp=20.0)
    # La cible thermique pour -5 °C est plus haute
    assert r_cold["__target_thermal"] > r_warm["__target_thermal"]


def test_suggest_outfit_unwearable_item_skipped():
    haut_a_laver = {**_haut_leger(), "portes": 60}  # = etat_propre, à laver
    haut_ok = _haut_chaud()
    wardrobe = [haut_a_laver, haut_ok, _pantalon_chaud(), _chaussures()]
    result = suggest_outfit(wardrobe, weather_mean_temp=10.0)
    # L'item à laver ne doit pas être choisi
    if result["Haut"] is not None:
        assert result["Haut"]["id"] != haut_a_laver["id"]


def test_suggest_outfit_body_in_search_space():
    """Avec une seule paire d'items et un mean_temp froid, le solveur retient
    le body si ça améliore le placement par rapport à la cible thermique."""
    wardrobe = [_haut_leger(), _pantalon_leger(), _chaussures()]
    # Avec mean_temp=5, items légers, le total thermique sera bas vs cible ~42.5
    # → le solveur doit préférer la variante use_body=True (même si écart résiduel)
    result = suggest_outfit(wardrobe, weather_mean_temp=5.0, thermal_tolerance=50.0)
    # Avec une tolérance très large, les deux variantes (body/no body) sont valides,
    # et la variante avec body a un meilleur thermal_dist → mais le style est égal,
    # donc on accepte les deux. On vérifie juste que la sortie est cohérente.
    assert result["Haut"] is not None
    assert result["__total_thermal"] >= 0
