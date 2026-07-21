"""Classification des actifs depuis la colonne 'Secteur 2' de ToutBroker."""

import pandas as pd


def _df(rows):
    return pd.DataFrame(rows, columns=["Ticker Yahoo Finance", "Secteur 1", "Secteur 2"])


def test_obligations_et_monetaire_fusionnes_en_taux():
    from app.services.finance.buffett.broker_availability import load_asset_classes
    df = _df([["OBLI.PA", "ETF", "Monétaire"], ["IGLT.L", "ETF", "Obligations"]])
    assert load_asset_classes(df) == {"OBLI.PA": "taux", "IGLT.L": "taux"}


def test_mojibake_du_tableur_reconnu():
    """Le fichier réel contient des accents cassés : la reconnaissance se fait par
    préfixe désaccentué, sinon Monétaire et Matières premières tombent dans actions."""
    from app.services.finance.buffett.broker_availability import load_asset_classes
    df = _df([["A", "ETF", "Mon�taire"], ["B", "ETF", "Mati�res premi�res"]])
    assert load_asset_classes(df) == {"A": "taux", "B": "matieres_premieres"}


def test_actions_et_secteurs_individuels():
    from app.services.finance.buffett.broker_availability import load_asset_classes
    df = _df([["C", "ETF", "Actions"], ["D", "Technologie", "Logiciels et services"]])
    assert load_asset_classes(df) == {"C": "actions", "D": "actions"}


def test_titre_vif_sans_secteur2_est_une_action():
    from app.services.finance.buffett.broker_availability import load_asset_classes
    df = _df([["E", "Santé", ""], ["F", "Technologie", None]])
    assert load_asset_classes(df) == {"E": "actions", "F": "actions"}


def test_etf_sans_secteur2_est_absent_du_dict():
    """Classe inconnue -> l'optimiseur retombe sur la médiane globale."""
    from app.services.finance.buffett.broker_availability import load_asset_classes
    df = _df([["G", "ETF", ""], ["H", "ETF", "Actions"]])
    assert load_asset_classes(df) == {"H": "actions"}


def test_reset_cache_invalide_les_classes():
    from app.services.finance.buffett import broker_availability as ba
    ba._ASSET_CLASS_CACHE = {"STALE": "actions"}
    ba.reset_etf_cache()
    assert ba._ASSET_CLASS_CACHE is None
