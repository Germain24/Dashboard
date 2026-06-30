"""Filtre de liquidité : on n'achète pas un titre dont le volume échangé/jour
(volume × prix) est sous le seuil (défaut 1 000 000 €)."""


def test_eur_volume():
    from app.services.finance.buffett.liquidity import daily_eur_volume
    assert daily_eur_volume(1150, 4.45) == 1150 * 4.45
    assert daily_eur_volume(None, 10) == 0.0
    assert daily_eur_volume(100, None) == 0.0


def test_is_liquid_1m_threshold():
    from app.services.finance.buffett.liquidity import is_liquid
    # BLEKEDROS.AT : 1150 × 4,45 ≈ 5 118 € -> illiquide
    assert is_liquid(1150, 4.45, min_eur=1_000_000) is False
    # BNKE.PA : 17 928 × 372,70 ≈ 6,68 M€ -> liquide
    assert is_liquid(17928, 372.70, min_eur=1_000_000) is True
    # pile au seuil -> accepté
    assert is_liquid(1, 1_000_000, min_eur=1_000_000) is True


def test_is_liquid_uses_config_default():
    from app.services.finance.buffett.liquidity import is_liquid
    from app.services.finance.buffett.config import Config
    assert Config.MIN_VOLUME_EUR == 100_000
    assert is_liquid(100, 100) is False        # 10 000 € < défaut (100k)
    assert is_liquid(100_000, 100) is True      # 10 M€ >= défaut
    # ETF obligataire d'État typique (volume faible mais > 100k €) -> éligible
    assert is_liquid(4_000, 130) is True        # ~520 000 € (ex. SEGA.L)
