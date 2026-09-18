"""Filtre de liquidité : le Volume est DÉJÀ en euros (cf. currency.volume_eur),
is_liquid le compare directement au seuil -- plus de multiplication par le prix
(l'ancienne formule volume x prix_local comparait des yens/wons au seuil en €)."""


def test_daily_eur_volume_passthrough_et_donnees_manquantes():
    from app.services.finance.buffett.liquidity import daily_eur_volume
    assert daily_eur_volume(5_117.5) == 5_117.5
    assert daily_eur_volume(None) == 0.0
    assert daily_eur_volume("n/a") == 0.0


def test_is_liquid_seuil_explicite():
    from app.services.finance.buffett.liquidity import is_liquid
    assert is_liquid(5_117.5, min_eur=1_000_000) is False    # REIT athenien
    assert is_liquid(6_682_265.0, min_eur=1_000_000) is True # OR.PA
    assert is_liquid(1_000_000.0, min_eur=1_000_000) is True # egalite


def test_is_liquid_seuil_par_defaut_config():
    from app.services.finance.buffett.config import Config
    from app.services.finance.buffett.liquidity import is_liquid
    assert Config.MIN_VOLUME_EUR == 100_000
    assert is_liquid(10_000.0) is False
    assert is_liquid(10_000_000.0) is True


def test_etf_is_not_excluded_by_single_exchange_volume():
    from app.services.finance.buffett.liquidity import passes_portfolio_liquidity

    assert passes_portfolio_liquidity(0, is_etf=True, min_eur=1_000_000)
    assert not passes_portfolio_liquidity(0, is_etf=False, min_eur=1_000_000)
